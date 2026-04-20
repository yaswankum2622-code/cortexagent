# Cost Engineering

## 1. Why Cost Is a Design Constraint

Cost is a product decision long
before it is a finance spreadsheet.

Multi-agent systems amplify this
problem because they multiply calls
by design.

In CortexAgent,
one user query can involve the
Researcher,
Self-RAG grading,
the Analyst,
the Writer,
the Critic,
and up to two revision loops.

That means a careless configuration
can easily produce ten or more model
calls for a single answer.

If every one of those calls uses a
premium model such as
Claude Sonnet 4.5,
unit economics degrade quickly.

At that point,
the model choice becomes a hidden tax
on every feature.

You cannot justify broader usage,
background jobs,
continuous eval,
or a generous demo experience if the
core query path is already too
expensive.

That is why CortexAgent treats cost
as part of system architecture rather
than an afterthought.

The goal is not "use the cheapest
model everywhere."

The goal is:
use the cheapest model that is still
good enough for the role,
and reserve premium models for the
judgment points where they create the
most value.

## 2. Model Assignment Decisions

The Researcher is mapped to
Gemini 2.5 Flash Lite in the intended
cost-optimized routing strategy.

This role performs retrieval-adjacent
summarization and Self-RAG-assisted
evidence inspection.

It has to be grounded and reasonably
structured,
but it does not need luxurious prose.

That makes it a good candidate for a
cheap fast model.

The Analyst follows the same logic.

Its job is JSON extraction:
facts,
numbers,
risks,
and opportunities.

This is precisely the kind of task
where a structured-output capable,
low-cost model is more valuable than
a premium writing model.

The Writer is where the tradeoff gets
more interesting.

In the frozen project design,
the best cost-quality assignment is
Claude Haiku 4.5.

The user sees this output directly,
so language quality matters,
but the Writer is still constrained
by structured findings and mandatory
citations.

It does not need the strongest
possible reasoning model for every
query.

In practice,
some evaluation-sensitive runs and
fallback paths may still land on
Claude Sonnet 4.5,
but the architecture is designed so
that Haiku can do the bulk of the
user-facing prose work.

The Critic is the opposite case.

This role is not about volume.

It is about quality control.

If the Critic is weak,
the system ships bad drafts.

That makes Claude Sonnet 4.5 the
right assignment.

The same argument applies to the
RAGAS judge.

Measurement integrity matters more
than saving a few cents on the
evaluation path.

Self-RAG grading is again a
high-volume,
bounded judgment task,
so Gemini 2.5 Flash Lite is a good
economic fit.

The broader principle is simple:
cheap models do retrieval-adjacent
and schema-adjacent work,
premium models do judgment-critical
work,
and the whole graph is designed
around that separation.

## 3. Cascading Fallback Architecture

CortexAgent uses a shared
`FALLBACK_CHAIN`
inside `agents/_llm_client.py`.

That chain defines how the system
moves from a preferred model to a
fallback model when provider-side
errors occur.

For example,
Gemini models can fall back to
Groq Llama 3.3 70B,
and then to Claude Sonnet 4.5.

The logic is not just "catch every
exception and try again."

The client distinguishes retryable
errors from permanent ones.

Rate limits,
quota exhaustion,
timeouts,
capacity errors,
and provider overload should trigger
fallback.

Authentication failures and invalid
request errors should fail fast.

That distinction is captured in
`_is_retryable_error()`.

Retries on the same model are handled
with Tenacity,
while cross-model fallback is handled
in the outer `chat()` wrapper.

The normalized `LLMResponse` also
contains a `fallback_used` flag.

That is a small detail with large
operational value because it makes
provider instability visible in logs,
in cost analysis,
and in demo explanations.

## 4. Cost Tracker

The API installs a wrapper around the
shared `llm_client.chat` method at
startup.

Every successful call records input
tokens,
output tokens,
and estimated USD into a
thread-safe `CostTracker`
singleton.

Pricing data lives in the
`MODEL_PRICING` map inside
`api/cost_tracker.py`.

The tracker aggregates totals across
the life of the API process and
exposes them through `GET /cost`.

That means the Streamlit dashboard
can show live spend without redoing
pricing logic client-side.

The key engineering point is not the
math itself.

It is the fact that spend is visible
at all.

Many demo systems have no cost
observability until deployment.

CortexAgent includes it as part of
the developer loop.

## 5. Actual Spend Analysis

The project has already demonstrated
that cost engineering changes the
economics materially.

The full build and iteration cycle
was completed on a small budget,
roughly on the order of
`$15`
across several days of development
and evaluation.

Observed per-query cost in the
current system typically falls in the
`$0.05-$0.15`
range depending on revision count,
provider fallback,
and whether premium models are hit
more heavily than planned.

Compared with a naive all-Sonnet
configuration,
the routed design is roughly
10-20x cheaper.

One note is important for honesty:
the project brief’s aggressive
production target of roughly
`$3-5/day` at very high query volume
is a future-state economics goal that
assumes heavier caching,
optimized routing,
and operational smoothing.

The current uncached demo stack is
not there yet.

That does not weaken the cost story.

It strengthens it,
because the architecture already
contains the controls required to
push toward that target rather than
locking the system into premium-model
spend by default.
