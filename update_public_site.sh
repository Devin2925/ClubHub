#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PYTHON_BIN="$BACKEND_DIR/venv/bin/python"
VERCEL_CMD=(npx vercel deploy --prod --yes -b NEXT_PUBLIC_DEMO_MODE=true)

RUN_DEPLOY=true
RUN_SYNC=true

for arg in "$@"; do
  case "$arg" in
    --no-deploy)
      RUN_DEPLOY=false
      ;;
    --skip-sync)
      RUN_SYNC=false
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: ./update_public_site.sh [--no-deploy] [--skip-sync]" >&2
      exit 1
      ;;
  esac
done

section() {
  printf "\n== %s ==\n" "$1"
}

section "ClubHub public refresh"
echo "Root: $ROOT_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing backend virtualenv python at $PYTHON_BIN" >&2
  exit 1
fi

if [[ "$RUN_SYNC" == true ]]; then
  section "Syncing backend data"
  (
    cd "$BACKEND_DIR"
    "$PYTHON_BIN" run_sync.py
  )
else
  section "Skipping backend sync"
fi

section "Current source alerts"
(
  cd "$BACKEND_DIR"
  "$PYTHON_BIN" source_alerts.py
)

section "Current venue alerts"
(
  cd "$BACKEND_DIR"
  "$PYTHON_BIN" venue_alerts.py
)

section "Core completeness audit"
(
  cd "$BACKEND_DIR"
  "$PYTHON_BIN" completeness_audit.py
)

section "Exporting demo snapshot"
(
  cd "$BACKEND_DIR"
  "$PYTHON_BIN" export_demo_snapshot.py
)

if [[ "$RUN_DEPLOY" == true ]]; then
  section "Deploying to Vercel production"
  (
    cd "$FRONTEND_DIR"
    "${VERCEL_CMD[@]}"
  )
else
  section "Skipping Vercel deploy"
fi

section "Done"
echo "Public site routine finished."
