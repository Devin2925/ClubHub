#!/usr/bin/env bash
# Tell IndexNow (Bing, Yandex, and others that share the protocol) that a site's
# pages changed, so a fresh scrape gets recrawled in hours instead of waiting for
# the next natural crawl. Best-effort: called after a successful deploy, never
# allowed to fail the publish.
#
#   ./indexnow_ping.sh <site_url> <key>
#   ./indexnow_ping.sh https://clubhubvancouver.ca <key>
#
# It reads the LIVE sitemap (so it submits exactly what Google is given) and POSTs
# the URL list to the shared IndexNow endpoint. The key must be hosted at
# <site_url>/<key>.txt (frontend/public/<key>.txt serves it on every ClubHub domain).
set -uo pipefail

SITE_URL="${1:?usage: indexnow_ping.sh <site_url> <key>}"
KEY="${2:?usage: indexnow_ping.sh <site_url> <key>}"
SITE_URL="${SITE_URL%/}"
HOST="$(printf '%s' "$SITE_URL" | sed -E 's#^https?://##; s#/.*$##')"

URLS="$(curl -sf --max-time 30 "$SITE_URL/sitemap.xml" | grep -oE '<loc>[^<]+</loc>' | sed -E 's#</?loc>##g')"
if [[ -z "$URLS" ]]; then
  echo "IndexNow: no URLs found in $SITE_URL/sitemap.xml - nothing submitted." >&2
  exit 1
fi
COUNT="$(printf '%s\n' "$URLS" | grep -c .)"

BODY="$(URLS="$URLS" HOST="$HOST" KEY="$KEY" SITE_URL="$SITE_URL" python3 - <<'PY'
import json, os
urls = [u.strip() for u in os.environ["URLS"].splitlines() if u.strip()]
print(json.dumps({
    "host": os.environ["HOST"],
    "key": os.environ["KEY"],
    "keyLocation": f'{os.environ["SITE_URL"]}/{os.environ["KEY"]}.txt',
    "urlList": urls,
}))
PY
)"

HTTP="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 \
  -X POST 'https://api.indexnow.org/indexnow' \
  -H 'Content-Type: application/json; charset=utf-8' \
  --data "$BODY")"

# 200 = accepted, 202 = received (key check pending). Others are informative, not fatal:
# 400 bad body, 403 key not found at keyLocation, 422 URL/host or key mismatch, 429 throttled.
echo "IndexNow: submitted $COUNT URLs for $HOST -> HTTP $HTTP"
case "$HTTP" in
  200|202) exit 0 ;;
  *) echo "IndexNow: endpoint returned $HTTP (see codes in script header)." >&2; exit 1 ;;
esac
