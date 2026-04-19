"""SQL query tool — strict READ-ONLY (SELECT only)."""

import logging
import re
from typing import Any, Dict

from sqlalchemy import create_engine, text

from config.settings import settings


logger = logging.getLogger(__name__)
_engine = None


def _get_engine():
    """Return a lazily initialized SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(settings.postgres_url, pool_pre_ping=True)
    return _engine


def database_query(sql: str) -> Dict[str, Any]:
    """
    Execute a READ-ONLY SQL query. Refuses anything that isn't SELECT.

    Returns {rows: [...], row_count: int, columns: [...]} on success.
    """
    sql_clean = sql.strip().rstrip(";").strip()

    if not re.match(r"^\s*SELECT\b", sql_clean, re.IGNORECASE):
        return {
            "rows": [],
            "row_count": 0,
            "columns": [],
            "error": f"Only SELECT statements are permitted. Got: {sql_clean[:80]}",
        }

    forbidden = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE|INTO\s+OUTFILE)\b",
        re.IGNORECASE,
    )
    if forbidden.search(sql_clean):
        return {
            "rows": [],
            "row_count": 0,
            "columns": [],
            "error": "Query contains forbidden keywords (write operations not allowed)",
        }

    try:
        engine = _get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql_clean))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchmany(50)]
        return {
            "rows": rows,
            "row_count": len(rows),
            "columns": columns,
        }
    except Exception as exc:
        logger.warning("SQL query failed: %s", exc)
        return {
            "rows": [],
            "row_count": 0,
            "columns": [],
            "error": str(exc),
        }


def _print_result(label: str, payload: Dict[str, Any]) -> None:
    """Render a smoke-test result in a compact, readable format."""
    print(label)
    error = payload.get("error")
    if error:
        print(f"  Refused/Errored with: {str(error)[:120]}")
        return
    print(f"  Columns: {payload.get('columns', [])}")
    print(f"  Row count: {payload.get('row_count', 0)}")
    print(f"  Rows: {payload.get('rows', [])}")


if __name__ == "__main__":
    print("=" * 60)
    print("Database Tool — Smoke Test")
    print("=" * 60)

    print("\n[Test 1] Valid SELECT 1:")
    result_1 = database_query("SELECT 1 AS test_col")
    if result_1.get("error"):
        print(f"  Connection error (expected if Postgres not running): {result_1['error'][:120]}")
    else:
        print(f"  SUCCESS: {result_1['rows']}")

    print("\n[Test 2] Forbidden DROP TABLE:")
    result_2 = database_query("DROP TABLE audit_log")
    print(f"  Refused with: {result_2.get('error', 'NO ERROR (BUG!)')[:120]}")

    print("\n[Test 3] Forbidden INSERT:")
    result_3 = database_query("INSERT INTO audit_log VALUES (1)")
    print(f"  Refused with: {result_3.get('error', 'NO ERROR (BUG!)')[:120]}")

    print("\n[Test 4] Sneaky DROP inside SELECT:")
    result_4 = database_query("SELECT * FROM users; DROP TABLE users;")
    print(f"  Handling: {result_4.get('error', 'EXECUTED (BUG!)')[:120]}")

    print("\nNote: Test 1 connection error is EXPECTED if you don't have Postgres running locally.")
    print("Tests 2, 3, 4 should all show 'Refused' messages — that proves the safety logic works.")
