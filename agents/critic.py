"""Critic agent: evaluates draft report quality and decides approve vs revise."""

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


class CriticAgent:
    """Grades the draft report on faithfulness, completeness, citation quality."""

    SYSTEM_PROMPT = """You are a strict editorial critic for financial research reports.

Evaluate the draft report on three dimensions (0-10 each):
- faithfulness: does every claim trace back to a [chunk_id] citation AND is that citation present in the provided chunks?
- completeness: does the report address the user's query thoroughly?
- citation_quality: are citations placed correctly, and are sources listed?

Then decide:
- "approve" if faithfulness >= 8 AND completeness >= 7 AND citation_quality >= 7
- "revise" otherwise

If revise, provide specific feedback and a revision_focus (a refined query string that the Researcher should re-run to fill gaps).

Return ONLY valid JSON:
{
  "faithfulness": 0-10,
  "completeness": 0-10,
  "citation_quality": 0-10,
  "decision": "approve" | "revise",
  "feedback": "concrete critique, 2-3 sentences",
  "revision_focus": "refined query string, or null if approving"
}"""

    def __init__(self) -> None:
        """Initialize the critic with its configured model."""
        self.model = settings.critic_model

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate the current report draft and decide approve versus revise."""
        t0 = time.perf_counter()
        query = state["query"]
        draft = state.get("draft_report", "") or ""
        chunks = state.get("retrieved_chunks", []) or []
        chunk_ids = sorted({chunk.get("id", "") for chunk in chunks if chunk.get("id")})

        print(f"[C] Critic: evaluating {len(draft)} char draft against {len(chunk_ids)} chunks")

        user_msg = (
            f"Query: {query}\n\n"
            f"Available chunk IDs (valid citations): {chunk_ids}\n\n"
            f"Draft report:\n{draft}\n\n"
            "Evaluate and return JSON."
        )

        resp = llm_client.chat(
            model=self.model,
            system=self.SYSTEM_PROMPT,
            user=user_msg,
            json_mode=True,
            max_tokens=600,
            temperature=0.1,
        )

        if resp.raw_json is None:
            logger.warning("Critic JSON parse failed. Raw response: %s", resp.content[:200])

        critique = resp.raw_json or {
            "faithfulness": 0,
            "completeness": 0,
            "citation_quality": 0,
            "decision": "approve",
            "feedback": f"Critic JSON parse failed. Raw: {resp.content[:200]}",
            "revision_focus": None,
        }

        latency = int((time.perf_counter() - t0) * 1000)
        audit_entry = {
            "agent": "critic",
            "action": "evaluate_report",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": latency,
            "model": resp.model,
            "input_summary": f"{len(draft)} char draft",
            "output_summary": (
                f"decision={critique.get('decision')}, "
                f"faith={critique.get('faithfulness')}, "
                f"comp={critique.get('completeness')}, "
                f"cite={critique.get('citation_quality')}"
            ),
        }

        return {
            **state,
            "critique": critique,
            "audit_trail": state.get("audit_trail", []) + [audit_entry],
        }
