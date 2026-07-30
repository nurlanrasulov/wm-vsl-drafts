"""Build the WM AZE shrink contributor Looker query."""

from __future__ import annotations

from looker_sdk import models40 as models

from shrink_report.config import FILTER_OVERRIDES
from vendor_report.config import REPORT3_QUERY_SLUG
from vendor_report.looker_client import _resolve_filter_overrides, _run_query_xlsx

# Template explore shares model/view/joins with paused-items report.
TEMPLATE_QUERY_SLUG = REPORT3_QUERY_SLUG

# Shrink-specific dimensions and measures for the built-in query.
SHRINK_QUERY_FIELDS: tuple[str, ...] = (
    "wolt_market_item.primary_category",
    "wolt_market_item.name",
    "wolt_market_item.gtin",
    "wolt_market_item.product_code",
    "wolt_market_item_metrics.shrink_value",
    "wolt_market_item_metrics.shrinkage_percentage",
    "wolt_market_item_metrics.shrink_units",
    "wolt_market_item_metrics.units_sold",
)

SHRINK_QUERY_SORTS: tuple[str, ...] = (
    "wolt_market_item_metrics.shrink_value desc",
)

SHRINK_QUERY_LIMIT = "5000"


def download_shrink_xlsx(
    sdk,
    *,
    query_slug: str | None = None,
    filter_overrides: dict[str, str] | None = None,
    field_additions: list[str] | None = None,
) -> bytes:
    """
    Download shrink data as xlsx.

    Uses SHRINK_REPORT_QUERY_SLUG when provided; otherwise clones the vendor
    explore template and applies shrink fields/filters.
    """
    slug = (query_slug or "").strip() or TEMPLATE_QUERY_SLUG
    query = sdk.query_for_slug(
        slug,
        fields="id,model,view,fields,filters,sorts,limit,pivots,fill_fields,"
        "filter_expression,column_limit,total,row_total,subtotals,vis_config,"
        "filter_config,visible_ui_sections,dynamic_fields,query_timezone",
    )
    if not query:
        raise RuntimeError(f"Looker query slug not found: {slug}")

    merged_filters = dict(FILTER_OVERRIDES)
    if filter_overrides:
        merged_filters.update(filter_overrides)
    resolved_filters = _resolve_filter_overrides(query.filters, merged_filters)

    using_template = not (query_slug or "").strip()
    if using_template:
        fields = list(SHRINK_QUERY_FIELDS)
        sorts = list(SHRINK_QUERY_SORTS)
        print(f"  Built shrink query from template explore ({query.model}/{query.view})")
    else:
        fields = list(query.fields or [])
        sorts = list(query.sorts or [])

    if field_additions:
        existing = set(fields)
        for field in field_additions:
            if field not in existing:
                fields.append(field)
                existing.add(field)

    body = models.WriteQuery(
        model=query.model,
        view=query.view,
        fields=fields,
        filters=resolved_filters or None,
        sorts=sorts or None,
        limit=SHRINK_QUERY_LIMIT if using_template else query.limit,
        pivots=query.pivots,
        fill_fields=query.fill_fields,
        filter_expression=query.filter_expression,
        column_limit=query.column_limit,
        total=query.total,
        row_total=query.row_total,
        subtotals=query.subtotals,
        vis_config=query.vis_config,
        filter_config=query.filter_config,
        visible_ui_sections=query.visible_ui_sections,
        dynamic_fields=query.dynamic_fields,
        query_timezone=query.query_timezone,
    )
    created = sdk.create_query(body)
    if not created or not created.id:
        raise RuntimeError("Failed to create shrink Looker query")
    return _run_query_xlsx(sdk, created.id)
