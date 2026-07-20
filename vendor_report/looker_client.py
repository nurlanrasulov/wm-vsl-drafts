"""Looker API helpers for downloading vendor reports."""

from __future__ import annotations

import time
import urllib.parse
from typing import Any

import looker_sdk
from looker_sdk import models40 as models

DEFAULT_RENDER_WIDTH = 1400
DEFAULT_RENDER_HEIGHT = 2400
POLL_INTERVAL_SEC = 1.0
POLL_TIMEOUT_SEC = 300


def init_sdk() -> looker_sdk.sdk.api40.methods40.Looker40SDK:
    return looker_sdk.init40()


def _poll_render_task(sdk: looker_sdk.sdk.api40.methods40.Looker40SDK, task_id: str) -> bytes:
    elapsed = 0.0
    while elapsed < POLL_TIMEOUT_SEC:
        task = sdk.render_task(task_id, fields="status,status_detail")
        status = task.status
        if status == "success":
            return sdk.render_task_results(task_id)
        if status == "failure":
            detail = getattr(task, "status_detail", "") or "unknown error"
            raise RuntimeError(f"Looker render task failed: {detail}")
        time.sleep(POLL_INTERVAL_SEC)
        elapsed += POLL_INTERVAL_SEC
    raise RuntimeError(f"Looker render task timed out after {POLL_TIMEOUT_SEC}s")


def download_dashboard_pdf(
    sdk: looker_sdk.sdk.api40.methods40.Looker40SDK,
    *,
    dashboard_id: str,
    dashboard_filters: str,
    width: int = DEFAULT_RENDER_WIDTH,
    height: int = DEFAULT_RENDER_HEIGHT,
) -> bytes:
    task = sdk.create_dashboard_render_task(
        dashboard_id,
        "pdf",
        models.CreateDashboardRenderTask(
            dashboard_style="tiled",
            dashboard_filters=dashboard_filters,
            pdf_paper_size="a4",
            pdf_landscape=True,
            long_tables=True,
        ),
        width,
        height,
    )
    if not task or not task.id:
        raise RuntimeError(f"Could not create PDF render task for dashboard {dashboard_id}")
    return _poll_render_task(sdk, task.id)


def _write_query_from_existing(
    sdk: looker_sdk.sdk.api40.methods40.Looker40SDK,
    query: models.Query,
    *,
    filter_overrides: dict[str, str] | None = None,
) -> str:
    merged_filters = _parse_filter_string(query.filters)
    if filter_overrides:
        merged_filters.update(filter_overrides)

    body = models.WriteQuery(
        model=query.model,
        view=query.view,
        fields=query.fields,
        pivots=query.pivots,
        fill_fields=query.fill_fields,
        filters=merged_filters or None,
        filter_expression=query.filter_expression,
        sorts=query.sorts,
        limit=query.limit,
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
        raise RuntimeError("Failed to create Looker query")
    return created.id


def _parse_filter_string(filters: str | None) -> dict[str, str]:
    if not filters:
        return {}
    parsed = urllib.parse.parse_qs(filters, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _run_query_xlsx(sdk: looker_sdk.sdk.api40.methods40.Looker40SDK, query_id: str) -> bytes:
    result = sdk.run_query(query_id=query_id, result_format="xlsx", cache=False)
    if isinstance(result, bytes):
        return result
    if isinstance(result, str):
        return result.encode("utf-8")
    raise RuntimeError(f"Unexpected xlsx result type: {type(result)!r}")


def download_dashboard_xlsx(
    sdk: looker_sdk.sdk.api40.methods40.Looker40SDK,
    *,
    dashboard_id: str,
    dashboard_filters: str,
    prefer_column: str | None = None,
) -> bytes:
    """Export the best-matching dashboard tile as xlsx with dashboard filters applied."""
    elements = sdk.dashboard_dashboard_elements(
        dashboard_id,
        fields="id,title,query",
    )
    candidates: list[tuple[int, str, models.Query]] = []
    for element in elements:
        if not element.query or not element.query.id:
            continue
        query = sdk.query(element.query.id, fields="id,model,view,fields,filters,sorts,limit")
        score = len(query.fields or [])
        if prefer_column and query.fields:
            for field in query.fields:
                if prefer_column.lower() in field.replace("_", " ").lower():
                    score += 1000
                    break
        candidates.append((score, element.title or element.id or "tile", query))

    if not candidates:
        raise RuntimeError(f"Dashboard {dashboard_id} has no exportable query tiles")

    candidates.sort(key=lambda item: item[0], reverse=True)
    _, title, query = candidates[0]
    filter_overrides = _dashboard_filters_to_query_filters(dashboard_filters, query.filters)
    query_id = _write_query_from_existing(sdk, query, filter_overrides=filter_overrides)
    data = _run_query_xlsx(sdk, query_id)
    print(f"  Exported dashboard tile: {title}")
    return data


def _dashboard_filters_to_query_filters(
    dashboard_filters: str,
    existing_query_filters: str | None,
) -> dict[str, str]:
    """
    Best-effort mapping from dashboard URL filters to query filter field names.
    Matches by exact key or by suffix (e.g. 'country' matches 'wolt_market_items.country').
    """
    dashboard = _parse_filter_string(dashboard_filters)
    query_keys = list(_parse_filter_string(existing_query_filters).keys())
    mapped: dict[str, str] = {}

    display_to_value = {
        _normalize_filter_label(key): value for key, value in dashboard.items()
    }

    for display_label, value in display_to_value.items():
        matched = _match_query_filter_key(display_label, query_keys)
        if matched:
            mapped[matched] = value

    return mapped


def _normalize_filter_label(label: str) -> str:
    return label.strip().lower().replace("_", " ")


def _match_query_filter_key(display_label: str, query_keys: list[str]) -> str | None:
    normalized = _normalize_filter_label(display_label)
    for key in query_keys:
        key_label = _normalize_filter_label(key.split(".")[-1])
        if key_label == normalized:
            return key
    for key in query_keys:
        if normalized in _normalize_filter_label(key):
            return key
    return None


def download_explore_xlsx(
    sdk: looker_sdk.sdk.api40.methods40.Looker40SDK,
    *,
    query_slug: str,
    filter_overrides: dict[str, str],
) -> bytes:
    query = sdk.query_for_slug(query_slug, fields="id,model,view,fields,filters,sorts,limit")
    if not query:
        raise RuntimeError(f"Looker query slug not found: {query_slug}")

    resolved_overrides = _resolve_filter_overrides(query.filters, filter_overrides)
    query_id = _write_query_from_existing(sdk, query, filter_overrides=resolved_overrides)
    return _run_query_xlsx(sdk, query_id)


def _resolve_filter_overrides(
    existing_filters: str | None,
    overrides: dict[str, str],
) -> dict[str, str]:
    query_keys = list(_parse_filter_string(existing_filters).keys())
    resolved: dict[str, str] = {}

    for override_key, value in overrides.items():
        if override_key in query_keys:
            resolved[override_key] = value
            continue
        matched = _match_query_filter_key(override_key, query_keys)
        if matched:
            resolved[matched] = value
            continue
        # Keep explicit key as fallback for explores that use short filter names.
        resolved[override_key] = value

    return resolved


def validate_looker_connection(sdk: looker_sdk.sdk.api40.methods40.Looker40SDK) -> dict[str, Any]:
    me = sdk.me()
    return {"id": me.id, "email": me.email, "display_name": me.display_name}
