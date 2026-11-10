#!/usr/bin/env bash
# The ClubHub Vancouver refresh: scrape every Metro Vancouver source into
# backend/clubhub_vancouver.db, check the results, publish clubhubvancouver.ca. See REFRESH.md.
#
#   ./update_vancouver.sh                         every source, then publish
#   ./update_vancouver.sh burnaby_activenet       only these source keys (vancouver_sync.py --list), then publish
#   ./update_vancouver.sh --no-publish            scrape + check only
#   ./update_vancouver.sh --skip-sync             re-check and publish what's already in the database
#   ./update_vancouver.sh --force                 publish even though the report flagged something
#   ./update_vancouver.sh --dry-run               fetch + filter, write nothing, list what filters dropped
#
# Publishing = export frontend/data/vancouver-snapshot.json, commit only that file, push
# main. The Vercel project that builds with NEXT_PUBLIC_CITY=vancouver deploys it; a
# failed Vercel build keeps the previous deploy live. There's no local next build here,
# so it can run alongside update_public_site.sh (which builds Victoria in frontend/).
# Victoria's database, snapshot and site are never touched.
#
# Exit code: 0 = all sources look right (and published), 2 = the report flagged something
# (nothing published unless --force), 1 = broke.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
PYTHON_BIN="$BACKEND_DIR/venv/bin/python"
[[ -x "$PYTHON_BIN" ]] || { echo "Missing backend venv python at $PYTHON_BIN" >&2; exit 1; }

SNAPSHOT="frontend/data/vancouver-snapshot.json"
SITE_URL="https://clubhubvancouver.ca"
# The Vercel project that builds ClubHub Vancouver (its deploy status links contain this name).
VERCEL_PROJECT="clubhub-vancouver"
# IndexNow key, hosted at frontend/public/<key>.txt. After a confirmed deploy we ping
# IndexNow so Bing/Yandex recrawl the fresh snapshot fast (best-effort, never fatal).
INDEXNOW_KEY="3b3716ec38394011928d74b1d93ed9f897fde6e270cb458798a71b17b88722e9"

DRY_RUN=false
PUBLISH=true
RUN_SYNC=true
FORCE=false
SOURCES=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --no-publish) PUBLISH=false ;;
    --skip-sync) RUN_SYNC=false ;;
    --force) FORCE=true ;;
    -*) echo "Unknown option: $arg" >&2; sed -n '5,10p' "$0" >&2; exit 1 ;;
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

SYNC_STATUS=0
if [[ "$RUN_SYNC" == true ]]; then
  section "Scraping ${SOURCES[*]:-all sources}"
  (cd "$BACKEND_DIR" && PYTHONUNBUFFERED=1 "$PYTHON_BIN" vancouver_sync.py --skipped --json "$SUMMARY" ${SOURCES[@]+"${SOURCES[@]}"}) 2>&1 | tee -a "$LOG"
  SYNC_STATUS=${PIPESTATUS[0]}
fi

section "Refresh report"
REPORT_ARGS=(--db clubhub_vancouver.db)
# Judge only this run's sources on a full sync; a partial run would mark the rest SKIPPED.
[[ "$RUN_SYNC" == true && ${#SOURCES[@]} -eq 0 ]] && REPORT_ARGS+=(--since "$START_UTC")
(cd "$BACKEND_DIR" && "$PYTHON_BIN" refresh_report.py "${REPORT_ARGS[@]}") 2>&1 | tee -a "$LOG"
REPORT_STATUS=${PIPESTATUS[0]}

# vancouver_sync.py prints "Registry check (N):" when venues and vancouver_registry.py disagree.
if grep -q "^Registry check" "$LOG"; then
  section "Registry check flagged venues (see above)"
  [[ "$REPORT_STATUS" -eq 0 ]] && REPORT_STATUS=2
fi

[[ "$SYNC_STATUS" -ne 0 ]] && exit 1

if [[ "$PUBLISH" != true ]]; then
  section "Not publishing (--no-publish)"
  exit "$REPORT_STATUS"
fi
if [[ "$REPORT_STATUS" -ne 0 && "$FORCE" != true ]]; then
  section "Not publishing: the report flagged something (fix it, or rerun with --skip-sync --force)"
  exit "$REPORT_STATUS"
fi

# --- Publish -----------------------------------------------------------------------
section "Exporting snapshot"
(cd "$BACKEND_DIR" && "$PYTHON_BIN" export_demo_snapshot.py --city vancouver) 2>&1 | tail -2 | tee -a "$LOG"
[[ ${PIPESTATUS[0]} -eq 0 ]] || { echo "Export failed - nothing published." | tee -a "$LOG"; exit 1; }

section "Publishing"
cd "$ROOT_DIR"
if [[ "$(git rev-parse --abbrev-ref HEAD)" != main ]]; then
  echo "Not on main - snapshot exported but not published." | tee -a "$LOG"; exit 1
fi
if git diff --quiet -- "$SNAPSHOT" && git ls-files --error-unmatch "$SNAPSHOT" >/dev/null 2>&1; then
  echo "Snapshot unchanged; nothing to publish." | tee -a "$LOG"; exit "$REPORT_STATUS"
fi
# update_public_site.sh may be committing in this same repo right now: retry on index.lock.
for attempt in 1 2 3 4 5; do
  git add -- "$SNAPSHOT" && git commit -q -m "Refresh ClubHub Vancouver snapshot with $(date '+%Y-%m-%d') scrape" -- "$SNAPSHOT" && break
  [[ $attempt -eq 5 ]] && { echo "git commit failed - see above." | tee -a "$LOG"; exit 1; }
  sleep 3
done
# Someone else may have pushed main meanwhile; this commit only touches the Vancouver snapshot.
for attempt in 1 2 3; do
  git push -q origin main 2>&1 | tee -a "$LOG"
  [[ ${PIPESTATUS[0]} -eq 0 ]] && break
  [[ $attempt -eq 3 ]] && { echo "git push failed - the commit is local only." | tee -a "$LOG"; exit 1; }
  git pull -q --rebase --autostash origin main 2>&1 | tee -a "$LOG"
done
SHA="$(git rev-parse HEAD)"
echo "Pushed $(git rev-parse --short HEAD); Vercel deploys main." | tee -a "$LOG"

section "Waiting for the live site"
# Vercel reports each project's deploy to GitHub as a commit status; pick this project's
# by its link. A 403 with x-vercel-mitigated from the site is Vercel's bot challenge.
REPO="$(git remote get-url origin | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"
DEPLOY=""
for _ in $(seq 1 40); do
  DEPLOY="$(gh api "repos/$REPO/commits/$SHA/status" --jq ".statuses[] | select(.target_url | test(\"/$VERCEL_PROJECT/\")) | .state" 2>/dev/null | head -1 || true)"
  [[ "$DEPLOY" == "success" || "$DEPLOY" == "failure" || "$DEPLOY" == "error" ]] && break
  sleep 15
done
case "$DEPLOY" in
  success)
    echo "Vercel deployed $(git rev-parse --short HEAD) to $VERCEL_PROJECT; $SITE_URL is live." | tee -a "$LOG"
    "$ROOT_DIR/indexnow_ping.sh" "$SITE_URL" "$INDEXNOW_KEY" 2>&1 | tee -a "$LOG" \
      || echo "IndexNow ping failed (non-fatal) - the deploy is still live." | tee -a "$LOG"
    ;;
  failure|error) echo "Vercel deploy of $(git rev-parse --short HEAD) to $VERCEL_PROJECT FAILED (the previous deploy stays live) - check the Vercel dashboard." | tee -a "$LOG"; exit 1 ;;
  *) echo "No Vercel deploy status for $VERCEL_PROJECT on $(git rev-parse --short HEAD) (project not set up yet, gh not logged in, or still building)." | tee -a "$LOG" ;;
esac
exit "$REPORT_STATUS"
