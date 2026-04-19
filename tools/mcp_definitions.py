"""MCP tool registry: schemas + handler dispatch for Researcher agent tool use."""

import json
import logging
from typing import Any, Callable, Dict, List

from tools.calendar_tool import calendar_book
from tools.database_tool import database_query
from tools.web_search_tool import web_search


logger = logging.getLogger(__name__)


TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "web_search",
        "description": (
            "Search the public web for recent information (e.g., news, analyst commentary, "
            "market events) that is NOT in our SEC 10-K corpus. Use only when you need "
            "information after the most recent 10-K filing date or for breaking news. "
            "Returns top results with titles, URLs, and snippets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query, ideally specific (e.g., 'Apple Q1 2025 earnings analyst response' not 'Apple news')",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 10)",
                    "default": 5,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "database_query",
        "description": (
            "Run a READ-ONLY SQL query against CortexAgent's internal audit log. "
            "Useful for checking past agent activity, citation patterns, or query history. "
            "Schema: audit_log(thread_id, agent_name, action, input_data, output_data, "
            "latency_ms, timestamp). Only SELECT statements allowed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A SELECT-only SQL query. Any non-SELECT will be refused.",
                }
            },
            "required": ["sql"],
        },
    },
    {
        "name": "calendar_book",
        "description": (
            "Book a follow-up calendar event (e.g., reminder to monitor a company's earnings "
            "release, schedule analyst review). Returns confirmation with event ID. This is a "
            "mock implementation that writes to a local JSON file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Event title, e.g. 'Monitor AAPL Q1 2025 earnings call'",
                },
                "date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD",
                },
                "duration_min": {
                    "type": "integer",
                    "description": "Duration in minutes (default 30)",
                    "default": 30,
                },
            },
            "required": ["title", "date"],
        },
    },
]


TOOL_HANDLERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "web_search": web_search,
    "database_query": database_query,
    "calendar_book": calendar_book,
}


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool by name with provided arguments."""
    if name not in TOOL_HANDLERS:
        return {
            "result": None,
            "error": f"Unknown tool: {name}. Available: {list(TOOL_HANDLERS.keys())}",
        }
    try:
        handler = TOOL_HANDLERS[name]
        result = handler(**arguments)
        return {"result": result, "error": None}
    except TypeError as exc:
        return {"result": None, "error": f"Invalid arguments for {name}: {exc}"}
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return {"result": None, "error": f"Tool {name} raised: {exc}"}


def get_schemas() -> List[Dict[str, Any]]:
    """Return the list of tool schemas for LLM tool_use registration."""
    return TOOL_SCHEMAS


def _print_schema(schema: Dict[str, Any]) -> None:
    """Render one schema in a human-readable smoke-test format."""
    print(f"\n[Tool: {schema['name']}]")
    print(f"  Description: {schema['description'][:120]}...")
    print(f"  Required args: {schema['input_schema'].get('required', [])}")
    print(f"  All properties: {list(schema['input_schema']['properties'].keys())}")


def _print_dispatch_result(title: str, payload: Dict[str, Any]) -> None:
    """Render one dispatch result for the smoke test."""
    print(f"\n{title}")
    print(json.dumps(payload, indent=2)[:600])


if __name__ == "__main__":
    print("=" * 60)
    print("MCP Definitions — Registered Tool Schemas")
    print("=" * 60)
    for schema in TOOL_SCHEMAS:
        _print_schema(schema)

    print("\n" + "=" * 60)
    print("Sample dispatch test:")
    print("=" * 60)

    result = execute_tool("web_search", {"query": "test", "num_results": 1})
    print("\n[1] execute_tool('web_search', {'query': 'test', 'num_results': 1})")
    print(
        f"    -> result count: {len((result.get('result') or {}).get('results', []))}, "
        f"error: {result.get('error')}"
    )

    result = execute_tool("calendar_book", {"title": "MCP dispatch test", "date": "2025-12-01"})
    print("\n[2] execute_tool('calendar_book', {'title': 'Test', 'date': '2025-12-01'})")
    print(
        f"    -> status: {(result.get('result') or {}).get('status')}, "
        f"error: {result.get('error')}"
    )

    result = execute_tool("database_query", {"sql": "SELECT 1"})
    error = result.get("error") or (result.get("result") or {}).get("error", "")
    print("\n[3] execute_tool('database_query', {'sql': 'SELECT 1'})")
    print(f"    -> error (connection expected if no postgres): {str(error)[:100]}")

    result = execute_tool("unknown_tool", {})
    print("\n[4] execute_tool('unknown_tool', {})")
    print(f"    -> {result.get('error')}")
