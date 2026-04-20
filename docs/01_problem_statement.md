# CortexAgent Problem Statement

## 1. The Problem

Financial research is still full of
manual extraction work.

That is especially true for the
SEC 10-K,
which is the single most useful
public source of company truth
and simultaneously one of the
most operationally painful
documents to use.

For a working analyst,
the hard part is rarely getting
access to data.

The hard part is turning a
200-400 page filing into a
defensible answer quickly enough
to matter.

Analysts routinely spend
40-60% of their research time
pulling out the same classes of
facts:
revenue drivers,
risk factors,
segment definitions,
capital allocation language,
management commentary,
and footnote-level caveats that
change the interpretation of
headline numbers.

The filing is long,
repetitive,
and structurally dense.

Key information is scattered across
more than twenty meaningful zones:
Item 1 Business,
Item 1A Risk Factors,
Item 7 MD&A,
Item 7A market risk,
Item 8 financial statements,
governance disclosures,
and multiple tables that only make
sense when read together.

Most generic LLM tools do not solve
this problem.

They compress it.

The common failure mode is not that
the model says something obviously
crazy.

The common failure mode is that the
model returns something plausible,
slightly paraphrased,
and numerically wrong.

That is unacceptable in finance.

If a system invents a revenue figure,
misstates a segment structure,
or cites the wrong risk factor,
the user cannot treat the output as
research.

They have to treat it as an
unverified draft,
which means the time savings
collapse.

Existing "AI for finance" products
generally fall into two categories.

The first category is open and cheap,
but weakly grounded.

These systems summarize filings with
shallow retrieval,
poor chunking,
and little or no evaluation
infrastructure.

The result is fast output with
fragile trust.

The second category is proprietary,
expensive,
and operationally opaque.

These products may be good,
but they are closed,
hard to inspect,
and difficult to use as a learning
artifact for engineers who want to
understand how production-grade
agentic RAG should be built.

That gap matters because the ground
truth itself is not proprietary.

SEC EDGAR is public,
free,
and relatively structured.

The bottleneck is engineering
discipline:
retrieval quality,
citation integrity,
safety behavior,
observability,
and cost control.

There is still no widely shared,
open-source,
production-grade agentic research
tool that combines those concerns
into one coherent system.

CortexAgent exists to fill that gap.

It treats financial research as a
grounded systems problem rather than
a prompt engineering demo.

It uses four specialized agents on
LangGraph,
a retrieval stack tuned to filing
structure,
RAGAS evaluation artifacts,
and a red-team suite that tests the
behavioral contract directly.

The goal is not just to answer
questions about filings.

The goal is to show what credible AI
engineering looks like when accuracy,
safety,
latency,
and cost all matter at once.

## 2. Who Feels This Pain

Equity research analysts at
investment banks feel this pain
most directly.

They need fast extraction of
verifiable facts from 10-Ks,
especially around earnings cycles,
sector updates,
and management guidance changes.

A system that saves even
thirty minutes per filing becomes
material across dozens of companies.

Fintech startups and internal product
teams feel it too.

Pre-IPO research,
credit underwriting workflows,
company dashboards,
and benchmark tools all need
reliable filing intelligence.

Those teams often cannot afford
Bloomberg-grade workflow tooling,
yet they still need output that can
survive scrutiny.

Financial journalists use the same
documents under deadline pressure.

They need to answer concrete
questions quickly:
What changed in risk language?
What business unit is growing?
What did management say about AI,
credit quality,
or regulatory exposure?

Retail investors and independent
researchers feel the pain from the
opposite side.

They technically have access to the
same public filings as professionals,
but not the time,
experience,
or retrieval tooling to navigate
them efficiently.

Academic finance researchers also
benefit from grounded extraction.

They often need repeatable access to
section-specific disclosures across
many firms and years.

An open system with explicit
architecture is more useful to them
than a black-box answer engine.

## 3. Why This Is Hard

Financial-document RAG is hard for
reasons that do not show up in toy
benchmarks.

The first problem is retrieval
quality.

Most naive chunking pipelines split
documents at fixed boundaries with no
respect for filing structure.

That is lethal in 10-Ks.

If Item 1A Risk Factors is split
mid-paragraph,
the retriever may return a fragment
that contains the right keywords but
not the surrounding logic.

The model then sees enough lexical
signal to sound confident,
but not enough context to be right.

The second problem is vocabulary.

Financial language is full of
near-synonyms that matter at query
time.

A user might ask about
"operating margin,"
"profitability,"
"cloud economics,"
or "credit loss reserves,"
while the filing phrases the same
idea differently.

Sparse retrieval alone misses
semantic matches.

Dense retrieval alone can miss exact
financial phrases,
item names,
or company-specific terms that must
match precisely.

The third problem is hallucination
risk.

General-purpose LLMs often fill gaps
with plausible business knowledge.

In casual chat that is annoying.

In finance it is a liability.

If a system invents a segment number,
pretends a risk disclosure exists,
or fabricates a citation,
the output is not "mostly useful."

It is operationally unsafe.

The fourth problem is citation
integrity.

A production research tool cannot
just say "according to the filing."

Every material claim needs a trace
back to a specific chunk,
which ideally encodes company,
year,
section,
and position.

Without that,
users cannot audit the answer,
and engineers cannot debug failures.

The fifth problem is economics.

Multi-agent systems multiply LLM
calls.

A four-agent flow with up to two
revisions can easily push past
ten model invocations for one user
question.

If every call hits a premium model,
unit economics break quickly.

The sixth problem is adversarial
behavior.

Users will try to jailbreak the
system,
extract hidden instructions,
invent citations,
or coerce financial advice.

A filing research tool must refuse
unsafe requests without becoming
useless for legitimate analysis.

Building that balance requires
evaluation and red-team discipline,
not just better prompting.

## 4. Our Approach

CortexAgent addresses the problem by
decomposing research into specialized
roles.

The Researcher retrieves and grades
evidence.

The Analyst converts evidence into
structured findings.

The Writer turns those findings into
a user-facing report with citations.

The Critic scores the result and can
send the system back for revision.

That structure separates concerns
cleanly.

Retrieval is optimized as retrieval.

Writing is optimized as writing.

Critique is optimized as a distinct
judgment task.

On the data side,
the system uses section-aware
chunking over real 2024 SEC filings
for AAPL,
MSFT,
GOOGL,
JPM,
and TSLA,
yielding 932 indexed chunks.

On the retrieval side,
it combines BM25,
dense embeddings with
`all-MiniLM-L6-v2`,
Reciprocal Rank Fusion,
and a
`BAAI/bge-reranker-v2-m3`
cross-encoder.

On the model side,
it uses a
three-provider cascade:
Gemini 2.5 Flash Lite,
Groq Llama 3.3 70B,
and Claude Sonnet 4.5 or
Haiku 4.5 depending on the role.

On the quality side,
every change can be evaluated with
RAGAS,
and the red-team suite verifies that
the system refuses unsafe prompts.

The result is not a claim that the
project is "solved."

The result is a concrete,
inspectable baseline for what
production-oriented AI engineering
looks like in a high-trust domain.
