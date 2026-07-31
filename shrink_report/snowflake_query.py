"""Snowflake SQL for WM AZE shrink contributor report."""

from __future__ import annotations

import os

from shrink_report.config import COUNTRY
from shrink_report.snowflake_client import execute_query

DEFAULT_METRICS_TABLE = (
    "WOLT_MARKET.RETAIL_PLATFORMS.RETAIL_PLATFORM_INVENTORY_WAREHOUSE_PRODUCT_REPORTING_WM"
)
DEFAULT_PRODUCTS_TABLE = (
    "WOLT_MARKET.INTERMEDIATE.F_RETAIL_PLATFORM_INVENTORY_AGGREGATED_EVENTS_WM"
)


def _metrics_table() -> str:
    return os.environ.get("SNOWFLAKE_METRICS_TABLE", DEFAULT_METRICS_TABLE)


def _products_table() -> str:
    return os.environ.get(
        "SNOWFLAKE_PRODUCTS_TABLE",
        os.environ.get("SNOWFLAKE_ITEMS_TABLE", DEFAULT_PRODUCTS_TABLE),
    )


def build_shrink_sql() -> str:
    custom = os.environ.get("SHRINK_SNOWFLAKE_SQL", "").strip()
    if custom:
        return custom

    metrics = _metrics_table()
    products = _products_table()
    # Country filter accepts both ISO code and full name variants.
    return f"""
WITH product_dim AS (
    SELECT
        PRODUCT_ID,
        ANY_VALUE(GTIN) AS GTIN,
        ANY_VALUE(PRODUCT_NAME) AS PRODUCT_NAME,
        ANY_VALUE(PRODUCT_CODE) AS PRODUCT_CODE,
        ANY_VALUE(PRODUCT_FAMILY_NAME_LEVEL_1) AS PRIMARY_CATEGORY
    FROM {products}
    WHERE UPPER(COALESCE(VENUE_COUNTRY, '')) IN (
        UPPER(%(country)s),
        'AZERBAIJAN',
        'AZ'
    )
    GROUP BY PRODUCT_ID
),
shrink AS (
    SELECT
        m.PRODUCT_ID,
        SUM(COALESCE(m.SHRINKED_UNITS_VALUE_LOCAL, 0)) AS SHRINK_VALUE,
        SUM(COALESCE(m.SHRINKED_UNITS, 0)) AS SHRINK_UNITS,
        SUM(COALESCE(m.SOLD_UNITS, 0)) AS SOLD_UNITS
    FROM {metrics} AS m
    INNER JOIN product_dim AS p
        ON m.PRODUCT_ID = p.PRODUCT_ID
    WHERE m.METRIC_DATE >= DATEADD(month, -3, CURRENT_DATE())
    GROUP BY m.PRODUCT_ID
)
SELECT
    p.PRIMARY_CATEGORY AS "Primary category",
    p.PRODUCT_NAME AS "Name",
    p.GTIN AS "Gtin",
    p.PRODUCT_CODE AS "Product code",
    s.SHRINK_VALUE AS "Shrink value",
    ROUND(100 * DIV0(s.SHRINK_UNITS, NULLIF(s.SOLD_UNITS, 0)), 2) AS "Shrinkage percentage",
    s.SHRINK_UNITS AS "Shrink units",
    s.SOLD_UNITS AS "Units sold"
FROM shrink AS s
INNER JOIN product_dim AS p
    ON s.PRODUCT_ID = p.PRODUCT_ID
WHERE COALESCE(p.PRIMARY_CATEGORY, '') NOT IN (
    'Herbs',
    'Fruits & Vegetables',
    'Fruits and Vegetables',
    'FnV',
    'F&V'
)
  AND s.SHRINK_VALUE > 0
ORDER BY s.SHRINK_VALUE DESC
LIMIT 5000
""".strip()


def fetch_shrink_rows() -> tuple[list[str], list[list]]:
    sql = build_shrink_sql()
    print("  Running Snowflake shrink query...")
    print(f"  Metrics: {_metrics_table()}")
    print(f"  Products: {_products_table()}")
    return execute_query(sql, params={"country": COUNTRY})
