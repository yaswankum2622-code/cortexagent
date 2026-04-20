"""FastAPI app exposing the CortexAgent multi-agent orchestrator as a web API."""

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents._llm_client import llm_client
from agents.orchestrator import CortexAgentOrchestrator
from api.cost_tracker import cost_tracker
from api.schemas import (
    AuditEntry,
    AuditTrailResponse,
    Citation,
    CostSummary,
    CritiqueInfo,
    HealthResponse,
    ResearchRequest,
    ResearchResponse,
)
from config.logging_setup import configure_logging
from config.settings import settings


logger = logging.getLogger(__name__)

_orchestrator: Optional[CortexAgentOrchestrator] = None
_audit_store: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
_llm_cost_hook_installed = False


def _install_cost_tracking_hook() -> None:
    """Wrap the shared llm_client.chat so API cost summaries reflect real usage."""
    global _llm_cost_hook_installed
    if _llm_cost_hook_installed:
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
    _llm_cost_hook_installed = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the orchestrator once at startup."""
    global _orchestrator
    configure_logging(settings.log_level)
    logger.info("Starting CortexAgent API...")
    _install_cost_tracking_hook()
    _orchestrator = CortexAgentOrchestrator()
    logger.info("Orchestrator initialized. API ready.")
    yield
    logger.info("Shutting down CortexAgent API.")


app = FastAPI(
    title="CortexAgent API",
    description=(
        "Production-grade agentic RAG platform for SEC 10-K financial research. "
        "Multi-agent LangGraph orchestrator (Researcher, Analyst, Writer, Critic) "
        "with 3-provider cascading LLM fallback and RAGAS-gated CI/CD."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_orchestrator() -> CortexAgentOrchestrator:
    """Return the initialized orchestrator or fail fast if startup is incomplete."""
    if _orchestrator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not initialized yet. Wait a moment and retry.",
        )
    return _orchestrator


def _extract_citations(state: Dict[str, Any]) -> List[Citation]:
    """Extract cited chunks from the final state."""
    chunks = state.get("retrieved_chunks", []) or []
    citations: List[Citation] = []
    for chunk in chunks[:5]:
        meta = chunk.get("metadata", {}) or {}
        citations.append(
            Citation(
                chunk_id=chunk.get("id", "unknown"),
                ticker=str(meta.get("ticker", "?")),
                year=int(meta.get("year", 0) or 0),
                preview=(chunk.get("text") or "")[:200],
            )
        )
    return citations


def _extract_models_used(state: Dict[str, Any]) -> List[str]:
    """Return distinct LLM model names seen in the audit trail."""
    audit = state.get("audit_trail", []) or []
    seen: List[str] = []
    for entry in audit:
        model = entry.get("model")
        if model and model not in seen:
            seen.append(model)
    return seen


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    """Service health check. Confirms orchestrator, ChromaDB, and provider keys."""
    providers = {
        "anthropic": bool(settings.anthropic_api_key),
        "gemini": bool(settings.gemini_api_key),
        "groq": bool(settings.groq_api_key),
    }
    chunks = 0
    collection_name = "sec_10k"
    try:
        import chromadb

        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        collection = client.get_collection(collection_name)
        chunks = collection.count()
    except Exception as exc:
        logger.warning("Chroma check failed: %s", exc)

    return HealthResponse(
        status="ok" if chunks > 0 else "degraded",
        chroma_collection_name=collection_name,
        chroma_chunks=chunks,
        providers_configured=providers,
        embedding_model=settings.embedding_model,
    )


@app.post("/research", response_model=ResearchResponse, tags=["research"])
async def research(req: ResearchRequest):
    """
    Run a full multi-agent research pass on an SEC 10-K query.

    Returns the final Markdown report, citations, and audit summary.
    Typical latency: 60-180 seconds depending on revision loops.
    """
    orchestrator = _get_orchestrator()
    thread_id = req.thread_id or f"api_{uuid.uuid4().hex[:12]}"

    final_state = await asyncio.to_thread(orchestrator.run, req.query, thread_id)

    _audit_store[thread_id].extend(final_state.get("audit_trail", []) or [])
    cost_tracker.record_query()

    critique = None
    critique_raw = final_state.get("critique") or {}
    if critique_raw:
        critique = CritiqueInfo(
            decision=str(critique_raw.get("decision", "unknown")),
            faithfulness=int(critique_raw.get("faithfulness", 0) or 0),
            completeness=int(critique_raw.get("completeness", 0) or 0),
            citation_quality=int(critique_raw.get("citation_quality", 0) or 0),
            feedback=critique_raw.get("feedback"),
        )

    return ResearchResponse(
        thread_id=thread_id,
        query=req.query,
        report=final_state.get("final_report", "") or "",
        citations=_extract_citations(final_state),
        revision_count=int(final_state.get("revision_count", 0) or 0),
        critique=critique,
        retrieval_grade=final_state.get("retrieval_grade"),
        wall_latency_ms=int(final_state.get("wall_latency_ms", 0) or 0),
        total_latency_ms=int(final_state.get("total_latency_ms", 0) or 0),
        models_used=_extract_models_used(final_state),
    )


@app.post("/research/stream", tags=["research"])
async def research_stream(req: ResearchRequest):
    """
    Streaming version: Server-Sent Events yield node-by-node state updates.

    Useful for UIs that want to show live agent progress.
    """
    orchestrator = _get_orchestrator()
    thread_id = req.thread_id or f"api_{uuid.uuid4().hex[:12]}"

    async def event_generator():
        yield f"event: start\ndata: {json.dumps({'thread_id': thread_id, 'query': req.query})}\n\n"

        try:
            updates = await asyncio.to_thread(
                lambda: list(orchestrator.stream(req.query, thread_id))
            )
            for update in updates:
                for node_name, node_state in update.items():
                    safe_payload: Dict[str, Any] = {"node": node_name, "revision_count": 0}
                    if isinstance(node_state, dict):
                        safe_payload["revision_count"] = int(
                            node_state.get("revision_count", 0) or 0
                        )
                        if node_state.get("research_notes"):
                            safe_payload["research_notes_preview"] = (
                                node_state["research_notes"] or ""
                            )[:300]
                        if node_state.get("draft_report"):
                            safe_payload["draft_preview"] = (
                                node_state["draft_report"] or ""
                            )[:300]
                        if node_state.get("critique"):
                            safe_payload["critique_decision"] = (
                                node_state["critique"] or {}
                            ).get("decision")
                    yield f"event: node\ndata: {json.dumps(safe_payload)}\n\n"
            yield f"event: end\ndata: {json.dumps({'thread_id': thread_id, 'status': 'complete'})}\n\n"
        except Exception as exc:
            logger.exception("Streaming failed")
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/audit/{thread_id}", response_model=AuditTrailResponse, tags=["observability"])
async def get_audit(thread_id: str):
    """Retrieve the in-memory audit trail for a thread."""
    entries_raw = _audit_store.get(thread_id, [])
    entries = [
        AuditEntry(
            agent=str(entry.get("agent", "unknown")),
            action=str(entry.get("action", "")),
            timestamp=str(entry.get("timestamp", "")),
            latency_ms=int(entry.get("latency_ms", 0) or 0),
            model=entry.get("model"),
            input_summary=entry.get("input_summary"),
            output_summary=entry.get("output_summary"),
        )
        for entry in entries_raw
    ]
    return AuditTrailResponse(
        thread_id=thread_id,
        entries=entries,
        total_entries=len(entries),
    )


@app.get("/cost", response_model=CostSummary, tags=["observability"])
async def get_cost():
    """Session-wide cost summary (in-memory)."""
    return CostSummary(**cost_tracker.summary())


@app.get("/", tags=["system"])
async def root():
    """Welcome message + quick links."""
    return {
        "service": "CortexAgent API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": [
            "POST /research",
            "POST /research/stream",
            "GET /audit/{thread_id}",
            "GET /cost",
            "GET /health",
        ],
    }


if __name__ == "__main__":
    import uvicorn

    configure_logging(settings.log_level)
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
