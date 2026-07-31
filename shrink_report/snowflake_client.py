"""Snowflake connection helpers for shrink reports."""

from __future__ import annotations

import os
from typing import Any

import snowflake.connector


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    # PATs can get line-wrapped when pasted into Terminal; remove all whitespace.
    cleaned = "".join(value.split())
    return cleaned or None


def load_snowflake_config() -> dict[str, str | None]:
    password = _clean(os.environ.get("SNOWFLAKE_PASSWORD") or os.environ.get("SNOWFLAKE_TOKEN"))
    return {
        "account": _clean(os.environ.get("SNOWFLAKE_ACCOUNT", "doordash")),
        "user": _clean(os.environ.get("SNOWFLAKE_USER", "nurlan.rasulov@wolt.com")),
        "password": password,
        "warehouse": _clean(os.environ.get("SNOWFLAKE_WAREHOUSE")),
        "database": _clean(os.environ.get("SNOWFLAKE_DATABASE")),
        "schema": _clean(os.environ.get("SNOWFLAKE_SCHEMA")),
        "role": _clean(os.environ.get("SNOWFLAKE_ROLE")),
    }


def connect():
    config = load_snowflake_config()
    authenticator = (os.environ.get("SNOWFLAKE_AUTHENTICATOR") or "").strip()
    # Browser SSO does not need a PAT / password.
    using_browser = authenticator.lower() in {"externalbrowser", "browser"}
    required = ["account", "user"] if using_browser else ["account", "user", "password"]
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise SystemExit(
            "Missing Snowflake configuration:\n  "
            + ", ".join(f"SNOWFLAKE_{key.upper()}" for key in missing)
            + "\nSet credentials in .env or Cursor Cloud secrets.\n"
            "Tip: if PAT fails with network policy, set "
            "SNOWFLAKE_AUTHENTICATOR=externalbrowser and log in via browser."
        )

    kwargs: dict[str, Any] = {
        "account": config["account"],
        "user": config["user"],
        "login_timeout": int(os.environ.get("SNOWFLAKE_LOGIN_TIMEOUT", "60")),
        "network_timeout": int(os.environ.get("SNOWFLAKE_NETWORK_TIMEOUT", "120")),
    }
    if using_browser:
        kwargs["authenticator"] = "externalbrowser"
    elif config.get("password"):
        kwargs["password"] = config["password"]
        # Only set authenticator when explicitly requested —
        # PROGRAMMATIC_ACCESS_TOKEN can crash older connector versions with TypeError.
        if authenticator and authenticator.upper() not in {"", "PASSWORD", "PAT"}:
            kwargs["authenticator"] = authenticator
    for key in ("warehouse", "database", "schema", "role"):
        value = config.get(key)
        if value:
            kwargs[key] = value

    try:
        return snowflake.connector.connect(**kwargs)
    except TypeError as exc:
        # Retry without authenticator for PAT-as-password flows.
        if "authenticator" in kwargs and not using_browser:
            kwargs.pop("authenticator", None)
            try:
                return snowflake.connector.connect(**kwargs)
            except Exception as retry_exc:
                message = str(retry_exc)
                raise SystemExit(f"Snowflake connection failed: {message}") from retry_exc
        raise SystemExit(f"Snowflake connection failed: {exc}") from exc
    except Exception as exc:
        message = str(exc)
        hints: list[str] = []
        if "not allowed to access" in message.lower() or "ip/" in message.lower():
            hints.append("Your IP may be blocked by Snowflake network policy.")
        if "network policy is required" in message.lower():
            hints.append(
                "PAT requires a Snowflake network policy. "
                "Easiest fix: set SNOWFLAKE_AUTHENTICATOR=externalbrowser in .env "
                "and run again (browser SSO login)."
            )
        if "programmatic access token is invalid" in message.lower():
            hints.append("Check SNOWFLAKE_USER matches the PAT owner, or generate a new PAT.")
        if "does not exist" in message.lower() or "not authorized" in message.lower():
            hints.append("Verify SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, and SNOWFLAKE_ROLE.")
        hint_text = "\n  ".join(hints)
        raise SystemExit(f"Snowflake connection failed: {message}\n  {hint_text}") from exc


def validate_connection() -> dict[str, str]:
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT CURRENT_USER(), CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_WAREHOUSE()"
        )
        row = cursor.fetchone()
        if not row:
            raise SystemExit("Snowflake connected, but auth check returned no rows.")
        user, account, role, warehouse = row
        return {
            "user": str(user),
            "account": str(account),
            "role": str(role or ""),
            "warehouse": str(warehouse or ""),
        }


def execute_query(sql: str, *, params: dict[str, Any] | None = None) -> tuple[list[str], list[list[Any]]]:
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or {})
        headers = [column[0] for column in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
        return headers, rows
