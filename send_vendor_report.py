#!/usr/bin/env python3
"""Generate and email weekly Unilever ice cream vendor reports from Looker."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vendor_report.config import (  # noqa: E402
    DEFAULT_RECIPIENT,
    EMAIL_BODY,
    REPORT1_DASHBOARD_FILTERS,
    REPORT1_DASHBOARD_ID,
    REPORT2_DASHBOARD_FILTERS,
    REPORT2_DASHBOARD_ID,
    REPORT2_VSL_COLUMN,
    REPORT3_FILTER_OVERRIDES,
    REPORT3_QUERY_SLUG,
)
from vendor_report.email_utils import send_report_email  # noqa: E402
from vendor_report.excel_utils import format_vsl_by_item_report  # noqa: E402
from vendor_report.looker_client import (  # noqa: E402
    download_dashboard_pdf,
    download_dashboard_xlsx,
    download_explore_xlsx,
    init_sdk,
    validate_looker_connection,
)
from vendor_report.week_utils import (  # noqa: E402
    last_week_start,
    parse_week_start,
    report1_basename,
    report2_basename,
    report3_basename,
)


def load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Unilever vendor reports from Looker and email them."
    )
    parser.add_argument(
        "--recipients",
        nargs="+",
        default=None,
        help=f"Email recipient(s) (default: {DEFAULT_RECIPIENT})",
    )
    parser.add_argument(
        "--week-start",
        help="Override week start date (DD.MM.YYYY) for file naming",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "vendor-reports",
        help="Directory to save generated files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate files but do not send email",
    )
    parser.add_argument(
        "--skip-email",
        action="store_true",
        help="Only generate files, skip email entirely",
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Validate Looker API credentials and exit",
    )
    return parser.parse_args()


def resolve_recipients(args: argparse.Namespace) -> list[str]:
    if args.recipients:
        return args.recipients
    env_value = os.environ.get("VENDOR_REPORT_RECIPIENT", DEFAULT_RECIPIENT)
    return [email.strip() for email in env_value.split(",") if email.strip()]


def resolve_week_start(args: argparse.Namespace) -> date:
    if args.week_start:
        return parse_week_start(args.week_start)
    return last_week_start()


def generate_reports(
    *,
    output_dir: Path,
    week_start: date,
) -> list[tuple[str, bytes]]:
    output_dir.mkdir(parents=True, exist_ok=True)

    sdk = init_sdk()
    me = validate_looker_connection(sdk)
    print(f"Looker connected as {me.get('display_name') or me.get('email')}")

    report1_name = f"{report1_basename(week_start)}.pdf"
    report2_name = f"{report2_basename(week_start)}.xlsx"
    report3_name = f"{report3_basename()}.xlsx"

    print("\n1/3 Downloading VSL dashboard PDF...")
    pdf_data = download_dashboard_pdf(
        sdk,
        dashboard_id=REPORT1_DASHBOARD_ID,
        dashboard_filters=REPORT1_DASHBOARD_FILTERS,
    )
    (output_dir / report1_name).write_bytes(pdf_data)
    print(f"  Saved {report1_name}")

    print("\n2/3 Downloading VSL by item Excel...")
    xlsx_raw = download_dashboard_xlsx(
        sdk,
        dashboard_id=REPORT2_DASHBOARD_ID,
        dashboard_filters=REPORT2_DASHBOARD_FILTERS,
        prefer_column=REPORT2_VSL_COLUMN,
    )
    xlsx_data = format_vsl_by_item_report(xlsx_raw, REPORT2_VSL_COLUMN)
    (output_dir / report2_name).write_bytes(xlsx_data)
    print(f"  Saved {report2_name}")

    print("\n3/3 Downloading paused items Excel...")
    paused_data = download_explore_xlsx(
        sdk,
        query_slug=REPORT3_QUERY_SLUG,
        filter_overrides=REPORT3_FILTER_OVERRIDES,
    )
    (output_dir / report3_name).write_bytes(paused_data)
    print(f"  Saved {report3_name}")

    return [
        (report1_name, pdf_data),
        (report2_name, xlsx_data),
        (report3_name, paused_data),
    ]


def main() -> None:
    load_dotenv()
    args = parse_args()

    if args.check_auth:
        sdk = init_sdk()
        me = validate_looker_connection(sdk)
        print(f"Looker auth OK: {me.get('email') or me.get('display_name')}")
        return

    week_start = resolve_week_start(args)
    recipients = resolve_recipients(args)
    subject = report1_basename(week_start)

    print(f"Week start: {week_start.strftime('%d.%m.%Y')}")
    print(f"Subject: {subject}")

    attachments = generate_reports(output_dir=args.output_dir, week_start=week_start)

    if args.skip_email:
        print("\nSkipping email (--skip-email).")
        return

    send_report_email(
        subject=subject,
        body=EMAIL_BODY,
        recipients=recipients,
        attachments=attachments,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
