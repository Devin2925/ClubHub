#!/bin/zsh
set -euo pipefail

ROOT="/Users/devinmcnair/Desktop/ClubHub/backend"
LOG_DIR="$ROOT/logs"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

mkdir -p "$LOG_DIR"

{
  echo "[$TIMESTAMP] Starting ClubHub sync"
  cd "$ROOT"
  ./venv/bin/python rotate_logs.py
  ./venv/bin/python run_sync.py
  ./venv/bin/python rerun_health.py
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ClubHub sync complete"
} >> "$LOG_DIR/sync.log" 2>&1
