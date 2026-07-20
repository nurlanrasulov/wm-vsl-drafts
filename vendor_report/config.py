"""Static configuration for Unilever ice cream vendor reports."""

from __future__ import annotations

REPORT1_DASHBOARD_ID = "41907"
REPORT2_DASHBOARD_ID = "52925"
REPORT3_QUERY_SLUG = "8bZ6NWIZNplilZfGKJRZlH"

VENDOR_NAME = "Safe Trade 2024"
COUNTRY = "AZE"
PURCHASE_ORDER_GROUP = "icecream"
VENDOR_CODE = "Safe1"

DEFAULT_RECIPIENT = "sh.bayramov@safetrade.az"

EMAIL_BODY = """Salam Şaiq bəy,
Əlavədə keçən həftənin sifariş qarşılanma göstəriciləri və müvəqqəti deaktiv edilmiş məhsulların siyahısı qeyd edilib.
Zəhmət olmasa, nəzərdən keçirərsiniz, hərhansı sualınız olarsa mənimlə əlaqə saxlaya bilərsiniz."""

# Dashboard filter strings use Looker UI display names (URL query format).
REPORT1_DASHBOARD_FILTERS = (
    f"Country={COUNTRY}"
    f"&Vendor Name={VENDOR_NAME}"
    f"&Expected Delivery Date=last week"
    f"&Purchase Order Group={PURCHASE_ORDER_GROUP}"
)

REPORT2_DASHBOARD_FILTERS = (
    "Expected Delivery Date=last week"
    f"&Vendor Name={VENDOR_NAME}"
    f"&Country={COUNTRY}"
    "&Deleted (Yes / No)=No"
    "&Status=-DELISTED"
    f"&Purchase Order Group={PURCHASE_ORDER_GROUP}"
)

# Explore filter overrides keyed by Looker filter field names.
# Keys are resolved at runtime from the saved query when possible.
REPORT3_FILTER_OVERRIDES: dict[str, str] = {
    "country": COUNTRY,
    "wolt_market_item.is_enabled": "yes,no",
    "wolt_market_item.is_removed": "yes,no",
    "vendor_offering.status": "AVAILABLE,AVAILABLE_LATER",
    "vendor.code": VENDOR_CODE,
    "wolt_market_item_metrics.is_reduce_to_clear": "No",
    "assortment_offer_variant.state": "PAUSED",
    "vendor_offering.purchase_order_group": PURCHASE_ORDER_GROUP,
}

REPORT2_VSL_COLUMN = "Vendor service level"
