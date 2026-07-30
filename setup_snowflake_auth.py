#!/usr/bin/env python3
"""Validate Snowflake credentials for shrink reports."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    import os

    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    load_dotenv()
    from shrink_report.snowflake_client import validate_connection
    from shrink_report.snowflake_query import build_shrink_sql

    info = validate_connection()
    print("Snowflake auth OK:")
    for key, value in info.items():
        print(f"  {key}: {value or '(default)'}")
    print("\nShrink SQL preview:\n")
    print(build_shrink_sql())


if __name__ == "__main__":
    main()
