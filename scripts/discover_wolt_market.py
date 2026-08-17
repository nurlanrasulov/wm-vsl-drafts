#!/usr/bin/env python3
"""Deep discovery inside WOLT_MARKET for shrink-related tables/columns."""

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
    import os

    os.environ.setdefault("SNOWFLAKE_DATABASE", "WOLT_MARKET")

    from shrink_report.snowflake_client import connect, execute_query, validate_connection

    info = validate_connection()
    print(f"Connected: {info['user']} @ {info['account']} role={info['role']}\n")

    with connect() as conn:
        cur = conn.cursor()
        cur.execute("USE DATABASE WOLT_MARKET")

        print("=== Schemas in WOLT_MARKET ===")
        cur.execute("SHOW SCHEMAS IN DATABASE WOLT_MARKET")
        schemas = cur.fetchall()
        for row in schemas:
            print(f"  {row[1]}")

        print("\n=== All tables/views in WOLT_MARKET (first 300) ===")
        cur.execute(
            """
            SELECT table_schema, table_name, table_type
            FROM WOLT_MARKET.INFORMATION_SCHEMA.TABLES
            WHERE table_schema NOT IN ('INFORMATION_SCHEMA')
            ORDER BY table_schema, table_name
            LIMIT 300
            """
        )
        tables = cur.fetchall()
        for schema, name, ttype in tables:
            print(f"  {schema}.{name} ({ttype})")
        print(f"Total listed: {len(tables)}")

        print("\n=== Names containing shrink/waste/loss/inventory/gtin/sales ===")
        keywords = (
            "shrink",
            "waste",
            "wastage",
            "spoil",
            "loss",
            "inventory",
            "gtin",
            "item",
            "product",
            "sales",
            "sold",
            "metric",
        )
        for schema, name, ttype in tables:
            hay = f"{schema}.{name}".lower()
            if any(k in hay for k in keywords):
                print(f"  {schema}.{name} ({ttype})")

        print("\n=== Columns containing shrink/waste/gtin/units_sold ===")
        cur.execute(
            """
            SELECT table_schema, table_name, column_name, data_type
            FROM WOLT_MARKET.INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema NOT IN ('INFORMATION_SCHEMA')
              AND (
                LOWER(column_name) LIKE '%shrink%'
                OR LOWER(column_name) LIKE '%waste%'
                OR LOWER(column_name) LIKE '%spoil%'
                OR LOWER(column_name) LIKE '%gtin%'
                OR LOWER(column_name) LIKE '%units_sold%'
                OR LOWER(column_name) LIKE '%sold_units%'
                OR LOWER(column_name) LIKE '%inventory_loss%'
              )
            ORDER BY table_schema, table_name, ordinal_position
            LIMIT 300
            """
        )
        cols = cur.fetchall()
        for schema, table, col, dtype in cols:
            print(f"  {schema}.{table}.{col} ({dtype})")
        if not cols:
            print("  (no matching columns)")

        # Peek likely mart tables
        candidates = [
            "MART.WOLT_MARKET_VENUE_METRICS_WM",
            "RETAIL_PLATFORMS.WOLT_MARKET_UNCONSTRAINED_SALES_WM",
            "RETAIL_PLATFORMS.WOLT_MARKET_STORE_OPS_REPORTING_HOURLY_WM",
        ]
        print("\n=== Sample columns for known tables ===")
        for full in candidates:
            try:
                cur.execute(
                    f"""
                    SELECT column_name, data_type
                    FROM WOLT_MARKET.INFORMATION_SCHEMA.COLUMNS
                    WHERE table_schema = '{full.split('.')[0]}'
                      AND table_name = '{full.split('.')[1]}'
                    ORDER BY ordinal_position
                    """
                )
                print(f"\n{full}:")
                for col, dtype in cur.fetchall():
                    print(f"  - {col} ({dtype})")
            except Exception as exc:
                print(f"{full}: {exc}")


if __name__ == "__main__":
    main()
