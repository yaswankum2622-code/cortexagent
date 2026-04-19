"""Writer agent: generates the final Markdown research report with citations."""

import json as _json
import logging
import os
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
EVAL_MODE = os.environ.get("CORTEX_EVAL_MODE", "0") == "1"


class WriterAgent:
    """Generates the final Markdown report with inline [chunk_id] citations."""

    SYSTEM_PROMPT = """You are a senior financial research writer. Given structured findings, write a clear Markdown report.

Required sections (in order):
## Executive Summary
## Key Findings
## Financial Figures
## Risk Factors
## Opportunities
## Sources

Rules:
- EVERY factual claim MUST end with a citation in the format [chunk_id]
- Do NOT introduce any fact not present in the structured findings
- Be concise - aim for ~400 words total
- Use bullet points for Key Findings, Risk Factors, and Opportunities
- In Sources section, list each unique chunk_id used, one per line
- If structured_findings has an _error field, write a one-paragraph apology report explaining the analysis failed"""

    def __init__(self) -> None:
        """Initialize the writer with its configured model."""
        self.model = settings.writer_model

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Draft the final Markdown report from structured findings and revision feedback."""
        t0 = time.perf_counter()
        query = state["query"]
        findings = state.get("structured_findings", {}) or {}

        revision_note = ""
        if state.get("critique") and state.get("revision_count", 0) > 0:
            prev_feedback = state["critique"].get("feedback", "")
            revision_note = (
                f"\n\nThis is revision #{state['revision_count']}. "
                f"Critic's previous feedback: {prev_feedback}\n"
                "Address those concerns in this draft."
            )

        print(f"[W] Writer: drafting report (revision #{state.get('revision_count', 0)})")

        findings_json = _json.dumps(findings, indent=2)[:4000]
        user_msg = (
            f"Query: {query}\n\n"
            f"Structured findings (JSON):\n{findings_json}\n"
            f"{revision_note}\n\n"
            "Write the Markdown report."
        )

        if EVAL_MODE:
            max_tokens_writer = 700
            user_msg += (
                "\n\nIMPORTANT: Keep the report concise. "
                "Target 250 words max. Still include all required sections."
            )
        else:
            max_tokens_writer = 1500

        resp = llm_client.chat(
            model=self.model,
            system=self.SYSTEM_PROMPT,
            user=user_msg,
            json_mode=False,
            max_tokens=max_tokens_writer,
            temperature=0.3,
        )

        latency = int((time.perf_counter() - t0) * 1000)
        audit_entry = {
            "agent": "writer",
            "action": "draft_report",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": latency,
            "model": resp.model,
            "input_summary": f"findings keys={list(findings.keys())}",
            "output_summary": f"{len(resp.content)} chars",
        }

        return {
            **state,
            "draft_report": resp.content,
            "audit_trail": state.get("audit_trail", []) + [audit_entry],
        }
