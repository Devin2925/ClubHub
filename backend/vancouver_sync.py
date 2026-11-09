"""Scrape ClubHub Vancouver's sources into clubhub_vancouver.db.

Separate from run_sync.py on purpose: Victoria's sync, database, alerts and snapshot
never see Vancouver rows.

    ./venv/bin/python vancouver_sync.py                      # every source
    ./venv/bin/python vancouver_sync.py burnaby_activenet    # just these source keys
    ./venv/bin/python vancouver_sync.py --dry-run --skipped  # fetch + filter, write nothing,
                                                             # list dropped and borderline titles
    ./venv/bin/python vancouver_sync.py --list               # source keys

After a run it compares venues against vancouver_registry.py: venues the sources list
that the registry doesn't know, and source_verified venues that came back empty.
"""
import argparse
import collections
import json
import sys
from datetime import datetime
from time import perf_counter

from sqlalchemy import func, or_

from models import Event, SourceSyncStatus, utcnow
from scrapers.vancouver_activenet import ACTIVENET_SOURCES, ActiveNetCalendarScraper
from scrapers.vancouver_perfectmind import PERFECTMIND_SOURCES, PerfectMindDropInScraper
from scrapers.vancouver_ubc import UBC_SOURCES, UBCRecreationScraper
from scrapers.vancouver_sfu import SFU_SOURCES, SFURecreationScraper
from vancouver_db import VANCOUVER_DB_PATH, VancouverSessionLocal, init_vancouver_db
from vancouver_registry import VANCOUVER_REGISTRY

# source_key → (config, scraper class)
SOURCES = {key: (cfg, ActiveNetCalendarScraper) for key, cfg in ACTIVENET_SOURCES.items()}
SOURCES.update({key: (cfg, PerfectMindDropInScraper) for key, cfg in PERFECTMIND_SOURCES.items()})
SOURCES.update({key: (cfg, UBCRecreationScraper) for key, cfg in UBC_SOURCES.items()})
SOURCES.update({key: (cfg, SFURecreationScraper) for key, cfg in SFU_SOURCES.items()})


def _record_status(source_key, display_name, municipality, *, ok, count=0, duration_ms=0, note=None):
    db = VancouverSessionLocal()
    try:
        row = db.query(SourceSyncStatus).filter_by(source_key=source_key).first()
        if not row:
            row = SourceSyncStatus(source_key=source_key, display_name=display_name, municipality=municipality)
            db.add(row)
        now = utcnow()
        row.display_name, row.municipality = display_name, municipality
        row.status = "ok" if ok else "error"
        row.last_completed_at = now
        if ok:
            row.last_succeeded_at = now
            row.previous_event_count = row.last_event_count or 0
            row.last_event_count = count
            row.last_event_delta = count - row.previous_event_count
        else:
            row.last_failed_at = now
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


def _db_venue_counts() -> collections.Counter:
    db = VancouverSessionLocal()
    try:
        return collections.Counter({
            (municipality, venue): count
            for municipality, venue, count in db.query(Event.municipality, Event.venue_name, func.count(Event.id))
            .group_by(Event.municipality, Event.venue_name)
        })
    finally:
        db.close()


def registry_check(counts: collections.Counter, municipalities: set[str]) -> list[str]:
    """Problems worth a look: unknown venues, and verified venues with nothing."""
    registry = {(v["municipality"], v["venue_name"]): v for v in VANCOUVER_REGISTRY}
    problems = []
    for (municipality, venue), count in sorted(counts.items()):
        if municipality in municipalities and (municipality, venue) not in registry:
            problems.append(f"NOT IN REGISTRY  {municipality} / {venue} ({count} sessions)")
    for (municipality, venue), row in sorted(registry.items()):
        if (
            municipality in municipalities
            and row["status"] == "source_verified"
            and row["connector"] in ("active_communities_api", "perfectmind_widget", "perfectmind")
            and not counts.get((municipality, venue))
        ):
            problems.append(f"NO SESSIONS      {municipality} / {venue} (registry says source_verified)")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sources", nargs="*", help="Source keys (default: all); see --list")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and filter only; write nothing")
    parser.add_argument("--skipped", action="store_true", help="List dropped titles and kept titles worth a look")
    parser.add_argument("--list", action="store_true", help="List source keys and exit")
    parser.add_argument("--json", help="Write a run summary (per-source counts, failures, registry problems) here")
    args = parser.parse_args()

    if args.list:
        for key, (cfg, cls) in SOURCES.items():
            print(f"{key:30} {cfg['municipality']:18} {cls.__name__}")
        return
    unknown = set(args.sources) - set(SOURCES)
    if unknown:
        sys.exit(f"Unknown source keys: {', '.join(sorted(unknown))} (see --list)")
    keys = args.sources or list(SOURCES)

    if not args.dry_run:
        init_vancouver_db()
        _prune_expired_events()

    summary = {"started": datetime.now().isoformat(timespec="seconds"), "dry_run": args.dry_run, "sources": []}
    dry_counts = collections.Counter()
    for key in keys:
        cfg, cls = SOURCES[key]
        municipality, display_name = cfg["municipality"], cfg["display_name"]
        scraper = cls(key, dry_run=args.dry_run, **cfg)
        started = perf_counter()
        try:
            events = scraper.scrape()
            ok, error = True, None
        except Exception as exc:  # one broken source must not stop the rest
            events, ok, error = [], False, f"{type(exc).__name__}: {exc}"
            print(f"[{municipality}] {display_name} FAILED: {error}")
        duration_ms = int((perf_counter() - started) * 1000)
        note = error or getattr(scraper, "last_status_note", None)
        if not args.dry_run:
            _record_status(key, display_name, municipality, ok=ok, count=len(events), duration_ms=duration_ms, note=note)
        dry_counts.update((e.get("municipality") or municipality, e["venue_name"]) for e in events)
        summary["sources"].append({
            "source": key, "municipality": municipality, "ok": ok, "sessions": len(events),
            "skipped": dict(scraper.skipped), "fetch_failures": scraper.failures[:10], "error": error,
            "seconds": round(duration_ms / 1000, 1),
        })

        if args.skipped:
            for reason, titles in scraper.skipped_titles.items():
                print(f"\n  Dropped as {reason.replace('_', ' ')}:")
                for title, count in titles.most_common():
                    print(f"    {count:4}  {title}")
            review = scraper.review_titles()
            if review:
                print("\n  Kept, but worth a look:")
                for title, count in review.most_common(40):
                    print(f"    {count:4}  {title}")
            print()

    counts = dry_counts if args.dry_run else _db_venue_counts()
    municipalities = {SOURCES[key][0]["municipality"] for key in keys}
    problems = registry_check(counts, municipalities)
    summary["registry_problems"] = problems

    print(f"\n{'Source':30} {'OK':3} {'Sessions':>8}  Notes")
    for row in summary["sources"]:
        notes = row["error"] or (f"{len(row['fetch_failures'])} fetch failures" if row["fetch_failures"] else "")
        print(f"{row['source']:30} {'yes' if row['ok'] else 'NO':3} {row['sessions']:>8}  {notes}")
    by_city = collections.Counter()
    for (municipality, _), count in counts.items():
        by_city[municipality] += count
    where = "dry run, nothing written" if args.dry_run else VANCOUVER_DB_PATH
    print(f"\n{sum(by_city.values())} upcoming sessions at {len(counts)} venues ({where})")
    for municipality, count in by_city.most_common():
        print(f"  {count:6}  {municipality}")
    if problems:
        print(f"\nRegistry check ({len(problems)}):")
        for line in problems:
            print(f"  {line}")

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(summary, handle, indent=1)
        print(f"\nWrote {args.json}")
    if not any(row["ok"] for row in summary["sources"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
