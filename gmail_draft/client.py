"""Gmail API helpers for finding and sending drafts."""

from __future__ import annotations

import base64
import json
import os
import re
from email import message_from_bytes
from email.header import decode_header, make_header
from email.policy import default as email_policy
from email.utils import formataddr, getaddresses
from pathlib import Path
from typing import Any

from gmail_draft.config import (
    EXCLUDED_RECIPIENT,
    ON_BEHALF_EMAIL,
    ON_BEHALF_NAME,
    SIGNATURE_HTML,
    SIGNATURE_MARKER,
    SIGNATURE_TEXT,
    UNSUBSCRIBE_MARKER,
    DRAFT_SUBJECT_CONTAINS,
)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
ROOT = Path(__file__).resolve().parents[1]
CREDENTIALS_FILE = ROOT / "gmail_credentials.json"
TOKEN_FILE = ROOT / "gmail_token.json"

GMAIL_EMBEDDED_IMAGE_RE = re.compile(
    r"""src=(["'])(?:https://mail\.google\.com/mail/[^"']*view=fimg[^"']*"""
    r"""|https://ci\d+\.googleusercontent\.com/meips/[^"']*view=fimg[^"']*)\1""",
    re.IGNORECASE,
)


def get_gmail_service():
    creds = _load_credentials()
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _load_credentials() -> Credentials:
    env_creds = _load_credentials_from_env()
    if env_creds is not None:
        if env_creds.expired and env_creds.refresh_token:
            env_creds.refresh(Request())
        return env_creds

    creds: Credentials | None = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
        TOKEN_FILE.chmod(0o600)
        return creds

    if not CREDENTIALS_FILE.exists():
        raise SystemExit(
            f"Missing {CREDENTIALS_FILE.name}.\n"
            "Run: python3 setup_gmail_auth.py\n"
            "Or set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN for cloud runs."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    TOKEN_FILE.chmod(0o600)
    return creds


def _load_credentials_from_env() -> Credentials | None:
    client_id = os.environ.get("GMAIL_CLIENT_ID")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET")
    refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        token_json = os.environ.get("GMAIL_TOKEN_JSON")
        if token_json:
            data = json.loads(token_json)
            client_id = client_id or data.get("client_id")
            client_secret = client_secret or data.get("client_secret")
            refresh_token = refresh_token or data.get("refresh_token")
        if not all([client_id, client_secret, refresh_token]):
            return None

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def decode_subject(raw_subject: str | None) -> str:
    if not raw_subject:
        return ""
    try:
        return str(make_header(decode_header(raw_subject)))
    except (UnicodeError, ValueError):
        return raw_subject


def find_draft_by_subject(service, subject_query: str) -> dict[str, Any]:
    """Find the most recent draft whose subject matches subject_query."""
    target = subject_query.strip().casefold()
    matches: list[tuple[str, dict[str, Any]]] = []

    response = service.users().drafts().list(userId="me").execute()
    drafts = response.get("drafts", [])

    while True:
        for draft_meta in drafts:
            try:
                draft = service.users().drafts().get(
                    userId="me",
                    id=draft_meta["id"],
                    format="full",
                ).execute()
            except Exception:
                continue
            message = draft.get("message", {})
            headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}
            subject = decode_subject(headers.get("Subject")).casefold()
            if subject == target or target in subject:
                matches.append((message.get("internalDate", "0"), draft))

        page_token = response.get("nextPageToken")
        if not page_token:
            break
        response = service.users().drafts().list(userId="me", pageToken=page_token).execute()
        drafts = response.get("drafts", [])

    if not matches:
        raise RuntimeError(f'No Gmail draft found with subject matching "{subject_query}"')

    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def remove_recipient_from_message(raw_message: bytes, email_to_remove: str) -> bytes:
    return _prepare_outbound_message(raw_message, email_to_remove)


def _fix_gmail_inline_images(msg) -> None:
    """
    Gmail drafts often reference embedded report images via mail.google.com URLs
    that only work inside Gmail. Rewire those to cid: references on inline parts.
    """
    inline_images: list[tuple[str, Any]] = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        content_id = part.get("Content-ID")
        if not content_id or part.get_content_maintype() != "image":
            continue
        cid = content_id.strip().strip("<>")
        inline_images.append((cid, part))

    if not inline_images:
        return

    report_cid = _pick_report_image_cid(inline_images)
    if not report_cid:
        return

    for part in msg.walk():
        if part.get_content_type() != "text/html":
            continue
        charset = part.get_content_charset() or "utf-8"
        html = part.get_content()
        if not isinstance(html, str):
            continue
        if "view=fimg" not in html:
            continue

        fixed_html = GMAIL_EMBEDDED_IMAGE_RE.sub(f'src="cid:{report_cid}"', html)
        if fixed_html == html:
            continue

        part.set_content(fixed_html, subtype="html", charset=charset, cte="quoted-printable")
        if "Content-Disposition" in part:
            del part["Content-Disposition"]
        part.add_header("Content-Disposition", "inline")

    for cid, part in inline_images:
        if cid == report_cid:
            if "Content-Disposition" in part:
                del part["Content-Disposition"]
            part.add_header("Content-Disposition", "inline")
            if part.get("Content-ID") and not part.get("Content-ID", "").startswith("<"):
                part.replace_header("Content-ID", f"<{cid}>")


def _pick_report_image_cid(inline_images: list[tuple[str, Any]]) -> str | None:
    for cid, part in inline_images:
        filename = (part.get_filename() or "").casefold()
        if any(token in filename for token in ("vsl", "report", "coca", "dashboard")):
            return cid
    for cid, part in inline_images:
        if (part.get_filename() or "").lower().endswith(".png"):
            return cid
    return inline_images[0][0]


def _decode_raw_message_bytes(raw: str) -> bytes:
    return _decode_raw(raw)


def _fetch_vacation_bodies(service) -> tuple[str, str]:
    """Return (html, plain) vacation auto-reply bodies from Gmail settings."""
    try:
        vacation = service.users().settings().getVacation(userId="me").execute()
    except Exception:
        return "", ""
    html = (vacation.get("responseBodyHtml") or "").strip()
    plain = (vacation.get("responseBodyPlainText") or "").strip()
    return html, plain


def _collapse_html_whitespace(html: str) -> str:
    return re.sub(r"\s+", " ", html).strip()


def _remove_vacation_reply(msg, vacation_html: str = "", vacation_plain: str = "") -> None:
    """Remove Gmail vacation auto-reply text if it appears in the draft body."""
    html_patterns: list[re.Pattern[str]] = [
        re.compile(
            r"(?:<div[^>]*dir=\"ltr\"[^>]*>\s*)?"
            r"(?:<p>\s*)?Hörmətli həmkarlar,\s*(?:</p>\s*)?"
            r".*?məzuniyyətdə olacağam.*?"
            r"(?:055-203-52-57|tural\.mehbaliyev@wolt\.com).*?"
            r"(?:</p>\s*)?(?:<p>\s*<br>\s*</p>\s*)?(?:</div>)?",
            re.IGNORECASE | re.DOTALL,
        ),
    ]
    text_patterns: list[re.Pattern[str]] = [
        re.compile(
            r"Hörmətli həmkarlar,\s*"
            r".*?məzuniyyətdə olacağam.*?"
            r"(?:055-203-52-57|tural\.mehbaliyev@wolt\.com)\s*",
            re.IGNORECASE | re.DOTALL,
        ),
    ]

    if vacation_html:
        html_patterns.insert(0, re.compile(re.escape(vacation_html), re.IGNORECASE | re.DOTALL))
        collapsed = _collapse_html_whitespace(vacation_html)
        if collapsed != vacation_html:
            html_patterns.insert(1, re.compile(re.escape(collapsed), re.IGNORECASE | re.DOTALL))
    if vacation_plain:
        text_patterns.insert(0, re.compile(re.escape(vacation_plain), re.IGNORECASE | re.DOTALL))

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        content_type = part.get_content_type()
        charset = part.get_content_charset() or "utf-8"
        if content_type == "text/html":
            html = part.get_content()
            if not isinstance(html, str):
                continue
            cleaned = html
            if vacation_html and vacation_html in cleaned:
                cleaned = cleaned.replace(vacation_html, "")
            collapsed_vacation = _collapse_html_whitespace(vacation_html) if vacation_html else ""
            if collapsed_vacation and collapsed_vacation in cleaned:
                cleaned = cleaned.replace(collapsed_vacation, "")
            for pattern in html_patterns:
                cleaned = pattern.sub("", cleaned)
            if cleaned == html:
                continue
            part.set_content(cleaned, subtype="html", charset=charset, cte="quoted-printable")
        elif content_type == "text/plain":
            text = part.get_content()
            if not isinstance(text, str):
                continue
            cleaned = text
            if vacation_plain and vacation_plain in cleaned:
                cleaned = cleaned.replace(vacation_plain, "")
            for pattern in text_patterns:
                cleaned = pattern.sub("", cleaned)
            if cleaned == text:
                continue
            part.set_content(cleaned, subtype="plain", charset=charset, cte="quoted-printable")


def _remove_analytics_quote_header(msg) -> None:
    """Remove Gmail 'On …, no-reply.analytics@wolt.com wrote:' reply header."""
    email_pattern = re.escape(EXCLUDED_RECIPIENT)
    html_patterns = [
        re.compile(
            rf'<div[^>]*class="[^"]*gmail_attr[^"]*"[^>]*>\s*'
            rf"On .+?, {email_pattern} wrote:\s*</div>\s*",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            rf"On .+?, {email_pattern} wrote:\s*(?:<br\s*/?>)?\s*",
            re.IGNORECASE,
        ),
    ]
    text_pattern = re.compile(
        rf"^On .+?, {email_pattern} wrote:\s*\n?",
        re.IGNORECASE | re.MULTILINE,
    )

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        content_type = part.get_content_type()
        charset = part.get_content_charset() or "utf-8"
        if content_type == "text/html":
            html = part.get_content()
            if not isinstance(html, str) or EXCLUDED_RECIPIENT.casefold() not in html.casefold():
                continue
            cleaned = html
            for pattern in html_patterns:
                cleaned = pattern.sub("", cleaned)
            if cleaned == html:
                continue
            part.set_content(cleaned, subtype="html", charset=charset, cte="quoted-printable")
        elif content_type == "text/plain":
            text = part.get_content()
            if not isinstance(text, str) or EXCLUDED_RECIPIENT.casefold() not in text.casefold():
                continue
            cleaned = text_pattern.sub("", text)
            if cleaned == text:
                continue
            part.set_content(cleaned, subtype="plain", charset=charset, cte="quoted-printable")


def _remove_looker_unsubscribe(msg, owner_email: str) -> None:
    """Remove Looker 'Click here to unsubscribe …' boilerplate from message bodies."""
    email_pattern = re.escape(owner_email.strip())
    html_patterns = [
        re.compile(
            r"This email was scheduled by you\.\s*"
            r'<a\b[^>]*href="[^"]*unsubscribe[^"]*"[^>]*>.*?</a>\.?\s*'
            r"(?:<p>\s*)?Generated by Looker\.?(?:\s*</p>)?",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r'<a\b[^>]*href="[^"]*unsubscribe[^"]*"[^>]*>\s*Click here to unsubscribe.*?</a>\.?',
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            rf"Click here to unsubscribe\s*(?:<span[^>]*>\s*)?{email_pattern}(?:\s*</span>)?\s*\.?",
            re.IGNORECASE,
        ),
    ]
    text_patterns = [
        re.compile(
            rf"This email was scheduled by you\.\s*Click here to unsubscribe\s*{email_pattern}\.?\s*Generated by Looker\.?",
            re.IGNORECASE,
        ),
        re.compile(rf"Click here to unsubscribe\s*{email_pattern}\.?", re.IGNORECASE),
    ]

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        content_type = part.get_content_type()
        charset = part.get_content_charset() or "utf-8"
        if content_type == "text/html":
            html = part.get_content()
            if not isinstance(html, str) or UNSUBSCRIBE_MARKER.casefold() not in html.casefold():
                continue
            cleaned = html
            for pattern in html_patterns:
                cleaned = pattern.sub("", cleaned)
            if cleaned == html:
                continue
            part.set_content(cleaned, subtype="html", charset=charset, cte="quoted-printable")
        elif content_type == "text/plain":
            text = part.get_content()
            if not isinstance(text, str) or UNSUBSCRIBE_MARKER.casefold() not in text.casefold():
                continue
            cleaned = text
            for pattern in text_patterns:
                cleaned = pattern.sub("", cleaned)
            if cleaned == text:
                continue
            part.set_content(cleaned, subtype="plain", charset=charset, cte="quoted-printable")


def _append_on_behalf_signature(msg, *, name: str, email: str) -> None:
    html_sig = SIGNATURE_HTML.format(name=name, email=email)
    text_sig = SIGNATURE_TEXT.format(name=name, email=email)

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        content_type = part.get_content_type()
        if content_type == "text/html":
            html = part.get_content()
            if not isinstance(html, str) or SIGNATURE_MARKER in html:
                continue
            if 'class="gmail_signature"' in html:
                html = html.replace(
                    '<div class="gmail_signature"',
                    html_sig + '<div class="gmail_signature"',
                    1,
                )
            else:
                html = html + html_sig
            charset = part.get_content_charset() or "utf-8"
            part.set_content(html, subtype="html", charset=charset, cte="quoted-printable")
        elif content_type == "text/plain":
            text = part.get_content()
            if not isinstance(text, str) or SIGNATURE_MARKER in text:
                continue
            charset = part.get_content_charset() or "utf-8"
            part.set_content(text + text_sig, subtype="plain", charset=charset, cte="quoted-printable")


def _has_recipients(raw_message: bytes) -> bool:
    msg = message_from_bytes(raw_message, policy=email_policy)
    for header in ("To", "Cc", "Bcc"):
        if header in msg and msg[header].strip():
            return True
    return False


def _draft_subject(draft: dict[str, Any]) -> str:
    headers = {
        h["name"]: h["value"]
        for h in draft.get("message", {}).get("payload", {}).get("headers", [])
    }
    return decode_subject(headers.get("Subject")) or "(no subject)"


def _matches_subject_filter(subject: str, subject_contains: str | None) -> bool:
    if not subject_contains:
        return True
    return subject_contains.casefold() in subject.casefold()


def list_all_drafts(service) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = service.users().drafts().list(userId="me", pageToken=page_token).execute()
        for draft_meta in response.get("drafts", []):
            try:
                draft = service.users().drafts().get(
                    userId="me",
                    id=draft_meta["id"],
                    format="full",
                ).execute()
            except Exception:
                continue
            drafts.append(draft)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    drafts.sort(
        key=lambda item: item.get("message", {}).get("internalDate", "0"),
        reverse=True,
    )
    return drafts


def _prepare_outbound_message(
    raw_message: bytes,
    exclude_email: str,
    *,
    on_behalf_name: str = ON_BEHALF_NAME,
    on_behalf_email: str = ON_BEHALF_EMAIL,
    add_signature: bool = True,
    vacation_html: str = "",
    vacation_plain: str = "",
) -> bytes:
    msg = message_from_bytes(raw_message, policy=email_policy)
    for header in (
        "Message-ID",
        "Date",
        "DKIM-Signature",
        "X-Google-DKIM-Signature",
        "X-Gm-Message-State",
        "X-Google-Smtp-Source",
        "Received",
    ):
        while header in msg:
            del msg[header]

    exclude = exclude_email.strip().casefold()
    for header in ("To", "Cc", "Bcc"):
        if header not in msg:
            continue
        existing = msg.get_all(header, [])
        filtered = []
        seen: set[str] = set()
        for value in existing:
            for name, addr in getaddresses([value]):
                key = addr.casefold()
                if key == exclude or key in seen:
                    continue
                seen.add(key)
                filtered.append((name, addr))
        while header in msg:
            del msg[header]
        if filtered:
            msg[header] = ", ".join(formataddr(pair) for pair in filtered)

    _fix_gmail_inline_images(msg)
    _remove_vacation_reply(msg, vacation_html, vacation_plain)
    _remove_analytics_quote_header(msg)
    _remove_looker_unsubscribe(msg, on_behalf_email)
    if add_signature:
        _append_on_behalf_signature(msg, name=on_behalf_name, email=on_behalf_email)
    return msg.as_bytes(policy=email_policy)


def send_sent_message_again(
    *,
    subject_query: str,
    exclude_email: str = EXCLUDED_RECIPIENT,
    dry_run: bool = False,
) -> dict[str, str]:
    """Resend the latest sent message matching subject, with inline images fixed."""
    service = get_gmail_service()
    results = service.users().messages().list(
        userId="me",
        labelIds=["SENT"],
        q=f'subject:"{subject_query}"',
        maxResults=10,
    ).execute()

    message_id = None
    for item in results.get("messages", []):
        meta = service.users().messages().get(
            userId="me",
            id=item["id"],
            format="metadata",
            metadataHeaders=["Subject"],
        ).execute()
        headers = {
            h["name"]: h["value"]
            for h in meta.get("payload", {}).get("headers", [])
        }
        subject = decode_subject(headers.get("Subject")).casefold()
        target = subject_query.strip().casefold()
        if subject == target or target in subject:
            message_id = item["id"]
            break

    if not message_id:
        raise RuntimeError(f'No sent message found with subject matching "{subject_query}"')

    raw_msg = service.users().messages().get(userId="me", id=message_id, format="raw").execute()
    raw = _decode_raw_message_bytes(raw_msg["raw"])
    prepared = _prepare_outbound_message(raw, exclude_email)

    if dry_run:
        return {
            "source_message_id": message_id,
            "action": "dry_run",
            "recipients_after": _recipients_summary(prepared),
        }

    sent = service.users().messages().send(
        userId="me",
        body={"raw": _encode_raw(prepared)},
    ).execute()
    return {
        "source_message_id": message_id,
        "message_id": sent.get("id", ""),
        "action": "sent",
        "recipients_after": _recipients_summary(prepared),
    }


def _decode_raw(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _encode_raw(raw_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(raw_bytes).decode("ascii")


def _extract_raw_message(service, draft_id: str) -> bytes:
    draft = service.users().drafts().get(userId="me", id=draft_id, format="raw").execute()
    raw = draft.get("message", {}).get("raw")
    if not raw:
        raise RuntimeError("Could not read draft message (missing raw format)")
    return _decode_raw(raw)


def _recipients_summary(raw_message: bytes) -> str:
    msg = message_from_bytes(raw_message, policy=email_policy)
    parts = []
    for header in ("To", "Cc", "Bcc"):
        if header in msg:
            parts.append(f"{header}: {msg[header]}")
    return "; ".join(parts) if parts else "(no recipients)"


def send_draft_by_id(
    service,
    draft_id: str,
    *,
    exclude_email: str = EXCLUDED_RECIPIENT,
    dry_run: bool = False,
    on_behalf_name: str = ON_BEHALF_NAME,
    on_behalf_email: str = ON_BEHALF_EMAIL,
    vacation_html: str = "",
    vacation_plain: str = "",
) -> dict[str, str]:
    original_raw = _extract_raw_message(service, draft_id)
    prepared = _prepare_outbound_message(
        original_raw,
        exclude_email,
        on_behalf_name=on_behalf_name,
        on_behalf_email=on_behalf_email,
        vacation_html=vacation_html,
        vacation_plain=vacation_plain,
    )

    if not _has_recipients(prepared):
        return {
            "draft_id": draft_id,
            "action": "skipped",
            "reason": "no recipients after exclusion",
        }

    if dry_run:
        return {
            "draft_id": draft_id,
            "action": "dry_run",
            "recipients_after": _recipients_summary(prepared),
        }

    encoded = _encode_raw(prepared)
    service.users().drafts().update(
        userId="me",
        id=draft_id,
        body={"message": {"raw": encoded}},
    ).execute()
    sent = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
    return {
        "draft_id": draft_id,
        "message_id": sent.get("id", ""),
        "action": "sent",
        "recipients_after": _recipients_summary(prepared),
    }


def send_all_drafts(
    *,
    exclude_email: str = EXCLUDED_RECIPIENT,
    dry_run: bool = False,
    on_behalf_name: str = ON_BEHALF_NAME,
    on_behalf_email: str = ON_BEHALF_EMAIL,
    subject_contains: str | None = DRAFT_SUBJECT_CONTAINS,
) -> list[dict[str, str]]:
    service = get_gmail_service()
    vacation_html, vacation_plain = _fetch_vacation_bodies(service)
    drafts = list_all_drafts(service)
    results: list[dict[str, str]] = []

    for draft in drafts:
        draft_id = draft["id"]
        subject = _draft_subject(draft)
        if not _matches_subject_filter(subject, subject_contains):
            continue
        try:
            outcome = send_draft_by_id(
                service,
                draft_id,
                exclude_email=exclude_email,
                dry_run=dry_run,
                on_behalf_name=on_behalf_name,
                on_behalf_email=on_behalf_email,
                vacation_html=vacation_html,
                vacation_plain=vacation_plain,
            )
            outcome["subject"] = subject
            results.append(outcome)
        except Exception as exc:
            results.append(
                {
                    "draft_id": draft_id,
                    "subject": subject,
                    "action": "error",
                    "reason": str(exc),
                }
            )
    return results


def send_draft_excluding_recipient(
    *,
    subject_query: str,
    exclude_email: str = EXCLUDED_RECIPIENT,
    dry_run: bool = False,
) -> dict[str, str]:
    service = get_gmail_service()
    draft = find_draft_by_subject(service, subject_query)
    draft_id = draft["id"]
    outcome = send_draft_by_id(service, draft_id, exclude_email=exclude_email, dry_run=dry_run)
    if outcome.get("action") == "skipped":
        raise RuntimeError(outcome.get("reason", "draft skipped"))
    return outcome


def validate_gmail_connection() -> str:
    service = get_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    return profile.get("emailAddress", "unknown")
