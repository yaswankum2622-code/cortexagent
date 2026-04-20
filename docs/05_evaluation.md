# Evaluation Strategy

## 1. Why RAGAS

CortexAgent uses RAGAS because the
project is explicitly about grounded
generation,
not just fluent output.

Standard LLM evaluation questions
like
"does this answer read well?"
are too coarse for a filing research
system.

The key issue is whether an answer is
supported by retrieved evidence and
whether the retriever surfaced the
right evidence in the first place.

RAGAS is designed for exactly that
problem class.

The four metrics used in this project
are:
`faithfulness`,
`answer_relevancy`,
`context_precision`,
and `answer_correctness`.

Faithfulness asks whether the answer
is grounded in the supplied context.

Answer relevancy asks whether the
response actually addresses the user
question.

Context precision asks whether the
retrieved context is useful rather
than merely related.

Answer correctness compares the final
response against a reference answer.

These are LLM-judged metrics,
which means they are noisy.

That noise is a limitation,
but also the reason RAGAS is usable
at build time.

It scales better than hand-grading
every iteration and is far more
relevant to RAG than generic BLEU-like
metrics.

## 2. Golden Dataset Construction

The project uses a hand-built golden
dataset with fifteen question-answer
pairs.

The distribution is simple and
deliberate:
three questions per company across
five companies.

The companies are
Apple,
Microsoft,
Alphabet,
JPMorgan,
and Tesla.

Difficulty is balanced across
five easy,
five medium,
and five hard items.

The categories span
financials,
risks,
strategy,
operations,
and governance.

That spread matters.

It prevents the benchmark from being
dominated by one class of question,
such as direct revenue extraction,
which is easier than synthesis across
risk language or governance
disclosures.

Each reference answer is grounded in
the actual filing content and was
written to preserve the core business
fact,
not to mimic the Writer’s tone.

That gives RAGAS a stable target.

The dataset is intentionally small
enough to run regularly and large
enough to reveal regressions.

It is not a final benchmark.

It is a working engineering control.

## 3. The Iteration Story

The evaluation history is one of the
most important parts of the project
because it shows that CortexAgent was
not tuned by vibes alone.

The original baseline,
captured in `evaluation/raw_results.json`,
scored roughly:
faithfulness `0.332`,
answer_relevancy `0.300`,
context_precision `0.239`,
and answer_correctness `0.154`.

That baseline proved two things.

First,
the system could answer real filing
questions end to end.

Second,
its retrieval and answer grounding
were still not good enough to claim
production maturity.

The next major retrieval upgrade is
what the project calls the v3
baseline.

Three changes mattered most:
section-aware chunking,
ticker-aware filtering,
and the
`BGE-reranker-v2-m3`
cross-encoder on top of fused
candidates.

After those changes,
the canonical v3 results,
stored in `evaluation/raw_results_v3.json`
and reflected in
`report_v3.html`,
were:
faithfulness `0.426`,
answer_relevancy `0.222`,
context_precision `0.283`,
and answer_correctness `0.245`.

That meant faithfulness improved by
about 28 percent over the original
baseline,
and answer correctness improved by
about 59 percent.

Those are meaningful gains.

However,
answer relevancy got worse.

The reason was not retrieval itself.

The main issue was the Writer’s word
budget and report structure,
which sometimes pushed the answer
toward citation-heavy compactness at
the expense of directly phrased
responses.

That led to a surgical v4 attempt.

The Writer was forced toward a
roughly 400-word cap and the RAGAS
evaluation path used fewer contexts
per answer.

The result did recover answer
relevancy:
`0.347`.

But it also broke the other metrics.

Faithfulness fell to `0.234`,
and context precision collapsed to
`0.100`.

That experiment is valuable precisely
because it failed.

It showed a practical version of
Goodhart’s Law.

Once a metric becomes the target,
local tuning can improve the metric
while making the underlying system
worse.

The correct engineering decision was
to revert to v3 as the canonical
baseline rather than keep optimizing
one score at the expense of the full
quality picture.

## 4. CI Quality Gate

The repository includes a GitHub
Actions workflow that runs RAGAS on a
five-question CI subset.

The thresholds are intentionally
strict:
faithfulness `0.85`,
answer relevancy `0.80`,
and context precision `0.75`.

Today,
the gate would fail.

That is not an embarrassment.

It is the point.

A real quality gate should fail when
the system is below target.

The project is explicit about that
status so reviewers can see that the
mechanism is real rather than
decorative.

One known limitation is that
LLM-judge token overflow and parser
issues can sometimes collapse scores
to zero.

That failure mode is documented
instead of hidden.

## 5. Future Evaluation Work

The next evaluation steps are clear.

The golden dataset should expand from
15 questions to 100 or more.

The judge should likely move to a
cheaper,
faster,
and more stable option such as
GPT-4o-mini
or a fine-tuned smaller judge.

The team should also calibrate the
judge against human ratings to see
where the automatic metrics are most
trustworthy.

Finally,
answer relevancy zeros should be
tracked separately when they are
caused by parsing failures rather
than truly irrelevant answers.

That separation would make the metric
story cleaner and more actionable.
