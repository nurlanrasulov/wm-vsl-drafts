"""Send Gmail drafts via macOS Mail.app (no Google Cloud setup)."""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "send_via_mailapp.applescript"
DEFAULT_DRAFT_SUBJECT = "COCA COLA VSL REPORT"
EXCLUDED_RECIPIENT = "no-reply.analytics@wolt.com"


def send_via_mailapp(
    *,
    subject_query: str = DEFAULT_DRAFT_SUBJECT,
    exclude_email: str = EXCLUDED_RECIPIENT,
    dry_run: bool = False,
) -> dict[str, str]:
    if not SCRIPT.exists():
        raise RuntimeError(f"Missing Mail.app script: {SCRIPT}")

    args = ["osascript", str(SCRIPT), subject_query, exclude_email]
    if dry_run:
        args.append("dry-run")

    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown Mail.app error").strip()
        raise RuntimeError(detail)

    output = (result.stdout or "").strip()
    if "|" not in output:
        raise RuntimeError(f"Unexpected Mail.app response: {output}")

    action, account, recipients = output.split("|", 2)
    return {
        "action": "dry_run" if action == "DRY_RUN" else "sent",
        "account": account,
        "recipients_after": recipients,
    }
