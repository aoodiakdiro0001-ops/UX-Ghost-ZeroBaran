#!/usr/bin/env bash
# =====================================================================
#  UX-Ghost ZeroBaran — One-shot installer
#  Author: Baran Avisat  <Baranavisat@gmail.com>
#
#  This script:
#    1) Verifies Python 3.10+
#    2) Creates a virtualenv
#    3) Installs all dependencies
#    4) Copies .env.example → .env (if missing)
#    5) Validates environment variables
#    6) Optionally bootstraps Supabase schema (requires `psql` or curl)
# =====================================================================
set -euo pipefail

PROJECT_NAME="UX-Ghost ZeroBaran"
AUTHOR="Baran Avisat"
EMAIL="Baranavisat@gmail.com"
PHONE="+90 531 326 3722"

cd "$(dirname "$0")"
ROOT="$(pwd)"

echo "════════════════════════════════════════════════════════════════"
echo " 👻 $PROJECT_NAME — Installer"
echo " 👤 Author: $AUTHOR"
echo " 📧 $EMAIL  |  📱 $PHONE"
echo "════════════════════════════════════════════════════════════════"

# --- 1) Python check
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ Python 3 not found. Install python3 ≥ 3.10 and re-run."
  exit 1
fi
PYV=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python $PYV detected"
if python3 -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)"; then
  echo "✓ Python ≥ 3.10 OK"
else
  echo "❌ Python < 3.10 — please upgrade."
  exit 1
fi

# --- 2) Virtualenv
if [ ! -d ".venv" ]; then
  echo "→ Creating virtualenv at ./.venv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# --- 3) Pip install
echo "→ Installing dependencies…"
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# --- 4) .env
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "→ Created .env from .env.example — EDIT IT NOW"
else
  echo "✓ .env already present"
fi

# --- 5) Validate
echo "→ Validating environment…"
missing=0
for var in SUPABASE_URL SUPABASE_SERVICE_KEY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID; do
  if [ -z "${!var:-}" ]; then
    val=$(grep "^$var=" .env 2>/dev/null | cut -d= -f2-)
    if [ -z "$val" ] || echo "$val" | grep -qi "YOUR-\|changeme\|example"; then
      echo "  ⚠ $var is empty or still a placeholder"
      missing=$((missing+1))
    fi
  fi
done
if [ "$missing" -gt 0 ]; then
  echo "  → $missing var(s) need filling. Open .env and edit them."
else
  echo "  ✓ All required variables look good"
fi

# --- 6) Optional Supabase schema bootstrap
if [ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_SERVICE_KEY:-}" ]; then
  echo "→ Schema file ready at: supabase/schema.sql"
  echo "  → Apply manually via Supabase SQL Editor, OR run:"
  echo "    curl -X POST '$SUPABASE_URL/rest/v1/rpc/' \\"
  echo "      -H 'apikey: $SUPABASE_SERVICE_KEY'"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo " ✅ Install complete. Next steps:"
echo "    • Edit .env  → fill all keys"
echo "    • Apply supabase/schema.sql to your Supabase project"
echo "    • Drop tracker/ux-ghost-tracker.js into your website"
echo "    • Launch dashboard:  streamlit run dashboard/app.py"
echo "    • Start bot:         python telegram_bot/bot.py --mode poll"
echo "    • Commit to GitHub to enable the scheduled Actions"
echo "════════════════════════════════════════════════════════════════"
