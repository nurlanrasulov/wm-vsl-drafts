#!/usr/bin/env python3
"""Print or upload GitHub Actions secrets for cloud draft sending."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CREDENTIALS_FILE = ROOT / "gmail_credentials.json"
TOKEN_FILE = ROOT / "gmail_token.json"


def load_client() -> tuple[str, str]:
    if not CREDENTIALS_FILE.exists():
        raise SystemExit(f"Missing {CREDENTIALS_FILE.name}. Run: python3 setup_gmail_auth.py")
    data = json.loads(CREDENTIALS_FILE.read_text())
    installed = data.get("installed") or data.get("web") or data
    client_id = installed["client_id"]
    client_secret = installed["client_secret"]
    return client_id, client_secret


def load_refresh_token() -> str:
    if not TOKEN_FILE.exists():
        raise SystemExit(f"Missing {TOKEN_FILE.name}. Run: python3 setup_gmail_auth.py")
    data = json.loads(TOKEN_FILE.read_text())
    token = data.get("refresh_token")
    if not token:
        raise SystemExit("gmail_token.json has no refresh_token. Re-run setup_gmail_auth.py.")
    return token


def gh_available() -> bool:
    try:
        subprocess.run(["gh", "auth", "status"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def set_secret(name: str, value: str) -> None:
    subprocess.run(
        ["gh", "secret", "set", name, "--body", value],
        check=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configure GitHub Actions secrets for VSL draft sending.")
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload secrets to GitHub via gh CLI (repo must exist and gh must be logged in)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client_id, client_secret = load_client()
    refresh_token = load_refresh_token()

    secrets = {
        "GMAIL_CLIENT_ID": client_id,
        "GMAIL_CLIENT_SECRET": client_secret,
        "GMAIL_REFRESH_TOKEN": refresh_token,
        "ON_BEHALF_NAME": "Nurlan Rasulov",
        "ON_BEHALF_EMAIL": "nurlan.rasulov@wolt.com",
    }

    if args.upload:
        if not gh_available():
            raise SystemExit("GitHub CLI (gh) is not logged in. Run: gh auth login")
        for name, value in secrets.items():
            set_secret(name, value)
            print(f"Set secret: {name}")
        print("\nDone. Secrets uploaded to this GitHub repo.")
        return

    print("Add these secrets in GitHub → Settings → Secrets and variables → Actions:\n")
    for name in secrets:
        print(f"  {name}")
    print(
        "\nOr after pushing to GitHub, run:\n"
        "  python3 setup_github_secrets.py --upload\n"
        "\nDo NOT paste secret values in chat or commit them to git."
    )


if __name__ == "__main__":
    main()
