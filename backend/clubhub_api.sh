#!/bin/zsh
set -euo pipefail

ROOT="/Users/devinmcnair/Desktop/ClubHub/backend"
LOG_DIR="$ROOT/logs"

mkdir -p "$LOG_DIR"
cd "$ROOT"

export CLUBHUB_HOST="${CLUBHUB_HOST:-0.0.0.0}"
export CLUBHUB_PORT="${CLUBHUB_PORT:-5001}"
export CLUBHUB_DEBUG="${CLUBHUB_DEBUG:-0}"

exec ./venv/bin/python app.py >> "$LOG_DIR/api.log" 2>&1
