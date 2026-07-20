#!/usr/bin/env python3
"""Create GitHub repo, push code, and upload Actions secrets."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from nacl import encoding, public

ROOT = Path(__file__).resolve().parent
CREDENTIALS_FILE = ROOT / "gmail_credentials.json"
TOKEN_FILE = ROOT / "gmail_token.json"
GH_HOSTS = Path.home() / "doordash-ai-helpers/.creds/gh/hosts.yml"

REPO_NAME = "wm-vsl-drafts"
REPO_OWNER = "nurlanrasulov"


def load_github_token() -> str:
    import os

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token.strip()
    if GH_HOSTS.exists():
        for line in GH_HOSTS.read_text().splitlines():
            if line.strip().startswith("oauth_token:"):
                return line.split(":", 1)[1].strip()
    raise SystemExit("No GitHub token found. Set GITHUB_TOKEN or run gh auth login.")


def api_request(token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"https://api.github.com{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "wm-vsl-drafts-setup",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed ({exc.code}): {detail}") from exc


def ensure_repo(token: str) -> str:
    try:
        repo = api_request(token, "GET", f"/repos/{REPO_OWNER}/{REPO_NAME}")
        return repo["html_url"]
    except RuntimeError as exc:
        if "404" not in str(exc):
            raise
    repo = api_request(
        token,
        "POST",
        "/user/repos",
        {"name": REPO_NAME, "private": True, "description": "Weekly VSL report draft sender"},
    )
    return repo["html_url"]


def encrypt_secret(public_key: str, secret_value: str) -> str:
    key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed = public.SealedBox(key).encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(sealed).decode("utf-8")


def upload_secret(token: str, name: str, value: str) -> None:
    key_info = api_request(
        token,
        "GET",
        f"/repos/{REPO_OWNER}/{REPO_NAME}/actions/secrets/public-key",
    )
    encrypted = encrypt_secret(key_info["key"], value)
    api_request(
        token,
        "PUT",
        f"/repos/{REPO_OWNER}/{REPO_NAME}/actions/secrets/{name}",
        {
            "encrypted_value": encrypted,
            "key_id": key_info["key_id"],
        },
    )


def load_gmail_secrets() -> dict[str, str]:
    creds = json.loads(CREDENTIALS_FILE.read_text())
    installed = creds.get("installed") or creds.get("web") or creds
    token_data = json.loads(TOKEN_FILE.read_text())
    refresh = token_data.get("refresh_token")
    if not refresh:
        raise SystemExit("Missing refresh_token in gmail_token.json")
    return {
        "GMAIL_CLIENT_ID": installed["client_id"],
        "GMAIL_CLIENT_SECRET": installed["client_secret"],
        "GMAIL_REFRESH_TOKEN": refresh,
        "ON_BEHALF_NAME": "Nurlan Rasulov",
        "ON_BEHALF_EMAIL": "nurlan.rasulov@wolt.com",
    }


def run(cmd: list[str], *, env: dict | None = None) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def push_files_via_api(token: str) -> None:
    files = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    failed: list[str] = []
    for rel_path in files:
        file_path = ROOT / rel_path
        if not file_path.is_file():
            continue
        content_b64 = base64.b64encode(file_path.read_bytes()).decode("ascii")
        body: dict[str, str] = {
            "message": f"Add {rel_path}",
            "content": content_b64,
            "branch": "main",
        }
        path = urllib.parse.quote(rel_path, safe="")
        try:
            existing = api_request(
                token,
                "GET",
                f"/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}?ref=main",
            )
            body["sha"] = existing["sha"]
        except RuntimeError as exc:
            if "404" not in str(exc):
                raise
        try:
            api_request(
                token,
                "PUT",
                f"/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}",
                body,
            )
            print(f"Uploaded: {rel_path}")
        except RuntimeError as exc:
            failed.append(f"{rel_path}: {exc}")
    if failed:
        print("\nSome files could not be uploaded:")
        for item in failed:
            print(f"  - {item}")


def git_push(token: str) -> None:
    remote = f"https://x-access-token:{token}@github.com/{REPO_OWNER}/{REPO_NAME}.git"
    if not (ROOT / ".git").exists():
        run(["git", "init", "-b", "main"])
    run(["git", "config", "user.email", "nurlan.rasulov@wolt.com"])
    run(["git", "config", "user.name", "Nurlan Rasulov"])
    run(["git", "add", "-A"])
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    if status.stdout.strip():
        run(["git", "commit", "-m", "Add VSL draft automation with GitHub Actions"])
    subprocess.run(["git", "remote", "remove", "origin"], cwd=ROOT, check=False)
    run(["git", "remote", "add", "origin", remote])
    run(["git", "push", "-u", "origin", "main"])


def remove_local_cron() -> None:
    marker = "wm-assortment-pause"
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return
    lines = [line for line in result.stdout.splitlines() if marker not in line]
    proc = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, check=False)


def main() -> None:
    if not CREDENTIALS_FILE.exists() or not TOKEN_FILE.exists():
        raise SystemExit("Run setup_gmail_auth.py first.")

    token = load_github_token()
    repo_url = ensure_repo(token)
    print(f"Repository: {repo_url}")

    for name, value in load_gmail_secrets().items():
        upload_secret(token, name, value)
        print(f"Uploaded secret: {name}")

    try:
        git_push(token)
        print("Pushed code to GitHub via git.")
    except subprocess.CalledProcessError:
        print("Git push blocked — uploading files via GitHub API instead...")
        push_files_via_api(token)
        print("Uploaded code to GitHub via API.")

    remove_local_cron()
    print("Removed local Monday cron (cloud job replaces it).")
    print("\nDone. Test at: Actions → Send VSL report drafts → Run workflow")


if __name__ == "__main__":
    main()
