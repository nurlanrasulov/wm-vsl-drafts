#!/usr/bin/env python3
"""Find product dimension tables with GTIN/name/category for join."""

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

        print("\n=== Tables that have PRODUCT_ID + (GTIN or NAME or CATEGORY) ===")
        cur.execute(
            """
            WITH cols AS (
              SELECT table_schema, table_name, LOWER(column_name) AS col
              FROM WOLT_MARKET.INFORMATION_SCHEMA.COLUMNS
              WHERE table_schema NOT IN ('INFORMATION_SCHEMA')
            )
            SELECT
              table_schema,
              table_name,
              MAX(IFF(col = 'product_id', 1, 0)) AS has_product_id,
              MAX(IFF(col IN ('gtin','ean','barcode','ean_code'), 1, 0)) AS has_gtin,
              MAX(IFF(col IN ('product_name','item_name','name'), 1, 0)) AS has_name,
              MAX(IFF(col LIKE '%category%', 1, 0)) AS has_category,
              MAX(IFF(col LIKE '%country%', 1, 0)) AS has_country
            FROM cols
            GROUP BY 1, 2
            HAVING has_product_id = 1
               AND (has_gtin = 1 OR has_name = 1 OR has_category = 1)
            ORDER BY has_gtin DESC, has_category DESC, has_name DESC, table_schema, table_name
            """
        )
        rows = cur.fetchall()
        for r in rows:
            print(f"  {r[0]}.{r[1]}  product_id={r[2]} gtin={r[3]} name={r[4]} category={r[5]} country={r[6]}")

        # Inspect top candidates
        candidates = [f"{r[0]}.{r[1]}" for r in rows[:8]]
        for full in candidates:
            schema, name = full.split(".", 1)
            print(f"\n=== Columns: {full} ===")
            cur.execute(
                f"""
                SELECT column_name, data_type
                FROM WOLT_MARKET.INFORMATION_SCHEMA.COLUMNS
                WHERE table_schema = '{schema}' AND table_name = '{name}'
                ORDER BY ordinal_position
                """
            )
            for col, dtype in cur.fetchall():
                low = col.lower()
                if any(k in low for k in ("product", "gtin", "ean", "barcode", "name", "category", "country", "sku")):
                    print(f"  - {col} ({dtype})")


if __name__ == "__main__":
    main()
