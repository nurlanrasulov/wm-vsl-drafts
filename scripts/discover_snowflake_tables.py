#!/usr/bin/env python3
"""Discover Snowflake databases/schemas/tables for WM shrink reporting."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_dotenv() -> None:
    import os

    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    load_dotenv()
    from shrink_report.snowflake_client import execute_query, validate_connection

    info = validate_connection()
    print(f"Connected: {info['user']} @ {info['account']} role={info['role']}\n")

    print("=== Databases ===")
    _, rows = execute_query("SHOW DATABASES")
    for row in rows[:50]:
        # SHOW DATABASES: name is typically index 1
        name = row[1] if len(row) > 1 else row[0]
        print(f"  {name}")

    print("\n=== Tables matching shrink / wolt_market / item_metric ===")
    sql = """
    SELECT table_catalog, table_schema, table_name
    FROM information_schema.tables
    WHERE (
        LOWER(table_name) LIKE '%shrink%'
        OR LOWER(table_name) LIKE '%wolt_market%'
        OR LOWER(table_name) LIKE '%item_metric%'
        OR LOWER(table_name) LIKE '%inventory%'
    )
    AND table_schema NOT IN ('INFORMATION_SCHEMA')
    ORDER BY table_catalog, table_schema, table_name
    LIMIT 200
    """
    try:
        headers, rows = execute_query(sql)
        print(" | ".join(headers))
        for row in rows:
            print(" | ".join(str(v) for v in row))
        if not rows:
            print("No matches in current database. Checking all accessible DBs via SHOW...")
    except Exception as exc:
        print(f"information_schema query failed: {exc}")

    print("\n=== SHOW TABLES LIKE '%SHRINK%' / '%WOLT%' across current context ===")
    for pattern in ("%SHRINK%", "%WOLT_MARKET%", "%ITEM%METRIC%"):
        try:
            _, rows = execute_query(f"SHOW TABLES LIKE '{pattern}' IN ACCOUNT")
            print(f"\nPattern {pattern}: {len(rows)} hits")
            for row in rows[:30]:
                # created_on, name, database_name, schema_name, ...
                name = row[1] if len(row) > 1 else row
                db = row[2] if len(row) > 2 else ""
                schema = row[3] if len(row) > 3 else ""
                print(f"  {db}.{schema}.{name}")
        except Exception as exc:
            print(f"SHOW TABLES {pattern} failed: {exc}")


if __name__ == "__main__":
    main()
