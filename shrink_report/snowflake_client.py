"""Snowflake connection helpers for shrink reports."""

from __future__ import annotations

import os
from typing import Any

import snowflake.connector


def load_snowflake_config() -> dict[str, str | None]:
    password = os.environ.get("SNOWFLAKE_PASSWORD") or os.environ.get("SNOWFLAKE_TOKEN")
    return {
        "account": os.environ.get("SNOWFLAKE_ACCOUNT", "doordash"),
        "user": os.environ.get("SNOWFLAKE_USER", "nurlan.rasulov@wolt.com"),
        "password": password,
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE"),
        "database": os.environ.get("SNOWFLAKE_DATABASE"),
        "schema": os.environ.get("SNOWFLAKE_SCHEMA"),
        "role": os.environ.get("SNOWFLAKE_ROLE"),
    }


def connect():
    config = load_snowflake_config()
    missing = [key for key in ("account", "user", "password") if not config.get(key)]
    if missing:
        raise SystemExit(
            "Missing Snowflake configuration:\n  "
            + ", ".join(f"SNOWFLAKE_{key.upper()}" for key in missing)
            + "\nSet credentials in .env or Cursor Cloud secrets."
        )

    kwargs: dict[str, Any] = {
        "account": config["account"],
        "user": config["user"],
        "password": config["password"],
        "authenticator": os.environ.get("SNOWFLAKE_AUTHENTICATOR", "PROGRAMMATIC_ACCESS_TOKEN"),
        "login_timeout": int(os.environ.get("SNOWFLAKE_LOGIN_TIMEOUT", "30")),
        "network_timeout": int(os.environ.get("SNOWFLAKE_NETWORK_TIMEOUT", "120")),
    }
    for key in ("warehouse", "database", "schema", "role"):
        value = config.get(key)
        if value:
            kwargs[key] = value

    try:
        return snowflake.connector.connect(**kwargs)
    except Exception as exc:
        message = str(exc)
        hints: list[str] = []
        if "not allowed to access" in message.lower() or "ip/" in message.lower():
            hints.append("Your IP may be blocked by Snowflake network policy.")
        if "programmatic access token is invalid" in message.lower():
            hints.append("Check SNOWFLAKE_USER matches the PAT owner.")
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
        user, account, role, warehouse = cursor.fetchone()
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
