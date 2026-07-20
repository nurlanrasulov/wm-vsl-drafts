#!/usr/bin/env python3
"""One-time Gmail OAuth setup for draft automation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gmail_draft.client import CREDENTIALS_FILE, validate_gmail_connection

SETUP_STEPS = """
Gmail API setup (one time):

1. Open https://console.cloud.google.com/
2. Create a project (or pick an existing one)
3. Enable "Gmail API" (APIs & Services → Library → Gmail API → Enable)
4. Configure OAuth consent screen (External or Internal, add your email as test user)
5. Create OAuth client:
   - APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: Desktop app
   - Download JSON and save as:
       gmail_credentials.json
     in this project folder:
       {root}

6. Run this script again:
       python3 setup_gmail_auth.py

A browser window will open — sign in with the Gmail account that holds the draft.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configure Gmail API OAuth for draft sending.")
    parser.add_argument(
        "--instructions",
        action="store_true",
        help="Print Google Cloud setup steps",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.instructions:
        print(SETUP_STEPS.format(root=ROOT))
        return

    if not CREDENTIALS_FILE.exists():
        print(SETUP_STEPS.format(root=ROOT))
        raise SystemExit(f"\nMissing {CREDENTIALS_FILE.name} — follow the steps above.")

    print("Opening browser for Gmail authorization...")
    email = validate_gmail_connection()
    print(f"Gmail auth OK: {email}")
    print("Token saved to gmail_token.json")


if __name__ == "__main__":
    main()
