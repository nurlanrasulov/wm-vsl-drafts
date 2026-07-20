#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${ROOT}/.venv/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

LOG_DIR="${ROOT}/output/gmail-drafts/logs"
LOG_FILE="${LOG_DIR}/monday-all-drafts.log"
CRON_MARKER="# wm-assortment-pause-send-all-drafts"

mkdir -p "$LOG_DIR"

read -r -p "Hour to run on Monday [10]: " HOUR
read -r -p "Minute to run on Monday [0]: " MINUTE
HOUR="${HOUR:-10}"
MINUTE="${MINUTE:-0}"

CRON_LINE="${MINUTE} ${HOUR} * * 1 cd ${ROOT} && ${PYTHON} send_all_drafts.py >> ${LOG_FILE} 2>&1 ${CRON_MARKER}"

EXISTING="$(crontab -l 2>/dev/null || true)"
FILTERED="$(printf '%s\n' "$EXISTING" | grep -Fv "$CRON_MARKER" || true)"

{
  printf '%s\n' "$FILTERED"
  printf '%s\n' "$CRON_LINE"
} | crontab -

echo "Installed Monday cron job:"
echo "  $CRON_LINE"
echo ""
echo "Logs: $LOG_FILE"
echo ""
echo "Test manually:"
echo "  cd ${ROOT} && ${PYTHON} send_all_drafts.py --dry-run"
