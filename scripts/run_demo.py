"""Run an interview-ready CortexAgent demo.

This script is designed for live demos and interview loops where opening the
full dashboard is not necessary or where screen-sharing a terminal is faster.
It runs representative questions through the full LangGraph orchestrator and
prints a concise summary of retrieval depth, quality signals, model usage, and
estimated spend.

Usage:
    python scripts/run_demo.py
    python scripts/run_demo.py --single
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents._llm_client import llm_client
from agents.orchestrator import CortexAgentOrchestrator
from api.cost_tracker import cost_tracker
from config.logging_setup import configure_logging
from config.settings import settings


DEMO_QUERIES = [
    {
        "id": "demo_1",
        "query": "What are Apple's main business segments in fiscal 2024?",
        "why": (
            "Demonstrates factual retrieval, structured extraction, citations, and "
            "critic scoring on a clear filing question."
        ),
    },
    {
        "id": "demo_2",
        "query": "How is Microsoft using AI across both productivity software and cloud infrastructure?",
        "why": (
            "Demonstrates cross-section synthesis and qualitative reasoning across "
            "strategy, products, and cloud positioning."
        ),
    },
]


def banner(text: str) -> None:
    print()
    print("=" * 70)
    print(f"  {text}")
    print("=" * 70)


def install_cost_tracking_hook() -> None:
    """Mirror the API-side cost hook so demo runs report real model spend."""
    if getattr(llm_client, "_demo_cost_hook_installed", False):
        return

    original_chat = llm_client.chat

    def chat_with_tracking(*args: Any, **kwargs: Any) -> Any:
        response = original_chat(*args, **kwargs)
        cost_tracker.record(
            response.model,
            int(response.input_tokens or 0),
            int(response.output_tokens or 0),
        )
        return response

    llm_client.chat = chat_with_tracking  # type: ignore[method-assign]
    setattr(llm_client, "_demo_cost_hook_installed", True)


def preview_text(text: str, limit: int = 500) -> str:
    """Return a screen-share-friendly preview string."""
    compact = (text or "").strip()
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."


def print_models_used(audit: Iterable[Dict[str, Any]]) -> None:
    """Print the set of models observed in the audit trail."""
    models_seen: Set[str] = {entry.get("model") for entry in audit if entry.get("model")}
    print("  MODELS USED:")
    if not models_seen:
        print("    - none recorded")
        return
    for model in sorted(models_seen):
        print(f"    - {model}")


def print_citation_preview(chunks: List[Dict[str, Any]]) -> None:
    """Print the top few cited chunks in a compact format."""
    print()
    print("  TOP CITATIONS:")
    if not chunks:
        print("    - none returned")
        return

    for chunk in chunks[:3]:
        metadata = chunk.get("metadata", {}) or {}
        chunk_id = chunk.get("id", "unknown")
        ticker = metadata.get("ticker", "?")
        year = metadata.get("year", "?")
        snippet = preview_text(chunk.get("text", "").replace("\n", " "), limit=110)
        print(f"    - {ticker} / {year} / {chunk_id}")
        print(f"      {snippet}")


def print_retrieval_grade(state: Dict[str, Any]) -> None:
    """Print the retrieval grading signal when available."""
    grade = state.get("retrieval_grade") or {}
    if not grade:
        return
    print()
    print("  RETRIEVAL GRADE:")
    print(f"    - decision:    {grade.get('decision', 'unknown')}")
    print(f"    - relevance:   {grade.get('relevance', 'n/a')}")
    print(f"    - sufficiency: {grade.get('sufficiency', 'n/a')}")
    reasoning = grade.get("reasoning")
    if reasoning:
        print(f"    - reasoning:   {preview_text(str(reasoning), limit=180)}")


def run_query(orch: CortexAgentOrchestrator, query_entry: Dict[str, str]) -> None:
    """Execute one demo query and print a structured summary."""
    banner(f"QUERY: {query_entry['query']}")
    print(f"Why this query: {query_entry['why']}")
    print()

    start = time.perf_counter()
    state = orch.run(query_entry["query"], thread_id=query_entry["id"])
    elapsed = time.perf_counter() - start

    cost_tracker.record_query()

    report = state.get("final_report", "") or ""
    citations = state.get("retrieved_chunks", []) or []
    critique = state.get("critique", {}) or {}
    audit = state.get("audit_trail", []) or []

    print("-" * 70)
    print("  RESULT SUMMARY")
    print("-" * 70)
    print(f"  Thread ID:       {query_entry['id']}")
    print(f"  Wall latency:    {elapsed:.1f}s")
    print(f"  Revisions:       {state.get('revision_count', 0)}")
    print(f"  Citations found: {len(citations[:5])}")
    print(f"  Audit entries:   {len(audit)}")
    print(f"  Report length:   {len(report)} chars")

    if critique:
        print(f"  Critic decision: {critique.get('decision', 'unknown')}")
        print(f"  Faithfulness:    {critique.get('faithfulness', 0)}/5")
        print(f"  Completeness:    {critique.get('completeness', 0)}/5")
        print(f"  Citations:       {critique.get('citation_quality', 0)}/5")
        feedback = critique.get("feedback")
        if feedback:
            print(f"  Critic note:     {preview_text(str(feedback), limit=180)}")

    print_retrieval_grade(state)
    print()
    print_models_used(audit)
    print_citation_preview(citations)

    print()
    print("  REPORT PREVIEW (first 500 chars):")
    print("  " + "-" * 66)
    preview = preview_text(report, limit=500)
    if not preview:
        print("  (empty report)")
    else:
        for line in preview.splitlines():
            print(f"  {line}")


def print_cost_summary() -> None:
    """Print session-wide token and cost totals."""
    banner("SESSION COST SUMMARY")
    summary = cost_tracker.summary()
    print(f"  Queries served:      {summary.get('queries_served', 0)}")
    print(f"  Total input tokens:  {summary.get('total_input_tokens', 0):,}")
    print(f"  Total output tokens: {summary.get('total_output_tokens', 0):,}")
    print(f"  Estimated USD:       ${summary.get('estimated_usd', 0):.4f}")
    print()
    print("  BY MODEL:")
    by_model = summary.get("by_model", {})
    if not by_model:
        print("    - no tracked calls")
        return
    for model, stats in by_model.items():
        print(f"    - {model}")
        print(f"        input:  {stats.get('input_tokens', 0):,} tokens")
        print(f"        output: {stats.get('output_tokens', 0):,} tokens")
        print(f"        cost:   ${stats.get('usd', 0):.4f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--single",
        action="store_true",
        help="Run only the first demo query for faster interviews.",
    )
    args = parser.parse_args()

    configure_logging(settings.log_level)
    install_cost_tracking_hook()

    banner("CortexAgent - Live Demo")
    print("  Multi-agent RAG over SEC 10-K filings")
    print("  Researcher -> Analyst -> Writer -> Critic (with up to 2 revisions)")
    print("  3-provider LLM cascade: Gemini -> Groq -> Claude")
    print("  Indexed: AAPL, MSFT, GOOGL, JPM, TSLA (2024 10-K filings)")
    print()
    print("Initializing orchestrator (loading retrieval indices + reranker)...")
    orch = CortexAgentOrchestrator()
    print("Ready.")

    queries = DEMO_QUERIES[:1] if args.single else DEMO_QUERIES
    for query in queries:
        run_query(orch, query)

    print_cost_summary()
    print()
    print("=" * 70)
    print("  Demo complete.")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
