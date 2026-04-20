# ADR-002: Hybrid Retrieval (BM25 + Dense + Reranker) over Single-Method

**Status:** Accepted

**Date:** 2026-04-18

**Deciders:** Yashwanth

## Context

Financial filings are hostile to
single-method retrieval.

The same query can depend on exact
term matches,
semantic similarity,
and section context at the same time.

If a user asks about
Microsoft’s cloud business,
the filing may say
`Microsoft Cloud revenue`,
`Azure and other cloud services`,
or `commercial cloud`.

If a user asks about JPMorgan’s
credit loss reserves,
literal phrases and precise table
terminology matter.

If a user asks for Apple’s risk
factors,
section structure matters as much as
keywords.

That means there are at least three
distinct retrieval problems:

1. exact lexical retrieval
2. semantic paraphrase retrieval
3. top-k precision among near-miss
   candidates

A pure BM25 solution is strong on
literal phrases and weak on semantic
equivalence.

A pure dense vector solution handles
semantic similarity better but can
miss exact-match financial language,
item labels,
and table-oriented phrasing.

A system that stops after either of
those stages also leaves precision on
the table,
because top candidates are often all
"kind of relevant" while only a few
are directly answering the user’s
question.

## Decision

Use hybrid retrieval:
BM25 sparse retrieval,
`all-MiniLM-L6-v2` dense retrieval in
ChromaDB,
Reciprocal Rank Fusion,
and a
`BAAI/bge-reranker-v2-m3`
cross-encoder reranker.

## Rationale

The first reason is complementarity.

BM25 and dense retrieval fail in
different ways.

That is exactly when combining them
makes sense.

BM25 excels at literal phrase matches,
financial jargon,
section references,
and numerical anchors.

It is especially useful when the
query contains terms that should map
very directly to the filing text.

Dense retrieval is better when the
user’s wording is conceptually close
but lexically different.

It captures paraphrase and semantic
similarity in a way BM25 cannot.

The second reason is engineering
economics.

This corpus is small enough that
running both retrieval branches in
parallel is cheap and operationally
simple.

There is no need for an exotic
distributed search architecture to
gain the benefit.

The project can simply use a
`ThreadPoolExecutor`
and merge the results.

The third reason is that fusion is
safer than trusting either branch as
the "real" answer.

Reciprocal Rank Fusion works well
because it rewards agreement between
retrievers without overfitting to
their raw score scales,
which are not directly comparable.

RRF is also easy to explain.

That matters in a system intended to
serve as a hiring artifact.

The fourth reason is precision.

Even after fusion,
the user still only wants the best
few chunks.

That is where the reranker matters.

The cross-encoder sees the query and
candidate together,
which gives a much richer relevance
signal than either BM25 scoring or
embedding similarity alone.

On a filing corpus,
that distinction is critical because
many chunks in the same section can
look superficially relevant.

The reranker helps answer the real
question:
which evidence is most worth showing
the Researcher right now?

The fifth reason is observed
evaluation improvement.

The v3 retrieval baseline,
which includes section-aware chunking,
ticker filtering,
and reranking,
improved faithfulness and answer
correctness materially over the
earlier baseline.

That does not prove optimality,
but it is enough evidence to justify
this stack as the project’s canonical
retrieval path.

## Alternatives Considered

### BM25 Only

Rejected because it is too brittle on
paraphrase and semantic drift.

Strong for exact terms,
weak for generalized financial
questions.

### Dense Only

Rejected because it can miss literal
phrases and exact-match financial
language that are disproportionately
important in 10-K workflows.

### ColBERT or Other Late Interaction

Promising in principle,
but more operationally complex than
needed for the current corpus and
hardware profile.

### HyDE

Considered conceptually,
but not prioritized because the
project already had larger gains
available from better chunking,
fusion,
and reranking.

### Larger Dense Model Only

Possible,
but higher compute cost with no
guarantee it would recover the exact
lexical precision of BM25.

## Consequences

### Positive

The system captures both exact-match
and semantic signals,
improves top-k precision,
and performs better on structured
financial documents than single-method
retrieval.

### Negative

The stack is more complex than one
vector store lookup.

There are more moving parts to debug:
BM25 corpus state,
fusion behavior,
reranker latency,
and ticker filtering.

### Neutral

The retrieval architecture remains
modular.

Any individual stage can be swapped
later if a better reranker,
vector store,
or embedding model is adopted.
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























