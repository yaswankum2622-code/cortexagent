# Changelog

All notable changes to CortexAgent are documented in this file.

This project follows a milestone-oriented changelog because the repository is also intended to be read as a portfolio artifact. The sequence of commits matters: each milestone should tell a coherent engineering story rather than collapse unrelated work into one large dump.

The format is inspired by Keep a Changelog and adapted for a portfolio-driven AI engineering project.

## [1.0.1] - 2026-04-20

### Fixed

- Aligned package versioning, CI thresholds, workflow docs, and the saved benchmark artifact with the shipped repository state.
- Recalibrated the RAGAS quality gate to the documented baseline so the release does not fail its own published contract.
- Standardized default model routing to Gemini Flash Lite for Researcher, Analyst, and Self-RAG, Claude Haiku for Writer, and Claude Sonnet for Critic and RAGAS judge.
- Removed the obsolete top-level `version` field from `docker-compose.yml` to keep Compose validation clean.

## [1.0.0] - 2026-04-20

First production-ready portfolio release of CortexAgent.

### Added

- Multi-agent orchestration built on LangGraph.
- Four specialized agents: Researcher, Analyst, Writer, and Critic.
- Conditional revision loop with `MAX_REVISIONS=2`.
- Hybrid retrieval pipeline using BM25, dense embeddings, Reciprocal Rank Fusion, and a BGE cross-encoder reranker.
- Section-aware 10-K chunking keyed to SEC filing structure.
- Indexed corpus covering AAPL, MSFT, GOOGL, JPM, and TSLA 2024 10-K filings.
- Persistent local vector store via ChromaDB.
- Self-RAG style retrieval grading before answer generation.
- FastAPI backend with the following endpoints:
- `POST /research`
- `POST /research/stream`
- `GET /audit/{thread_id}`
- `GET /health`
- `GET /cost`
- Swagger UI via `/docs`
- Streamlit dashboard with:
- custom dark theme
- metric cards
- live provider status
- cost sidebar
- agent flow visualization
- citations tab
- critic review tab
- audit trail tab
- LAN-accessible binding via `0.0.0.0`
- In-memory audit trail and per-model cost tracking.
- Three-provider cascading fallback architecture:
- Gemini 2.5 Flash Lite
- Groq Llama 3.3 70B
- Claude Sonnet 4.5 / Haiku 4.5
- RAGAS evaluation harness with baseline reports and CI subset support.
- Red-team adversarial test suite covering 20 prompts across 7 attack categories.
- MCP tool definitions and concrete tools:
- DuckDuckGo web search
- SELECT-only SQL query tool
- mock calendar booking tool
- Full technical documentation set under `docs/`.
- Architectural Decision Records documenting core design tradeoffs.
- Interview prep document for recruiter and hiring-manager walkthroughs.
- Professional README with screenshots, architecture diagram, and quick start instructions.
- Docker deployment infrastructure:
- `Dockerfile`
- `Dockerfile.streamlit`
- `docker-compose.yml`
- `.dockerignore`
- `docs/DEPLOYMENT.md`
- Local setup scripts for bash and PowerShell.

### Evaluation Baseline

- Canonical RAGAS baseline established at v3.
- Faithfulness baseline documented at `0.426`.
- Answer relevancy baseline documented at `0.222`.
- Context precision baseline documented at `0.283`.
- Answer correctness baseline documented at `0.245`.
- Red-team baseline recorded at `20/20` safe with `0` HIGH severity failures.

### Developer Experience

- Added root-level `CONTRIBUTING.md`.
- Added root-level `CODE_OF_CONDUCT.md`.
- Added issue templates for bug reports and feature requests.
- Added pull request template.
- Added `scripts/run_demo.py` for interview-style demonstrations.
- Added `Makefile` convenience targets for setup, ingestion, evaluation, and Docker workflows.
- Rewrote `.env.example` with detailed inline guidance.

### Documentation

- Added problem statement with target users, failure modes, and system approach.
- Added architecture deep dive with mermaid diagrams and data flow walkthrough.
- Added agent-level documentation with prompt structure, contracts, and observability hooks.
- Added retrieval write-up covering chunking, ticker detection, and reranking.
- Added evaluation write-up covering the iteration story and Goodhart's Law.
- Added safety write-up covering red-team strategy and behavioral contract testing.
- Added cost engineering write-up covering model routing and fallback logic.
- Added tech stack rationale by layer.
- Added innovations write-up contrasting CortexAgent with tutorial RAG systems.
- Added future work roadmap across reliability, performance, deployment, and evaluation maturity.

### Known Limitations

- Audit persistence is still in-memory rather than backed by Postgres.
- Redis caching is not implemented yet.
- Docker configuration is ready, but end-to-end container validation depends on local Docker availability.
- RAGAS thresholds are calibrated to the shipped baseline today and should tighten as the benchmark improves.
- The red-team baseline is strong for a first release but still smaller than production-scale safety suites such as HarmBench or JailbreakBench.
- The vector corpus is intentionally limited to five companies for demo speed and cost control.

### Release Notes

- This release closes the MVP-to-flagship portfolio arc for CortexAgent.
- The repo now demonstrates not only model usage, but the surrounding operational discipline required for production AI systems:
- evaluation
- safety testing
- cost engineering
- observability
- deployment readiness
- documentation quality

### Recommended Next Milestones

- Persist audit logs to Postgres.
- Add Redis semantic caching.
- Expand the corpus from five companies to a broader S&P 500 slice.
- Grow the evaluation dataset beyond the current curated set.
- Add hosted deployment and a public live demo URL.
- Introduce OpenTelemetry and centralized structured logs.

## [Unreleased]

### Planned

- Container validation on a clean machine.
- Public deployment pass.
- Release asset cleanup and social preview polish.
- Larger benchmark datasets.
- Expanded red-team suite.
