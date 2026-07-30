"""Configuration for WM AZE shrink contributor reports."""

from __future__ import annotations

COUNTRY = "AZE"

# Looker filter overrides keyed by filter field names from the saved explore.
# Herbs and FnV are excluded via category filter; metrics use the last 3 months.
FILTER_OVERRIDES: dict[str, str] = {
    "country": COUNTRY,
    "wolt_market_item.primary_category": "-Herbs,-Fruits & Vegetables",
    "wolt_market_item_metrics.shrinkage_date": "3 months",
}

DEFAULT_CONTRIBUTOR_COLUMN = "Shrink value (AZN)"
DEFAULT_SHRINKAGE_COLUMN = "Shrinkage % (3M)"
DEFAULT_CATEGORY_COLUMN = "Primary category"
DEFAULT_GTIN_COLUMN = "GTIN"
DEFAULT_ITEM_NAME_COLUMN = "Item name"
DEFAULT_TOP_N = 10
DEFAULT_RECIPIENT = "wolt-market-aze-category@wolt.com"

# Looker field name appended to the explore query when GTIN is not already selected.
LOOKER_GTIN_FIELD = "wolt_market_item.gtin"

# Preferred Excel column order (missing columns are skipped gracefully).
OUTPUT_COLUMN_ORDER = (
    DEFAULT_CATEGORY_COLUMN,
    DEFAULT_ITEM_NAME_COLUMN,
    DEFAULT_GTIN_COLUMN,
    "Product code",
    DEFAULT_CONTRIBUTOR_COLUMN,
    DEFAULT_SHRINKAGE_COLUMN,
    "Shrink units",
    "Units sold (3M)",
)

EXCLUDED_CATEGORIES = (
    "Herbs",
    "herbs",
    "HERBS",
    "Fruits & Vegetables",
    "Fruits and Vegetables",
    "FnV",
    "F&V",
)

DEFAULT_ON_BEHALF_NAME = "Nurlan Rasulov"
DEFAULT_ON_BEHALF_EMAIL = "nurlan.rasulov@wolt.com"


def email_body(*, name: str, email: str) -> str:
    return f"""Salam,

Keçən 3 ay üzrə shrink-ə ən böyük töhfə verən top 10 məhsulun siyahısı əlavədədir.
Herbs və Fruits & Vegetables (FnV) kateqoriyaları hesabata daxil edilməyib.

Zəhmət olmasa, nəzərdən keçirin.

--
Bu məktub {name} ({email}) adından avtomatik assistent vasitəsilə göndərilib.
Sent automatically on behalf of {name}.
"""
