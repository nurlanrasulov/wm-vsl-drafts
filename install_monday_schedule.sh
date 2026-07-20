#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
LOG_DIR="${ROOT}/output/vendor-reports/logs"
LOG_FILE="${LOG_DIR}/monday-run.log"
CRON_MARKER="# wm-assortment-pause-unilever-vendor-report"

mkdir -p "$LOG_DIR"

read -r -p "Hour to run on Monday [9]: " HOUR
read -r -p "Minute to run on Monday [0]: " MINUTE
HOUR="${HOUR:-9}"
MINUTE="${MINUTE:-0}"

CRON_LINE="${MINUTE} ${HOUR} * * 1 cd ${ROOT} && ${PYTHON} send_vendor_report.py >> ${LOG_FILE} 2>&1 ${CRON_MARKER}"

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
echo "  cd ${ROOT} && ${PYTHON} send_vendor_report.py --dry-run"
