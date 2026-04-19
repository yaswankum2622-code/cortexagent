"""Multi-agent LangGraph orchestrator: Researcher -> Analyst -> Writer -> Critic with revision loop."""

import logging
import time
from typing import Any, Dict, List, Literal, Optional

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.analyst import AnalystAgent
from agents.critic import CriticAgent
from agents.researcher import ResearcherAgent
from agents.writer import WriterAgent
from config.settings import settings


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

MAX_REVISIONS = 2


class AgentState(TypedDict, total=False):
    """State carried through the multi-agent research graph."""

    query: str
    retrieved_chunks: List[Dict[str, Any]]
    retrieval_grade: Dict[str, Any]
    retrieval_retry_history: List[Dict[str, Any]]
    research_notes: str
    structured_findings: Dict[str, Any]
    draft_report: str
    critique: Dict[str, Any]
    revision_count: int
    revision_focus: Optional[str]
    final_report: str
    audit_trail: List[Dict[str, Any]]
    total_latency_ms: int
    wall_latency_ms: int


def route_after_critic(state: AgentState) -> Literal["revise", "done"]:
    """Decide whether to revise (loop back to researcher) or finalize."""
    critique = state.get("critique", {}) or {}
    decision = critique.get("decision", "approve")
    revision_count = state.get("revision_count", 0)
    if decision == "approve":
        return "done"
    if revision_count >= MAX_REVISIONS:
        logger.warning("Max revisions (%s) reached, shipping draft as-is", MAX_REVISIONS)
        print("[ORCHESTRATOR] Max revisions reached, shipping current draft")
        return "done"
    return "revise"


def prepare_revision(state: AgentState) -> AgentState:
    """Before looping back to researcher, bump revision counter and set revision_focus."""
    critique = state.get("critique", {}) or {}
    new_count = state.get("revision_count", 0) + 1
    focus = critique.get("revision_focus") or state.get("query", "")
    print(f"[REVISE] Attempt {new_count}: {focus[:80]}")
    return {
        **state,
        "revision_count": new_count,
        "revision_focus": focus,
    }


def finalize(state: AgentState) -> AgentState:
    """Mark the draft as final and compute total agent latency."""
    draft = state.get("draft_report", "") or ""
    total = sum(entry.get("latency_ms", 0) for entry in state.get("audit_trail", []) or [])
    print(f"[FINALIZE] Report ready ({len(draft)} chars, total agent latency {total}ms)")
    return {
        **state,
        "final_report": draft,
        "total_latency_ms": total,
    }


class CortexAgentOrchestrator:
    """LangGraph-based multi-agent orchestrator for financial research."""

    def __init__(self) -> None:
        """Instantiate agents and compile the LangGraph workflow."""
        self.researcher = ResearcherAgent()
        self.analyst = AnalystAgent()
        self.writer = WriterAgent()
        self.critic = CriticAgent()

        graph = StateGraph(AgentState)
        graph.add_node("researcher", self.researcher.run)
        graph.add_node("analyst", self.analyst.run)
        graph.add_node("writer", self.writer.run)
        graph.add_node("critic", self.critic.run)
        graph.add_node("prepare_revision", prepare_revision)
        graph.add_node("finalize", finalize)

        graph.add_edge(START, "researcher")
        graph.add_edge("researcher", "analyst")
        graph.add_edge("analyst", "writer")
        graph.add_edge("writer", "critic")
        graph.add_conditional_edges(
            "critic",
            route_after_critic,
            {
                "revise": "prepare_revision",
                "done": "finalize",
            },
        )
        graph.add_edge("prepare_revision", "researcher")
        graph.add_edge("finalize", END)

        self.checkpointer = MemorySaver()
        self.graph = graph.compile(checkpointer=self.checkpointer)

    def run(self, query: str, thread_id: str = "default") -> Dict[str, Any]:
        """Run the full agent flow synchronously. Returns final state."""
        print("=" * 70)
        print(f"CortexAgent - query: {query}")
        print("=" * 70)
        t0 = time.perf_counter()

        initial_state: AgentState = {
            "query": query,
            "revision_count": 0,
            "audit_trail": [],
        }
        config = {"configurable": {"thread_id": thread_id}}
        result = self.graph.invoke(initial_state, config=config)

        wall_latency = int((time.perf_counter() - t0) * 1000)
        final_state: Dict[str, Any] = {
            **result,
            "wall_latency_ms": wall_latency,
        }
        return final_state

    def stream(self, query: str, thread_id: str = "default") -> Any:
        """Yield state updates node-by-node for UI streaming."""
        initial_state: AgentState = {
            "query": query,
            "revision_count": 0,
            "audit_trail": [],
        }
        config = {"configurable": {"thread_id": thread_id}}
        for update in self.graph.stream(initial_state, config=config):
            yield update


if __name__ == "__main__":
    from config.logging_setup import configure_logging
    from config.settings import settings

    configure_logging(settings.log_level)

    queries = [
        "What are Apple's top 3 disclosed risk factors in the 2024 10-K?",
        "Summarize JPMorgan's main revenue segments for fiscal 2024.",
    ]

    orchestrator = CortexAgentOrchestrator()
    final_runs: List[Dict[str, Any]] = []

    for index, query in enumerate(queries, start=1):
        print("\n" + "=" * 70)
        print(f"DEMO {index}/{len(queries)}: {query}")
        print("=" * 70)

        final = orchestrator.run(query, thread_id=f"demo_{index}")
        final_runs.append(final)

        print("\n--- AUDIT TRAIL ---")
        print(f"{'Agent':<12} {'Action':<25} {'Latency(ms)':<12} {'Model':<30} {'Output summary'}")
        print("-" * 120)
        for entry in final.get("audit_trail", []):
            print(
                f"{entry.get('agent', '?'):<12} "
                f"{entry.get('action', '?'):<25} "
                f"{entry.get('latency_ms', 0):<12} "
                f"{entry.get('model', '?'):<30} "
                f"{entry.get('output_summary', '')}"
            )

        retrieval_grade = final.get("retrieval_grade", {})
        print("\n--- RETRIEVAL GRADE ---")
        print(
            f"Decision: {retrieval_grade.get('decision')}, "
            f"Relevance: {retrieval_grade.get('relevance')}, "
            f"Sufficiency: {retrieval_grade.get('sufficiency')}"
        )

        critique = final.get("critique", {})
        print("\n--- FINAL CRITIQUE ---")
        print(f"Decision: {critique.get('decision')}")
        print(
            f"Faithfulness: {critique.get('faithfulness')}, "
            f"Completeness: {critique.get('completeness')}, "
            f"Citation Quality: {critique.get('citation_quality')}"
        )
        print(f"Feedback: {critique.get('feedback')}")

        print(f"\n--- REVISIONS: {final.get('revision_count', 0)} ---")

        final_report = final.get("final_report", "")
        print(f"\n--- FINAL REPORT ({len(final_report):,} chars) ---")
        print(final_report or "(no report)")

        print("\n--- LATENCY ---")
        print(f"Total agent latency: {final.get('total_latency_ms', 0)} ms")
        print(f"Wall clock latency:  {final.get('wall_latency_ms', 0)} ms")

    total_audit_entries = sum(len(run.get("audit_trail", [])) for run in final_runs)
    total_revisions = sum(run.get("revision_count", 0) for run in final_runs)
    combined_wall_latency = sum(run.get("wall_latency_ms", 0) for run in final_runs)

    print("\n" + "=" * 70)
    print("SESSION SUMMARY")
    print("=" * 70)
    print(f"Total audit entries: {total_audit_entries}")
    print(f"Total revisions observed: {total_revisions}")
    print(f"Combined wall latency: {combined_wall_latency} ms")
