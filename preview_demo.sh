#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/backend"

REFRESH_DATA=false
if [[ "${1:-}" == "--refresh-data" ]]; then
  REFRESH_DATA=true
fi

if [[ "$REFRESH_DATA" == true ]]; then
  echo "[demo] exporting fresh snapshot from local backend data"
  "$BACKEND_DIR/venv/bin/python" "$BACKEND_DIR/export_demo_snapshot.py"
fi

echo "[demo] deploying current frontend working tree to Vercel preview"
cd "$FRONTEND_DIR"
npx vercel deploy --yes -b NEXT_PUBLIC_DEMO_MODE=true
