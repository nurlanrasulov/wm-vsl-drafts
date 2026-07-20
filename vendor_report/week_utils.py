"""Week date helpers for vendor report naming."""

from __future__ import annotations

from datetime import date, datetime, timedelta


def last_week_start(reference: date | None = None) -> date:
    """Return Monday of the previous calendar week."""
    today = reference or date.today()
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=7)


def week_date_label(week_start: date) -> str:
    """Format week start as DD.MM.YYYY (e.g. 13.07.2026)."""
    return week_start.strftime("%d.%m.%Y")


def report1_basename(week_start: date) -> str:
    return f"UNILEVER ICECREAM VSL REPORT WEEK - WEEK {week_date_label(week_start)}"


def report2_basename(week_start: date) -> str:
    return f"UNILEVER ICECREAM VSL REPORT BY ITEM - WEEK {week_date_label(week_start)}"


def report3_basename() -> str:
    return "UNILEVER ICECREAM PAUSED ITEMS"


def parse_week_start(value: str) -> date:
    return datetime.strptime(value, "%d.%m.%Y").date()
