#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$BACKEND_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$BACKEND_DIR"
./venv/bin/python rotate_logs.py

start_if_missing() {
  local port="$1"
  local name="$2"
  local cmd="$3"
  local log_file="$4"

  if lsof -iTCP:"$port" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
    echo "[$name] already listening on :$port"
    return
  fi

  echo "[$name] starting on :$port"
  /bin/zsh -lc "$cmd" >>"$log_file" 2>&1 &
  disown
}

start_if_missing \
  "5001" \
  "backend" \
  "cd '$BACKEND_DIR' && env -u ELECTRON_RUN_AS_NODE ./venv/bin/python app.py" \
  "$LOG_DIR/backend_dev.log"

start_if_missing \
  "3000" \
  "frontend" \
  "cd '$FRONTEND_DIR' && env -u ELECTRON_RUN_AS_NODE npm run dev" \
  "$LOG_DIR/frontend_dev.log"

echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:5001"
