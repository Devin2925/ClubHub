#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/backend/logs"

mkdir -p "$LOG_DIR"

if lsof -iTCP:3000 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "[frontend] already listening on :3000"
  echo "Frontend: http://localhost:3000"
  exit 0
fi

echo "[frontend] starting demo mode on :3000"
/bin/zsh -lc "cd '$FRONTEND_DIR' && printf 'NEXT_PUBLIC_DEMO_MODE=true\n' > .env.local && env -u ELECTRON_RUN_AS_NODE npm run dev" >>"$LOG_DIR/frontend_dev.log" 2>&1 &
disown

echo "Frontend: http://localhost:3000"
