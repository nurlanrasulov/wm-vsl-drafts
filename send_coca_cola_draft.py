#!/usr/bin/env python3
"""Send the COCA COLA VSL REPORT Gmail draft every Monday."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gmail_draft.mailapp import EXCLUDED_RECIPIENT, send_via_mailapp

DEFAULT_DRAFT_SUBJECT = "COCA COLA VSL REPORT"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find a Gmail draft by subject, remove Wolt analytics address, and send."
    )
    parser.add_argument(
        "--subject",
        default=DEFAULT_DRAFT_SUBJECT,
        help=f'Draft subject to match (default: "{DEFAULT_DRAFT_SUBJECT}")',
    )
    parser.add_argument(
        "--exclude",
        default=EXCLUDED_RECIPIENT,
        help=f"Recipient to remove before sending (default: {EXCLUDED_RECIPIENT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent without sending",
    )
    parser.add_argument(
        "--resend",
        action="store_true",
        help="Resend the latest sent message (when no draft exists)",
    )
    parser.add_argument(
        "--via",
        choices=("auto", "mailapp", "gmail-api"),
        default="auto",
        help="Send via Mail.app (default/auto) or Gmail API",
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Validate Gmail API connection and exit",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.check_auth:
        from gmail_draft.client import validate_gmail_connection

        email = validate_gmail_connection()
        print(f"Gmail auth OK: {email}")
        return

    print(f'Looking for draft: "{args.subject}"')
    print(f"Excluding recipient: {args.exclude}")

    if args.resend:
        from gmail_draft.client import send_sent_message_again

        result = send_sent_message_again(
            subject_query=args.subject,
            exclude_email=args.exclude,
            dry_run=args.dry_run,
        )
        if result["action"] == "dry_run":
            print("\nDry run — message not sent.")
            print(f"  Source message: {result['source_message_id']}")
            print(f"  Recipients after exclusion: {result['recipients_after']}")
            return
        print("\nSent again from Sent folder via Gmail API.")
        print(f"  Message id: {result.get('message_id', '')}")
        print(f"  Recipients: {result['recipients_after']}")
        return

    use_mailapp = args.via in {"auto", "mailapp"}
    if use_mailapp:
        try:
            result = send_via_mailapp(
                subject_query=args.subject,
                exclude_email=args.exclude,
                dry_run=args.dry_run,
            )
            if result["action"] == "dry_run":
                print("\nDry run — draft not sent.")
                print(f"  Account: {result['account']}")
                print(f"  Recipients after exclusion: {result['recipients_after']}")
                return
            print("\nDraft sent via Mail.app.")
            print(f"  Account: {result['account']}")
            print(f"  Recipients: {result['recipients_after']}")
            return
        except RuntimeError as exc:
            if args.via == "mailapp":
                raise SystemExit(str(exc)) from exc
            print(f"Mail.app failed ({exc}); trying Gmail API...")

    from gmail_draft.client import send_draft_excluding_recipient

    result = send_draft_excluding_recipient(
        subject_query=args.subject,
        exclude_email=args.exclude,
        dry_run=args.dry_run,
    )

    if result["action"] == "dry_run":
        print("\nDry run — draft not sent.")
        print(f"  Draft id: {result['draft_id']}")
        print(f"  Recipients after exclusion: {result['recipients_after']}")
        return

    print("\nDraft sent via Gmail API.")
    print(f"  Message id: {result.get('message_id', '')}")
    print(f"  Recipients: {result['recipients_after']}")


if __name__ == "__main__":
    main()
