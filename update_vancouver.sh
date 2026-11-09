#!/usr/bin/env bash
# The ClubHub Vancouver refresh: scrape every Metro Vancouver source into
# backend/clubhub_vancouver.db and check the results. See REFRESH.md.
#
#   ./update_vancouver.sh                         every source
#   ./update_vancouver.sh burnaby_activenet       only these source keys (vancouver_sync.py --list)
#   ./update_vancouver.sh --dry-run               fetch + filter, write nothing, list what filters dropped
#
# There is no Vancouver site yet, so nothing is exported or published. Victoria's
# database, snapshot and site are never touched.
#
# Exit code: 0 = all sources look right, 2 = the report flagged something, 1 = broke.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
PYTHON_BIN="$BACKEND_DIR/venv/bin/python"
[[ -x "$PYTHON_BIN" ]] || { echo "Missing backend venv python at $PYTHON_BIN" >&2; exit 1; }

DRY_RUN=false
SOURCES=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    -*) echo "Unknown option: $arg" >&2; sed -n '5,7p' "$0" >&2; exit 1 ;;
    *) SOURCES+=("$arg") ;;
  esac
done

STAMP="$(date '+%Y%m%d-%H%M%S')"
mkdir -p "$BACKEND_DIR/logs"
LOG="$BACKEND_DIR/logs/vancouver-refresh-$STAMP.log"
SUMMARY="$BACKEND_DIR/logs/vancouver_sync_last.json"
section() { printf "\n== %s ==\n" "$1" | tee -a "$LOG"; }

section "ClubHub Vancouver refresh $STAMP (log: backend/logs/vancouver-refresh-$STAMP.log)"
START_UTC="$(date -u '+%Y-%m-%d %H:%M:%S')"

if [[ "$DRY_RUN" == true ]]; then
  section "Dry run (nothing written)"
  (cd "$BACKEND_DIR" && PYTHONUNBUFFERED=1 "$PYTHON_BIN" vancouver_sync.py --dry-run --skipped ${SOURCES[@]+"${SOURCES[@]}"}) 2>&1 | tee -a "$LOG"
  exit "${PIPESTATUS[0]}"
fi

section "Scraping ${SOURCES[*]:-all sources}"
(cd "$BACKEND_DIR" && PYTHONUNBUFFERED=1 "$PYTHON_BIN" vancouver_sync.py --skipped --json "$SUMMARY" ${SOURCES[@]+"${SOURCES[@]}"}) 2>&1 | tee -a "$LOG"
SYNC_STATUS=${PIPESTATUS[0]}

section "Refresh report"
REPORT_ARGS=(--db clubhub_vancouver.db)
# Judge only this run's sources on a full sync; a partial run would mark the rest SKIPPED.
[[ ${#SOURCES[@]} -eq 0 ]] && REPORT_ARGS+=(--since "$START_UTC")
(cd "$BACKEND_DIR" && "$PYTHON_BIN" refresh_report.py "${REPORT_ARGS[@]}") 2>&1 | tee -a "$LOG"
REPORT_STATUS=${PIPESTATUS[0]}

# vancouver_sync.py prints "Registry check (N):" when venues and vancouver_registry.py disagree.
if grep -q "^Registry check" "$LOG"; then
  section "Registry check flagged venues (see above)"
  [[ "$REPORT_STATUS" -eq 0 ]] && REPORT_STATUS=2
fi

[[ "$SYNC_STATUS" -ne 0 ]] && exit 1
exit "$REPORT_STATUS"
