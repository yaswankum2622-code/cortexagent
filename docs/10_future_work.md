# Future Work

## Layer 1: Reliability

The first production layer is not new
features.

It is reliability.

Today,
the API keeps audit trails in memory
by thread ID.

That is acceptable for a local demo,
but not for a durable service.

The most immediate upgrade is
PostgreSQL-backed audit persistence.

That would preserve every agent
action,
latency measurement,
model choice,
and output summary across restarts.

The second reliability upgrade is
distributed tracing.

OpenTelemetry would let a request be
followed from FastAPI ingress through
retrieval,
each LLM call,
and final serialization.

That becomes critical once multiple
replicas or background jobs exist.

Third,
logging should move to structured
JSON with a system such as Loki or a
similar sink.

Human-readable logs are useful during
development.

Machine-queryable logs are what make
incident response and aggregate
analysis possible.

Fourth,
health checks should become real
dependency probes rather than simple
configuration echoes.

`/health` should verify Chroma,
PostgreSQL,
Redis,
and provider reachability with clear
degraded-state signaling.

Fifth,
provider circuit breakers should be
added.

Right now the LLM client distinguishes
retryable errors and falls back
intelligently,
but the system does not yet learn
that one provider is unhealthy over a
time window.

Circuit breakers would keep the graph
from repeatedly paying failed-call
latency on a broken upstream.

## Layer 2: Performance and Cost

The next layer is performance.

The biggest likely win is semantic
caching with Redis.

Many filing questions are repeated or
near-repeated,
especially in demos and analyst
workflows.

Caching retrieval outputs,
or even full reports for normalized
queries,
would dramatically improve cost and
latency.

Streaming is the second major win.

The API already exposes
`/research/stream`,
but the UI does not yet surface a
truly end-to-end streaming
experience.

Streaming node status and partial
draft previews would make the product
feel faster even before absolute
latency falls.

Third,
reranker work could be reduced by
precomputing or caching common query
patterns,
especially for known benchmark and
demo questions.

Fourth,
the API server should run with
multiple Uvicorn workers in
production rather than the current
single-process developer mode.

That is especially relevant because
some calls involve CPU work from the
reranker and local embedding stack.

The general theme of Layer 2 is that
the current system is already
architected for quality,
but it still has obvious optimization
surface for a real multi-user
deployment.

## Layer 3: New Capabilities

The most obvious capability expansion
is corpus breadth.

Five companies are enough to prove
the architecture,
but not enough to make the product
widely useful.

The natural next step is expansion to
the S&P 500 or at least a curated
sector-balanced subset.

The second capability is time.

Right now the corpus is focused on
2024 filings.

Adding multi-year filings would allow
temporal reasoning:
trend comparisons,
risk language shifts,
and segment evolution over time.

Third,
the system should support follow-up
questions and conversational memory.

That would let a user ask about
Apple’s service mix,
then immediately ask for risk factors
without re-specifying the company.

Fourth,
the MCP tools should move from
"registered and ready"
to fully wired into the orchestrator
control path.

The Researcher already has a
`run_with_tools` path,
but tool use is not yet central to
the main query flow.

Fifth,
custom financial embeddings may be
worth exploring.

`all-MiniLM-L6-v2`
is a strong small baseline,
but a finance-tuned embedding model
could improve semantic recall on
specialized filings vocabulary.

## Layer 4: Production Deployment

The deployment layer is
straightforward but unfinished.

The first milestone is a full
Docker Compose setup that runs API,
UI,
Chroma,
Postgres,
and Redis together.

After that,
lightweight hosting targets such as
Railway or Fly.io are plausible.

An external edge should sit in front,
likely Cloudflare,
to handle TLS,
basic protection,
and routing.

Authentication and rate limiting also
need to become first-class before
any public deployment.

The current system is a strong local
demo and engineering artifact.

It is not yet a public SaaS surface.

## Layer 5: Evaluation Maturity

The evaluation layer needs to grow in
both depth and efficiency.

The first step is a larger golden
dataset:
100 or more questions rather than
15.

The second is a cheaper judge path
for routine eval runs so CI can stay
fast and affordable.

The third is human calibration.

LLM judges are useful,
but a production team eventually
needs to know where automated scores
track human judgment and where they
do not.

The fourth is safety benchmark
expansion with datasets such as
HarmBench and JailbreakBench.

The fifth is nightly continuous
evaluation,
not just pull-request gating.

At that point,
CortexAgent would stop being only a
demoable agentic RAG system and start
looking like a continuously measured
AI product platform.
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













