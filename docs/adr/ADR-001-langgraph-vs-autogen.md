# ADR-001: LangGraph over AutoGen for Multi-Agent Orchestration

**Status:** Accepted

**Date:** 2026-04-18

**Deciders:** Yashwanth

## Context

CortexAgent needs a framework to
coordinate four specialized agents:
Researcher,
Analyst,
Writer,
and Critic.

The workflow is not a simple
conversation.

It has explicit stages,
typed state,
revision loops,
and a need for per-thread persistence
so audit trails and iterative
artifacts can survive across a single
request lifecycle.

The core question was therefore not
"which agent framework is most
popular?"

The question was:
which framework best matches a
structured state machine where each
node owns a well-defined piece of
work and the graph can branch based
on quality decisions?

The main candidates in this design
space were LangGraph,
AutoGen,
CrewAI,
and Pydantic AI.

AutoGen is strong when the primary
abstraction is conversation among
roles.

CrewAI is opinionated and approachable
for task-role flows.

Pydantic AI is compelling for typed
tooling and model interfaces.

But CortexAgent’s most important
requirements were:
explicit graph control,
clear typed state,
easy revision branching,
and inspectable node-level
observability.

## Decision

Use LangGraph as the orchestration
framework for the CortexAgent
multi-agent workflow.

## Rationale

The strongest reason to choose
LangGraph is that CortexAgent is
fundamentally a state machine.

The system does not need agents to
negotiate with each other through
open-ended chat.

It needs a deterministic sequence:
Researcher,
then Analyst,
then Writer,
then Critic,
with a conditional edge back to the
Researcher when the Critic decides the
draft is not good enough.

That structure maps directly onto
LangGraph’s model.

The graph nodes can own their slice of
state transformation,
and routing logic can remain explicit
and testable.

The second reason is typed state.

CortexAgent tracks more than raw
message history.

It tracks:
retrieved chunks,
retrieval grade,
retry history,
research notes,
structured findings,
draft report,
critique,
revision count,
revision focus,
and audit trail.

LangGraph makes that explicit through
`AgentState`.

That clarity is valuable both for
engineering and for documentation.

When a bug occurs,
the team can ask:
which field was malformed,
which node wrote it,
and which downstream node depended on
it?

That is far easier than debugging a
system where "state" is effectively a
conversation transcript plus some
implicit hidden memory.

The third reason is persistence.

LangGraph’s `MemorySaver`
checkpointer provides a simple
per-thread persistence mechanism that
fits the current project phase well.

It gives the graph a coherent notion
of thread identity without forcing a
full external state-store design on
day one.

For a system that already exposes
`thread_id`,
`/audit/{thread_id}`,
and streaming updates,
that is a strong fit.

The fourth reason is observability.

Each node in CortexAgent appends a
structured audit entry with model,
latency,
input summary,
and output summary.

LangGraph does not fight that design.

It supports node-level reasoning about
execution flow,
and its graph mental model aligns well
with how the project explains itself
to senior engineers and hiring
reviewers.

That matters.

A framework can be functionally
capable and still be the wrong choice
if it makes the resulting system hard
to understand.

The fifth reason is ecosystem
stability.

LangGraph is closely tied to the
LangChain ecosystem,
which means good interoperability with
model wrappers,
evaluation utilities,
and surrounding tooling already
present in the repo.

That is not a guarantee of perfect
stability,
but it reduces integration friction.

The final reason is conceptual
honesty.

CortexAgent wants to show a production
pattern,
not a roleplay.

The workflow is a graph with routing
and checkpoints.

LangGraph names that architecture
directly.

## Alternatives Considered

### AutoGen

AutoGen was a serious alternative
because it is widely associated with
multi-agent workflows.

Its strength is conversational role
play and emergent agent interaction.

That is also its weakness for this
project.

CortexAgent does not benefit much from
agents chatting freely with each
other.

That would obscure state transitions
that should remain explicit.

Structured revision control is simply
more awkward in a conversational
framework than in a graph-native one.

### CrewAI

CrewAI offers a friendlier,
more opinionated task-based surface.

That can be valuable for rapidly
scaffolding role flows.

The downside is reduced control over
the exact state schema and transition
logic.

For CortexAgent,
the ability to name every state field
and route based on precise Critic
output was more important than quick
ergonomics.

### Pydantic AI

Pydantic AI is attractive because it
leans hard into type safety and clear
interfaces.

That is philosophically aligned with
this project.

However,
its surrounding ecosystem for
graph-based agent orchestration is
still younger.

For CortexAgent,
the higher priority was mature graph
control rather than maximal
type-centric purity.

## Consequences

### Positive

The system gets explicit state
management,
clean revision routing,
easy future graph expansion,
and observability that matches the
product story.

### Negative

LangGraph documentation often assumes
some familiarity with LangChain
concepts.

That slightly raises the learning
curve for new contributors.

### Neutral

The choice increases the project’s
gravitational pull toward the
LangChain ecosystem.

That is acceptable for this phase,
but should remain a conscious tradeoff
rather than an accidental lock-in.
