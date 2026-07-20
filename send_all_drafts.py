#!/usr/bin/env python3
"""Send all Gmail drafts: remove Wolt analytics, fix inline images, add on-behalf signature."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send Gmail drafts whose subject matches a filter (default: VSL REPORT)."
    )
    parser.add_argument(
        "--subject-contains",
        default=None,
        help='Only send drafts whose subject includes this text (default: "VSL REPORT")',
    )
    parser.add_argument(
        "--all-drafts",
        action="store_true",
        help="Send every draft (ignore subject filter — use with care)",
    )
    parser.add_argument(
        "--exclude",
        default=None,
        help="Recipient to remove (default: no-reply.analytics@wolt.com)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview all drafts without sending",
    )
    parser.add_argument(
        "--on-behalf-name",
        default=None,
        help="Name shown in signature (default: Nurlan Rasulov)",
    )
    parser.add_argument(
        "--on-behalf-email",
        default=None,
        help="Email shown in signature (default: nurlan.rasulov@wolt.com)",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    from gmail_draft.client import send_all_drafts
    from gmail_draft.config import DRAFT_SUBJECT_CONTAINS, EXCLUDED_RECIPIENT, ON_BEHALF_EMAIL, ON_BEHALF_NAME

    exclude = args.exclude or EXCLUDED_RECIPIENT
    name = args.on_behalf_name or os.environ.get("ON_BEHALF_NAME", ON_BEHALF_NAME)
    email = args.on_behalf_email or os.environ.get("ON_BEHALF_EMAIL", ON_BEHALF_EMAIL)
    if args.all_drafts:
        subject_filter = None
    else:
        subject_filter = (
            args.subject_contains
            or os.environ.get("DRAFT_SUBJECT_CONTAINS", DRAFT_SUBJECT_CONTAINS)
        )

    print(f"Excluding: {exclude}")
    print(f"On behalf of: {name} <{email}>")
    if subject_filter:
        print(f'Subject filter: contains "{subject_filter}"')
    else:
        print("Subject filter: none (all drafts)")
    if args.dry_run:
        print("Mode: dry run\n")

    results = send_all_drafts(
        exclude_email=exclude,
        dry_run=args.dry_run,
        on_behalf_name=name,
        on_behalf_email=email,
        subject_contains=subject_filter,
    )

    sent = dry = skipped = errors = 0
    for item in results:
        action = item.get("action", "")
        subject = item.get("subject", "?")
        if action == "sent":
            sent += 1
            print(f"✓ Sent: {subject}")
            print(f"    → {item.get('recipients_after', '')}")
        elif action == "dry_run":
            dry += 1
            print(f"• Preview: {subject}")
            print(f"    → {item.get('recipients_after', '')}")
        elif action == "skipped":
            skipped += 1
            print(f"– Skipped: {subject} ({item.get('reason', '')})")
        else:
            errors += 1
            print(f"✗ Error: {subject} ({item.get('reason', '')})")

    print(
        f"\nDone: {sent} sent, {dry} previewed, {skipped} skipped, {errors} errors "
        f"(total {len(results)} drafts)"
    )


if __name__ == "__main__":
    main()
