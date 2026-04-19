"""Web search tool using DuckDuckGo (free, no API key)."""

import logging
import sys
from typing import Any, Dict

from duckduckgo_search import DDGS


logger = logging.getLogger(__name__)


def _safe_for_console(value: str) -> str:
    """Best-effort sanitization for Windows console encodings like cp1252."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return value.encode(encoding, errors="replace").decode(encoding, errors="replace")


def web_search(query: str, num_results: int = 5) -> Dict[str, Any]:
    """
    Search the web via DuckDuckGo. Returns up to num_results items.

    Schema: {results: [{title, url, snippet}, ...], query: str, count: int}
    """
    num_results = min(max(int(num_results), 1), 10)
    results = []
    try:
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=num_results):
                results.append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("href") or result.get("url", ""),
                        "snippet": (result.get("body") or "")[:300],
                    }
                )
    except Exception as exc:
        logger.warning("DDG search failed: %s", exc)
        return {"results": [], "query": query, "count": 0, "error": str(exc)}
    return {"results": results, "query": query, "count": len(results)}


if __name__ == "__main__":
    print("=" * 60)
    print("Web Search Tool — Smoke Test")
    print("=" * 60)
    output = web_search("Anthropic Claude Sonnet release 2026", num_results=3)
    print(f"Query: {output['query']}")
    print(f"Count: {output['count']}")
    if output.get("error"):
        print(f"Error: {_safe_for_console(output['error'])}")
    for index, result in enumerate(output["results"], 1):
        print(f"\n[{index}] {_safe_for_console(result['title'])}")
        print(f"    URL: {_safe_for_console(result['url'])}")
        print(f"    Snippet: {_safe_for_console(result['snippet'][:150])}...")
