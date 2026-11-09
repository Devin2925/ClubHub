"""Scrape ClubHub Vancouver's sources into clubhub_vancouver.db.

Separate from run_sync.py on purpose: Victoria's sync, database, alerts and snapshot
never see Vancouver rows.

    ./venv/bin/python vancouver_sync.py               # every source
    ./venv/bin/python vancouver_sync.py --dry-run     # fetch and filter, write nothing
    ./venv/bin/python vancouver_sync.py --skipped     # also list the titles that were filtered out
"""
import argparse
import collections
from datetime import datetime
from time import perf_counter

from sqlalchemy import func, or_

from models import Event, SourceSyncStatus, utcnow
from scrapers.vancouver_activenet import VancouverActiveNetScraper
from vancouver_db import VANCOUVER_DB_PATH, VancouverSessionLocal, init_vancouver_db

# (source_key, display name, municipality, scraper factory)
SOURCES = [
    ("vancouver_activenet", "Vancouver Park Board ActiveNet", "Vancouver", VancouverActiveNetScraper),
]


def _record_status(source_key, display_name, municipality, *, ok, count=0, duration_ms=0, note=None):
    db = VancouverSessionLocal()
    try:
        row = db.query(SourceSyncStatus).filter_by(source_key=source_key).first()
        if not row:
            row = SourceSyncStatus(source_key=source_key, display_name=display_name, municipality=municipality)
            db.add(row)
        now = utcnow()
        row.status = "ok" if ok else "error"
        row.last_completed_at = now
        if ok:
            row.last_succeeded_at = now
        else:
            row.last_failed_at = now
        row.previous_event_count = row.last_event_count or 0
        row.last_event_count = count
        row.last_event_delta = count - row.previous_event_count
        row.last_duration_ms = duration_ms
        row.last_error = note
        db.commit()
    finally:
        db.close()


def _prune_expired_events():
    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    db = VancouverSessionLocal()
    try:
        deleted = (
            db.query(Event)
            .filter(Event.start_time < cutoff)
            .filter(or_(Event.end_date == "", Event.end_date < cutoff.date().isoformat()))
            .delete(synchronize_session=False)
        )
        db.commit()
        print(f"[DB] Pruned {deleted} expired Vancouver events")
    finally:
        db.close()


def _print_venue_counts():
    db = VancouverSessionLocal()
    try:
        rows = (
            db.query(Event.venue_name, func.count(Event.id))
            .group_by(Event.venue_name)
            .order_by(func.count(Event.id).desc())
            .all()
        )
    finally:
        db.close()
    print(f"\n{sum(count for _, count in rows)} upcoming sessions at {len(rows)} venues in {VANCOUVER_DB_PATH}")
    for venue, count in rows:
        print(f"  {count:5}  {venue}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and filter only; write nothing")
    parser.add_argument("--skipped", action="store_true", help="List the titles each filter dropped")
    args = parser.parse_args()

    if not args.dry_run:
        init_vancouver_db()
        _prune_expired_events()

    for source_key, display_name, municipality, factory in SOURCES:
        scraper = factory(dry_run=args.dry_run)
        started = perf_counter()
        try:
            events = scraper.scrape()
        except Exception as exc:
            print(f"[{municipality}] {display_name} FAILED: {exc}")
            if not args.dry_run:
                _record_status(source_key, display_name, municipality, ok=False,
                               duration_ms=int((perf_counter() - started) * 1000), note=str(exc)[:4000])
            continue
        if not args.dry_run:
            _record_status(source_key, display_name, municipality, ok=True, count=len(events),
                           duration_ms=int((perf_counter() - started) * 1000),
                           note=getattr(scraper, "last_status_note", None))
        if args.dry_run:
            venues = collections.Counter(event["venue_name"] for event in events)
            print(f"\n{len(events)} sessions at {len(venues)} venues (dry run, nothing written)")
            for venue, count in venues.most_common():
                print(f"  {count:5}  {venue}")
        if args.skipped:
            for reason, titles in getattr(scraper, "skipped_titles", {}).items():
                print(f"\nSkipped as {reason.replace('_', ' ')}:")
                for title, count in titles.most_common():
                    print(f"  {count:4}  {title}")

    if not args.dry_run:
        _print_venue_counts()


if __name__ == "__main__":
    main()
