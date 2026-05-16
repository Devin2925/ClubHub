import argparse
import os
import signal
import shutil
import threading
from datetime import datetime
from time import perf_counter
from sqlalchemy import func

from models import Event, SessionLocal, SourceSyncStatus, VenueSyncStatus, init_db, utcnow
from scrapers.burnside_gorge import BurnsideGorgeScraper
from scrapers.calendar_online import CalendarOnlineScraper
from scrapers.cookstreet_pdf import CookStreetPDFScraper
from scrapers.fernwood import FernwoodScraper
from scrapers.jamesbay_events import JamesBayEventsScraper
from scrapers.jbnh_pdf import JBNHPDFScraper
from scrapers.oakbay_fitness import OakBayFitnessScraper
from scrapers.oakbay_group_fitness_pdf import OakBayGroupFitnessPDFScraper
from scrapers.oakbay_pdf import OakBayPDFScraper
from scrapers.oakbay_arena_pdf import OakBayArenaPDFScraper
from scrapers.oakbay_aquatics_pdf import OakBayAquaticsPDFScraper
from scrapers.pearkes_pdf import PearkesPDFScraper
from scrapers.saanich_commonwealth_swimming_pdf import SaanichCommonwealthSwimmingPDFScraper
from scrapers.perfectmind import PerfectMindScraper
from scrapers.perfectmind_sources import PERFECTMIND_SOURCES
from scrapers.recdesk_calendar import RecDeskCalendarScraper
from scrapers.saanich import SaanichScraper
from scrapers.vikesrec import VikesRecScraper
from scrapers.wspr import WSPRScraper
from venue_registry import VENUE_REGISTRY

SCRAPER_TIMEOUT_SECONDS = 90
BACKUP_DIR = "backups"
BACKUP_RETENTION = 12


class ScraperTimeoutError(RuntimeError):
    pass


def _handle_timeout(signum, frame):
    raise ScraperTimeoutError(f"Scraper exceeded {SCRAPER_TIMEOUT_SECONDS}s timeout")


def _upsert_source_status(
    source_key: str,
    display_name: str,
    municipality: str,
    *,
    status: str,
    event_count: int = 0,
    duration_ms: int = 0,
    error: str | None = None,
):
    db = SessionLocal()
    try:
        row = db.query(SourceSyncStatus).filter_by(source_key=source_key).first()
        if not row:
            row = SourceSyncStatus(
                source_key=source_key,
                display_name=display_name,
                municipality=municipality,
            )
            db.add(row)

        now = utcnow()
        row.display_name = display_name
        row.municipality = municipality

        if status == "running":
            row.status = "running"
            row.last_started_at = now
            row.last_error = None
        elif status == "ok":
            row.status = "ok"
            row.last_succeeded_at = now
            row.last_completed_at = now
            row.previous_event_count = row.last_event_count or 0
            row.last_event_count = event_count
            row.last_event_delta = event_count - (row.previous_event_count or 0)
            row.last_duration_ms = duration_ms
            row.last_error = None
        elif status == "error":
            row.status = "error"
            row.last_failed_at = now
            row.last_completed_at = now
            row.previous_event_count = row.last_event_count or 0
            row.last_event_count = event_count
            row.last_event_delta = event_count - (row.previous_event_count or 0)
            row.last_duration_ms = duration_ms
            row.last_error = error

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _mark_abandoned_runs():
    db = SessionLocal()
    try:
        rows = db.query(SourceSyncStatus).filter_by(status="running").all()
        now = utcnow()
        for row in rows:
            row.status = "error"
            row.last_failed_at = now
            row.last_completed_at = now
            row.last_error = "Previous sync run was interrupted before completion."
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _prune_expired_events():
    db = SessionLocal()
    try:
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        deleted = (
            db.query(Event)
            .filter(Event.start_time < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        print(f"[DB] Pruned {deleted} expired events before {cutoff.isoformat(sep=' ')}")
    except Exception:
        db.rollback()
    finally:
        db.close()


def _backup_database():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clubhub.db")
    backup_dir = os.path.join(os.path.dirname(db_path), BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(backup_dir, f"clubhub-{timestamp}.sqlite3")
    shutil.copy2(db_path, backup_path)

    backups = sorted(
        [
            os.path.join(backup_dir, name)
            for name in os.listdir(backup_dir)
            if name.endswith(".sqlite3")
        ]
    )
    for stale_path in backups[:-BACKUP_RETENTION]:
        os.remove(stale_path)

    print(f"[DB] Backup created: {backup_path}")


def _sync_venue_statuses():
    db = SessionLocal()
    try:
        current_counts = {
            (municipality, venue_name): count
            for municipality, venue_name, count in (
                db.query(Event.municipality, Event.venue_name, func.count(Event.id))
                .group_by(Event.municipality, Event.venue_name)
                .all()
            )
        }
    finally:
        db.close()

    tracked_venues = [
        (entry["municipality"], entry["venue_name"])
        for entry in VENUE_REGISTRY
        if entry.get("automation_ready")
    ]

    db = SessionLocal()
    try:
        now = utcnow()
        for municipality, venue_name in tracked_venues:
            venue_key = f"{municipality}::{venue_name}"
            row = db.query(VenueSyncStatus).filter_by(venue_key=venue_key).first()
            if not row:
                row = VenueSyncStatus(
                    venue_key=venue_key,
                    municipality=municipality,
                    venue_name=venue_name,
                )
                db.add(row)

            current = current_counts.get((municipality, venue_name), 0)
            previous = row.last_event_count or 0
            row.previous_event_count = previous
            row.last_event_count = current
            row.last_event_delta = current - previous
            row.last_succeeded_at = now
            row.status = "ok" if current > 0 else "warning"
            row.last_error = None if current > 0 else "No current upcoming events after latest sync."

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _run_scraper(source_key: str, display_name: str, municipality: str, scraper):
    _upsert_source_status(
        source_key,
        display_name,
        municipality,
        status="running",
    )
    started = perf_counter()
    can_use_signal_timeout = threading.current_thread() is threading.main_thread()
    previous_handler = signal.getsignal(signal.SIGALRM) if can_use_signal_timeout else None
    try:
        if can_use_signal_timeout:
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(SCRAPER_TIMEOUT_SECONDS)
        events = scraper.scrape() or []
        reported_count = getattr(scraper, "last_reported_count", len(events))
        duration_ms = int((perf_counter() - started) * 1000)
        _upsert_source_status(
            source_key,
            display_name,
            municipality,
            status="ok",
            event_count=reported_count,
            duration_ms=duration_ms,
        )
        return events
    except Exception as exc:
        duration_ms = int((perf_counter() - started) * 1000)
        _upsert_source_status(
            source_key,
            display_name,
            municipality,
            status="error",
            duration_ms=duration_ms,
            error=str(exc)[:4000],
        )
        print(f"[{municipality}] Sync failure for {display_name}: {exc}")
        return []
    finally:
        if can_use_signal_timeout:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_handler)


def iter_scrapers():
    yield ("saanich_active_communities", "Saanich Active Communities", "Saanich", SaanichScraper())
    yield ("saanich_pearkes_pdf", "G. R. Pearkes Recreation Centre PDF", "Saanich", PearkesPDFScraper())
    yield (
        "saanich_commonwealth_swimming_pdf",
        "Saanich Commonwealth Swimming PDF",
        "Saanich",
        SaanichCommonwealthSwimmingPDFScraper(),
    )

    for source in PERFECTMIND_SOURCES:
        display_name = source.get("municipality") or source.get("subdomain") or "PerfectMind"
        yield (
            f"perfectmind_{display_name.lower().replace(' ', '_')}",
            display_name,
            source["municipality"],
            PerfectMindScraper(**source),
        )

    yield ("oakbay_henderson_pdf", "Henderson Recreation Centre PDF", "Oak Bay", OakBayPDFScraper())
    yield ("oakbay_fitness_hours", "Oak Bay Fitness Hours", "Oak Bay", OakBayFitnessScraper())
    yield ("oakbay_aquatics_pdf", "Oak Bay Aquatics PDF", "Oak Bay", OakBayAquaticsPDFScraper())
    yield ("oakbay_arena_pdf", "Oak Bay Arena PDF", "Oak Bay", OakBayArenaPDFScraper())
    yield ("oakbay_group_fitness_pdf", "Oak Bay Group Fitness PDF", "Oak Bay", OakBayGroupFitnessPDFScraper())
    yield (
        "oaklands_recdesk",
        "Oaklands Community Centre",
        "Victoria",
        RecDeskCalendarScraper(
            municipality="Victoria",
            venue_name="Oaklands Community Centre",
            base_url="https://oca.recdesk.com",
        ),
    )
    yield (
        "victoria_west_recdesk",
        "Victoria West Community Centre",
        "Victoria",
        RecDeskCalendarScraper(
            municipality="Victoria",
            venue_name="Victoria West Community Centre",
            base_url="https://victoriawest.recdesk.com",
        ),
    )
    yield (
        "fairfield_recdesk",
        "Fairfield Community Place",
        "Victoria",
        RecDeskCalendarScraper(
            municipality="Victoria",
            venue_name="Fairfield Community Place",
            base_url="https://fgca.recdesk.com",
        ),
    )
    yield (
        "quadra_calendar_online",
        "Quadra Village Community Centre",
        "Victoria",
        CalendarOnlineScraper(
            municipality="Victoria",
            venue_name="Quadra Village Community Centre",
            capability_id="3014533ec3d996e84c39",
        ),
    )
    yield ("james_bay_events_html", "James Bay Community School Centre", "Victoria", JamesBayEventsScraper())
    yield ("jbnh_monthly_pdf", "James Bay New Horizons", "Victoria", JBNHPDFScraper())
    yield ("burnside_gorge_html", "Burnside Gorge Community Centre", "Victoria", BurnsideGorgeScraper())
    yield ("fernwood_eventon", "Fernwood Community Centre", "Victoria", FernwoodScraper())
    yield ("cook_street_pdf", "Cook Street Village Activity Centre", "Victoria", CookStreetPDFScraper())
    yield (
        "silver_threads_recdesk",
        "Silver Threads",
        "Victoria",
        RecDeskCalendarScraper(
            municipality="Victoria",
            venue_name="Victoria Silver Threads Seniors Centre",
            base_url="https://silverthreads.recdesk.com",
            location_rules=[
                {
                    "pattern": r"\((?:Victoria|Victoria Centre)",
                    "municipality": "Victoria",
                    "venue_name": "Victoria Silver Threads Seniors Centre",
                },
                {
                    "pattern": r"\((?:Saanich|Saa|Saanich Centre)",
                    "municipality": "Saanich",
                    "venue_name": "Saanich Silver Threads Seniors Centre",
                },
            ],
        ),
    )
    yield ("uvic_vikesrec", "UVic CARSA / Vikes Recreation", "UVic", VikesRecScraper())
    yield ("west_shore_public", "West Shore Parks & Recreation", "West Shore", WSPRScraper())


def list_sync_targets():
    targets = []
    municipalities = set()
    for source_key, display_name, municipality, _scraper in iter_scrapers():
        municipalities.add(municipality)
        targets.append(
            {
                "source_key": source_key,
                "display_name": display_name,
                "municipality": municipality,
            }
        )
    return {
        "sources": targets,
        "municipalities": sorted(municipalities),
    }

def run_all(source_keys: list[str] | None = None, municipalities: list[str] | None = None):
    print("=== Starting ClubHub Sync ===")
    init_db()
    _backup_database()
    _mark_abandoned_runs()
    allowed_keys = set(source_keys or [])
    allowed_municipalities = {value.lower() for value in (municipalities or [])}

    for source_key, display_name, municipality, scraper in iter_scrapers():
        if allowed_keys and source_key not in allowed_keys:
            continue
        if allowed_municipalities and municipality.lower() not in allowed_municipalities:
            continue
        _run_scraper(source_key, display_name, municipality, scraper)

    _prune_expired_events()
    _sync_venue_statuses()

    print("=== Sync Complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ClubHub source sync.")
    parser.add_argument(
        "--source-key",
        action="append",
        dest="source_keys",
        help="Refresh only the given source key. Repeat for multiple sources.",
    )
    parser.add_argument(
        "--municipality",
        action="append",
        dest="municipalities",
        help="Refresh only the given municipality. Repeat for multiple municipalities.",
    )
    args = parser.parse_args()
    run_all(source_keys=args.source_keys, municipalities=args.municipalities)
