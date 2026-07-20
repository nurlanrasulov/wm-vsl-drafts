#!/usr/bin/env python3
"""Pause WM AZE products as Sold Out in Fulfillment Store Assortment."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://fulfillment.wolt.com"
DEFAULT_COUNTRY = "AZE"
DEFAULT_VENUES = [
    "WM_BINEGEDI",
    "WM_KHALGLAR",
    "WM_LANDMARK",
    "WM_NASIMI",
    "WM_YASAMAL",
]

SOLD_OUT_TRIGGER = {
    "type": "OUT_OF_STOCK",
    "newState": "PAUSED",
    "activationTime": None,
}


@dataclass
class OfferTarget:
    offer_id: str
    venue_code: str
    venue_name: str
    product_code: str
    product_name: str
    current_state: str


class FulfillmentClient:
    def __init__(self, token: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.session.request(method, f"{BASE_URL}{path}", timeout=60, **kwargs)
        if response.status_code >= 400:
            detail = response.text[:500]
            raise RuntimeError(f"{method} {path} failed ({response.status_code}): {detail}")
        if not response.content:
            return None
        return response.json()

    def search_offers(
        self,
        *,
        country_code: str,
        query: str,
        venue_codes: list[str],
        page: int = 0,
        page_size: int = 100,
    ) -> dict[str, Any]:
        body = {
            "countryCode": country_code,
            "q": query,
            "filters": {"venueCodes": venue_codes},
            "meta": {"page": page, "pageSize": page_size},
        }
        return self._request("POST", "/assortment/public/v1/offers-summary/search", json=body)

    def get_offer(self, offer_id: str) -> dict[str, Any]:
        return self._request("GET", f"/assortment/public/v1/offers/{offer_id}")

    def pause_offer_sold_out(self, offer_id: str, offer: dict[str, Any]) -> None:
        body = {
            "venueId": offer["venueId"],
            "primaryCategoryId": offer["primaryCategory"]["id"],
            "additionalCategoryIds": [c["id"] for c in offer.get("additionalCategories", [])],
            "salesModeV2": offer["salesModeV2"],
            "price": offer["price"],
            "state": offer["state"],
            "stateChangeTrigger": SOLD_OUT_TRIGGER,
            "maxQuantityPerPurchase": offer.get("maxQuantityPerPurchase"),
            "weeklyAvailability": offer.get("weeklyAvailability"),
            "weeklyVisibility": offer.get("weeklyVisibility"),
            "inventoryMode": offer.get("inventoryMode", "LIMITED_QUANTITY"),
            "version": offer.get("version", 0),
        }
        self._request("PUT", f"/assortment/public/v1/offers/{offer_id}", json=body)

    def bulk_pause_sold_out(
        self,
        *,
        country_code: str,
        offer_ids: list[str],
    ) -> dict[str, Any]:
        body = {
            "countryCode": country_code,
            "offerIds": offer_ids,
            "changes": {
                "offerStateChangeTrigger": {
                    "isModified": True,
                    "value": SOLD_OUT_TRIGGER,
                }
            },
        }
        return self._request(
            "POST",
            "/assortment/public/v3/bulk-operations/edit-offers",
            json=body,
        )


def load_token(explicit: str | None) -> str:
    token = explicit or os.environ.get("FULFILLMENT_BEARER_TOKEN")
    if token:
        return token.strip()

    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("FULFILLMENT_BEARER_TOKEN="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value

    raise SystemExit(
        "Missing Fulfillment auth token.\n"
        "Set FULFILLMENT_BEARER_TOKEN in .env or pass --token.\n"
        "See .env.example for setup steps."
    )


def collect_offers_for_code(
    client: FulfillmentClient,
    *,
    product_code: str,
    country_code: str,
    venue_codes: list[str],
) -> list[OfferTarget]:
    targets: list[OfferTarget] = []
    page = 0

    while True:
        result = client.search_offers(
            country_code=country_code,
            query=product_code,
            venue_codes=venue_codes,
            page=page,
        )
        items = result.get("items", [])
        for item in items:
            product = item.get("product") or {}
            code = product.get("code") or product.get("productCode") or ""
            if code.upper() != product_code.upper():
                continue
            name = ""
            names = product.get("name") or product.get("productName") or []
            if isinstance(names, list) and names:
                name = names[0].get("value") or names[0].get("name") or ""
            elif isinstance(names, str):
                name = names

            for row in item.get("offers") or []:
                offer = row.get("offer") or row
                venue = offer.get("venue") or {}
                venue_code = venue.get("code") or venue.get("venueCode") or ""
                if venue_codes and venue_code not in venue_codes:
                    continue
                targets.append(
                    OfferTarget(
                        offer_id=offer["id"],
                        venue_code=venue_code,
                        venue_name=venue.get("name") or venue_code,
                        product_code=code,
                        product_name=name,
                        current_state=offer.get("state") or "?",
                    )
                )

        page_info = result.get("page") or {}
        if len(items) < page_info.get("pageSize", 20):
            break
        page += 1

    return targets


def pause_targets(
    client: FulfillmentClient,
    targets: list[OfferTarget],
    *,
    country_code: str,
    dry_run: bool,
    use_bulk: bool,
) -> None:
    if not targets:
        print("No matching offers found.")
        return

    print(f"Found {len(targets)} offer(s) to pause:")
    for target in targets:
        print(
            f"  - {target.product_code} @ {target.venue_code} "
            f"({target.venue_name}) state={target.current_state}"
        )

    if dry_run:
        print("\nDry run — no changes applied.")
        return

    if use_bulk and len(targets) > 1:
        offer_ids = [t.offer_id for t in targets]
        result = client.bulk_pause_sold_out(country_code=country_code, offer_ids=offer_ids)
        print(f"\nBulk pause submitted: {json.dumps(result, indent=2)}")
        return

    for target in targets:
        offer = client.get_offer(target.offer_id)
        if offer.get("state") == "PAUSED" and (
            (offer.get("stateChangeTrigger") or {}).get("type") == "OUT_OF_STOCK"
        ):
            print(f"  skip {target.venue_code}: already paused (sold out)")
            continue
        client.pause_offer_sold_out(target.offer_id, offer)
        print(f"  paused {target.venue_code}: sold out")
        time.sleep(0.2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pause WM AZE products as Sold Out in Fulfillment Store Assortment."
    )
    parser.add_argument(
        "product_codes",
        nargs="+",
        help="Product code(s), e.g. DTGHY-61043",
    )
    parser.add_argument(
        "--country",
        default=DEFAULT_COUNTRY,
        help=f"Country code (default: {DEFAULT_COUNTRY})",
    )
    parser.add_argument(
        "--venues",
        nargs="*",
        default=DEFAULT_VENUES,
        help="Venue codes to update (default: all WM AZE stores except Baku)",
    )
    parser.add_argument(
        "--token",
        help="Fulfillment Bearer token (overrides FULFILLMENT_BEARER_TOKEN)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be paused without making changes",
    )
    parser.add_argument(
        "--no-bulk",
        action="store_true",
        help="Pause offers one-by-one instead of bulk edit",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = load_token(args.token)
    client = FulfillmentClient(token)

    all_targets: list[OfferTarget] = []
    for code in args.product_codes:
        print(f"\nSearching for {code}...")
        targets = collect_offers_for_code(
            client,
            product_code=code,
            country_code=args.country,
            venue_codes=args.venues,
        )
        if not targets:
            print(f"  No offers found for {code}")
        all_targets.extend(targets)

    # Deduplicate by offer id
    seen: set[str] = set()
    unique_targets = []
    for target in all_targets:
        if target.offer_id in seen:
            continue
        seen.add(target.offer_id)
        unique_targets.append(target)

    pause_targets(
        client,
        unique_targets,
        country_code=args.country,
        dry_run=args.dry_run,
        use_bulk=not args.no_bulk,
    )


if __name__ == "__main__":
    main()
