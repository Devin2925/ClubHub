# Refreshing ClubHub Victoria

One command scrapes every source, checks the results, builds the site, publishes
the new data and waits until it's live:

```sh
./update_public_site.sh
```

It takes about 5–10 minutes. Everything it prints is also saved to
`backend/logs/refresh-<timestamp>.log`.

## What it does

1. **Preflight.** Confirms you're on `main` and lists any other uncommitted
   changes. It leaves those changes alone and never commits them.
2. **Scrape.** Runs `backend/run_sync.py` (every source in `iter_scrapers()`).
   A source that fails keeps its existing rows.
3. **Check.** Runs `backend/refresh_report.py`, which gives one line per source:
   - `OK`: it ran and returned plausible numbers.
   - `KNOWN`: something looks odd, but it's expected (listed in `KNOWN_NOISE`).
   - `CHECK`: it ran but returned 0, or dropped by half. **Look before publishing.**
   - `FAILED`: the scrape errored. Its old rows are still in place.
   - `SKIPPED`: it didn't run in this refresh.
   - `STALE`: upcoming rows that no source has refreshed in 10+ days. This is
     usually a dead feed or a removed scraper; Fernwood's old EventON feed did this.

   If anything is `CHECK`, `FAILED`, `SKIPPED` or `STALE`, the script **stops
   here** without publishing.
4. **Export + build.** Writes `frontend/data/demo-snapshot.json` and runs
   `next build`. iCloud's "name 2.tsx" copies are moved aside for the build and
   always put back.
5. **Publish.** Commits only the snapshot and pushes `main`. Vercel deploys `main`
   on its own.
6. **Confirm.** Waits for Vercel's deploy status on the pushed commit (read from
   GitHub with `gh`), then checks that the live sitemap shows the new snapshot
   time. Vercel's firewall sometimes answers scripts with a challenge (403,
   `x-vercel-mitigated`). The script says so, and it isn't a failed deploy; open
   the site in a browser to look.

## Options

| | |
|---|---|
| `--no-publish` | Stop after the local build (nothing committed or pushed) |
| `--skip-sync` | Re-check and publish what's already in the database |
| `--source-key KEY` | Scrape only that source (repeatable), then publish |
| `--force` | Publish even though the report flagged something |

## When it stops at the report

1. Find the source in the log, e.g. `grep -n "\[Oak Bay\]" backend/logs/refresh-*.log | tail`.
2. Open the source's own page (the URL is in the scraper's docstring and in
   `backend/venue_registry.py`).
3. Then do one of these:
   - **The site changed:** fix the scraper, then rerun just that source with
     `--source-key`.
   - **The number is expected** (a closure, an off-season month): add it to
     `KNOWN_NOISE` in `backend/refresh_report.py` with a one-line reason.
   - **The source is gone for good:** remove it from `run_sync.py` and delete its
     upcoming rows (`delete from events where source='<prefix>'`, after copying
     `backend/clubhub.db` to `backend/backups/`). Otherwise its rows show as STALE.
   - **Publish anyway:** `./update_public_site.sh --skip-sync --force`.

Known noise today: Crystal Pool is closed (`perfectmind_victoria` has few rows);
Cook Street and James Bay New Horizons post month-only PDFs, so their counts
dip mid-month. Off-season, the City of Victoria calendar (`victoria_events`) can
be empty; in summer it fills with CityVibe events.

### Community event calendars

Events are saved as offering "event" (Community). Each scraper's docstring says
where it reads from.

| Source key | Calendar | How it's read |
|---|---|---|
| `oakbay_events` | oakbay.ca events | The Events Calendar (Tribe) JSON API |
| `saanich_events` | saanich.ca events, plus ActiveNet "Social - Events" | RSS, plus each page's `calendarEvent` |
| `esquimalt_events`, `victoria_events`, `wspr_events` | esquimalt.ca, victoria.ca, wspr.ca | Drupal FullCalendar JSON in the page (`drupal_calendar_events.py`) |
| `langford_events` | langford.ca/events | Modern Events Calendar REST list, plus each page's JSON-LD |
| `panorama_events`, `seaparc_events` | Panorama and SEAPARC special events | CRD month grid (`crd_special_events.py`), 6 months ahead |
| `fernwood_calendar` | fernwoodnrg.ca | Tribe JSON API (programs plus events) |

- When a calendar breaks, it's usually a redesign. Open its page and check that
  the data is still where the docstring says.
- Event times are B.C. local time (UTC-7 year-round since Nov 2026), stored as
  wall-clock time.
- WSPR hockey games stop after March. A sharp drop then is the season ending,
  not a bug.

## Adding a new source

1. Write `backend/scrapers/<name>.py` (a `BaseScraper` subclass). Put the source
   URL and anything odd about it in the docstring. Shared helpers:
   - `event_utils.event_row` for community events.
   - `camp_utils.camp_row` for camps.
   - `prune_unseen_upcoming()` after a complete run.
2. Add a `yield` for it in `iter_scrapers()` in `backend/run_sync.py`.
3. Add or update the venue in `backend/venue_registry.py`.
4. Try it: `./update_public_site.sh --source-key <key> --no-publish`.

## Where things live

| | |
|---|---|
| Live database | `backend/clubhub.db` (gitignored; the sync backs it up to `backend/backups/` each run) |
| Published data | `frontend/data/demo-snapshot.json` |
| Vancouver (separate) | `./update_vancouver.sh` → `backend/clubhub_vancouver.db`; see below |

## ClubHub Vancouver

```sh
./update_vancouver.sh                     # every source, then publish (~5 min)
./update_vancouver.sh burnaby_activenet   # one source (keys: backend/vancouver_sync.py --list), then publish
./update_vancouver.sh --no-publish        # scrape + check only
./update_vancouver.sh --skip-sync         # re-check and publish what's in the database
./update_vancouver.sh --dry-run           # fetch + filter only; lists what the filters dropped
```

It scrapes the 16 Metro Vancouver sources into `backend/clubhub_vancouver.db`:
- four ActiveNet cities (`scrapers/vancouver_activenet.py`)
- nine PerfectMind sources (`scrapers/vancouver_perfectmind.py`): eight cities, plus
  Township of Langley skating only so far
- UBC Recreation (`scrapers/vancouver_ubc.py`), read from the JSON feed behind
  recreation.ubc.ca's schedule pages
- SFU Recreation (`scrapers/vancouver_sfu.py`), whose weekly drop-in table repeats
  until the term ends
- City of Surrey (`scrapers/vancouver_surrey.py` + `scrapers/surrey_grid.py`), read from
  the weekday-grid PDFs on surrey.ca/dropin (Gym, Youth, Seniors, Arena, Aquatics)

Then it runs the same `refresh_report.py` (`--db clubhub_vancouver.db`) and compares the venues with
`backend/vancouver_registry.py`. If everything is OK it exports
`frontend/data/vancouver-snapshot.json` (`export_demo_snapshot.py --city vancouver`),
commits only that file, pushes main, and waits for the `clubhub-vancouver` Vercel
project's deploy status. Nothing touches Victoria.

**The site** is the same Next app as Victoria, built with `NEXT_PUBLIC_CITY=vancouver`:

- `frontend/app/lib/city.ts` holds each city's name, domain and region.
- Per-city copy sits next to Victoria's in `lib/seo.ts`, `lib/searchPages.ts`,
  `lib/closures.ts` and `layout.tsx`.
- `next.config.ts` points `@clubhub/snapshot` at the city's snapshot.
- `/camps` is Victoria-only.
- To preview it locally:
  `cd frontend && NEXT_PUBLIC_CITY=vancouver NEXT_PUBLIC_DEMO_MODE=true npx next dev`.

- **Drop-in filters:** `scrapers/vancouver_common.py` drops private lessons,
  rentals (including per-court bookings) and closures. Each run's log lists what
  was dropped and what was kept but looks borderline.
- **Registry check:** `NOT IN REGISTRY` means add a `VENUE_ALIASES` entry for a
  spelling difference, or a registry `venue(...)` entry for a new venue.
  `NO SESSIONS` means the venue closed, was renamed or is off-season.
- **"go":** in Claude Code, saying "go" runs both refreshes, triages the flags and
  publishes Victoria (`.claude/skills/go/SKILL.md`).
