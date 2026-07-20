#!/usr/bin/env python3
"""Save and validate Fulfillment Bearer token in .env."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
BASE_URL = "https://fulfillment.wolt.com"


def read_clipboard() -> str | None:
    try:
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            text=True,
            check=False,
        )
        text = (result.stdout or "").strip()
        return text or None
    except OSError:
        return None


def normalize_token(raw: str) -> str:
    token = raw.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def looks_like_token(token: str) -> bool:
    return len(token) > 40 and token.count(".") >= 2


def write_env(token: str) -> None:
    ENV_FILE.write_text(f"FULFILLMENT_BEARER_TOKEN={token}\n")
    ENV_FILE.chmod(0o600)


def validate_token(token: str) -> None:
    response = requests.post(
        f"{BASE_URL}/assortment/public/v1/offers-summary/search",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={
            "countryCode": "AZE",
            "q": "DTGHY",
            "filters": {"venueCodes": ["WM_YASAMAL"]},
            "meta": {"page": 0, "pageSize": 1},
        },
        timeout=30,
    )
    if response.status_code == 401:
        raise SystemExit("Token rejected (401). Copy a fresh Bearer token from Fulfillment DevTools.")
    if response.status_code >= 400:
        raise SystemExit(f"Auth check failed ({response.status_code}): {response.text[:300]}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configure Fulfillment API auth token.")
    parser.add_argument(
        "token",
        nargs="?",
        help="Bearer token (optional; reads --clipboard or stdin if omitted)",
    )
    parser.add_argument(
        "--clipboard",
        action="store_true",
        help="Read token from macOS clipboard",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Save token without validating against the API",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = args.token

    if not token and args.clipboard:
        token = read_clipboard()

    if not token and not sys.stdin.isatty():
        token = sys.stdin.read()

    if token:
        token = normalize_token(token)
    else:
        print(
            "Paste your Fulfillment Bearer token (from DevTools → Network → Authorization header).\n"
            "Press Enter, then Ctrl+D when done:\n",
            file=sys.stderr,
        )
        token = normalize_token(sys.stdin.read())

    if not looks_like_token(token):
        raise SystemExit(
            "That doesn't look like a JWT Bearer token.\n"
            "Copy the value after 'Bearer ' from any fulfillment.wolt.com API request."
        )

    if not args.skip_check:
        print("Validating token...")
        validate_token(token)
        print("Token OK.")

    write_env(token)
    print(f"Saved to {ENV_FILE} (mode 600).")


if __name__ == "__main__":
    main()
