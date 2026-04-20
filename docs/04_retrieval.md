# Retrieval System

## 1. The Retrieval Problem

Naive RAG performs badly on 10-Ks for
predictable reasons.

The documents are long,
hierarchical,
and semantically dense.

The same concept may be introduced in
management commentary,
qualified in risk factors,
and quantified in the financial
statements.

If a system chunks the filing at
blind token boundaries,
it frequently destroys exactly the
context that gives a paragraph its
meaning.

That is why generic chunk-and-embed
pipelines can look acceptable in
small demos and then fail on real
financial questions.

A retrieval hit that starts halfway
through an Item 1A paragraph may
contain the right keywords while
missing the key causal clause.

Likewise,
a question about profitability may be
expressed by the user as
"operating margin,"
"profit margin,"
"unit economics,"
or "EBIT-like profitability."

The filing may use different wording.

Sparse retrieval alone struggles with
the vocabulary gap.

Dense retrieval alone often misses
exact-match signals such as
`Form 10-K`,
`traffic acquisition costs`,
or a specific dollar figure.

The system therefore needs retrieval
that respects document structure and
captures both lexical precision and
semantic similarity.

## 2. Section-Aware Chunking

CortexAgent does not chunk the filing
as one undifferentiated text blob.

It first detects major SEC section
headers with regex patterns:
Item 1,
1A,
1B,
2,
3,
5,
7,
7A,
8,
9,
9A,
10,
and 11.

Each section is then chunked
independently using
LlamaIndex `SentenceSplitter`
with a target chunk size of
512 tokens and
50 tokens of overlap.

This preserves semantic boundaries
far better than fixed global
chunking.

The result is a chunk ID that carries
meaning.

For example:

`AAPL_2024_item_7_mda_02_0001`

This encodes ticker,
year,
section family,
local section occurrence,
and chunk index.

That structure is useful for both
retrieval debugging and user-facing
citations.

The current corpus contains
932 chunks across five companies,
an average of roughly
186 chunks per company.

That is small enough to iterate on
quickly,
but large enough to expose real
retrieval problems and benefits.

## 3. Hybrid Retrieval

The retrieval stack uses two first
stage retrievers in parallel.

The sparse branch is BM25.

BM25 is excellent at exact-match
finance terms,
section labels,
specific names,
and literal strings that a dense
embedding model may smooth away.

If a user asks for
`traffic acquisition costs`,
`allowance for credit losses`,
or a phrase that appears verbatim in
the filing,
BM25 is often the most reliable
signal.

The dense branch uses ChromaDB with
`all-MiniLM-L6-v2`
sentence-transformer embeddings.

This branch captures semantic
similarity.

It helps when the user’s wording does
not exactly match the filing’s
surface form,
such as
"cloud business growth"
versus
"Microsoft Cloud revenue."

The two result lists are combined via
Reciprocal Rank Fusion.

CortexAgent uses an
`rrf_k` value of 60,
which is a conventional choice that
prevents the highest-ranked result in
either branch from dominating too
aggressively.

Instead of trusting one method,
the system trusts agreement.

If both sparse and dense search rank
a chunk highly,
it rises.

If only one method likes it,
it still has a chance,
but a smaller one.

Dense and BM25 search run in
parallel using a
`ThreadPoolExecutor`.

That matters because the architecture
is not only about quality.

It is also about query-time latency.

Parallelizing the two retrievers
avoids paying the full sum of both
costs on the critical path.

## 4. Cross-Encoder Reranking

Hybrid retrieval improves recall,
but recall alone is not enough for a
high-trust answering system.

The user does not care whether the
correct evidence is somewhere in the
top twenty candidates.

The user cares whether the top five
pieces of evidence are the right
ones.

That is why CortexAgent adds a
cross-encoder reranker after RRF.

The model is
`BAAI/bge-reranker-v2-m3`.

It is loaded locally and runs on CPU,
roughly a
568 MB footprint in this project’s
setup.

The reranker sees the query-chunk
pair together under cross-attention,
which is far more precise than
comparing two independent vector
embeddings.

Operationally,
the pipeline works like this:
BM25 plus dense retrieval produce a
fused candidate set,
the top twenty candidates are kept,
the reranker scores each
`(query, chunk)` pair,
and then the top five chunks are
returned to the Researcher.

This stage is where many near-miss
results are filtered out.

It is especially valuable when the
corpus contains several chunks from
the same section that all look
plausible at a lexical level but only
one of them directly answers the
query.

## 5. Ticker Auto-Detection

Cross-company corpora create a simple
but damaging failure mode:
a query about JPMorgan retrieves an
Apple chunk because both mention
"risk factors."

To reduce that,
CortexAgent scans the query for known
company names,
tickers,
and high-signal aliases such as
`Tim Cook`,
`Azure`,
`YouTube`,
`Chase`,
or `Autopilot`.

If exactly one ticker is detected,
the dense retriever applies a Chroma
`where` filter and BM25 also filters
its candidate set to that ticker.

If multiple companies are detected,
the filter is disabled so true
cross-company questions still work.

This simple routing step meaningfully
improves precision on single-company
queries.

## 6. Query-Time Flow

At query time,
the system first checks whether the
user text implies a specific ticker.

It then launches dense search and
BM25 search concurrently.

Each branch returns ranked hits.

Those lists are fused with RRF into a
single candidate set.

If a ticker filter was detected,
the fused set is narrowed further
when enough in-company hits exist.

If reranking is enabled and there are
more than `k_final` candidates,
the top twenty go through the
cross-encoder.

The final top five chunks become the
Researcher’s evidence window.

That output is not yet considered
good enough by default.

It is passed into Self-RAG grading,
which can mark the retrieval as
sufficient,
partial,
or insufficient,
and can trigger query refinement.

The key design choice is that
retrieval is treated as an optimizable
subsystem with its own stages,
filters,
and evaluators,
not as a single vector similarity
lookup hidden behind an SDK call.
