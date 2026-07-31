#!/usr/bin/env python3
"""Inspect inventory warehouse product reporting table for shrink report."""

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


TABLE = "WOLT_MARKET.RETAIL_PLATFORMS.RETAIL_PLATFORM_INVENTORY_WAREHOUSE_PRODUCT_REPORTING_WM"


def main() -> None:
    load_dotenv()
    import os

    os.environ.setdefault("SNOWFLAKE_DATABASE", "WOLT_MARKET")
    from shrink_report.snowflake_client import connect, validate_connection

    print(validate_connection())
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("USE DATABASE WOLT_MARKET")

        print(f"\n=== Columns in {TABLE} ===")
        cur.execute(
            """
            SELECT column_name, data_type
            FROM WOLT_MARKET.INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema = 'RETAIL_PLATFORMS'
              AND table_name = 'RETAIL_PLATFORM_INVENTORY_WAREHOUSE_PRODUCT_REPORTING_WM'
            ORDER BY ordinal_position
            """
        )
        cols = [r[0] for r in cur.fetchall()]
        for col in cols:
            print(f"  - {col}")

        print("\n=== Sample 5 rows (key fields if present) ===")
        preferred = [
            "COUNTRY",
            "COUNTRY_CODE",
            "PRIMARY_CATEGORY",
            "CATEGORY",
            "CATEGORY_NAME",
            "PRODUCT_NAME",
            "ITEM_NAME",
            "NAME",
            "GTIN",
            "EAN",
            "BARCODE",
            "PRODUCT_ID",
            "PRODUCT_CODE",
            "SKU",
            "SHRINKED_UNITS_VALUE_LOCAL",
            "SOLD_UNITS",
            "SHRINKED_UNITS_EXPIRED",
            "SHRINKED_UNITS_SPOILED",
            "METRIC_DATE",
            "DATE",
            "REPORT_DATE",
        ]
        existing = [c for c in preferred if c in cols]
        # also include any SHRINKED_UNITS* columns
        existing += [c for c in cols if c.startswith("SHRINKED_") and c not in existing]
        select_cols = existing[:40] or cols[:20]
        sql = f"SELECT {', '.join(select_cols)} FROM {TABLE} LIMIT 5"
        print("SQL:", sql)
        cur.execute(sql)
        print(select_cols)
        for row in cur.fetchall():
            print(row)

        print("\n=== Distinct category-like values (if category column exists) ===")
        for cat_col in ("PRIMARY_CATEGORY", "CATEGORY", "CATEGORY_NAME", "PRODUCT_CATEGORY"):
            if cat_col in cols:
                cur.execute(
                    f"""
                    SELECT {cat_col}, COUNT(*) AS n
                    FROM {TABLE}
                    GROUP BY 1
                    ORDER BY n DESC
                    LIMIT 30
                    """
                )
                print(f"\n{cat_col}:")
                for row in cur.fetchall():
                    print(" ", row)
                break


if __name__ == "__main__":
    main()
