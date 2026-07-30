"""Snowflake SQL for WM AZE shrink contributor report."""

from __future__ import annotations

import os

from shrink_report.config import COUNTRY
from shrink_report.snowflake_client import execute_query

DEFAULT_METRICS_TABLE = "PROD.DBT.WOLT_MARKET_ITEM_METRICS"
DEFAULT_ITEMS_TABLE = "PROD.DBT.WOLT_MARKET_ITEMS"


def _metrics_table() -> str:
    return os.environ.get("SNOWFLAKE_METRICS_TABLE", DEFAULT_METRICS_TABLE)


def _items_table() -> str:
    return os.environ.get("SNOWFLAKE_ITEMS_TABLE", DEFAULT_ITEMS_TABLE)


def build_shrink_sql() -> str:
    custom = os.environ.get("SHRINK_SNOWFLAKE_SQL", "").strip()
    if custom:
        return custom

    metrics = _metrics_table()
    items = _items_table()
    return f"""
SELECT
    item.primary_category AS "Primary category",
    item.name AS "Name",
    item.gtin AS "Gtin",
    item.product_code AS "Product code",
    SUM(metrics.shrink_value) AS "Shrink value",
    ROUND(
        100 * DIV0(SUM(metrics.shrink_value), NULLIF(SUM(metrics.sales_value), 0)),
        2
    ) AS "Shrinkage percentage",
    SUM(metrics.shrink_units) AS "Shrink units",
    SUM(metrics.units_sold) AS "Units sold"
FROM {metrics} AS metrics
INNER JOIN {items} AS item
    ON metrics.item_id = item.item_id
WHERE item.country = %(country)s
  AND metrics.metric_date >= DATEADD(month, -3, CURRENT_DATE())
  AND COALESCE(item.primary_category, '') NOT IN (
      'Herbs', 'Fruits & Vegetables', 'Fruits and Vegetables', 'FnV', 'F&V'
  )
GROUP BY
    item.primary_category,
    item.name,
    item.gtin,
    item.product_code
ORDER BY "Shrink value" DESC
LIMIT 5000
""".strip()


def fetch_shrink_rows() -> tuple[list[str], list[list]]:
    sql = build_shrink_sql()
    print("  Running Snowflake shrink query...")
    return execute_query(sql, params={"country": COUNTRY})
