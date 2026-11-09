"""One-screen health check after a sync: is this scrape safe to publish?

    ./venv/bin/python refresh_report.py                      # every source's latest run
    ./venv/bin/python refresh_report.py --since "2026-11-09 17:00"   # this refresh only (UTC)
    ./venv/bin/python refresh_report.py --db clubhub_vancouver.db    # ClubHub Vancouver's sources

Each source gets a verdict:
  OK      ran, returned events, no sharp drop
  KNOWN   something looks off but it's expected (see KNOWN_NOISE) - no action
  CHECK   ran but returned 0, or dropped by half - look before publishing
  FAILED  the scrape errored (its old rows are kept)
  SKIPPED didn't run in this refresh (only with --since)

It also lists STALE rows: upcoming sessions whose source hasn't refreshed them in
STALE_DAYS. That catches a scraper that "succeeds" with nothing (a dead feed)
while its old rows stay on the site - Fernwood's EventON feed did this for five
weeks in Oct-Nov 2026.

Exit code 0 = ready to publish, 2 = at least one CHECK/FAILED/SKIPPED.
update_public_site.sh stops before publishing on exit code 2 unless --force.
"""
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "clubhub.db"

# Sources whose odd numbers are expected. Keep each note to what to expect and why.
KNOWN_NOISE = {
    "perfectmind_victoria": "Crystal Pool closed for good (2026-09-25); only a few City of Victoria rows remain.",
    "cook_street_pdf": "Month-only PDF: counts fall through the month and jump when next month's PDF posts.",
    "jbnh_monthly_pdf": "Month-only PDF: 0 is normal between James Bay New Horizons monthly posts.",
    # ClubHub Vancouver (clubhub_vancouver.db) sources go here too; keys don't overlap.
}

# A source that normally lists at least this many should never come back empty.
DROP_SHARE = 0.5
DROP_MIN_PREVIOUS = 20
STALE_DAYS = 10


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).split(".")[0])


def verdict(row: sqlite3.Row, since: datetime | None) -> tuple[str, str]:
    key = row["source_key"]
    completed = _parse(row["last_completed_at"])
    current, previous = row["last_event_count"] or 0, row["previous_event_count"] or 0
    error = (row["last_error"] or "").strip().splitlines()[0][:110] if row["last_error"] else ""

    if since and (not completed or completed < since):
        return "SKIPPED", f"last ran {completed:%Y-%m-%d %H:%M} UTC" if completed else "never ran"
    if error.startswith("planned_closure:"):
        return "KNOWN", error
    problem = ""
    if row["status"] == "error":
        problem = f"error: {error or 'unknown'}"
    elif current == 0:
        problem = "ran but returned 0 events"
    elif previous >= DROP_MIN_PREVIOUS and current <= previous * DROP_SHARE:
        problem = f"dropped {previous} -> {current}"
    if not problem:
        return "OK", ""
    if key in KNOWN_NOISE:
        return "KNOWN", f"{problem}. {KNOWN_NOISE[key]}"
    return ("FAILED" if row["status"] == "error" else "CHECK"), problem


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", help="Only judge runs completed at/after this UTC time (YYYY-MM-DD HH:MM[:SS])")
    parser.add_argument("--db", default=str(DB_PATH), help="Database to check (default: Victoria's clubhub.db)")
    args = parser.parse_args()
    since = _parse(args.since) if args.since else None

    db_path = Path(args.db) if Path(args.db).is_absolute() else Path(__file__).resolve().parent / args.db
    if not db_path.exists():
        print(f"No database at {db_path}")
        return 2
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("select * from source_sync_status order by municipality, source_key").fetchall()

    order = {"FAILED": 0, "CHECK": 1, "SKIPPED": 2, "KNOWN": 3, "OK": 4}
    judged = sorted(((verdict(row, since), row) for row in rows), key=lambda item: (order[item[0][0]], item[1]["municipality"]))

    print(f"Refresh report - {len(rows)} sources" + (f", runs since {since:%Y-%m-%d %H:%M} UTC" if since else ""))
    print(f"{'verdict':8} {'source':38} {'events':>13} {'secs':>5}  note")
    for (label, note), row in judged:
        counts = f"{row['previous_event_count'] or 0}->{row['last_event_count'] or 0}"
        secs = round((row["last_duration_ms"] or 0) / 1000)
        print(f"{label:8} {row['source_key'][:38]:38} {counts:>13} {secs:>5}  {note}")

    today = datetime.now().strftime("%Y-%m-%d")
    print("\nUpcoming rows by type:", ", ".join(
        f"{offering or '?'} {count}"
        for offering, count in conn.execute(
            "select offering_type, count(*) from events where start_time >= ? group by 1 order by 2 desc", (today,)
        )
    ))
    print("Upcoming rows by area:", ", ".join(
        f"{municipality} {count}"
        for municipality, count in conn.execute(
            "select municipality, count(*) from events where start_time >= ? group by 1 order by 2 desc", (today,)
        )
    ))

    # Upcoming rows nobody has refreshed lately (by events.source, the scraper's prefix).
    stale = conn.execute(
        """
        select source, count(*), max(last_fetched) from events
        where start_time >= ? group by source
        having max(last_fetched) < datetime('now', ?)
        order by 2 desc
        """,
        (today, f"-{STALE_DAYS} days"),
    ).fetchall()
    if stale:
        print(f"\nSTALE upcoming rows (not refreshed in {STALE_DAYS}+ days - dead feed or retired scraper?):")
        for source, count, fetched in stale:
            print(f"  {source:38} {count:>5} rows, last fetched {str(fetched)[:16]} UTC")

    needs_review = [row["source_key"] for (label, _), row in judged if label in ("FAILED", "CHECK", "SKIPPED")]
    needs_review += [f"stale:{source}" for source, _, _ in stale]
    if needs_review:
        print(f"\nCHECK BEFORE PUBLISHING: {', '.join(needs_review)}")
        print("Look at the sync log for these sources. If a result is expected, add it to KNOWN_NOISE.")
        return 2
    print("\nREADY TO PUBLISH: every source ran and returned plausible numbers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
