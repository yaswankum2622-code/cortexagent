# Deployment Guide

CortexAgent supports three practical deployment modes:

1. Local Docker Compose for reproducible evaluation on a laptop or desktop
2. Public demo deployment on a PaaS such as Railway or Fly.io
3. Self-hosted deployment for teams that want tighter control over networking and secrets

This document focuses on operational reality rather than a hello-world deploy. The system has two user-facing services today:

- a FastAPI backend on port `8000`
- a Streamlit dashboard on port `8501`

The backend owns orchestration, retrieval, provider routing, audit endpoints, and cost tracking. The dashboard is a thin client that calls the API. The deployment design reflects that split. Containers are intentionally small and composable, and the Compose file is scaffolded so future Postgres and Redis services can be dropped in without reworking the rest of the stack.

---

## 1. Local Docker Compose

Local Docker Compose is the recommended mode for evaluators, recruiters, and teammates who want a deterministic setup. It avoids Python version drift, avoids machine-specific package conflicts, and makes the repo feel like a real service rather than a notebook project.

### Prerequisites

- Docker Desktop 4.x or newer
- Docker Compose v2
- 8 GB RAM minimum
- 5 GB free disk space
- valid provider keys in `.env`

### First-time setup

```bash
git clone https://github.com/yaswankum2622-code/cortexagent.git
cd cortexagent
cp .env.example .env
```

Edit `.env` and set:

- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `SEC_IDENTITY`

The `SEC_IDENTITY` value should look like:

```text
Your Name your.email@example.com
```

That string is required by SEC EDGAR etiquette and helps keep the ingestion flow compliant.

### Build and start the stack

```bash
docker-compose build
docker-compose up -d
```

The first build takes a few minutes because it needs to install the Python dependency graph, including retrieval and evaluation packages. Subsequent rebuilds are much faster if the lockfile and dependencies have not changed.

### One-time ingestion inside the container

The FastAPI service will boot without data, but the health endpoint will report a degraded state until the Chroma collection exists. After the containers are up, run ingestion once inside the API container:

```bash
docker-compose exec api python -m rag.ingestion
```

This step downloads or processes the SEC corpus and persists it into the named Docker volumes defined in `docker-compose.yml`.

### Open the services

- Dashboard: `http://localhost:8501`
- API docs: `http://localhost:8000/docs`
- Health endpoint: `http://localhost:8000/health`

### Operational commands

```bash
docker-compose logs -f api
docker-compose logs -f dashboard
docker-compose ps
docker-compose down
docker-compose down -v
docker-compose up -d --build
```

Use `down` when you want to stop the stack but preserve indexed data. Use `down -v` only when you intentionally want a clean slate, because it removes the named volumes for Chroma and SEC data.

### Access from your phone on the same Wi-Fi

Because the API and dashboard both bind to `0.0.0.0`, they are reachable from other devices once the host ports are published by Docker. Use:

```bash
python scripts/find_my_ip.py
```

Then open:

- `http://YOUR_LAN_IP:8501`
- `http://YOUR_LAN_IP:8000/docs`

This is useful for demoing the Streamlit dashboard on a phone or tablet without changing the deployment topology.

---

## 2. Architecture of the Docker Stack

The current Compose file is intentionally simple:

- `api` builds from `Dockerfile`
- `dashboard` builds from `Dockerfile.streamlit`
- `chroma_data` persists vector state
- `sec_data` persists downloaded and processed filing data
- `cortex_net` provides container-to-container DNS

The dashboard talks to the backend through:

```text
http://api:8000
```

That hostname works because Docker Compose registers service names in the shared bridge network. The dashboard does not need provider keys for ordinary use because it does not talk to Anthropic, Gemini, or Groq directly. It calls the API only.

### Why two Dockerfiles?

The API and Streamlit dashboard have different runtime concerns:

- the API needs the orchestration and retrieval modules
- the dashboard needs Streamlit and the UI layer

Splitting them keeps concerns clean and allows independent restart or scaling later. In a future production deployment, the API may scale horizontally while the dashboard remains a single lightweight service.

### Why multi-stage builds?

The builder stage installs dependencies into a virtual environment, while the runtime stage stays smaller and omits build tooling. This reduces attack surface and cuts image size relative to a single giant build image.

### Why a non-root user?

Both runtime images drop privileges to a `cortex` user. That is not enough to make a service secure on its own, but it is the correct baseline for a production-minded repository and avoids the common anti-pattern of shipping everything as root.

---

## 3. Railway Deployment

Railway is the easiest path to a public demo URL. It is a good option when the goal is recruiter-friendly evaluation rather than a deeply customized production network.

### Recommended Railway layout

Create two Railway services from the same repo:

1. `cortexagent-api`
2. `cortexagent-dashboard`

Point the API service at `Dockerfile` and the dashboard service at `Dockerfile.streamlit`.

### Steps

```bash
npm install -g @railway/cli
railway login
railway init
```

Then create the two services in the Railway dashboard or CLI and set environment variables for the API service:

- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `SEC_IDENTITY`

For the dashboard service, set:

- `CORTEX_API_BASE=https://YOUR_API_SERVICE_URL`

### Persistence on Railway

The vector store and processed SEC data need persistence if you do not want to ingest on every deploy. Railway supports attached volumes. Mount those volumes to the same paths used in Docker Compose:

- `/app/chroma_db`
- `/app/data`

### Practical caveats

- free or hobby plans may sleep, which hurts demo readiness
- initial ingestion is still a one-time operational step
- if you separate services, make sure the dashboard points to the deployed API URL rather than `localhost`

---

## 4. Fly.io Deployment

Fly.io is attractive if you want more control over public deployment shape without running your own VPS. It is well-suited to small Python services and supports secrets management cleanly.

### Basic flow

```bash
fly auth login
fly launch --no-deploy
fly secrets set ANTHROPIC_API_KEY=... GEMINI_API_KEY=... GROQ_API_KEY=... SEC_IDENTITY="Your Name your.email@example.com"
fly deploy
```

If you deploy the dashboard separately, set:

```text
CORTEX_API_BASE=https://your-api-app.fly.dev
```

### Storage considerations

If you want persistent Chroma data on Fly, provision a volume and mount it at:

```text
/app/chroma_db
```

Do the same for `/app/data` if you want to keep the SEC corpus between releases.

---

## 5. Self-Hosted Deployment

For a self-hosted Linux box or cloud VM, Docker Compose is already the correct starting point. Install Docker, clone the repo, configure `.env`, run ingestion once, and put a reverse proxy such as Caddy, Nginx, or Traefik in front if you need HTTPS and custom domains.

### Minimal self-hosted shape

- 1 VM
- Docker + Compose
- ports `8000` and `8501` exposed internally
- reverse proxy terminating TLS
- optional basic auth or OAuth in front of Streamlit

This is enough for a portfolio demo or an internal team tool. Production hardening beyond that would add rate limiting, provider circuit breakers, structured logging aggregation, and a persistent audit database.

---

## 6. Environment Variables Reference

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude Sonnet and Haiku for critique, writing, and RAGAS judging |
| `GEMINI_API_KEY` | Yes | Gemini Flash / Flash Lite for retrieval-heavy agent tasks |
| `GROQ_API_KEY` | Yes | Groq fallback tier for resilience and latency control |
| `SEC_IDENTITY` | Yes | SEC EDGAR identity string |
| `RESEARCHER_MODEL` | No | Override the default Researcher model |
| `ANALYST_MODEL` | No | Override the default Analyst model |
| `WRITER_MODEL` | No | Override the default Writer model |
| `CRITIC_MODEL` | No | Override the default Critic model |
| `RAGAS_JUDGE_MODEL` | No | Override the evaluation judge model |
| `EMBEDDING_MODEL` | No | Local embedding model, defaults to `all-MiniLM-L6-v2` |
| `CHROMA_PERSIST_DIR` | No | Chroma persistence directory |
| `LOG_LEVEL` | No | Logging verbosity |

The API service loads `.env` directly through Compose. The dashboard service only needs `CORTEX_API_BASE` to locate the backend.

---

## 7. Troubleshooting

### Port collision

If `8000` or `8501` is already taken, Docker Compose will fail to bind the host port. Stop the conflicting process or adjust the left-hand side of the port mapping in `docker-compose.yml`.

### Health endpoint says degraded

This usually means Chroma has not been ingested yet. Run:

```bash
docker-compose exec api python -m rag.ingestion
```

### Dashboard cannot talk to API

Check:

- `docker-compose ps`
- `docker-compose logs -f api`
- `docker-compose logs -f dashboard`

If the dashboard is deployed separately from the API, verify `CORTEX_API_BASE` points to the deployed API URL rather than `http://api:8000`.

### Container rebuild seems stale

Rebuild the stack cleanly:

```bash
docker-compose up -d --build
```

If that still looks wrong, remove old volumes only if you intend to wipe persisted state:

```bash
docker-compose down -v
```

### Ingestion is slow or memory-heavy

That is expected relative to ordinary API startup. Increase Docker Desktop memory if needed. A one-time ingestion on a typical laptop is acceptable for portfolio use, but a larger corpus would justify background indexing jobs and dedicated storage services.

---

## 8. Cost Expectations

### Portfolio / demo usage

- local Docker compute cost: effectively zero beyond your machine
- public demo hosting: usually low double-digit USD per month
- per-query LLM cost: roughly `$0.05-$0.15`

### Production-ish usage

At `10,000` queries per day, infrastructure is still manageable if provider routing stays efficient. The dominant cost remains model usage, not Docker itself. The point of containerization here is portability and professionalism, not cost reduction.

For deeper reasoning on model routing and spend, see [07_cost_engineering.md](./07_cost_engineering.md).

---

## 9. Recommended Next Infrastructure Layers

This deployment layer is intentionally scoped. It does not yet include:

- Postgres audit persistence
- Redis semantic caching
- OpenTelemetry tracing
- provider circuit breakers
- cloud object storage for large corpora

Those belong to the next reliability and performance layers after the Docker baseline is in place. The current Compose file is a solid portfolio milestone because it proves the repo can be packaged, run, and reasoned about like a service.
