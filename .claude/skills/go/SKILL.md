---
name: go
description: Run the whole ClubHub refresh end to end - scrape ClubHub Victoria and ClubHub Vancouver, fix whatever the reports flag (changed PDFs, broken scrapers, new junk rows, unknown venues), publish both sites, and report back. Use when Devin says "go", "/go", "it's that time again", "refresh", "run the scrape" or similar in the ClubHub repo.
---

# ClubHub "go"

Devin's standing request: when he says "go", run the full refresh for both cities without
asking, fix what breaks, publish both sites, and tell him what happened.

**Pre-approved for this routine:** committing and pushing `frontend/data/demo-snapshot.json`
and `frontend/data/vancouver-snapshot.json` (the scripts do this), and committing and pushing the fixes you make during the run:
scraper fixes, `KNOWN_NOISE` entries, registry entries, `VENUE_ALIASES`, filter patterns.
Commit only the exact files you changed.

**Ask first:** retiring a source or deleting its rows, frontend/page changes, committing
anyone else's uncommitted work, or `--force` over a flag you haven't verified is expected.

The two cities never mix: Victoria = `backend/clubhub.db` → `demo-snapshot.json` → clubhubvictoria.ca;
Vancouver = `backend/clubhub_vancouver.db` → `vancouver-snapshot.json` → clubhubvancouver.ca.
It's one Next app deployed twice: the Vercel project `clubhub-vancouver` builds with
`NEXT_PUBLIC_CITY=vancouver` (see `frontend/app/lib/city.ts`). Both deploy on every push to main.

## 0. Preflight

```sh
cd <repo root> && git status --short && git pull --ff-only
```

- Must be on `main`. Other sessions also push to main, so pull first.
- Leave other people's uncommitted changes alone; the scripts never commit them. If a fix
  you need touches a file someone else has uncommitted edits in, stop and ask.
- Don't start if another refresh is running (a `backend/logs/refresh-*.log` still being
  written, or another Claude session says it's refreshing).

## 1. Run both refreshes, in parallel

They use different databases, so run both in the background and wait for both:

```sh
./update_public_site.sh      # Victoria: scrape, report, export, build, publish, confirm live (5-10 min)
./update_vancouver.sh        # Vancouver: scrape 12 sources, report, registry check, export, publish, confirm (~5 min)
```

Only Victoria's script runs `next build` locally (Vancouver relies on Vercel's build), so they
don't collide in `frontend/`. Both commit just their own snapshot and retry the push if the
other got there first.

| Exit | Victoria (`update_public_site.sh`) | Vancouver (`update_vancouver.sh`) |
|---|---|---|
| 0 | Published and Vercel deployed | Every source OK, registry matches, published |
| 2 | Stopped at the report, **nothing published** | Report or registry check flagged something, **nothing published** |
| 1 | Build or deploy broke | Sync, export, push or Vercel deploy broke |

Logs: `backend/logs/refresh-<stamp>.log` (Victoria) and `backend/logs/vancouver-refresh-<stamp>.log`.
REFRESH.md explains the report verdicts (OK / KNOWN / CHECK / FAILED / SKIPPED / STALE).

## 2. Triage every flag

Find the source's lines in the log: `grep -n "\[Oak Bay\]" backend/logs/refresh-<stamp>.log`.
Then decide which case it is:

1. **Transient** (timeout, 5xx, one-off empty page): rerun that source alone.
   Victoria: `./update_public_site.sh --source-key <key> --no-publish`; Vancouver: `./update_vancouver.sh <key>`.
2. **Expected** (closure, off-season, month-only PDF between posts): add the key to
   `KNOWN_NOISE` in `backend/refresh_report.py` with a one-line reason so it won't flag again.
3. **The source changed:** fix the scraper (below), rerun just that source, and confirm the
   numbers look right before publishing.

### Victoria PDFs and scrapers

- PDF scrapers find the newest PDF on their page by themselves (`_discover_pdf_url` and
  similar), so new months and seasons flow in without code changes. A PDF breaks when its
  **layout** changes. The signs are "Skipping schedule" or "Unrecognized row" in the log, or
  a count that halves.
- To fix one: download the PDF into the scratchpad, look at it with pdfplumber
  (`page.extract_words()` gives x/y positions), and compare with the parser. Oak Bay's PDFs
  share `backend/scrapers/oakbay_grid.py`. Run one scraper alone with
  `cd backend && ./venv/bin/python -c "from scrapers.<mod> import <Cls>; print(len(<Cls>().scrape()))"`.
- A failed scrape keeps its old rows. STALE means rows nobody refreshes; usually a dead
  feed (Fernwood's EventON did this).
- Known noise: Crystal Pool is closed (the closure note is in `frontend/app/lib/closures.ts`).
  The interim Victoria Recreation Centre opens early 2027 and will need a new source, plus a
  change to that closure entry. Cook Street and JBNH dip mid-month (month-only PDFs). Summer
  and spring camps appear when providers publish (early 2027); no code change is needed.
- Each term: recheck the CARSA student facts (vikesrec.ca/membership) used in `VENUE_SPORT_SEO`.
- Community event calendars: Oak Bay, Saanich, Esquimalt, City of Victoria, WSPR, Langford,
  Panorama, SEAPARC and Fernwood. The REFRESH.md table "Community event calendars" says how
  each one is read. Small counts are normal: Victoria's city calendar is near-empty outside the
  CityVibe summer season, and WSPR's hockey games end in March. A FAILED one is usually a
  redesign, so check that the data is still where the scraper's docstring says.

### Vancouver sources (`backend/scrapers/vancouver_*.py`)

- **FAILED ActiveNet** (`*_activenet`): open `https://anc.ca.apm.activecommunities.com/<tenant>/calendars`.
  The tenant list is `ACTIVENET_SOURCES` in `vancouver_activenet.py`.
- **FAILED PerfectMind** (`*_perfectmind`) with "widget page refused": the city changed
  its widget or account id. Find the new BookMe4 link on the city's drop-in page and update
  `PERFECTMIND_SOURCES` in `vancouver_perfectmind.py`.
- **CHECK on a count:** PerfectMind cities publish only 2-4 weeks ahead (Coquitlam ~2,
  Delta ~4), and holiday weeks dip, so look at the source before calling it broken.
- **Registry check** (printed by `vancouver_sync.py`):
  - `NOT IN REGISTRY`: either a spelling difference, which goes in `VENUE_ALIASES` in
    `vancouver_common.py`, or a real new venue, which needs a `venue(...)` entry in
    `backend/vancouver_registry.py`.
  - `NO SESSIONS`: the venue closed, was renamed or is off-season. Check it, then update its
    registry status and notes.
- **Junk rows:** read the "Dropped as …" and "Kept, but worth a look" lists in the log. If
  rentals, private lessons or closures got through, add a pattern in `vancouver_common.py`,
  check it with `./update_vancouver.sh --dry-run <key>`, then rerun that source.
- **Rules Devin set (don't relitigate):**
  - Drop private lessons, rentals and closures or cancellations.
  - A per-court or per-table booking counts as a rental, unless its description calls it a drop-in.
  - Keep Vancouver's pool-calendar "Lessons" rows; they're public swim during lessons.
  - Keep Burnaby's "Reserve In Advance" drop-ins, including squash and racquetball courts.
- Kerrisdale Pool: the registry asks to confirm its sessions are real (news said it was
  closed most of 2026). Vancouver Aquatic Centre has been closed since 2026-06-28.

## 3. Publish Victoria and save fixes

1. Commit your fixes first, naming only the files you changed:
   `git add <files> && git commit -m "<what broke and how it's fixed>" && git push`.
2. If a script exited 0, that site is already live. Otherwise rerun it without scraping to
   re-check, publish and confirm: `./update_public_site.sh --skip-sync` (Victoria) or
   `./update_vancouver.sh --skip-sync` (Vancouver).
   - Use `--force` only when every remaining flag is verified expected.
   - Prefer adding the flag to `KNOWN_NOISE`, so it won't flag again next time.
3. The script confirms the deploy through Vercel's GitHub status, then the sitemap. A
   403 with `x-vercel-mitigated` is Vercel's bot challenge, not a failed deploy.
   Pages are client-rendered, so to eyeball the live data, render the page with Playwright
   (`backend/venv` has chromium) instead of curl.
4. Vancouver's deploy check finds the `clubhub-vancouver` project's status by its link
   (`VERCEL_PROJECT` in `update_vancouver.sh`). "No Vercel deploy status" means the project
   isn't connected or is still building; look at the Vercel dashboard. A failed Vancouver
   build keeps its previous deploy live and never affects Victoria.

## 4. Report to Devin

Keep it short:
- **Victoria:** published or not, upcoming sessions by area, and what flagged and what you
  did about each.
- **Vancouver:** published or not, sessions by city, what flagged and what you did.
- **Fixes:** each fix you committed, with its commit hash.
- **Needs Devin:** anything that's his call, such as a source to retire, a closure notice,
  or a new venue worth a page.

Put new recurring quirks into REFRESH.md or `KNOWN_NOISE` rather than only in memory, so the
next "go" knows them.
