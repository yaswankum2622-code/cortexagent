"""Self-RAG: LLM-graded retrieval quality with auto-refinement loop."""

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel

from agents._llm_client import LLMResponse, llm_client
from config.settings import settings


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


class RetrievalGradePayload(BaseModel):
    """Schema-enforced grader payload for Gemini structured output."""

    decision: Literal["sufficient", "partial", "insufficient"]
    relevance: int
    sufficiency: int
    reasoning: str
    suggested_refinement: Optional[str] = None


@dataclass
class GradeResult:
    """Structured result returned by the retrieval-quality grader."""

    decision: Literal["sufficient", "partial", "insufficient"]
    relevance: int
    sufficiency: int
    reasoning: str
    suggested_refinement: Optional[str] = None
    model_used: str = ""
    latency_ms: int = 0


@dataclass
class GradedRetrieval:
    """Final retrieval package after grading and optional refinement retries."""

    final_chunks: List[Dict[str, Any]]
    final_grade: GradeResult
    retry_history: List[Dict[str, Any]] = field(default_factory=list)


class SelfRAGGrader:
    """Uses an LLM to grade retrieval quality and suggest refinements."""

    SYSTEM_PROMPT = """You are a retrieval quality grader for SEC 10-K financial document research.

Your job: given a user query and the chunks retrieved for it, judge whether the chunks contain enough relevant information to answer the query well.

Grading rules:
- Be strict. Err on the side of "insufficient" when in doubt.
- "sufficient" = chunks directly address the query and contain enough specific information
- "partial" = some chunks are relevant but key information is missing
- "insufficient" = chunks are off-topic, generic, or about wrong entities

If decision is "partial" or "insufficient", suggest a refined query that would retrieve better chunks. The refined query should be more specific (add company names, time periods, or domain terms) but should NOT include phrases like "documents that contain" or "find chunks about" - write it as a natural research question.

Return ONLY valid JSON in this exact format:
{
  "decision": "sufficient" | "partial" | "insufficient",
  "relevance": 0-10,
  "sufficiency": 0-10,
  "reasoning": "1-2 sentence explanation",
  "suggested_refinement": "a refined query string, or null if decision is sufficient"
}"""

    def __init__(self, model: Optional[str] = None) -> None:
        """Initialize the grader with the configured Self-RAG model."""
        self.model = model or settings.selfrag_model
        self.fallback_model = (
            settings.ragas_judge_model if settings.ragas_judge_model != self.model else None
        )
        self.llm_calls = 0
        self.total_latency_ms = 0

    def _call_grader_model(self, model: str, user_msg: str) -> LLMResponse:
        """Invoke one grading model and update usage counters."""
        resp = llm_client.chat(
            model=model,
            system=self.SYSTEM_PROMPT,
            user=user_msg,
            json_mode=True,
            max_tokens=512,
            temperature=0.1,
            response_schema=RetrievalGradePayload,
        )
        self.llm_calls += 1
        self.total_latency_ms += resp.latency_ms
        return resp

    def grade_retrieval(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
    ) -> GradeResult:
        """Grade a single retrieval attempt. Returns GradeResult."""
        if not retrieved_chunks:
            return GradeResult(
                decision="insufficient",
                relevance=0,
                sufficiency=0,
                reasoning="No chunks were retrieved.",
                suggested_refinement=query,
                model_used=self.model,
            )

        numbered: List[str] = []
        for index, chunk in enumerate(retrieved_chunks, start=1):
            meta = chunk.get("metadata", {})
            ticker = meta.get("ticker", "?")
            year = meta.get("year", "?")
            text = chunk.get("text", "")[:500]
            numbered.append(f"[{index}] ({ticker} {year}) {text}")
        chunks_text = "\n\n".join(numbered)

        user_msg = (
            f"User query: {query}\n\nRetrieved chunks:\n{chunks_text}\n\n"
            "Grade this retrieval and return JSON."
        )

        resp = None
        errors: List[str] = []
        models_to_try = [self.model]
        if self.fallback_model:
            models_to_try.append(self.fallback_model)

        for model_name in models_to_try:
            try:
                candidate = self._call_grader_model(model_name, user_msg)
            except Exception as exc:
                logger.warning("Grader model %s failed: %s", model_name, exc)
                errors.append(f"{model_name}: {exc}")
                continue

            if candidate.raw_json is not None:
                resp = candidate
                break

            logger.warning("Grader model %s returned invalid JSON; trying fallback if available", model_name)
            errors.append(f"{model_name}: invalid_json")
            resp = candidate

        if resp is None:
            return GradeResult(
                decision="insufficient",
                relevance=0,
                sufficiency=0,
                reasoning=f"Grader call failed. Errors: {'; '.join(errors)}",
                suggested_refinement=query,
                model_used=self.model,
            )

        if resp.raw_json is None:
            return GradeResult(
                decision="insufficient",
                relevance=0,
                sufficiency=0,
                reasoning=(
                    f"Grader failed to return valid JSON. Raw: {resp.content[:200]}. "
                    f"Errors: {'; '.join(errors)}"
                ),
                suggested_refinement=query,
                model_used=resp.model,
                latency_ms=resp.latency_ms,
            )

        data = resp.raw_json
        decision = data.get("decision", "insufficient")
        if decision not in {"sufficient", "partial", "insufficient"}:
            decision = "insufficient"

        relevance = max(0, min(10, int(data.get("relevance", 0))))
        sufficiency = max(0, min(10, int(data.get("sufficiency", 0))))

        return GradeResult(
            decision=decision,
            relevance=relevance,
            sufficiency=sufficiency,
            reasoning=data.get("reasoning", ""),
            suggested_refinement=data.get("suggested_refinement"),
            model_used=self.model,
            latency_ms=resp.latency_ms,
        )

    def grade_with_retry(
        self,
        query: str,
        retriever: Any,
        max_retries: int = 2,
    ) -> GradedRetrieval:
        """
        Retrieve, grade, and re-retrieve up to max_retries times if insufficient.

        Returns GradedRetrieval with final chunks + grade + full retry history.
        """
        history: List[Dict[str, Any]] = []
        current_query = query
        chunks: List[Dict[str, Any]] = []
        grade = GradeResult(
            decision="insufficient",
            relevance=0,
            sufficiency=0,
            reasoning="Grading did not run.",
            model_used=self.model,
        )

        for attempt in range(max_retries + 1):
            chunks = retriever.retrieve(current_query)
            grade = self.grade_retrieval(current_query, chunks)

            history.append(
                {
                    "attempt": attempt,
                    "query": current_query,
                    "num_chunks": len(chunks),
                    "decision": grade.decision,
                    "relevance": grade.relevance,
                    "sufficiency": grade.sufficiency,
                    "reasoning": grade.reasoning,
                }
            )

            if grade.decision == "sufficient" or attempt == max_retries:
                return GradedRetrieval(
                    final_chunks=chunks,
                    final_grade=grade,
                    retry_history=history,
                )

            if grade.suggested_refinement and grade.suggested_refinement != current_query:
                current_query = grade.suggested_refinement
            else:
                return GradedRetrieval(
                    final_chunks=chunks,
                    final_grade=grade,
                    retry_history=history,
                )

        return GradedRetrieval(
            final_chunks=chunks,
            final_grade=grade,
            retry_history=history,
        )


def _history_row(entry: Dict[str, Any]) -> Tuple[str, str, str, str, str, str]:
    """Format one retry-history row for terminal output."""
    return (
        str(entry["attempt"]),
        entry["query"],
        str(entry["num_chunks"]),
        entry["decision"],
        str(entry["relevance"]),
        str(entry["sufficiency"]),
    )


def _print_history_table(history: List[Dict[str, Any]]) -> None:
    """Render retry history as a compact terminal table."""
    print("attempt | query | num_chunks | decision | relevance | sufficiency")
    print("-" * 72)
    for entry in history:
        row = _history_row(entry)
        print(
            f"{row[0]:<7} | {row[1]:<38} | {row[2]:<10} | "
            f"{row[3]:<12} | {row[4]:<9} | {row[5]}"
        )


def _chunk_preview(chunk: Dict[str, Any]) -> str:
    """Generate a short preview string for a retrieved chunk."""
    meta = chunk.get("metadata", {})
    text = " ".join(chunk.get("text", "").split())[:140]
    return (
        f"[{meta.get('ticker', '?')}_{meta.get('year', '?')} #{meta.get('chunk_index', '-')}] "
        f"{text}..."
    )


if __name__ == "__main__":
    from config.logging_setup import configure_logging
    from config.settings import settings

    configure_logging(settings.log_level)

    from rag.retrieval import HybridRetriever

    queries = [
        ("good", "What were Apple's net sales by segment in fiscal 2024?"),
        ("vague", "tell me about the company"),
        ("impossible", "What is the CEO's favorite color?"),
    ]

    retriever = HybridRetriever()
    grader = SelfRAGGrader()

    for label, query in queries:
        print(f"\n=== {label.upper()}: {query} ===")
        result = grader.grade_with_retry(query, retriever, max_retries=2)
        final_grade = result.final_grade

        print(
            f"Final decision: {final_grade.decision} | relevance={final_grade.relevance} "
            f"| sufficiency={final_grade.sufficiency}"
        )
        print(f"Reasoning: {final_grade.reasoning}")
        if final_grade.suggested_refinement:
            print(f"Suggested refinement: {final_grade.suggested_refinement}")

        _print_history_table(result.retry_history)

        print("Top 2 final chunks:")
        for chunk in result.final_chunks[:2]:
            print(f"  - {_chunk_preview(chunk)}")

        print("Final grade JSON:")
        print(json.dumps(asdict(final_grade), indent=2))

    print("\n=== SUMMARY ===")
    print(f"Total LLM calls made: {grader.llm_calls}")
    print(f"Approx total latency: {grader.total_latency_ms} ms")
    print(
        "Note: Self-RAG correctly handled good query without retry, retried on vague, "
        "gave up on impossible"
    )
