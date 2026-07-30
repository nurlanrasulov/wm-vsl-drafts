#!/usr/bin/env python3
"""Email top 10 biggest shrink contributors (3M) to the category team every Monday."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shrink_report.config import (  # noqa: E402
    DEFAULT_CATEGORY_COLUMN,
    DEFAULT_CONTRIBUTOR_COLUMN,
    DEFAULT_GTIN_COLUMN,
    DEFAULT_ON_BEHALF_EMAIL,
    DEFAULT_ON_BEHALF_NAME,
    DEFAULT_RECIPIENT,
    DEFAULT_SOLD_UNITS_COLUMN,
    DEFAULT_TOP_N,
    EXCLUDED_CATEGORIES,
    FILTER_OVERRIDES,
    LOOKER_GTIN_FIELD,
    LOOKER_SOLD_UNITS_FIELD,
    OUTPUT_COLUMN_ORDER,
    email_body,
)
from shrink_report.excel_utils import format_shrink_report  # noqa: E402
from shrink_report.looker_query import download_shrink_xlsx  # noqa: E402
from shrink_report.week_utils import last_week_start, parse_week_start, report_basename  # noqa: E402
from vendor_report.email_utils import send_report_email  # noqa: E402
from vendor_report.looker_client import (  # noqa: E402
    init_sdk,
    validate_looker_connection,
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
        description=(
            "Download WM AZE shrink data from Looker, "
            "select top 10 biggest contributors by 3-month shrink value (Herbs and FnV excluded), "
            "and email the category team."
        )
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
        default=ROOT / "output" / "shrink-reports",
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
    env_value = os.environ.get("SHRINK_REPORT_RECIPIENT", DEFAULT_RECIPIENT)
    return [email.strip() for email in env_value.split(",") if email.strip()]


def resolve_week_start(args: argparse.Namespace) -> date:
    if args.week_start:
        return parse_week_start(args.week_start)
    return last_week_start()


def resolve_query_slug() -> str | None:
    slug = os.environ.get("SHRINK_REPORT_QUERY_SLUG", "").strip()
    return slug or None


def resolve_contributor_column() -> str:
    return os.environ.get("SHRINK_REPORT_CONTRIBUTOR_COLUMN", DEFAULT_CONTRIBUTOR_COLUMN)


def resolve_category_column() -> str:
    return os.environ.get("SHRINK_REPORT_CATEGORY_COLUMN", DEFAULT_CATEGORY_COLUMN)


def resolve_gtin_column() -> str:
    return os.environ.get("SHRINK_REPORT_GTIN_COLUMN", DEFAULT_GTIN_COLUMN)


def resolve_sold_units_column() -> str:
    return os.environ.get("SHRINK_REPORT_SOLD_UNITS_COLUMN", DEFAULT_SOLD_UNITS_COLUMN)


def resolve_looker_field_additions() -> list[str]:
    additions = [LOOKER_GTIN_FIELD, LOOKER_SOLD_UNITS_FIELD]
    extra = os.environ.get("SHRINK_REPORT_LOOKER_FIELD_ADDITIONS", "")
    additions.extend(field.strip() for field in extra.split(",") if field.strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for field in additions:
        if field not in seen:
            deduped.append(field)
            seen.add(field)
    return deduped


def resolve_top_n() -> int:
    raw = os.environ.get("SHRINK_REPORT_TOP_N", str(DEFAULT_TOP_N))
    try:
        return int(raw)
    except ValueError as exc:
        raise SystemExit(f"Invalid SHRINK_REPORT_TOP_N: {raw}") from exc


def generate_report(*, output_dir: Path, week_start: date) -> tuple[str, bytes]:
    output_dir.mkdir(parents=True, exist_ok=True)

    sdk = init_sdk()
    me = validate_looker_connection(sdk)
    print(f"Looker connected as {me.get('display_name') or me.get('email')}")

    report_name = f"{report_basename(week_start)}.xlsx"
    query_slug = resolve_query_slug()

    print("\nDownloading shrink data from Looker...")
    xlsx_raw = download_shrink_xlsx(
        sdk,
        query_slug=query_slug,
        filter_overrides=FILTER_OVERRIDES,
        field_additions=resolve_looker_field_additions() if query_slug else None,
    )

    contributor_column = resolve_contributor_column()
    category_column = resolve_category_column()
    gtin_column = resolve_gtin_column()
    top_n = resolve_top_n()

    print(
        f"  Top {top_n} by {contributor_column!r} (descending), "
        f"excluding {', '.join(EXCLUDED_CATEGORIES)}, including {gtin_column!r}"
    )
    xlsx_data = format_shrink_report(
        xlsx_raw,
        contributor_column=contributor_column,
        category_column=category_column,
        gtin_column=gtin_column,
        excluded_categories=EXCLUDED_CATEGORIES,
        top_n=top_n,
        output_column_order=OUTPUT_COLUMN_ORDER,
    )
    (output_dir / report_name).write_bytes(xlsx_data)
    print(f"  Saved {report_name}")

    return report_name, xlsx_data


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
    subject = report_basename(week_start)

    print(f"Week start: {week_start.strftime('%d.%m.%Y')}")
    print(f"Subject: {subject}")
    print(f"Recipients: {', '.join(recipients)}")

    attachment = generate_report(output_dir=args.output_dir, week_start=week_start)

    if args.skip_email:
        print("\nSkipping email (--skip-email).")
        return

    on_behalf_name = os.environ.get("ON_BEHALF_NAME", DEFAULT_ON_BEHALF_NAME)
    on_behalf_email = os.environ.get("ON_BEHALF_EMAIL", DEFAULT_ON_BEHALF_EMAIL)

    send_report_email(
        subject=subject,
        body=email_body(name=on_behalf_name, email=on_behalf_email),
        recipients=recipients,
        attachments=[attachment],
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
