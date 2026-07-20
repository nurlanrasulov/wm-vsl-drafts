#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

python3 -m pip install -q -r requirements.txt
chmod +x pause_products.py setup_auth.py setup_looker_auth.py setup_gmail_auth.py setup_github_secrets.py send_vendor_report.py send_coca_cola_draft.py send_all_drafts.py install_monday_schedule.sh install_monday_draft_schedule.sh

if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
fi

echo "Dependencies installed."

if grep -q '^FULFILLMENT_BEARER_TOKEN=.\+' .env 2>/dev/null; then
  echo "Validating saved token..."
  if TOKEN="$(grep '^FULFILLMENT_BEARER_TOKEN=' .env | cut -d= -f2-)" python3 -c "
import os, sys
sys.path.insert(0, '$ROOT')
from setup_auth import validate_token
validate_token(os.environ['TOKEN'])
"; then
    exit 0
  fi
  echo "Saved token is missing or expired."
fi

echo ""
echo "Copy your Fulfillment Bearer token from DevTools, then run:"
echo "  python3 setup_auth.py --clipboard"
