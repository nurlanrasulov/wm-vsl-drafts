"""Week date helpers for shrink report naming."""

from __future__ import annotations

from datetime import date

from vendor_report.week_utils import last_week_start, parse_week_start, week_date_label


def report_basename(week_start: date) -> str:
    return f"WM AZE SHRINK TOP 10 CONTRIBUTORS - WEEK {week_date_label(week_start)}"


__all__ = ["last_week_start", "parse_week_start", "report_basename", "week_date_label"]
