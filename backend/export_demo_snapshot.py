import json
import os
import sqlite3
from datetime import UTC, datetime

from app import build_source_alert, build_venue_alert, serialize_source_status
from models import SessionLocal, SourceSyncStatus, VenueSyncStatus


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "clubhub.db")
OUTPUT_PATH = os.path.join(os.path.dirname(BASE_DIR), "frontend", "data", "demo-snapshot.json")


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    events = [dict(row) for row in cur.execute("SELECT * FROM events ORDER BY start_time ASC")]
    db = SessionLocal()
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
