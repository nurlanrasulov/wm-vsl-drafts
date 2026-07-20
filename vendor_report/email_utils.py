"""Email delivery for vendor reports."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path


def load_smtp_config() -> dict[str, str | int]:
    required = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise SystemExit(
            "Missing SMTP configuration in .env:\n  "
            + ", ".join(missing)
            + "\nAdd SMTP settings to .env (see .env.example)."
        )

    port_raw = os.environ.get("SMTP_PORT", "587")
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise SystemExit(f"Invalid SMTP_PORT: {port_raw}") from exc

    return {
        "host": os.environ["SMTP_HOST"],
        "port": port,
        "user": os.environ["SMTP_USER"],
        "password": os.environ["SMTP_PASSWORD"],
        "from_addr": os.environ["SMTP_FROM"],
        "use_tls": os.environ.get("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"},
    }


def send_report_email(
    *,
    subject: str,
    body: str,
    recipients: list[str],
    attachments: list[tuple[str, bytes]],
    dry_run: bool = False,
) -> None:
    if not recipients:
        raise SystemExit("No email recipients configured.")

    if dry_run:
        print("\nDry run — email not sent.")
        print(f"  To: {', '.join(recipients)}")
        print(f"  Subject: {subject}")
        print(f"  Attachments: {', '.join(name for name, _ in attachments)}")
        return

    config = load_smtp_config()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = str(config["from_addr"])
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    for filename, data in attachments:
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            maintype, subtype = "application", "pdf"
        elif ext in {".xlsx", ".xls"}:
            maintype, subtype = (
                "application",
                "vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            maintype, subtype = "application", "octet-stream"
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

    host = str(config["host"])
    port = int(config["port"])
    user = str(config["user"])
    password = str(config["password"])
    use_tls = bool(config["use_tls"])

    if use_tls:
        with smtplib.SMTP(host, port, timeout=60) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(user, password)
            server.send_message(message)
    else:
        with smtplib.SMTP_SSL(host, port, timeout=60, context=ssl.create_default_context()) as server:
            server.login(user, password)
            server.send_message(message)

    print(f"\nEmail sent to {', '.join(recipients)}")
