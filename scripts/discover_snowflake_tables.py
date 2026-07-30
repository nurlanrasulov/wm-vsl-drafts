#!/usr/bin/env python3
"""Search Snowflake information_schema for shrink-related tables."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shrink_report.snowflake_client import execute_query, validate_connection


def main() -> None:
    info = validate_connection()
    print(f"Connected: {info['user']} @ {info['account']}\n")

    sql = """
    SELECT table_catalog, table_schema, table_name
    FROM information_schema.tables
    WHERE (
        LOWER(table_name) LIKE '%shrink%'
        OR LOWER(table_name) LIKE '%wolt_market%'
    )
    AND table_schema NOT IN ('INFORMATION_SCHEMA')
    ORDER BY table_catalog, table_schema, table_name
    LIMIT 100
    """
    headers, rows = execute_query(sql)
    print(" | ".join(headers))
    print("-" * 80)
    for row in rows:
        print(" | ".join(str(value) for value in row))
    if not rows:
        print("No matching tables found.")


if __name__ == "__main__":
    main()
