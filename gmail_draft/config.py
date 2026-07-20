"""Configuration for Gmail draft automation."""

from __future__ import annotations

import os

EXCLUDED_RECIPIENT = "no-reply.analytics@wolt.com"

ON_BEHALF_NAME = os.environ.get("ON_BEHALF_NAME", "Nurlan Rasulov")
ON_BEHALF_EMAIL = os.environ.get("ON_BEHALF_EMAIL", "nurlan.rasulov@wolt.com")

SIGNATURE_MARKER = "Sent automatically on behalf of"

SIGNATURE_HTML = """
<br><br>
<div style="margin-top:16px;padding-top:12px;border-top:1px solid #e0e0e0;color:#666;font-size:12px;font-family:Arial,sans-serif;line-height:1.5;">
Bu məktub <strong>{name}</strong> ({email}) adından avtomatik assistent vasitəsilə göndərilib.<br>
<em>Sent automatically on behalf of {name}.</em>
</div>
"""

SIGNATURE_TEXT = """

--
Bu məktub {name} ({email}) adından avtomatik assistent vasitəsilə göndərilib.
Sent automatically on behalf of {name}.
"""

UNSUBSCRIBE_MARKER = "Click here to unsubscribe"

# Only auto-send drafts whose subject contains this text (case-insensitive).
DRAFT_SUBJECT_CONTAINS = os.environ.get("DRAFT_SUBJECT_CONTAINS", "VSL REPORT")
