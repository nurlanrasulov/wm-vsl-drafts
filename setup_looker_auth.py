#!/usr/bin/env python3
"""Configure Looker API credentials in .env for vendor reports."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

import looker_sdk

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
DEFAULT_BASE_URL = "https://looker.wolt.com"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    for line in ENV_FILE.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_looker_env(base_url: str, client_id: str, client_secret: str) -> None:
    existing = read_env()
    lines: list[str] = []
    looker_keys = {
        "LOOKERSDK_BASE_URL": base_url,
        "LOOKERSDK_CLIENT_ID": client_id,
        "LOOKERSDK_CLIENT_SECRET": client_secret,
        "LOOKERSDK_VERIFY_SSL": "true",
    }

    written_keys: set[str] = set()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if not line or line.startswith("#") or "=" not in line:
                lines.append(line)
                continue
            key = line.split("=", 1)[0].strip()
            if key in looker_keys:
                lines.append(f"{key}={looker_keys[key]}")
                written_keys.add(key)
            else:
                lines.append(line)

    for key, value in looker_keys.items():
        if key not in written_keys:
            lines.append(f"{key}={value}")

    if not ENV_FILE.exists():
        lines = [f"{key}={value}" for key, value in looker_keys.items()] + lines

    ENV_FILE.write_text("\n".join(lines).rstrip() + "\n")
    ENV_FILE.chmod(0o600)


def validate_credentials(base_url: str, client_id: str, client_secret: str) -> None:
    import os

    os.environ["LOOKERSDK_BASE_URL"] = base_url
    os.environ["LOOKERSDK_CLIENT_ID"] = client_id
    os.environ["LOOKERSDK_CLIENT_SECRET"] = client_secret
    os.environ["LOOKERSDK_VERIFY_SSL"] = "true"

    sdk = looker_sdk.init40()
    me = sdk.me()
    print(f"Looker auth OK: {me.email or me.display_name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configure Looker API credentials.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Looker instance URL")
    parser.add_argument("--client-id", help="Looker API3 client id")
    parser.add_argument("--client-secret", help="Looker API3 client secret")
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Save credentials without validating against Looker",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    existing = read_env()

    base_url = args.base_url or existing.get("LOOKERSDK_BASE_URL", DEFAULT_BASE_URL)
    client_id = args.client_id or existing.get("LOOKERSDK_CLIENT_ID")
    client_secret = args.client_secret or existing.get("LOOKERSDK_CLIENT_SECRET")

    if not client_id:
        client_id = input("Looker API3 client id: ").strip()
    if not client_secret:
        client_secret = getpass.getpass("Looker API3 client secret: ").strip()

    if not client_id or not client_secret:
        raise SystemExit("Client id and client secret are required.")

    if not args.skip_check:
        print("Validating Looker credentials...")
        validate_credentials(base_url, client_id, client_secret)

    write_looker_env(base_url, client_id, client_secret)
    print(f"Saved Looker credentials to {ENV_FILE}")


if __name__ == "__main__":
    main()
