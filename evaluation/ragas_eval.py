"""RAGAS evaluation harness: run orchestrator on golden dataset, score, generate HTML report."""

import html
import json
import logging
import math
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from datasets import Dataset
from langchain_anthropic import ChatAnthropic
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_correctness,
    answer_relevancy,
    context_precision,
    faithfulness,
)

from agents.orchestrator import CortexAgentOrchestrator
from config.logging_setup import configure_logging
from config.settings import settings

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "langchain-huggingface is required for RAGAS evaluation. "
        "Run `uv pip install -e .` after updating dependencies."
    ) from exc


logger = logging.getLogger(__name__)


def _safe_score(value: Any) -> float:
    """Normalize missing or NaN metric outputs to 0.0 for stable gating."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(numeric) else numeric


def _build_ragas_llm() -> LangchainLLMWrapper:
    """Build the Claude-based RAGAS judge model wrapper."""
    llm = ChatAnthropic(
        model_name=settings.ragas_judge_model,
        api_key=settings.anthropic_api_key,
        temperature=0.0,
        max_tokens=2048,
    )
    return LangchainLLMWrapper(llm)


def _build_ragas_embeddings() -> LangchainEmbeddingsWrapper:
    """Build local Hugging Face embeddings for evaluation-time similarity metrics."""
    embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    return LangchainEmbeddingsWrapper(embeddings)


def _preprocess_answer_for_ragas(raw_answer: str) -> str:
    """
    Normalize Writer output for RAGAS scoring.

    Removes:
    - Inline [chunk_id] citations
    - "## Sources" section and everything after it
    - Markdown headers (##) and bullet markers - keep the text content
    - Excess whitespace

    Extracts:
    - Content from "## Executive Summary" through end of content before "## Sources"
      (if that structure exists). Else the whole cleaned body.

    Why: RAGAS treats chunk_ids and source-list lines as atomic claims. Those claims have
    no supporting context, which artificially deflates faithfulness and answer_correctness.
    """
    if not raw_answer:
        return ""

    text = raw_answer

    text = re.split(
        r"^\s*##+\s*Sources?\s*$",
        text,
        maxsplit=1,
        flags=re.MULTILINE | re.IGNORECASE,
    )[0]

    text = re.sub(r"\[[A-Z]{1,6}_\d{4}_?#?\d+\]", "", text)
    text = re.sub(r"\[[A-Z]{1,6}_\d{4}\s*#\s*\d+\]", "", text)
    text = re.sub(r"\[[A-Z]{1,6}[_\s]?\d{4}[_\s#]*\d+\]", "", text)

    text = re.sub(r"^\s*##+\s*(.+?)\s*$", r"\1\n", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(
        r"^(Executive Summary|Key Findings|Financial Figures|Risk Factors|Opportunities)\n(?!\n)",
        r"\1\n\n",
        text,
        flags=re.MULTILINE,
    )

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def run_orchestrator_on_dataset(
    dataset_path: str,
    max_questions: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Run the orchestrator on each golden question and collect evaluation artifacts."""
    with open(dataset_path, "r", encoding="utf-8") as handle:
        qa_pairs = json.load(handle)

    if max_questions:
        qa_pairs = qa_pairs[:max_questions]

    orchestrator = CortexAgentOrchestrator()
    results: List[Dict[str, Any]] = []

    for index, qa in enumerate(qa_pairs, start=1):
        logger.info("[%s/%s] Running: %s - %s", index, len(qa_pairs), qa["id"], qa["question"][:80])
        t0 = time.perf_counter()
        try:
            final = orchestrator.run(qa["question"], thread_id=f"eval_{qa['id']}")
            contexts = [chunk.get("text", "") for chunk in (final.get("retrieved_chunks") or [])]
            latency_ms = int((time.perf_counter() - t0) * 1000)
            results.append(
                {
                    "id": qa["id"],
                    "ticker": qa["ticker"],
                    "question": qa["question"],
                    "contexts": contexts,
                    "answer": final.get("final_report", ""),
                    "ground_truth": qa["ground_truth"],
                    "category": qa["category"],
                    "difficulty": qa["difficulty"],
                    "revision_count": final.get("revision_count", 0),
                    "critique": final.get("critique", {}),
                    "wall_latency_ms": final.get("wall_latency_ms", latency_ms),
                    "fallbacks_used": [
                        entry.get("model", "")
                        for entry in (final.get("audit_trail", []) or [])
                    ],
                    "_error": None,
                }
            )
            print(f"[OK]  {qa['id']} completed in {latency_ms}ms")
        except Exception as exc:
            logger.exception("Question %s failed: %s", qa["id"], exc)
            results.append(
                {
                    "id": qa["id"],
                    "ticker": qa["ticker"],
                    "question": qa["question"],
                    "contexts": [],
                    "answer": "",
                    "ground_truth": qa["ground_truth"],
                    "category": qa["category"],
                    "difficulty": qa["difficulty"],
                    "revision_count": 0,
                    "critique": {},
                    "wall_latency_ms": 0,
                    "fallbacks_used": [],
                    "_error": str(exc),
                }
            )
            print(f"[FAIL] {qa['id']} raised: {exc}")

    return results


def run_ragas_eval(
    orchestrator_results: List[Dict[str, Any]],
    use_preprocessing: bool = True,
) -> Dict[str, Any]:
    """Score orchestrator outputs with RAGAS and return aggregate plus per-question metrics."""
    valid = [row for row in orchestrator_results if not row.get("_error") and row.get("answer")]
    if not valid:
        return {
            "per_question": [],
            "aggregate": {},
            "_error": "No valid results to evaluate.",
        }

    answers_for_ragas = [
        _preprocess_answer_for_ragas(row["answer"]) if use_preprocessing else row["answer"]
        for row in valid
    ]
    original_avg_len = sum(len(row["answer"]) for row in valid) / max(len(valid), 1)
    preprocessed_avg_len = sum(len(answer) for answer in answers_for_ragas) / max(len(valid), 1)
    if use_preprocessing:
        print(
            "Preprocessing: avg answer length "
            f"{original_avg_len:.0f} -> {preprocessed_avg_len:.0f} chars "
            "(citations/sources stripped)"
        )
    else:
        print(
            "Preprocessing disabled: avg answer length "
            f"{original_avg_len:.0f} chars (raw Markdown sent to RAGAS)"
        )

    dataset = Dataset.from_list(
        [
            {
                "question": row["question"],
                "contexts": (row["contexts"][:3] if row["contexts"] else [""]),
                "answer": answer,
                "ground_truth": row["ground_truth"],
                "reference": row["ground_truth"],
                "user_input": row["question"],
                "retrieved_contexts": (row["contexts"][:3] if row["contexts"] else [""]),
                "response": answer,
            }
            for row, answer in zip(valid, answers_for_ragas)
        ]
    )

    judge_llm = _build_ragas_llm()
    judge_embeddings = _build_ragas_embeddings()

    print(f"Running RAGAS on {len(valid)} valid entries (this takes 5-15 minutes)...")
    scores = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, answer_correctness],
        llm=judge_llm,
        embeddings=judge_embeddings,
        raise_exceptions=False,
        show_progress=True,
    )

    dataframe = scores.to_pandas()
    per_question: List[Dict[str, Any]] = []
    for row, score_row in zip(valid, dataframe.to_dict(orient="records")):
        per_question.append(
            {
                "id": row["id"],
                "ticker": row["ticker"],
                "question": row["question"],
                "category": row["category"],
                "difficulty": row["difficulty"],
                "faithfulness": _safe_score(score_row.get("faithfulness", 0.0)),
                "answer_relevancy": _safe_score(score_row.get("answer_relevancy", 0.0)),
                "context_precision": _safe_score(score_row.get("context_precision", 0.0)),
                "answer_correctness": _safe_score(score_row.get("answer_correctness", 0.0)),
                "revision_count": row.get("revision_count", 0),
                "wall_latency_ms": row.get("wall_latency_ms", 0),
            }
        )

    aggregate: Dict[str, float] = {}
    for metric_name in [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "answer_correctness",
    ]:
        values = [
            _safe_score(item.get(metric_name))
            for item in per_question
            if item.get(metric_name) is not None
        ]
        aggregate[metric_name] = sum(values) / len(values) if values else 0.0

    errored = [row for row in orchestrator_results if row.get("_error")]
    return {
        "per_question": per_question,
        "aggregate": aggregate,
        "total_questions": len(orchestrator_results),
        "evaluated_questions": len(valid),
        "errored_questions": len(errored),
        "errored_ids": [row["id"] for row in errored],
    }


def check_thresholds(results: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Compare aggregate scores against configured gate thresholds."""
    aggregate = results.get("aggregate", {}) or {}
    failures: List[str] = []

    faith_score = _safe_score(aggregate.get("faithfulness", 0.0))
    if faith_score < settings.ragas_faithfulness_threshold:
        failures.append(
            f"Faithfulness {faith_score:.3f} < threshold {settings.ragas_faithfulness_threshold}"
        )

    relevance_score = _safe_score(aggregate.get("answer_relevancy", 0.0))
    if relevance_score < settings.ragas_answer_relevance_threshold:
        failures.append(
            f"Answer relevancy {relevance_score:.3f} < threshold "
            f"{settings.ragas_answer_relevance_threshold}"
        )

    context_score = _safe_score(aggregate.get("context_precision", 0.0))
    if context_score < settings.ragas_context_precision_threshold:
        failures.append(
            f"Context precision {context_score:.3f} < threshold "
            f"{settings.ragas_context_precision_threshold}"
        )

    return (len(failures) == 0, failures)


def generate_html_report(results: Dict[str, Any], output_path: str) -> None:
    """Write a self-contained HTML report with aggregate and per-question scoring."""
    aggregate = results.get("aggregate", {}) or {}
    per_question = results.get("per_question", []) or []
    passed, failures = check_thresholds(results)

    def row_class(score: float, threshold: float) -> str:
        return "pass" if _safe_score(score) >= threshold else "fail"

    now = datetime.now(timezone.utc).isoformat()
    report_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>CortexAgent - RAGAS Eval Report</title>
<style>
body {{ font-family: -apple-system, Segoe UI, sans-serif; max-width: 1200px; margin: 40px auto; padding: 20px; color: #222; }}
h1 {{ color: #1a1a1a; }}
.pass {{ background: #e8f7ec; }}
.fail {{ background: #fdecea; }}
.banner-pass {{ background: #16a34a; color: white; padding: 15px; border-radius: 6px; font-size: 18px; }}
.banner-fail {{ background: #dc2626; color: white; padding: 15px; border-radius: 6px; font-size: 18px; }}
table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #e5e7eb; font-size: 14px; }}
th {{ background: #f9fafb; font-weight: 600; }}
.metric-box {{ display: inline-block; padding: 20px; margin: 10px; border-radius: 6px; background: #f3f4f6; min-width: 180px; text-align: center; }}
.metric-box .label {{ color: #6b7280; font-size: 13px; }}
.metric-box .value {{ font-size: 28px; font-weight: 700; margin: 8px 0; }}
.threshold-note {{ color: #6b7280; font-size: 12px; }}
.q-text {{ max-width: 400px; }}
code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 3px; font-size: 12px; }}
</style></head><body>

<h1>CortexAgent - RAGAS Evaluation Report</h1>
<p class="threshold-note">Generated: {now}</p>

<div class="{'banner-pass' if passed else 'banner-fail'}">
  {"PASSED all thresholds" if passed else "FAILED: " + "; ".join(failures)}
</div>

<h2>Aggregate Scores ({results.get('evaluated_questions', 0)} evaluated / {results.get('total_questions', 0)} total)</h2>

<div>
  <div class="metric-box {row_class(float(aggregate.get('faithfulness', 0.0) or 0.0), settings.ragas_faithfulness_threshold)}">
    <div class="label">Faithfulness</div>
    <div class="value">{float(aggregate.get('faithfulness', 0.0) or 0.0):.3f}</div>
    <div class="threshold-note">threshold {settings.ragas_faithfulness_threshold}</div>
  </div>
  <div class="metric-box {row_class(float(aggregate.get('answer_relevancy', 0.0) or 0.0), settings.ragas_answer_relevance_threshold)}">
    <div class="label">Answer Relevancy</div>
    <div class="value">{float(aggregate.get('answer_relevancy', 0.0) or 0.0):.3f}</div>
    <div class="threshold-note">threshold {settings.ragas_answer_relevance_threshold}</div>
  </div>
  <div class="metric-box {row_class(float(aggregate.get('context_precision', 0.0) or 0.0), settings.ragas_context_precision_threshold)}">
    <div class="label">Context Precision</div>
    <div class="value">{float(aggregate.get('context_precision', 0.0) or 0.0):.3f}</div>
    <div class="threshold-note">threshold {settings.ragas_context_precision_threshold}</div>
  </div>
  <div class="metric-box">
    <div class="label">Answer Correctness</div>
    <div class="value">{float(aggregate.get('answer_correctness', 0.0) or 0.0):.3f}</div>
    <div class="threshold-note">no threshold set</div>
  </div>
</div>

<h2>Per-Question Results</h2>
<table>
  <tr>
    <th>ID</th><th>Ticker</th><th>Difficulty</th><th>Question</th>
    <th>Faith</th><th>Rel</th><th>CtxPrec</th><th>Correct</th><th>Revisions</th><th>Latency</th>
  </tr>
"""

    for item in per_question:
        faith_cls = row_class(
            float(item.get("faithfulness", 0.0) or 0.0),
            settings.ragas_faithfulness_threshold,
        )
        report_html += f"""  <tr class="{faith_cls}">
    <td><code>{html.escape(item['id'])}</code></td>
    <td>{html.escape(item['ticker'])}</td>
    <td>{html.escape(item['difficulty'])}</td>
    <td class="q-text">{html.escape(item['question'])}</td>
    <td>{float(item.get('faithfulness', 0.0) or 0.0):.2f}</td>
    <td>{float(item.get('answer_relevancy', 0.0) or 0.0):.2f}</td>
    <td>{float(item.get('context_precision', 0.0) or 0.0):.2f}</td>
    <td>{float(item.get('answer_correctness', 0.0) or 0.0):.2f}</td>
    <td>{item.get('revision_count', 0)}</td>
    <td>{item.get('wall_latency_ms', 0)}ms</td>
  </tr>
"""

    report_html += """
</table>
</body></html>
"""

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(report_html)
    print(f"HTML report written to: {output_path}")
