"""Write the frontend's data snapshot from a city's database.

    ./venv/bin/python export_demo_snapshot.py                   # ClubHub Victoria -> frontend/data/demo-snapshot.json
    ./venv/bin/python export_demo_snapshot.py --city vancouver  # ClubHub Vancouver -> frontend/data/vancouver-snapshot.json

The frontend picks a snapshot by NEXT_PUBLIC_CITY at build time (frontend/next.config.ts).
"""
import argparse
import json
import os
import sqlite3
from datetime import UTC, datetime

from app import build_source_alert, build_venue_alert, serialize_source_status
from camp_sources import CAMP_SOURCES
from models import SessionLocal, SourceSyncStatus, VenueSyncStatus


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend", "data")
CITIES = {
    "victoria": {"db": os.path.join(BASE_DIR, "clubhub.db"), "output": os.path.join(DATA_DIR, "demo-snapshot.json")},
    "vancouver": {
        "db": os.path.join(BASE_DIR, "clubhub_vancouver.db"),
        "output": os.path.join(DATA_DIR, "vancouver-snapshot.json"),
        # The site only shows a one-line note from each description; Vancouver's run long
        # (11 MB in all), so cap them to keep the snapshot small.
        "description_limit": 300,
        # ActiveNet lists camps one row per day; Vancouver has no camps section yet.
        "skip_offerings": ("camp",),
    },
}


def _trim(text: str, limit: int) -> str:
    if not text or len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--city", choices=sorted(CITIES), default="victoria")
    args = parser.parse_args()
    city = CITIES[args.city]
    OUTPUT_PATH = city["output"]

    conn = sqlite3.connect(city["db"])
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    events = [dict(row) for row in cur.execute("SELECT * FROM events ORDER BY start_time ASC")]
    if args.city == "vancouver":
        from vancouver_db import VancouverSessionLocal as session_factory
        events = [
            {**event, "description": _trim(event["description"] or "", city["description_limit"])}
            for event in events
            if event["offering_type"] not in city["skip_offerings"]
        ]
    else:
        session_factory = SessionLocal
    db = session_factory()
    try:
        source_models = (
            db.query(SourceSyncStatus)
            .order_by(SourceSyncStatus.municipality.asc(), SourceSyncStatus.display_name.asc())
            .all()
        )
        venue_models = (
            db.query(VenueSyncStatus)
            .order_by(VenueSyncStatus.municipality.asc(), VenueSyncStatus.venue_name.asc())
            .all()
        )

        source_rows = [serialize_source_status(row) for row in source_models]
        venue_rows = [row.to_dict() for row in venue_models]
        source_alerts = [alert for row in source_models if (alert := build_source_alert(row))]
        venue_alerts = [alert for row in venue_models if (alert := build_venue_alert(row))]
    finally:
        db.close()

    payload = {
        "generated_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        "counts": {
            "events": len(events),
            "sources": len(source_rows),
            "venues": len(venue_rows),
        },
        "source_summary": {
            "total": len(source_rows),
            "healthy": len([row for row in source_rows if row["freshness"] == "fresh"]),
            "warning": len([row for row in source_rows if row["freshness"] == "warning"]),
            "stale": len([row for row in source_rows if row["freshness"] == "stale"]),
            "error": len([row for row in source_rows if row["freshness"] == "error"]),
            "running": len([row for row in source_rows if row["freshness"] == "running"]),
        },
        "venue_summary": {
            "total": len(venue_rows),
            "alerts": len(venue_alerts),
        },
        "source_alerts": source_alerts,
        "venue_alerts": venue_alerts,
        "events": events,
        "camp_sources": CAMP_SOURCES if args.city == "victoria" else [],
        "sources": source_rows,
        "venues": venue_rows,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    print(f"Wrote demo snapshot to {OUTPUT_PATH}")
    print(f"Events: {len(events)} | Sources: {len(source_rows)} | Venues: {len(venue_rows)}")


if __name__ == "__main__":
    main()
