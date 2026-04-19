"""SEC 10-K download → chunk → local embed → ChromaDB index pipeline."""

import json
import logging
import os
import re
from html import unescape
from pathlib import Path
from typing import Dict, List

import chromadb
import edgar
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from tqdm import tqdm

from config.settings import settings


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)

edgar.set_identity(settings.sec_identity)


def _doc_key(ticker: str, year: int) -> str:
    """Build the stable document key used for filenames and chunk IDs."""
    return f"{ticker.upper()}_{year}"


def _load_json(path: Path) -> Dict[str, object]:
    """Load JSON data from disk."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _count_jsonl_lines(path: Path) -> int:
    """Count the number of JSONL records in a file."""
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _coerce_year(value: str) -> int:
    """Extract the filing year from a filing date-like value."""
    return int(str(value)[:4])


def _parse_doc_key_from_raw_file(raw_path: Path) -> Dict[str, object]:
    """Parse ticker and year from a raw SEC filing filename."""
    stem = raw_path.stem
    if not stem.endswith("_10K"):
        raise ValueError(f"Unexpected raw filing name: {raw_path.name}")
    parts = stem[:-4].split("_")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse ticker/year from {raw_path.name}")
    ticker = "_".join(parts[:-1]).upper()
    year = int(parts[-1])
    return {"ticker": ticker, "year": year}


def _metadata_path_for(ticker: str, year: int, raw_dir: Path) -> Path:
    """Build the metadata file path for a ticker/year pair."""
    return raw_dir / f"{_doc_key(ticker, year)}_metadata.json"


def _html_to_text(html_content: str) -> str:
    """Convert HTML content into plain text with light cleanup."""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_content)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_text_from_object(filing_object: object) -> str:
    """Try to recover readable text from an edgartools filing data object."""
    if filing_object is None:
        return ""

    for attr_name in ("markdown", "text"):
        value = getattr(filing_object, attr_name, None)
        if callable(value):
            try:
                value = value()
            except Exception as exc:
                LOGGER.debug("Failed %s() on filing object: %s", attr_name, exc)
                value = None
        if isinstance(value, str) and value.strip():
            return value.strip()

    get_section_text = getattr(filing_object, "get_section_text", None)
    if callable(get_section_text):
        section_names = [
            "Business",
            "Risk Factors",
            "Properties",
            "Legal Proceedings",
            "Management's Discussion and Analysis",
        ]
        sections: List[str] = []
        for section_name in section_names:
            try:
                section_text = get_section_text(section_name)
            except Exception as exc:
                LOGGER.debug(
                    "Failed to extract section '%s' from filing object: %s",
                    section_name,
                    exc,
                )
                continue
            if isinstance(section_text, str) and section_text.strip():
                sections.append(f"{section_name}\n{section_text.strip()}")
        if sections:
            return "\n\n".join(sections)

    return ""


def _extract_filing_text(filing: object) -> str:
    """Extract clean text from a filing using text, object, then HTML fallbacks."""
    try:
        text_content = filing.text()
        if isinstance(text_content, str) and text_content.strip():
            return text_content.strip()
    except Exception as exc:
        LOGGER.warning(
            "Primary text extraction failed for %s: %s",
            getattr(filing, "accession_number", "unknown"),
            exc,
        )

    try:
        filing_object = filing.obj()
        object_text = _extract_text_from_object(filing_object)
        if object_text:
            return object_text
    except Exception as exc:
        LOGGER.warning(
            "Object-based text extraction failed for %s: %s",
            getattr(filing, "accession_number", "unknown"),
            exc,
        )

    try:
        html_content = filing.html()
        if isinstance(html_content, str) and html_content.strip():
            converted = _html_to_text(html_content)
            if converted:
                return converted
    except Exception as exc:
        LOGGER.warning(
            "HTML fallback extraction failed for %s: %s",
            getattr(filing, "accession_number", "unknown"),
            exc,
        )

    return ""


def _load_chunk_records(jsonl_path: Path) -> List[Dict[str, object]]:
    """Load chunk records from a JSONL file."""
    records: List[Dict[str, object]] = []
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


SECTION_PATTERNS = [
    (r"(?i)\bItem\s+1\.\s+Business\b", "item_1_business"),
    (r"(?i)\bItem\s+1A\.\s+Risk\s+Factors\b", "item_1a_risk_factors"),
    (r"(?i)\bItem\s+1B\.\s+Unresolved\s+Staff\s+Comments\b", "item_1b_unresolved_comments"),
    (r"(?i)\bItem\s+2\.\s+Properties\b", "item_2_properties"),
    (r"(?i)\bItem\s+3\.\s+Legal\s+Proceedings\b", "item_3_legal"),
    (r"(?i)\bItem\s+5\.\s+Market\s+for", "item_5_market"),
    (r"(?i)\bItem\s+7\.\s+Management", "item_7_mda"),
    (r"(?i)\bItem\s+7A\.\s+Quantitative", "item_7a_market_risk"),
    (r"(?i)\bItem\s+8\.\s+Financial\s+Statements\b", "item_8_financials"),
    (r"(?i)\bItem\s+9\.\s+Changes", "item_9_changes"),
    (r"(?i)\bItem\s+9A\.\s+Controls", "item_9a_controls"),
    (r"(?i)\bItem\s+10\.\s+Directors", "item_10_directors"),
    (r"(?i)\bItem\s+11\.\s+Executive\s+Compensation\b", "item_11_compensation"),
]


def _split_into_sections(text: str) -> List[tuple[str, str]]:
    """
    Split 10-K text into (section_name, section_text) tuples based on Item headers.

    Returns list of (section_label, section_body). Unlabeled preamble goes under
    "front_matter".
    """
    if not text:
        return []

    matches: List[tuple[int, str]] = []
    for pattern, label in SECTION_PATTERNS:
        for match in re.finditer(pattern, text):
            matches.append((match.start(), label))

    matches.sort(key=lambda item: item[0])

    if not matches:
        return [("full_document", text)]

    sections: List[tuple[str, str]] = []
    if matches[0][0] > 0:
        preamble = text[: matches[0][0]].strip()
        if len(preamble) > 200:
            sections.append(("front_matter", preamble))

    label_counts: Dict[str, int] = {}
    for index, (start, label) in enumerate(matches):
        end = matches[index + 1][0] if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if len(body) > 100:
            label_counts[label] = label_counts.get(label, 0) + 1
            occurrence = label_counts[label]
            unique_label = label if occurrence == 1 else f"{label}_{occurrence:02d}"
            sections.append((unique_label, body))

    return sections


def download_10k_filings(
    tickers: List[str],
    years: List[int],
    output_dir: str = "data/raw",
) -> List[Path]:
    """Download SEC 10-K filings for the requested tickers and years."""
    raw_dir = Path(output_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    downloaded_files: List[Path] = []
    for ticker in tickers:
        normalized_ticker = ticker.upper()
        for year in years:
            doc_key = _doc_key(normalized_ticker, year)
            text_path = raw_dir / f"{doc_key}_10K.txt"
            metadata_path = _metadata_path_for(normalized_ticker, year, raw_dir)

            if text_path.exists() and text_path.stat().st_size > 0:
                LOGGER.info("[SKIP] %s already downloaded", doc_key)
                print(f"[SKIP] {doc_key} already downloaded")
                downloaded_files.append(text_path)
                continue

            try:
                company = edgar.Company(normalized_ticker)
                filings = company.get_filings(form="10-K")
                matches = [
                    filing
                    for filing in filings
                    if _coerce_year(getattr(filing, "filing_date", "")) == year
                ]
                if not matches:
                    LOGGER.warning("No 10-K filing found for %s in %s", normalized_ticker, year)
                    continue

                matches.sort(key=lambda filing: str(getattr(filing, "filing_date", "")), reverse=True)
                filing = matches[0]
                filing_text = _extract_filing_text(filing)
                if not filing_text:
                    raise ValueError(
                        f"No usable filing text returned for {normalized_ticker} {year}"
                    )

                text_path.write_text(filing_text, encoding="utf-8")

                metadata = {
                    "ticker": normalized_ticker,
                    "cik": getattr(company, "cik", getattr(filing, "cik", None)),
                    "filing_date": str(getattr(filing, "filing_date", "")),
                    "accession_number": getattr(filing, "accession_number", ""),
                    "fiscal_year_end": getattr(company, "fiscal_year_end", None),
                }
                metadata_path.write_text(
                    json.dumps(metadata, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

                size_mb = os.path.getsize(text_path) / (1024 * 1024)
                print(f"[OK] Downloaded {normalized_ticker} {year} 10-K ({size_mb:.1f} MB)")
                downloaded_files.append(text_path)
            except Exception as exc:
                LOGGER.exception(
                    "Failed to download 10-K for %s %s: %s",
                    normalized_ticker,
                    year,
                    exc,
                )
                continue

    return downloaded_files


def chunk_documents(
    raw_dir: str = "data/raw",
    processed_dir: str = "data/processed",
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> int:
    """Chunk downloaded filings into JSONL records ready for embedding."""
    raw_path = Path(raw_dir)
    processed_path = Path(processed_dir)
    processed_path.mkdir(parents=True, exist_ok=True)
    total_chunks = 0

    for text_file in sorted(raw_path.glob("*_10K.txt")):
        try:
            parsed = _parse_doc_key_from_raw_file(text_file)
            ticker = str(parsed["ticker"])
            year = int(parsed["year"])
            doc_key = _doc_key(ticker, year)
            chunks_path = processed_path / f"{doc_key}_chunks.jsonl"

            if chunks_path.exists() and chunks_path.stat().st_size > 0:
                existing_chunks = _count_jsonl_lines(chunks_path)
                total_chunks += existing_chunks
                LOGGER.info("[SKIP] %s already chunked", doc_key)
                print(f"[SKIP] {doc_key} already chunked")
                continue

            metadata_path = _metadata_path_for(ticker, year, raw_path)
            metadata: Dict[str, object] = {}
            if metadata_path.exists():
                metadata = _load_json(metadata_path)
            else:
                LOGGER.warning("Missing metadata for %s; using filename-derived fallback", doc_key)
                metadata = {
                    "ticker": ticker,
                    "filing_date": "",
                }

            text = text_file.read_text(encoding="utf-8")
            if not text.strip():
                LOGGER.warning("Skipping empty raw filing file %s", text_file.name)
                continue

            sections = _split_into_sections(text)
            LOGGER.info("[%s] Split into %s sections", doc_key, len(sections))

            section_chunk_count = 0
            splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

            with chunks_path.open("w", encoding="utf-8") as handle:
                for section_label, section_body in sections:
                    document = Document(text=section_body)
                    nodes = splitter.get_nodes_from_documents([document])
                    for node_index, node in enumerate(nodes):
                        chunk_record = {
                            "chunk_id": f"{doc_key}_{section_label}_{node_index:04d}",
                            "ticker": metadata.get("ticker", ticker),
                            "year": year,
                            "filing_date": metadata.get("filing_date", ""),
                            "source_file": str(text_file),
                            "section": section_label,
                            "chunk_index": node_index,
                            "text": node.text,
                        }
                        handle.write(json.dumps(chunk_record, ensure_ascii=False) + "\n")
                        section_chunk_count += 1

            total_chunks += section_chunk_count
            print(f"[OK] Chunked {doc_key} -> {section_chunk_count} chunks")
        except Exception as exc:
            LOGGER.exception("Failed to chunk %s: %s", text_file.name, exc)
            continue

    return total_chunks


def ingest_to_chromadb(
    processed_dir: str = "data/processed",
    collection_name: str = "sec_10k",
) -> int:
    """Embed processed chunks locally and persist them into ChromaDB."""
    try:
        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    except Exception as exc:
        LOGGER.exception("Failed to initialize ChromaDB persistent client: %s", exc)
        raise

    embed_fn = SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embed_fn,
    )

    existing_ids = set(collection.get()["ids"]) if collection.count() else set()
    processed_path = Path(processed_dir)

    for jsonl_file in sorted(processed_path.glob("*_chunks.jsonl")):
        doc_label = jsonl_file.stem.replace("_chunks", "")
        chunk_records = _load_chunk_records(jsonl_file)
        if not chunk_records:
            LOGGER.warning("Skipping empty chunk file %s", jsonl_file.name)
            continue

        new_chunks = [
            chunk for chunk in chunk_records if chunk["chunk_id"] not in existing_ids
        ]
        if not new_chunks:
            LOGGER.info("[SKIP] %s already indexed (%s chunks)", doc_label, len(chunk_records))
            print(f"[SKIP] {doc_label} already indexed ({len(chunk_records)} chunks)")
            continue

        progress = tqdm(
            total=len(new_chunks),
            desc=f"Indexing {doc_label}",
            unit="chunk",
        )
        for start in range(0, len(new_chunks), 100):
            batch = new_chunks[start : start + 100]
            batch_ids = [chunk["chunk_id"] for chunk in batch]
            batch_documents = [chunk["text"] for chunk in batch]
            batch_metadatas = [
                {
                    "ticker": chunk["ticker"],
                    "year": chunk["year"],
                    "filing_date": chunk["filing_date"],
                    "source_file": chunk["source_file"],
                    "section": chunk.get("section", "unknown"),
                    "chunk_index": chunk["chunk_index"],
                }
                for chunk in batch
            ]
            collection.upsert(
                ids=batch_ids,
                documents=batch_documents,
                metadatas=batch_metadatas,
            )
            existing_ids.update(batch_ids)
            progress.update(len(batch))
        progress.close()

    return collection.count()


def run_full_pipeline(tickers: List[str], years: List[int]) -> Dict[str, object]:
    """Run the full SEC 10-K ingestion pipeline end to end."""
    collection_name = "sec_10k"
    downloaded_paths = download_10k_filings(tickers=tickers, years=years)
    total_chunks = chunk_documents()
    indexed_chunks = ingest_to_chromadb(collection_name=collection_name)

    summary = {
        "downloaded_files": len(downloaded_paths),
        "total_chunks": total_chunks,
        "indexed_chunks": indexed_chunks,
        "embedding_model": settings.embedding_model,
        "collection_name": collection_name,
    }

    print("=" * 60)
    print("Pipeline complete.")
    print(f"  Downloaded files:    {summary['downloaded_files']}")
    print(f"  Total chunks:        {summary['total_chunks']}")
    print(f"  Indexed chunks:      {summary['indexed_chunks']}")
    print(f"  Embedding model:     {summary['embedding_model']} (local)")
    print(f"  Collection:          {summary['collection_name']}")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    from config.logging_setup import configure_logging
    from config.settings import settings

    configure_logging(settings.log_level)

    tickers = ["AAPL", "MSFT", "GOOGL", "JPM", "TSLA"]
    years = [2024]

    print("=" * 60)
    print("CortexAgent — SEC 10-K Ingestion Pipeline")
    print(f"Tickers: {tickers}")
    print(f"Years: {years}")
    print(f"Embedding model: {settings.embedding_model} (local)")
    print("=" * 60)

    result = run_full_pipeline(tickers=tickers, years=years)
    print(json.dumps(result, indent=2))
