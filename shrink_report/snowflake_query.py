"""Snowflake SQL for WM AZE shrink contributor report."""

from __future__ import annotations

import os
from typing import Any

from shrink_report.config import COUNTRY
from shrink_report.snowflake_client import connect

DEFAULT_METRICS_TABLE = (
    "WOLT_MARKET.RETAIL_PLATFORMS.RETAIL_PLATFORM_INVENTORY_WAREHOUSE_PRODUCT_REPORTING_WM"
)
# Highest-scoring product dim from discovery (GTIN + name + category + country).
DEFAULT_PRODUCTS_TABLE = (
    "WOLT_MARKET.INTERMEDIATE.F_RETAIL_PLATFORM_VENDOR_DRAFT_PURCHASE_ORDER_ITEMS_WM"
)


def _metrics_table() -> str:
    return os.environ.get("SNOWFLAKE_METRICS_TABLE", DEFAULT_METRICS_TABLE)


def _products_table() -> str:
    return os.environ.get(
        "SNOWFLAKE_PRODUCTS_TABLE",
        os.environ.get("SNOWFLAKE_ITEMS_TABLE", DEFAULT_PRODUCTS_TABLE),
    )


def _split_fqn(table: str) -> tuple[str, str, str]:
    parts = table.split(".")
    if len(parts) != 3:
        raise SystemExit(f"Expected fully-qualified table name db.schema.table, got: {table}")
    return parts[0], parts[1], parts[2]


def _table_columns(cursor, table: str) -> set[str]:
    database, schema, name = _split_fqn(table)
    cursor.execute(
        f"""
        SELECT column_name
        FROM {database}.INFORMATION_SCHEMA.COLUMNS
        WHERE table_schema = %(schema)s
          AND table_name = %(name)s
        """,
        {"schema": schema, "name": name},
    )
    return {str(row[0]).upper() for row in cursor.fetchall()}


def _pick_column(columns: set[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate.upper() in columns:
            return candidate
    return None


def build_shrink_sql(products_table: str, product_columns: set[str]) -> str:
    custom = os.environ.get("SHRINK_SNOWFLAKE_SQL", "").strip()
    if custom:
        return custom

    metrics = _metrics_table()
    gtin_col = _pick_column(product_columns, ("GTIN", "EAN", "BARCODE", "EAN_CODE"))
    name_col = _pick_column(product_columns, ("PRODUCT_NAME", "ITEM_NAME", "NAME"))
    code_col = _pick_column(product_columns, ("PRODUCT_CODE", "SKU", "VENDOR_SKU"))
    category_col = _pick_column(
        product_columns,
        (
            "PRODUCT_FAMILY_NAME_LEVEL_1",
            "PRIMARY_CATEGORY",
            "CATEGORY_NAME",
            "CATEGORY",
        ),
    )
    country_col = _pick_column(product_columns, ("VENUE_COUNTRY", "COUNTRY_CODE", "COUNTRY"))

    gtin_expr = f"ANY_VALUE({gtin_col})" if gtin_col else "NULL"
    name_expr = f"ANY_VALUE({name_col})" if name_col else "NULL"
    code_expr = f"ANY_VALUE({code_col})" if code_col else "NULL"
    category_expr = f"ANY_VALUE({category_col})" if category_col else "NULL"

    if country_col:
        country_filter = f"""
    WHERE UPPER(COALESCE({country_col}, '')) IN (
        UPPER(%(country)s),
        'AZERBAIJAN',
        'AZ'
    )
"""
    else:
        country_filter = ""
        print("  Warning: no country column on product table; country filter skipped.")

    return f"""
WITH product_dim AS (
    SELECT
        PRODUCT_ID,
        {gtin_expr} AS GTIN,
        {name_expr} AS PRODUCT_NAME,
        {code_expr} AS PRODUCT_CODE,
        {category_expr} AS PRIMARY_CATEGORY
    FROM {products_table}
    {country_filter}
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


def fetch_shrink_rows() -> tuple[list[str], list[list[Any]]]:
    """Run shrink report using a single Snowflake connection (one browser login)."""
    metrics = _metrics_table()
    products = _products_table()
    print("  Running Snowflake shrink query...")
    print(f"  Metrics: {metrics}")
    print(f"  Products: {products}")

    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT CURRENT_USER(), CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_WAREHOUSE()"
        )
        user, account, role, warehouse = cursor.fetchone()
        print(
            f"  Snowflake connected as {user} @ {account} "
            f"(role={role or 'default'}, warehouse={warehouse or 'default'})"
        )

        product_columns = _table_columns(cursor, products)
        if "PRODUCT_ID" not in product_columns:
            raise SystemExit(f"Product table {products} has no PRODUCT_ID column.")

        sql = build_shrink_sql(products, product_columns)
        cursor.execute(sql, {"country": COUNTRY})
        headers = [column[0] for column in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
        return headers, rows
