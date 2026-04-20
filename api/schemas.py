"""Pydantic request/response models for the CortexAgent API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """Request body for /research endpoints."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Natural-language research question about SEC 10-K filings",
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Conversation thread ID for audit tracking. Auto-generated if not provided.",
    )


class Citation(BaseModel):
    """One cited chunk surfaced in the API response."""

    chunk_id: str
    ticker: str
    year: int
    preview: str


class CritiqueInfo(BaseModel):
    """Structured final critique summary returned by the Critic agent."""

    decision: str
    faithfulness: int
    completeness: int
    citation_quality: int
    feedback: Optional[str] = None


class ResearchResponse(BaseModel):
    """Response body for POST /research."""

    thread_id: str
    query: str
    report: str = Field(
        ...,
        description="The final Markdown report with inline citations",
    )
    citations: List[Citation] = Field(
        default_factory=list,
        description="Sources cited in the report",
    )
    revision_count: int
    critique: Optional[CritiqueInfo] = None
    retrieval_grade: Optional[Dict[str, Any]] = None
    wall_latency_ms: int
    total_latency_ms: int
    models_used: List[str] = Field(
        default_factory=list,
        description="Distinct LLM models that served this query",
    )


class AuditEntry(BaseModel):
    """One audit trail row."""

    agent: str
    action: str
    timestamp: str
    latency_ms: int
    model: Optional[str] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None


class AuditTrailResponse(BaseModel):
    """Response body for GET /audit/{thread_id}."""

    thread_id: str
    entries: List[AuditEntry]
    total_entries: int


class HealthResponse(BaseModel):
    """Service health response."""

    status: str
    chroma_collection_name: str
    chroma_chunks: int
    providers_configured: Dict[str, bool]
    embedding_model: str
    version: str = "0.1.0"


class CostSummary(BaseModel):
    """Session-wide or thread-scoped cost summary."""

    thread_id: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_usd: float = 0.0
    by_model: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    queries_served: int = 0
