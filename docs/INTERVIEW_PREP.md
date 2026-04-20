# CortexAgent Interview Prep

## 1. Elevator Pitch

CortexAgent is a production-grade
agentic RAG platform for SEC 10-K
financial research.

It uses four specialized LLM agents:
Researcher,
Analyst,
Writer,
and Critic,
orchestrated with LangGraph and a
revision loop.

The system is grounded in a
932-chunk corpus built from the 2024
10-K filings of Apple,
Microsoft,
Alphabet,
JPMorgan,
and Tesla.

On the model side,
it uses a cascading fallback chain
across Gemini,
Groq,
and Claude.

On the quality side,
every pull request can be measured by
RAGAS,
and a 20-prompt red-team suite checks
that the system refuses adversarial
inputs.

I built it end to end in three days
as a demonstration that modern AI
engineering is as much about eval,
safety,
and cost control as it is about model
selection.

## 2. Technical Stack Summary

The core stack is LangGraph for
orchestration,
ChromaDB plus BM25 plus a
BGE reranker for retrieval,
FastAPI for the backend,
Streamlit for the UI,
RAGAS for evaluation,
and GitHub Actions for CI/CD.

The models are routed through a
provider-agnostic client spanning
Gemini,
Groq,
and Claude.

The project runs on Python 3.11 with
modern packaging and reproducible
local environment management.

## 3. The Five Interview Stories

### Story 1: Cascading Multi-Provider LLM Resilience

I did not want the system tied to one
provider because real demos fail when
quota or rate limits show up.

So I built a shared LLM client with a
fallback chain.

If Gemini fails for retryable reasons
such as quota or rate limiting,
the call can fall to Groq,
and then to Claude as the quality
floor.

The important part is that fallback
is not hidden.

The normalized response object carries
a `fallback_used` flag,
and the API-side cost tracker records
the actual model that served the
request.

That means resiliency is observable,
not just implied.

### Story 2: RAGAS Iteration and Goodhart's Law

The early RAGAS baseline was not
strong enough,
especially on faithfulness and answer
correctness.

I improved retrieval with
section-aware chunking,
ticker-aware filtering,
and a cross-encoder reranker.

That produced the v3 baseline:
faithfulness `0.426`,
answer_relevancy `0.222`,
context_precision `0.283`,
answer_correctness `0.245`.

Then I tried a surgical v4 tweak to
recover answer relevancy by changing
Writer length and context usage.

Answer relevancy did improve,
but faithfulness and context
precision collapsed.

That was a concrete lesson in
Goodhart’s Law:
if you optimize one correlated metric
too directly,
you can damage the underlying system.

The correct engineering choice was to
revert to v3 and document the tradeoff
openly.

### Story 3: Test the Right Layer at the Right Cost

My first red-team design ran the full
orchestrator on every adversarial
prompt.

It was conceptually pure but
operationally terrible:
around `$0.50` and roughly ten
minutes per prompt.

That would have made the 20-prompt
suite cost about `$10`
and take three hours.

I realized the thing I actually
needed to test was the behavioral
contract encoded in the system prompt.

So I refactored the suite to call the
LLM directly,
then judge the response with another
LLM.

That cut cost to about `$0.02` per
prompt and turned the suite into
something I could actually run during
development.

### Story 4: Cost-Aware Production Engineering

Multi-agent systems get expensive
fast.

If every role uses a premium model,
one query can burn through ten or
more costly calls.

So I assigned cheaper models to
high-volume structured tasks and kept
premium reasoning models for the
judgment-critical path.

Researcher and Analyst can live on
Gemini Flash Lite,
the Writer can target Claude Haiku,
and the Critic plus RAGAS judge can
use Claude Sonnet.

I also installed an API-side cost
tracker so the system exposes live
spend through `/cost`
and the Streamlit dashboard.

### Story 5: Quality Gates as Engineering Discipline

One of the main reasons GenAI pilots
fail is that teams evaluate outputs by
demo feel instead of treating quality
as a release criterion.

I wanted CortexAgent to make the
opposite statement.

So I wired in a RAGAS-gated GitHub
Actions workflow.

The thresholds are calibrated to the
current shipped baseline,
so the gate is useful as a real
non-regression mechanism today and
can be tightened as the benchmark
improves.

The right engineering posture is not
"pretend the model is ready."

It is
"measure it,
show the deficit,
and stop regressions from slipping
through."

## 4. Likely Follow-Up Questions and Answers

### Q1

**Q:** Why LangGraph over AutoGen?

**A:** CortexAgent is a state machine
with explicit revision routing,
not an open-ended multi-agent chat.

LangGraph makes typed state,
conditional edges,
and per-thread persistence much
cleaner.

### Q2

**Q:** What would you do with a
bigger budget?

**A:** I would prioritize the five
layers in the future-work plan:
durable audit persistence,
distributed tracing,
semantic caching,
corpus expansion,
and a larger calibrated evaluation
suite.

### Q3

**Q:** How do you handle
hallucinations?

**A:** At three levels:
better retrieval,
Self-RAG grading before writing,
and a Critic agent that can reject a
draft and force another pass before
the user sees it.

### Q4

**Q:** Why not just use GPT-4 or
Sonnet for everything?

**A:** Because multi-agent graphs
multiply calls.

Routing every role to a premium model
would destroy unit economics without
improving every step equally.

### Q5

**Q:** How do you prevent prompt
injection?

**A:** I encode the behavioral
contract explicitly in the system
prompt and then test it directly with
a 20-prompt red-team suite that
includes injection,
jailbreak,
PII,
and citation-faking cases.

### Q6

**Q:** How does CI catch regressions
in a non-deterministic system?

**A:** By using fixed evaluation
artifacts,
a stable golden dataset,
and threshold-based gating on RAGAS
aggregate metrics rather than trying
to assert exact string matches.

### Q7

**Q:** What was the hardest bug?

**A:** The most important design bug
was realizing my first red-team
architecture was testing the wrong
layer.

It was accurate in principle but
useless in practice because it was too
expensive and too slow.

### Q8

**Q:** What is still missing for
production?

**A:** Durable PostgreSQL-backed audit
logging,
distributed tracing,
semantic caching,
a larger corpus,
and a broader adversarial evaluation
set.

### Q9

**Q:** Would you do anything
differently?

**A:** I would recognize Goodhart’s
Law earlier and stop chasing local
RAGAS improvements once the metric
tradeoffs became obvious.

### Q10

**Q:** What surprised you most?

**A:** How much of production AI
engineering is infrastructure:
eval,
safety,
cost,
state management,
and observability,
rather than just choosing a stronger
model.

## 5. Demo Script

Start on the hero panel and say:

"This is CortexAgent.
It is not just a chat UI over a
vector store.
It is a four-agent LangGraph system
for SEC 10-K research,
with a retrieval stack tuned to
financial filings and a quality gate
behind the scenes."

Then point at the sidebar and say:

"The API is live,
the current corpus contains
932 indexed chunks across Apple,
Microsoft,
Alphabet,
JPMorgan,
and Tesla,
and the cost tracker is updating off
real model calls rather than mock
numbers."

Then point at the query console and
say:

"When I run a question,
the Researcher first performs hybrid
retrieval using BM25,
dense vectors,
RRF fusion,
and a cross-encoder reranker.
That evidence goes to the Analyst for
structured extraction,
then to the Writer for the final
report,
and finally to the Critic,
which decides whether the answer is
good enough or whether it needs a
revision loop."

Then move to the report tab and say:

"The report is citation-grounded.
The system is designed so every
material claim can be traced back to
a chunk from the filing."

Then move to the citations tab and
say:

"These are the actual evidence chunks
returned by retrieval.
Because the chunk IDs encode ticker,
year,
and filing section,
debugging and source verification are
much easier."

Then move to the audit tab and say:

"This is the internal execution trace.
Every node logs latency,
model,
and a compact summary of what it did.
That is important because one of the
main differences between a demo and a
real product is observability."

Then close with:

"Behind the demo,
I also wired in a RAGAS evaluation
pipeline and a 20-prompt red-team
suite.
So the project is not only about
getting answers.
It is about showing what disciplined
AI engineering looks like when
quality,
safety,
and cost are treated as first-class
system concerns."
