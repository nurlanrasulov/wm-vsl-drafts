# AGENTS.md

## Cursor Cloud specific instructions

### What this repo is
A collection of Python CLI automation scripts for Wolt Market Azerbaijan (WM AZE) operations. There is **no web app, no server, and no test suite** — each top-level `*.py` is an independently runnable CLI. Python deps come from `requirements.txt` (installed by the startup update script). Python 3.12 is present; the GitHub Actions workflows pin 3.11, but both work.

### Services / entry points
All of these require **external corporate credentials** (see `.env.example`) and live network access, so they cannot be fully run in the cloud VM without secrets:

- `pause_products.py` — pauses WM AZE products as "Sold Out" via the Wolt Fulfillment API. Needs `FULFILLMENT_BEARER_TOKEN`.
- `send_shrink_report.py` / `preview_shrink_report.py` — weekly shrink-contributor report. Needs Snowflake (default) or Looker, plus SMTP to email.
- `send_vendor_report.py` — vendor report from Looker + SMTP.
- `send_all_drafts.py` / `send_coca_cola_draft.py` — Gmail draft automation (`gmail_draft/`). Needs Gmail OAuth (`GMAIL_CLIENT_ID/SECRET/REFRESH_TOKEN`).

Config is loaded from a local `.env` (copy from `.env.example`). `setup.sh` installs deps and bootstraps `.env`; the auth helpers (`setup_auth.py`, `setup_looker_auth.py`, `setup_snowflake_auth.py`, `setup_gmail_auth.py`) are for one-time credential capture.

### Lint / test / build / run
- **Lint / syntax check:** No linter is configured or vendored (the `# noqa` comments reference flake8, but it is not a project dependency). Use `python -m compileall .` as the syntax check.
- **Tests:** none exist.
- **Build:** none (pure Python scripts).
- **Run:** `python <script>.py --help` for most CLIs. Many support `--dry-run` and `--skip-email`; `send_shrink_report.py` supports `--check-auth` to validate credentials without sending.

### Non-obvious gotchas
- `preview_shrink_report.py` has **no `--help`** — importing/running it immediately attempts a Snowflake connection and will fail fast without valid `SNOWFLAKE_*` secrets. This is expected, not a setup problem.
- The core, credential-free logic worth exercising is the shrink-report data pipeline: `shrink_report.excel_builder.rows_to_xlsx` → `shrink_report.excel_utils.format_shrink_report` (excludes Herbs/FnV, sorts by shrink value desc, keeps top-N, reorders columns). It can be run on synthetic rows with no external services.
- Generated reports are written under `output/` (gitignored).
- pip installs to `~/.local` (user site) in this environment; that's fine and already on `sys.path` for `python3`.
