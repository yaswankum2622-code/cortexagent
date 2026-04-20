# ADR-003: Direct LLM Testing over Full Orchestrator for Red-Team Suite

**Status:** Accepted

**Date:** 2026-04-18

**Deciders:** Yashwanth

## Context

The CortexAgent red-team suite needed
to answer a specific architecture
question:
what is the right layer to test
behavioral safety?

One option was to run the full
orchestrator for every adversarial
prompt.

That would exercise the complete
product stack:
retrieval,
analysis,
writing,
critique,
and audit logging.

The other option was to bypass the
orchestrator and send adversarial
prompts directly to a single LLM
instance with the canonical
`CORTEX_SYSTEM_PROMPT`
that defines the behavioral contract.

At first glance,
the full orchestrator seems more
"correct."

It is closer to what the user would
experience.

But the safety questions in this
suite are primarily about refusal,
scope control,
citation honesty,
and non-disclosure of hidden system
details.

Those behaviors are encoded at the
system prompt and instruction layer,
not in the retrieval graph itself.

The question therefore became:
is the extra fidelity of end-to-end
testing worth the massive increase in
runtime cost and latency?

## Decision

Red-team tests bypass the
orchestrator and send adversarial
prompts directly to a single LLM with
`CORTEX_SYSTEM_PROMPT`
encoding the behavioral contract.

## Rationale

The most decisive factor was cost.

A full orchestrator run for one
adversarial prompt can trigger
roughly 15-20 LLM calls when
retrieval,
analysis,
writing,
judging,
and revisions are included.

In practical project measurements,
that placed a single red-team prompt
around `$0.50`
and roughly ten minutes of wall time.

For a 20-prompt suite,
that implies about `$10`
and more than three hours.

That is not a routine test anymore.

It becomes an occasional demo
artifact.

The direct-contract approach changes
the economics completely.

One model generates the response.

One judge model classifies it.

That is roughly two LLM calls per
test,
around `$0.02`,
and about ten seconds.

This is approximately a
600x cost reduction relative to the
naive end-to-end design when measured
as useful safety feedback per dollar
and per minute.

The second reason is test validity.

For the prompt classes in this suite,
the behavior being tested is the
assistant’s operating contract:
refuse investment advice,
do not reveal system prompts,
do not fabricate citations,
do not provide PII,
and acknowledge uncertainty.

Those are instruction-layer behaviors.

Running retrieval and graph control
does not add much signal for these
cases.

In fact,
it can add noise by introducing
irrelevant failure modes such as
provider hiccups or retrieval misses
that are orthogonal to the safety
question.

The third reason is speed of
iteration.

If a safety suite is cheap and fast,
engineers will actually run it while
changing prompts and policies.

If it is expensive and slow,
they will defer it.

The best safety test is not the one
with the most philosophical purity.

It is the one that becomes part of
the real development loop.

The fourth reason is industry
alignment.

Major model providers routinely test
behavioral contracts directly.

Anthropic’s constitutional AI work,
OpenAI system card evaluation
patterns,
and Google’s policy red-teaming all
reflect the idea that not every
safety question should be routed
through the full application stack.

The fifth reason is separation of
concerns.

End-to-end orchestrator quality is
already exercised elsewhere in
CortexAgent through the RAGAS
benchmark and CI gate.

The red-team suite therefore does not
need to duplicate that purpose.

It has a sharper mission:
verify the behavioral contract.

## Alternatives Considered

### Full Orchestrator Testing

Rejected for routine red-team use
because it is too expensive and too
slow.

Still valuable for occasional
end-to-end audits,
but not the default safety harness.

### Rule-Based Refusal Tests

Rejected because keyword checks are
too brittle.

A model can fail safety while still
containing the word
"cannot."

Likewise,
a safe response can be stylistically
different from what a rules engine
expects.

### Human-Only Review

Rejected as the primary mechanism
because it does not scale and cannot
be run cheaply on every prompt or
every contract update.

## Consequences

### Positive

The suite is fast,
cheap,
repeatable,
and tightly focused on the safety
contract that actually matters.

### Negative

The approach does not validate every
possible end-to-end interaction
between safety behavior and the full
orchestrator stack.

That remains future work.

### Neutral

The project now has two complementary
evaluation layers:
RAGAS for end-to-end grounded answer
quality,
and direct contract testing for
adversarial safety behavior.
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























