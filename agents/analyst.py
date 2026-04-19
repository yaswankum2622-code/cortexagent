"""Analyst agent: extracts structured findings from retrieved chunks."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from agents._llm_client import llm_client
from config.settings import settings


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


class AnalystAgent:
    """Extracts key_facts, numbers, risks, and opportunities as structured JSON."""

    SYSTEM_PROMPT = """You are a financial analyst. Extract structured findings from the provided chunks.
Every fact must cite the chunk it came from using [chunk_id] notation.

Return ONLY valid JSON with this exact schema:
{
  "key_facts": [{"fact": "string", "citation": "chunk_id"}],
  "numbers": [{"metric": "string", "value": "string", "context": "string", "citation": "chunk_id"}],
  "risks": [{"risk": "string", "severity": "low|medium|high", "citation": "chunk_id"}],
  "opportunities": [{"opportunity": "string", "citation": "chunk_id"}]
}

Rules:
- Every item MUST have a citation matching a chunk_id from the provided chunks
- If information is missing, return empty arrays rather than inventing
- "numbers" should capture specific financial figures mentioned (revenue, costs, growth rates)
- Keep each field concise (one sentence max)"""

    def __init__(self) -> None:
        """Initialize the analyst with its configured model."""
        self.model = settings.analyst_model

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured findings from retrieved chunks and update graph state."""
        t0 = time.perf_counter()
        query = state["query"]
        chunks = state.get("retrieved_chunks", []) or []
        print(f"[A] Analyst: extracting findings from {len(chunks)} chunks")

        chunks_for_llm = []
        for chunk in chunks[:8]:
            chunk_id = chunk.get("id") or "unknown"
            meta = chunk.get("metadata", {}) or {}
            text = (chunk.get("text") or "")[:600]
            chunks_for_llm.append(
                f"[{chunk_id}] ({meta.get('ticker', '?')}_{meta.get('year', '?')}) {text}"
            )
        chunks_text = "\n\n".join(chunks_for_llm) if chunks_for_llm else "(no chunks)"

        user_msg = (
            f"Query: {query}\n\nChunks:\n{chunks_text}\n\n"
            "Extract structured findings as JSON per the schema."
        )

        resp = llm_client.chat(
            model=self.model,
            system=self.SYSTEM_PROMPT,
            user=user_msg,
            json_mode=True,
            max_tokens=1500,
            temperature=0.1,
        )

        if resp.raw_json is None:
            logger.warning("Analyst JSON parse failed. Raw response: %s", resp.content[:200])

        findings = resp.raw_json or {
            "key_facts": [],
            "numbers": [],
            "risks": [],
            "opportunities": [],
            "_error": f"Analyst JSON parse failed. Raw: {resp.content[:200]}",
        }

        latency = int((time.perf_counter() - t0) * 1000)
        audit_entry = {
            "agent": "analyst",
            "action": "extract_findings",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": latency,
            "model": resp.model,
            "input_summary": f"{len(chunks)} chunks",
            "output_summary": (
                f"facts={len(findings.get('key_facts', []))}, "
                f"numbers={len(findings.get('numbers', []))}, "
                f"risks={len(findings.get('risks', []))}, "
                f"opps={len(findings.get('opportunities', []))}"
            ),
        }

        return {
            **state,
            "structured_findings": findings,
            "audit_trail": state.get("audit_trail", []) + [audit_entry],
        }
