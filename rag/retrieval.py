"""Hybrid retrieval: ChromaDB dense + BM25 keyword + Reciprocal Rank Fusion."""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from config.settings import settings


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)

RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
KNOWN_TICKERS = {
    "AAPL": ["apple", "aapl", "iphone", "ipad", "mac", "tim cook"],
    "MSFT": ["microsoft", "msft", "azure", "windows", "satya nadella", "copilot"],
    "GOOGL": ["google", "alphabet", "googl", "youtube", "android", "sundar pichai"],
    "JPM": ["jpmorgan", "jp morgan", "jpm", "chase", "jamie dimon"],
    "TSLA": ["tesla", "tsla", "elon musk", "autopilot", "robotaxi", "cybertruck"],
}


def _tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric terms for BM25."""
    return re.findall(r"\b[a-z0-9]+\b", text.lower())


def _preview(text: str, limit: int = 120) -> str:
    """Create a compact one-line preview for terminal output."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[:limit]}..."


def _ticker_year(metadata: Dict[str, Any]) -> str:
    """Format ticker and year metadata into a compact label."""
    ticker = metadata.get("ticker", "?")
    year = metadata.get("year", "?")
    return f"{ticker}_{year}"


def _rank_display(rank: Any) -> str:
    """Format optional rank values for display."""
    return str(rank) if rank is not None else "-"


def _score_display(score: Any) -> str:
    """Format optional floating point scores for display."""
    if score is None:
        return "-"
    return f"{float(score):.3f}"


def _detect_ticker_from_query(query: str) -> Optional[str]:
    """
    Return the single clearly-mentioned ticker in a query, else None.

    If multiple tickers match, no filter is applied.
    """
    lowered = query.lower()
    hits = set()
    for ticker, keywords in KNOWN_TICKERS.items():
        for keyword in keywords:
            if keyword in lowered:
                hits.add(ticker)
                break
    if len(hits) == 1:
        return hits.pop()
    return None


def _result_row(
    rank: int,
    result: Dict[str, Any],
) -> Tuple[str, str, str, str, str, str, str, str]:
    """Convert a retrieval result into fixed-width table cells."""
    metadata = result["metadata"]
    return (
        f"{rank}",
        _ticker_year(metadata),
        str(metadata.get("chunk_index", "-")),
        _rank_display(result.get("dense_rank")),
        _rank_display(result.get("bm25_rank")),
        f"{result.get('rrf_score', 0.0):.4f}",
        _score_display(result.get("reranker_score")),
        _preview(result["text"]),
    )


class HybridRetriever:
    """Combines ChromaDB dense retrieval with in-memory BM25, fused via RRF."""

    def __init__(
        self,
        collection_name: str = "sec_10k",
        k_dense: int = 10,
        k_bm25: int = 10,
        k_final: int = 5,
        rrf_k: int = 60,
    ) -> None:
        """Initialize the dense store and build an in-memory BM25 index."""
        self.collection_name = collection_name
        self.k_dense = k_dense
        self.k_bm25 = k_bm25
        self.k_final = k_final
        self.rrf_k = rrf_k
        self.use_reranker = True
        self._reranker: Optional[CrossEncoder] = None

        self.client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self.embedding_function = SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
        try:
            self.collection = self.client.get_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
            )
        except Exception as exc:
            raise RuntimeError(
                f"ChromaDB collection '{self.collection_name}' not found. "
                "Run `python -m rag.ingestion` first."
            ) from exc

        collection_data = self.collection.get(include=["documents", "metadatas"])
        self._chunk_ids: List[str] = list(collection_data.get("ids") or [])
        self._chunk_texts: List[str] = [
            document if isinstance(document, str) else ""
            for document in (collection_data.get("documents") or [])
        ]
        self._chunk_metas: List[Dict[str, Any]] = [
            metadata if isinstance(metadata, dict) else {}
            for metadata in (collection_data.get("metadatas") or [])
        ]

        if not self._chunk_ids:
            raise RuntimeError(
                f"ChromaDB collection '{self.collection_name}' is empty. "
                "Run `python -m rag.ingestion` first."
            )

        tokenized_texts = [_tokenize(text) for text in self._chunk_texts]
        self._bm25 = BM25Okapi(tokenized_texts)
        LOGGER.info(
            "[OK] HybridRetriever initialized: %s chunks, dense+BM25 ready",
            len(self._chunk_ids),
        )

    def _get_reranker(self) -> CrossEncoder:
        """Load the local cross-encoder reranker on first use."""
        if self._reranker is None:
            LOGGER.info("Loading cross-encoder reranker: %s", RERANKER_MODEL)
            self._reranker = CrossEncoder(RERANKER_MODEL, max_length=512)
        return self._reranker

    def dense_search(
        self,
        query: str,
        k: int,
        detected_ticker: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve top-k semantically similar chunks from ChromaDB."""
        if not query.strip():
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=k,
            include=["documents", "metadatas", "distances"],
            where={"ticker": detected_ticker} if detected_ticker else None,
        )

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        dense_hits: List[Dict[str, Any]] = []
        for rank, (doc_id, text, metadata, distance) in enumerate(
            zip(ids, documents, metadatas, distances),
            start=1,
        ):
            dense_hits.append(
                {
                    "id": doc_id,
                    "text": text,
                    "metadata": metadata or {},
                    "score": 1 - distance,
                    "rank": rank,
                }
            )
        return dense_hits

    def bm25_search(
        self,
        query: str,
        k: int,
        detected_ticker: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve top-k lexical matches from the in-memory BM25 index."""
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)
        candidate_indices = list(range(len(scores)))
        if detected_ticker:
            candidate_indices = [
                index
                for index in candidate_indices
                if (self._chunk_metas[index] or {}).get("ticker") == detected_ticker
            ]
        top_indices = sorted(
            candidate_indices,
            key=lambda index: scores[index],
            reverse=True,
        )[:k]

        bm25_hits: List[Dict[str, Any]] = []
        for rank, index in enumerate(top_indices, start=1):
            bm25_hits.append(
                {
                    "id": self._chunk_ids[index],
                    "text": self._chunk_texts[index],
                    "metadata": self._chunk_metas[index],
                    "score": float(scores[index]),
                    "rank": rank,
                }
            )
        return bm25_hits

    def reciprocal_rank_fusion(
        self,
        dense_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Fuse dense and BM25 result lists using Reciprocal Rank Fusion."""
        fused: Dict[str, Dict[str, Any]] = {}

        for result in dense_results:
            doc_id = result["id"]
            fused.setdefault(
                doc_id,
                {
                    "id": doc_id,
                    "text": result["text"],
                    "metadata": result["metadata"],
                    "rrf_score": 0.0,
                    "dense_rank": None,
                    "bm25_rank": None,
                },
            )
            fused[doc_id]["rrf_score"] += 1 / (self.rrf_k + result["rank"])
            fused[doc_id]["dense_rank"] = result["rank"]

        for result in bm25_results:
            doc_id = result["id"]
            fused.setdefault(
                doc_id,
                {
                    "id": doc_id,
                    "text": result["text"],
                    "metadata": result["metadata"],
                    "rrf_score": 0.0,
                    "dense_rank": None,
                    "bm25_rank": None,
                },
            )
            fused[doc_id]["rrf_score"] += 1 / (self.rrf_k + result["rank"])
            fused[doc_id]["bm25_rank"] = result["rank"]

        return sorted(fused.values(), key=lambda item: item["rrf_score"], reverse=True)

    def retrieve(self, query: str, ticker_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Run dense and BM25 retrieval in parallel and return fused top-k results."""
        try:
            detected_ticker = ticker_filter or _detect_ticker_from_query(query)
            if detected_ticker:
                LOGGER.info("Ticker filter applied: %s", detected_ticker)

            with ThreadPoolExecutor(max_workers=2) as executor:
                dense_future = executor.submit(
                    self.dense_search,
                    query,
                    self.k_dense,
                    detected_ticker,
                )
                bm25_future = executor.submit(
                    self.bm25_search,
                    query,
                    self.k_bm25,
                    detected_ticker,
                )
                dense_results = dense_future.result()
                bm25_results = bm25_future.result()
            fused_results = self.reciprocal_rank_fusion(dense_results, bm25_results)

            if detected_ticker:
                filtered = [
                    candidate
                    for candidate in fused_results
                    if (candidate.get("metadata") or {}).get("ticker") == detected_ticker
                ]
                if len(filtered) >= 3:
                    fused_results = filtered

            if self.use_reranker and len(fused_results) > self.k_final:
                candidates = fused_results[:20]
                reranker = self._get_reranker()
                pairs = [(query, candidate.get("text", "")[:512]) for candidate in candidates]
                scores = reranker.predict(pairs, show_progress_bar=False)
                for candidate, score in zip(candidates, scores):
                    candidate["reranker_score"] = float(score)
                candidates.sort(key=lambda candidate: candidate["reranker_score"], reverse=True)
                return candidates[: self.k_final]

            return fused_results[: self.k_final]
        except Exception as exc:
            LOGGER.exception("Hybrid retrieval failed for query '%s': %s", query, exc)
            raise

    def explain(self, query: str) -> Dict[str, Any]:
        """Return dense-only, BM25-only, and fused results for debugging."""
        detected_ticker = _detect_ticker_from_query(query)
        dense_results = self.dense_search(query, self.k_dense, detected_ticker)
        bm25_results = self.bm25_search(query, self.k_bm25, detected_ticker)
        fused_results = self.reciprocal_rank_fusion(dense_results, bm25_results)
        if detected_ticker:
            filtered = [
                candidate
                for candidate in fused_results
                if (candidate.get("metadata") or {}).get("ticker") == detected_ticker
            ]
            if len(filtered) >= 3:
                fused_results = filtered
        if self.use_reranker and fused_results:
            candidates = fused_results[:20]
            reranker = self._get_reranker()
            scores = reranker.predict(
                [(query, candidate.get("text", "")[:512]) for candidate in candidates],
                show_progress_bar=False,
            )
            for candidate, score in zip(candidates, scores):
                candidate["reranker_score"] = float(score)
            fused_results = sorted(
                candidates,
                key=lambda candidate: candidate.get("reranker_score", 0.0),
                reverse=True,
            )
        return {
            "query": query,
            "dense_top": dense_results[: self.k_final],
            "bm25_top": bm25_results[: self.k_final],
            "fused_top": fused_results[: self.k_final],
        }


def _print_results_table(query: str, results: List[Dict[str, Any]]) -> None:
    """Render fused retrieval results as a terminal table."""
    print("=" * 60)
    print(f'Query: "{query}"')
    print("=" * 60)
    print(
        f"{'Rank':<4} | {'Ticker_Year':<11} | {'Idx':<5} | {'Dense':<5} | "
        f"{'BM25':<4} | {'RRF':<7} | {'Rerank':<6} | Preview"
    )
    print("-" * 60)
    for rank, result in enumerate(results, start=1):
        row = _result_row(rank, result)
        print(
            f"{row[0]:<4} | {row[1]:<11} | {row[2]:<5} | {row[3]:<5} | "
            f"{row[4]:<4} | {row[5]:<7} | {row[6]:<6} | {row[7]}"
        )
    print()


def _print_ranked_section(title: str, results: List[Dict[str, Any]]) -> None:
    """Render a compact ranked list for explain-mode comparisons."""
    print(f"{title}:")
    for rank, result in enumerate(results[:5], start=1):
        metadata = result["metadata"]
        print(
            f"  {rank}. {_ticker_year(metadata)} chunk {metadata.get('chunk_index', '-')}"
            f" — \"{_preview(result['text'], limit=90)}\""
        )
    print()


if __name__ == "__main__":
    from config.logging_setup import configure_logging
    from config.settings import settings

    configure_logging(settings.log_level)

    queries = [
        "What are Apple's primary revenue drivers in fiscal 2024?",
        "iPhone 15 Pro",
        "JPMorgan litigation and legal proceedings",
        "Tesla autonomous driving Robotaxi",
        "Tesla autonomous driving capabilities",
    ]

    print("=" * 60)
    print("CortexAgent — Hybrid Retrieval Demo")
    print("=" * 60)

    retriever = HybridRetriever()
    for query in queries:
        query_results = retriever.retrieve(query)
        _print_results_table(query, query_results)

    explanation = retriever.explain("iPhone 15 Pro")
    print("=" * 60)
    print('SIDE-BY-SIDE: "iPhone 15 Pro"')
    print("=" * 60)
    _print_ranked_section("DENSE-ONLY top 5", explanation["dense_top"])
    _print_ranked_section("BM25-ONLY top 5", explanation["bm25_top"])
    _print_ranked_section("RRF FUSED top 5", explanation["fused_top"])
