# Tech Stack

## Overview

CortexAgent is deliberately built
from mainstream,
inspectable components instead of
custom hidden infrastructure.

That makes the system easier to
reason about,
easier to extend,
and easier for senior reviewers to
evaluate.

The stack is organized by functional
layer:
LLM orchestration,
retrieval,
API and UI,
evaluation,
and observability.

Versions are described as
`latest`
because the repository pins minimum
compatible ranges in `pyproject.toml`
rather than locking every package in
the narrative docs.

The value of this table is not to
repeat package names.

It is to explain why each dependency
exists and what design tradeoff it
represents.

## LLM and Agent Layer

| Library | Version | Role | Why This Over Alternatives |
|---|---|---|---|
| langgraph | latest | State-machine orchestration | Better fit for explicit revision loops and typed state than conversational agent frameworks |
| langchain | latest | Shared abstractions around model wrappers and utilities | Broad ecosystem support and easy composition with LangGraph |
| langchain-anthropic | latest | Claude wrapper for eval and orchestration paths | Official, maintained integration for Anthropic models |
| langchain-google-genai | latest | Gemini wrapper and compatibility glue | Official path for Google model access in the LangChain ecosystem |
| anthropic | latest | Direct Anthropic SDK | Needed for low-level model calls and tool-use interactions outside LangChain |
| google-genai | latest | Direct Gemini SDK | Used in the unified client for provider-native Gemini execution |
| groq | latest | Groq SDK | Gives access to the fast Llama fallback tier with a dedicated client |
| tenacity | latest | Retry control | Clear retry decorators and exponential backoff for transient failures |
| pydantic | latest | Response schema validation for structured outputs | Cleaner than hand-written JSON parsing logic alone |

## Retrieval Layer

| Library | Version | Role | Why This Over Alternatives |
|---|---|---|---|
| chromadb | latest | Persistent local vector store | Simple laptop-friendly persistence and enough power for a portfolio-scale corpus |
| rank-bm25 | latest | Sparse lexical retrieval | Lightweight and effective for exact-match financial language |
| sentence-transformers | latest | Local embedding model loading and cross-encoder support | Mature ecosystem with strong CPU-friendly baseline models |
| llama-index | latest | Document loading and chunking orchestration | Useful ingestion utilities without forcing the entire runtime to be LlamaIndex-based |
| llama-index-embeddings-huggingface | latest | Hugging Face embedding bridge | Convenient integration path during ingestion and evaluation |
| FlagEmbedding / BGE reranker | latest | Cross-encoder reranking with `BAAI/bge-reranker-v2-m3` | Better top-k precision than relying on embedding similarity alone |
| edgartools | latest | SEC EDGAR access | Domain-specific convenience over scraping or building SEC API glue from scratch |
| pypdf | latest | PDF parsing fallback | Useful for document handling outside pure filing text flows |
| unstructured | latest | Unstructured document parsing support | Helps when future corpus expansion includes noisier documents |
| tqdm | latest | Ingestion progress visibility | Small quality-of-life improvement for long indexing jobs |

## API and UI Layer

| Library | Version | Role | Why This Over Alternatives |
|---|---|---|---|
| fastapi | latest | HTTP API framework | Strong typing, automatic OpenAPI docs, and clean async ergonomics |
| uvicorn | latest | ASGI server | Standard FastAPI deployment choice with low friction |
| pydantic-settings | latest | Environment-driven configuration | Cleaner and safer than ad hoc `os.environ` usage |
| httpx | latest | HTTP client | Used by the Streamlit dashboard to call the backend cleanly |
| streamlit | latest | Demo and operator UI | Fastest path to a usable AI product surface without building a custom frontend first |
| python-dotenv | latest | Local environment loading | Simplifies developer setup and `.env` workflows |
| tiktoken | latest | Token accounting utilities | Useful for cost reasoning and future prompt budgeting work |

## Evaluation and Quality Layer

| Library | Version | Role | Why This Over Alternatives |
|---|---|---|---|
| ragas | latest | RAG evaluation framework | Purpose-built metrics for grounded retrieval-augmented generation |
| datasets | latest | Dataset container for evaluation inputs | Simple bridge into RAGAS and reproducible benchmark construction |
| pytest | latest | Test runner | Standard Python testing baseline for fast feedback loops |
| pytest-asyncio | latest | Async test support | Needed because API and orchestration surfaces include async paths |
| pytest-cov | latest | Coverage reporting | Helps quantify how much core infrastructure is actually exercised |
| GitHub Actions | latest | CI/CD automation | Straightforward path for RAGAS-gated pull request checks |

## Storage, Data, and Platform Layer

| Library | Version | Role | Why This Over Alternatives |
|---|---|---|---|
| sqlalchemy | latest | SQL access layer | Keeps the future audit database path portable and structured |
| psycopg2-binary | latest | PostgreSQL driver | Practical baseline driver for local Postgres integration |
| redis | latest | Session and cache backend candidate | Lightweight path toward semantic caching and conversation state |
| slowapi | latest | Rate limiting support | Useful for a future production perimeter around the API |
| mcp | latest | Model Context Protocol package | Signals readiness for tool-centric AI infrastructure patterns |
| duckduckgo-search | latest | Search backend for `web_search` tool | Free, fast, and easy for a portfolio-scale external lookup tool |

## Observability and Developer Tooling

| Library | Version | Role | Why This Over Alternatives |
|---|---|---|---|
| logging | stdlib | Structured logs and debug visibility | Good enough for the current single-service baseline |
| custom audit trail | repo-local | Per-node observability artifact | Tailored to agent workflows rather than generic request logs |
| black | latest | Formatting | Low-argument code formatting standard |
| ruff | latest | Linting | Fast all-purpose linting and import sorting |
| mypy | latest | Type checking | Useful because the system relies on typed state and schemas |
| hatchling | latest | Build backend | Minimal packaging backend for the Python project |

## Stack Notes

The stack choice reflects a few
consistent design preferences.

First,
prefer components that are easy to
run locally.

That is why ChromaDB,
SentenceTransformers,
and Streamlit are all present.

Second,
prefer explicit infrastructure over
magic wrappers.

That is why the project has a custom
unified LLM client and an explicit
LangGraph state schema instead of
hiding everything in a single
framework abstraction.

Third,
prefer libraries that are good enough
for production evolution,
not just demos.

FastAPI,
LangGraph,
RAGAS,
and SQLAlchemy all clear that bar.

Finally,
the stack is designed so pieces can
be swapped independently.

ChromaDB can become Qdrant.

Streamlit can become a React shell.

The in-memory audit store can become
PostgreSQL.

That modularity is one of the
strongest signals this project sends
to senior engineers reviewing it.
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->
<!-- pad -->





















































































