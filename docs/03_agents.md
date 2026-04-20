# CortexAgent Agents

## Overview

CortexAgent is intentionally
multi-agent.

That is not a branding decision.

It is a control decision.

The system separates retrieval,
extraction,
writing,
and critique because those tasks have
different failure modes,
different cost profiles,
and different observability needs.

The four agents are:
Researcher,
Analyst,
Writer,
and Critic.

They run on LangGraph with a
revision loop and a typed shared
state.

The graph also carries a
`retrieval_grade`
from Self-RAG and a
`revision_count`
bounded by
`MAX_REVISIONS = 2`.

## Shared State Contract

The graph state is a `TypedDict`
called `AgentState`.

The fields most relevant to agent
contracts are:

- `query`
- `retrieved_chunks`
- `retrieval_grade`
- `retrieval_retry_history`
- `research_notes`
- `structured_findings`
- `draft_report`
- `critique`
- `revision_count`
- `revision_focus`
- `final_report`
- `audit_trail`
- `wall_latency_ms`

Each agent is expected to read only
the fields it needs and write only
the fields it owns.

That keeps the graph debuggable.

## 1. Researcher

### Role and Responsibility

The Researcher is responsible for
evidence acquisition,
evidence quality checking,
and first-pass synthesis.

It is the only agent that talks
directly to the hybrid retrieval
stack.

Its job is to turn a user query into
high-signal chunks,
grade whether those chunks are
actually sufficient,
and produce concise research notes
that the downstream agents can use.

This matters because the rest of the
system cannot compensate for poor
evidence.

If the Researcher returns the wrong
company,
a generic paragraph,
or a partial section fragment,
the Analyst will extract weak facts,
the Writer will sound fluent but thin,
and the Critic will spend cycles
judging a bad starting point.

### System Prompt Excerpt

```text
You are a financial research assistant specialized in SEC 10-K filings.
Given a user query and retrieved document chunks, write a concise 2-paragraph research summary
of what was found. Stay grounded in the chunks - do NOT add outside knowledge or speculation.
If the chunks don't contain enough info, say so explicitly.
```

### Model Assignment and Reasoning

The Researcher is a high-volume role.

It benefits from a cheap,
fast model with adequate grounding
ability more than from maximum prose
quality.

The intended routing is
Gemini 2.5 Flash Lite first,
with Groq Llama 3.3 70B and Claude
as fallback through the shared
cascade.

That is a good fit because the task
is bounded:
look at chunks,
summarize them,
stay grounded.

### Input and Output Contract

Inputs:
`query`,
optional `revision_focus`,
and the current `audit_trail`.

Outputs:
`retrieved_chunks`,
`retrieval_grade`,
`retrieval_retry_history`,
`research_notes`,
and one appended audit entry.

### Error Handling

The Researcher delegates retrieval
quality checking to `SelfRAGGrader`.

If the first retrieval is weak,
the grader can refine the query.

If no chunks are retrieved or JSON
grading fails,
the system still returns a structured
`insufficient` grade instead of
crashing.

### Observability Hooks

The Researcher logs:
agent name,
action,
timestamp,
latency,
model,
input query summary,
and the output summary in the form
`N chunks, grade=<decision>`.

## 2. Analyst

### Role and Responsibility

The Analyst converts free-form
retrieved evidence into a schema that
the Writer can reliably consume.

This is a compression step,
but unlike naive summarization,
it compresses into categories that
map cleanly to financial questions:
key facts,
numbers,
risks,
and opportunities.

That structure is important because
it limits the Writer’s creative
degrees of freedom.

The Writer should not decide what the
important numbers are from scratch.

The Analyst should decide first,
with citations attached.

### System Prompt Excerpt

```text
Return ONLY valid JSON with this exact schema:
{
  "key_facts": [{"fact": "string", "citation": "chunk_id"}],
  "numbers": [{"metric": "string", "value": "string", "context": "string", "citation": "chunk_id"}],
  "risks": [{"risk": "string", "severity": "low|medium|high", "citation": "chunk_id"}],
  "opportunities": [{"opportunity": "string", "citation": "chunk_id"}]
}
```

### Model Assignment and Reasoning

The Analyst is also a good fit for a
cheap structured-output model.

This role is primarily extraction,
not narrative generation.

Gemini 2.5 Flash Lite is the intended
front-line choice because JSON mode
and low temperature behavior matter
more than style.

### Input and Output Contract

Inputs:
`query`
and `retrieved_chunks`.

Output:
`structured_findings`,
plus an audit entry that records
counts for facts,
numbers,
risks,
and opportunities.

### Error Handling

If JSON parsing fails,
the Analyst does not hide the issue.

It emits empty arrays plus an
`_error` field containing the raw
failure prefix.

That lets the Writer degrade
gracefully instead of pretending the
analysis worked.

### Observability Hooks

The Analyst logs its model,
latency,
input chunk count,
and category counts in the output.

## 3. Writer

### Role and Responsibility

The Writer produces the artifact the
user actually sees.

Its job is to convert
`structured_findings`
into a readable Markdown report with
strict section order and inline
citations.

Unlike the Analyst,
the Writer must balance structure and
clarity.

It needs enough language quality to
sound like research,
but not so much freedom that it
hallucinates connective tissue.

### System Prompt Excerpt

```text
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
```

### Model Assignment and Reasoning

This is the first user-facing role,
so prose quality matters more.

The cost-engineered target is
Claude Haiku 4.5,
with Claude Sonnet 4.5 available as
fallback or evaluation-sensitive
floor.

That routing keeps the report clean
without spending Critic-grade budget
on every line of prose.

### Input and Output Contract

Inputs:
`query`,
`structured_findings`,
optional `critique`,
and `revision_count`.

Output:
`draft_report`
and an audit entry.

### Error Handling

If the Analyst emitted an `_error`,
the Writer prompt explicitly tells
the model to generate a one-paragraph
apology report rather than invent
facts.

In eval mode,
the Writer is also forced to be more
concise to reduce token pressure in
RAGAS scoring.

### Observability Hooks

The Writer logs:
model,
latency,
input summary keyed by finding
sections,
and the final character count.

## 4. Critic

### Role and Responsibility

The Critic is the internal quality
gate.

It inspects the draft against the
available chunk IDs and determines
whether the user should ever see the
current output.

This is what makes the workflow
agentic instead of sequential.

The Critic can reject the draft and
force another pass through retrieval
and writing.

### System Prompt Excerpt

```text
Evaluate the draft report on three dimensions (0-10 each):
- faithfulness
- completeness
- citation_quality

Then decide:
- "approve" if faithfulness >= 8 AND completeness >= 7 AND citation_quality >= 7
- "revise" otherwise
```

### Model Assignment and Reasoning

The Critic is the highest-leverage
reasoning role in the graph.

A weak Critic makes the whole system
look more accurate than it is.

That is why this role is assigned to
Claude Sonnet 4.5 rather than a
cheaper model.

The value of the Critic is not speed.

It is judgment fidelity.

### Input and Output Contract

Inputs:
`query`,
`draft_report`,
and `retrieved_chunks`.

Output:
`critique`
with
`faithfulness`,
`completeness`,
`citation_quality`,
`decision`,
`feedback`,
and `revision_focus`.

### Error Handling

If JSON parsing fails,
the Critic returns a defensive
default object.

The scores are set to zero,
the feedback contains the parse
failure,
and the graph still has a consistent
shape.

### Observability Hooks

The Critic logs the draft size,
model,
latency,
decision,
and the three score dimensions.

## Revision Loop Logic

After the Critic runs,
LangGraph calls `route_after_critic`.

If the decision is `approve`,
the graph goes directly to
`finalize`.

If the decision is `revise`,
the graph enters `prepare_revision`,
increments `revision_count`,
and stores `revision_focus`.

The Researcher then uses
`revision_focus` instead of the raw
query on the next pass.

That makes revisions concrete.

The system is not just "trying
again."

It is trying again with a better
information request.

## Why MAX_REVISIONS = 2

Two revisions is a pragmatic cap.

One revision is often enough to
recover from a weak retrieval or a
thin first draft.

More than two revisions tends to add
latency and cost faster than it adds
quality,
especially in a demo-scale corpus.

The cap also prevents a bad critique
or bad query from causing an
unbounded loop.

## How Self-RAG Interacts With the Flow

Self-RAG operates inside the
Researcher before the main graph
advances.

That means retrieval problems are
caught at the evidence layer,
not after the Writer has already
constructed a weak draft.

The Critic and Self-RAG therefore
operate at different altitudes.

Self-RAG asks:
"Did we retrieve the right evidence?"

The Critic asks:
"Given the evidence we have,
is the final report faithful and
complete enough to ship?"

That separation is one of the key
reasons CortexAgent behaves more like
a production system than a tutorial
chain.
