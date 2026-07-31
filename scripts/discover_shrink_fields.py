#!/usr/bin/env python3
"""Find item-level shrink + sales columns in WOLT_MARKET."""

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
    from shrink_report.snowflake_client import connect, validate_connection

    print(validate_connection())
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("USE DATABASE WOLT_MARKET")

        print("\n=== Columns with shrink/gtin/category/product/item/sold ===")
        cur.execute(
            """
            SELECT table_schema, table_name, column_name, data_type
            FROM WOLT_MARKET.INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema NOT IN ('INFORMATION_SCHEMA')
              AND (
                LOWER(column_name) LIKE '%shrink%'
                OR LOWER(column_name) LIKE '%shrunk%'
                OR LOWER(column_name) LIKE '%gtin%'
                OR LOWER(column_name) LIKE '%ean%'
                OR LOWER(column_name) LIKE '%barcode%'
                OR LOWER(column_name) LIKE '%category%'
                OR LOWER(column_name) LIKE '%product%'
                OR LOWER(column_name) LIKE '%item_name%'
                OR LOWER(column_name) LIKE '%item_id%'
                OR LOWER(column_name) LIKE '%sold_unit%'
                OR LOWER(column_name) LIKE '%units_sold%'
              )
            ORDER BY table_schema, table_name, column_name
            """
        )
        rows = cur.fetchall()
        for r in rows:
            print(f"  {r[0]}.{r[1]}.{r[2]} ({r[3]})")
        print(f"Total: {len(rows)}")

        print("\n=== Sample from STORE_OPS hourly (top shrink venues, last 90 days) ===")
        cur.execute(
            """
            SELECT
              RETAIL_PLATFORM_VENUE_ID,
              SUM(UNITS_SHRUNK) AS units_shrunk,
              SUM(SHRINKAGE_EVENTS) AS shrink_events,
              SUM(UNITS_RECEIVED) AS units_received
            FROM WOLT_MARKET.RETAIL_PLATFORMS.WOLT_MARKET_STORE_OPS_REPORTING_HOURLY_WM
            WHERE METRIC_TIMESTAMP >= DATEADD(day, -90, CURRENT_TIMESTAMP())
            GROUP BY 1
            ORDER BY units_shrunk DESC NULLS LAST
            LIMIT 10
            """
        )
        print([d[0] for d in cur.description])
        for row in cur.fetchall():
            print(row)

        print("\n=== Columns in UNCONSTRAINED_SALES ===")
        cur.execute(
            """
            SELECT column_name, data_type
            FROM WOLT_MARKET.INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema = 'RETAIL_PLATFORMS'
              AND table_name = 'WOLT_MARKET_UNCONSTRAINED_SALES_WM'
            ORDER BY ordinal_position
            """
        )
        for col, dtype in cur.fetchall():
            print(f"  - {col} ({dtype})")

        print("\n=== Columns in VENUE_METRICS_WM ===")
        cur.execute(
            """
            SELECT column_name, data_type
            FROM WOLT_MARKET.INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema = 'MART'
              AND table_name = 'WOLT_MARKET_VENUE_METRICS_WM'
            ORDER BY ordinal_position
            """
        )
        for col, dtype in cur.fetchall():
            print(f"  - {col} ({dtype})")


if __name__ == "__main__":
    main()
