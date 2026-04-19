"""Researcher agent: runs Self-RAG-graded hybrid retrieval and summarizes findings."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from agents._llm_client import llm_client
from config.settings import settings
from rag.retrieval import HybridRetriever
from rag.self_rag import SelfRAGGrader


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


class ResearcherAgent:
    """Agent that retrieves and summarizes relevant 10-K content for a query."""

    SYSTEM_PROMPT = """You are a financial research assistant specialized in SEC 10-K filings.
Given a user query and retrieved document chunks, write a concise 2-paragraph research summary
of what was found. Stay grounded in the chunks - do NOT add outside knowledge or speculation.
If the chunks don't contain enough info, say so explicitly."""

    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        grader: Optional[SelfRAGGrader] = None,
    ) -> None:
        """Initialize the researcher with retrieval and Self-RAG grading components."""
        self.retriever = retriever or HybridRetriever()
        self.grader = grader or SelfRAGGrader()
        self.model = settings.researcher_model

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve relevant chunks, grade them, and summarize findings for the graph state."""
        t0 = time.perf_counter()
        query = state.get("revision_focus") or state["query"]
        print(f"[R] Researcher: retrieving for -> {query[:80]}")

        graded = self.grader.grade_with_retry(query, self.retriever, max_retries=2)

        chunks_for_llm = []
        for index, chunk in enumerate(graded.final_chunks[:5], start=1):
            meta = chunk.get("metadata", {}) or {}
            chunk_id = chunk.get("id") or f"chunk_{index}"
            text = (chunk.get("text") or "")[:500]
            chunks_for_llm.append(
                f"[{chunk_id}] ({meta.get('ticker', '?')}_{meta.get('year', '?')}) {text}"
            )
        chunks_text = "\n\n".join(chunks_for_llm) if chunks_for_llm else "(no chunks retrieved)"

        user_msg = (
            f"Query: {query}\n\n"
            f"Retrieved chunks:\n{chunks_text}\n\n"
            "Write a 2-paragraph research summary grounded ONLY in these chunks."
        )

        resp = llm_client.chat(
            model=self.model,
            system=self.SYSTEM_PROMPT,
            user=user_msg,
            json_mode=False,
            max_tokens=800,
            temperature=0.2,
        )

        latency = int((time.perf_counter() - t0) * 1000)
        audit_entry = {
            "agent": "researcher",
            "action": "retrieve_and_summarize",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": latency,
            "model": resp.model,
            "input_summary": query[:100],
            "output_summary": f"{len(graded.final_chunks)} chunks, grade={graded.final_grade.decision}",
        }

        return {
            **state,
            "retrieved_chunks": graded.final_chunks,
            "retrieval_grade": {
                "decision": graded.final_grade.decision,
                "relevance": graded.final_grade.relevance,
                "sufficiency": graded.final_grade.sufficiency,
                "reasoning": graded.final_grade.reasoning,
            },
            "retrieval_retry_history": list(graded.retry_history),
            "research_notes": resp.content,
            "audit_trail": state.get("audit_trail", []) + [audit_entry],
        }
