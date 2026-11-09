#!/usr/bin/env bash
# The ClubHub refresh: scrape everything, check it, publish it, confirm it's live.
# See REFRESH.md for how to read the report and what to do when a step stops.
#
#   ./update_public_site.sh                       full refresh and publish
#   ./update_public_site.sh --no-publish          everything up to a local build; no commit/push
#   ./update_public_site.sh --skip-sync           re-check/re-publish the data already in the DB
#   ./update_public_site.sh --source-key oakbay_events --source-key saanich_events
#                                                 refresh only those sources, then publish
#   ./update_public_site.sh --force               publish even if the report says CHECK
#
# Publishing = commit frontend/data/demo-snapshot.json only, push main; Vercel
# deploys main by itself. Nothing else in the working tree is committed.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PYTHON_BIN="$BACKEND_DIR/venv/bin/python"
SNAPSHOT="frontend/data/demo-snapshot.json"
SITE_URL="https://clubhubvictoria.ca"

RUN_SYNC=true
PUBLISH=true
FORCE=false
SYNC_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-sync) RUN_SYNC=false ;;
    --no-publish|--no-deploy) PUBLISH=false ;;
    --force) FORCE=true ;;
    --source-key) SYNC_ARGS+=(--source-key "$2"); shift ;;
    *)
      echo "Unknown option: $1" >&2
      sed -n '4,10p' "$0" >&2
      exit 1
      ;;
  esac
  shift
done

STAMP="$(date '+%Y%m%d-%H%M%S')"
mkdir -p "$BACKEND_DIR/logs"
LOG="$BACKEND_DIR/logs/refresh-$STAMP.log"
section() { printf "\n== %s ==\n" "$1" | tee -a "$LOG"; }

section "ClubHub refresh $STAMP (log: backend/logs/refresh-$STAMP.log)"

# --- 1. Preflight ----------------------------------------------------------------
[[ -x "$PYTHON_BIN" ]] || { echo "Missing backend venv python at $PYTHON_BIN" >&2; exit 1; }
cd "$ROOT_DIR"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$PUBLISH" == true && "$BRANCH" != "main" ]]; then
  echo "On branch '$BRANCH'; publishing pushes main. Switch to main or use --no-publish." >&2
  exit 1
fi
# Other people's/sessions' work in progress is left alone; just say it's there.
OTHER_CHANGES="$(git status --porcelain | grep -v -e " 2\." -e " 3\." -e "backend.code-workspace" -e "$SNAPSHOT" || true)"
if [[ -n "$OTHER_CHANGES" ]]; then
  echo "Note: uncommitted changes besides the snapshot (not touched, not committed):" | tee -a "$LOG"
  echo "$OTHER_CHANGES" | sed 's/^/  /' | tee -a "$LOG"
fi

# --- 2. Scrape -------------------------------------------------------------------
START_UTC="$(date -u '+%Y-%m-%d %H:%M:%S')"
if [[ "$RUN_SYNC" == true ]]; then
  if [[ ${#SYNC_ARGS[@]} -gt 0 ]]; then section "Scraping (${SYNC_ARGS[*]})"; else section "Scraping all sources"; fi
  (cd "$BACKEND_DIR" && PYTHONUNBUFFERED=1 "$PYTHON_BIN" run_sync.py ${SYNC_ARGS[@]+"${SYNC_ARGS[@]}"}) 2>&1 | tee -a "$LOG"
else
  section "Skipping scrape"
fi

# --- 3. Check --------------------------------------------------------------------
section "Refresh report"
REPORT_ARGS=()
# Judge only this run's sources on a full sync; a partial run would mark the rest SKIPPED.
if [[ "$RUN_SYNC" == true && ${#SYNC_ARGS[@]} -eq 0 ]]; then
  REPORT_ARGS=(--since "$START_UTC")
fi
set +e
(cd "$BACKEND_DIR" && "$PYTHON_BIN" refresh_report.py ${REPORT_ARGS[@]+"${REPORT_ARGS[@]}"}) 2>&1 | tee -a "$LOG"
REPORT_STATUS=${PIPESTATUS[0]}
set -e
{
  echo; echo "-- source_alerts / venue_alerts / completeness_audit (detail, log only) --"
  (cd "$BACKEND_DIR" && "$PYTHON_BIN" source_alerts.py && "$PYTHON_BIN" venue_alerts.py && "$PYTHON_BIN" completeness_audit.py)
} >> "$LOG" 2>&1 || true

if [[ "$REPORT_STATUS" -ne 0 && "$FORCE" != true ]]; then
  section "Stopped before publishing"
  echo "The report flagged sources to check (above). Look at them in $LOG."
  echo "When the result is expected, add it to KNOWN_NOISE in backend/refresh_report.py,"
  echo "or rerun with --skip-sync --force to publish the data as it is."
  exit 2
fi

# --- 4. Export + build check -----------------------------------------------------
section "Exporting snapshot"
(cd "$BACKEND_DIR" && "$PYTHON_BIN" export_demo_snapshot.py) 2>&1 | tail -2 | tee -a "$LOG"

section "Build check"
# The Desktop is iCloud-synced and grows "name 2.tsx" copies that break next build.
# Park them outside the app for the build and always put them back.
PARKED="$(mktemp -d)"
restore_parked() {
  if [[ -d "$PARKED/app" ]]; then
    (cd "$PARKED" && find app -type f -print0) | while IFS= read -r -d '' f; do
      mkdir -p "$FRONTEND_DIR/$(dirname "$f")"
      mv "$PARKED/$f" "$FRONTEND_DIR/$f"
    done
  fi
  rm -rf "$PARKED"
}
trap restore_parked EXIT
(cd "$FRONTEND_DIR" && find app -name "* [0-9].*" -print0) | while IFS= read -r -d '' f; do
  mkdir -p "$PARKED/$(dirname "$f")"
  mv "$FRONTEND_DIR/$f" "$PARKED/$f"
done
if ! (cd "$FRONTEND_DIR" && NEXT_PUBLIC_DEMO_MODE=true npx next build) >> "$LOG" 2>&1; then
  echo "next build failed - nothing published. See the end of $LOG." | tee -a "$LOG"
  exit 1
fi
restore_parked
trap - EXIT
echo "Build OK." | tee -a "$LOG"

# --- 5. Publish ------------------------------------------------------------------
if [[ "$PUBLISH" != true ]]; then
  section "Not publishing (--no-publish)"
  echo "Snapshot exported and built locally; $SNAPSHOT is uncommitted."
  exit 0
fi

section "Publishing"
git add "$SNAPSHOT"
if git diff --cached --quiet -- "$SNAPSHOT"; then
  echo "Snapshot unchanged; nothing to publish." | tee -a "$LOG"
  exit 0
fi
git commit -q -m "Refresh public snapshot with $(date '+%Y-%m-%d') scrape" -- "$SNAPSHOT"
git push -q origin main 2>&1 | tee -a "$LOG"
echo "Pushed $(git rev-parse --short HEAD); Vercel deploys main." | tee -a "$LOG"

# --- 6. Confirm live -------------------------------------------------------------
section "Waiting for the live site"
# Vercel reports each deploy back to GitHub as a commit status; that's the
# authoritative "it's live". The sitemap check is a second look: its lastmod is the
# snapshot's generated_at. Vercel's firewall sometimes challenges scripted requests
# (403 + x-vercel-mitigated), so a blocked sitemap isn't treated as a failed deploy.
SHA="$(git rev-parse HEAD)"
REPO="$(git remote get-url origin | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"
EXPECTED="$("$PYTHON_BIN" -c "import json; print(json.load(open('$SNAPSHOT'))['generated_at'][:16])")"
DEPLOY=""
for _ in $(seq 1 40); do
  # Victoria's Vercel project is "frontend". Match on its URL, not the status name, which
  # becomes "Vercel – <project>" once a second (Vancouver) project deploys the same repo.
  DEPLOY="$(gh api "repos/$REPO/commits/$SHA/status" --jq '.statuses[] | select((.context | startswith("Vercel")) and (.target_url // "" | contains("/frontend/"))) | .state' 2>/dev/null | head -1 || true)"
  [[ "$DEPLOY" == "success" || "$DEPLOY" == "failure" || "$DEPLOY" == "error" ]] && break
  sleep 15
done
case "$DEPLOY" in
  success) echo "Vercel deployed $(git rev-parse --short HEAD)." | tee -a "$LOG" ;;
  failure|error) echo "Vercel deploy of $(git rev-parse --short HEAD) FAILED - check the Vercel dashboard." | tee -a "$LOG"; exit 1 ;;
  *) echo "Couldn't read the Vercel deploy status from GitHub (gh missing/not logged in, or still building)." | tee -a "$LOG" ;;
esac

HEADERS="$(curl -s -D - -o "$PARKED.sitemap" "$SITE_URL/sitemap.xml" || true)"
if grep -q "$EXPECTED" "$PARKED.sitemap" 2>/dev/null; then
  echo "Live: $SITE_URL serves the snapshot generated $EXPECTED UTC." | tee -a "$LOG"
elif grep -qi "x-vercel-mitigated" <<<"$HEADERS"; then
  echo "Couldn't read $SITE_URL from this script: Vercel's firewall answered with a challenge" | tee -a "$LOG"
  echo "(normal browsers pass it). Open the site in a browser to eyeball the new data." | tee -a "$LOG"
else
  echo "$SITE_URL doesn't show the snapshot generated $EXPECTED UTC yet; recheck in a few minutes." | tee -a "$LOG"
fi
rm -f "$PARKED.sitemap"
[[ "$DEPLOY" == "success" ]] && exit 0 || exit 1
