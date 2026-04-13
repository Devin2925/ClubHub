import json
import os
import sqlite3
from datetime import UTC, datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "clubhub.db")
OUTPUT_PATH = os.path.join(os.path.dirname(BASE_DIR), "frontend", "data", "demo-snapshot.json")


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    events = [dict(row) for row in cur.execute("SELECT * FROM events ORDER BY start_time ASC")]

    source_rows = [
        dict(row)
        for row in cur.execute(
            """
            SELECT source_key, display_name, municipality, status, last_started_at, last_succeeded_at,
                   last_failed_at, last_completed_at, last_error, last_event_count,
                   previous_event_count, last_event_delta, last_duration_ms
            FROM source_sync_status
            ORDER BY municipality ASC, display_name ASC
            """
        )
    ]

    venue_rows = [
        dict(row)
        for row in cur.execute(
            """
            SELECT venue_key, municipality, venue_name, status, last_succeeded_at,
                   previous_event_count, last_event_count, last_event_delta, last_error
            FROM venue_sync_status
            ORDER BY municipality ASC, venue_name ASC
            """
        )
    ]

    payload = {
        "generated_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        "counts": {
            "events": len(events),
            "sources": len(source_rows),
            "venues": len(venue_rows),
        },
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
