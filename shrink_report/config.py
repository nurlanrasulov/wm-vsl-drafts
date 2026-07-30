"""Configuration for WM AZE shrink performance reports."""

from __future__ import annotations

COUNTRY = "AZE"

# Looker filter overrides keyed by filter field names from the saved explore.
# Herbs are excluded via category filter; metrics use the last 3 months.
FILTER_OVERRIDES: dict[str, str] = {
    "country": COUNTRY,
    "wolt_market_item.primary_category": "-Herbs",
    "wolt_market_item_metrics.shrinkage_date": "3 months",
}

DEFAULT_SHRINKAGE_COLUMN = "Shrinkage % (3M)"
DEFAULT_CATEGORY_COLUMN = "Primary category"
DEFAULT_TOP_N = 100
DEFAULT_RECIPIENT = "wolt-market-aze-category@wolt.com"

EXCLUDED_CATEGORIES = ("Herbs", "herbs", "HERBS")

DEFAULT_ON_BEHALF_NAME = "Nurlan Rasulov"
DEFAULT_ON_BEHALF_EMAIL = "nurlan.rasulov@wolt.com"


def email_body(*, name: str, email: str) -> str:
    return f"""Salam,

Keçən 3 ay üzrə shrink göstəricilərinə görə ən yaxşı performans göstərən məhsulların siyahısı əlavədədir.
Herbs kateqoriyası hesabata daxil edilməyib.

Zəhmət olmasa, nəzərdən keçirin.

--
Bu məktub {name} ({email}) adından avtomatik assistent vasitəsilə göndərilib.
Sent automatically on behalf of {name}.
"""
