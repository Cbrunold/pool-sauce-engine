#!/usr/bin/env bash
# Pool Sauce Engine — start (or restart) both servers, detached.
# Idempotent: kills any existing instances first, then relaunches.
# Used by the Windows logon task so the app is up whenever you're logged in.
set -u

REPO="$HOME/code/pool-sauce-engine"

# Stop existing instances.
pkill -f "uvicorn api.main" 2>/dev/null
pkill -f "vite.*5173"       2>/dev/null
sleep 1

# Backend (FastAPI engine).
cd "$REPO"
setsid python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 \
  > /tmp/pse-api.log 2>&1 < /dev/null &
disown

# Frontend (Vite dev server).
# shellcheck disable=SC1090
source "$HOME/.nvm/nvm.sh" 2>/dev/null
cd "$REPO/web"
setsid npm run dev -- --host 0.0.0.0 --port 5173 \
  > /tmp/pse-web.log 2>&1 < /dev/null &
disown

echo "Pool Sauce Engine servers launched (api:8000, web:5173)."
