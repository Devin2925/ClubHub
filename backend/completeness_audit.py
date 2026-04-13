import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from models import SessionLocal, SourceSyncStatus
from venue_registry import VENUE_REGISTRY


def freshness_label(row: SourceSyncStatus | None) -> str:
    if not row:
        return "unknown"
    if row.status == "running":
        return "running"
    if row.status == "error":
        return "error"
    if not row.last_succeeded_at:
        return "never"
    age_hours = (datetime.now(UTC).replace(tzinfo=None) - row.last_succeeded_at).total_seconds() / 3600
    if age_hours >= 168:
        return "stale"
    if age_hours >= 72:
        return "warning"
    return "fresh"


def source_key_for_venue(venue: dict) -> str | None:
    connector = venue["connector"]
    municipality = venue["municipality"]
    venue_name = venue["venue_name"]

    if connector == "active_communities_api":
        return "saanich_active_communities"
    if connector == "perfectmind_widget_v2":
        return f"perfectmind_{municipality.lower().replace(' ', '_')}"
    if connector == "wordpress_google_calendar_html":
        return "burnside_gorge_html"
    if connector == "wordpress_events_html":
        return "james_bay_events_html"
    if connector == "weebly_pdf_calendar":
        return "jbnh_monthly_pdf"
    if connector == "static_program_pdfs":
        return "cook_street_pdf"
    if connector == "wspr_public_html":
        return "west_shore_public"
    return None


def next_step(venue: dict) -> str:
    connector = venue["connector"]
    fallback = venue["fallback_connector"] or "-"
    venue_name = venue["venue_name"]

    if connector == "active_communities_api":
        return "PDF fallback is now in place for Pearkes; next verify whether any figure-skate or stick-and-puck rows still differ from the public skating page."
    if connector == "wordpress_google_calendar_html":
        return "Keep Burnside on the explicit program pages for now; only expand into the calendar plugin if new timed activities appear there."
    if connector == "wordpress_events_html":
        return "Keep the WordPress events and meals pages, then add Amilia program-detail extraction for classes whose real times are not exposed on the main site pages."
    if connector == "weebly_pdf_calendar":
        return "Supplement the monthly PDF with the upcoming-events poster page or image OCR for one-off items and better durations."
    if connector == "static_program_pdfs":
        return "Combine the monthly calendar with linked program-guide/poster PDFs so special events and richer pricing notes are preserved."
    if connector == "perfectmind_widget_v2" and venue_name == "Oak Bay Recreation Centre":
        return "Public skating and aquatics are now covered via the Oak Bay PDFs; next add any remaining court-based Oak Bay Recreation Centre drop-ins that only appear on the drop-in page."
    if connector == "perfectmind_widget_v2" and venue_name == "Esquimalt Recreation Centre":
        return "Compare PerfectMind sports rows to the public site and trim non-sport noise while checking for missed sports blocks."
    if connector == "wspr_public_html":
        return "Sports plus weight/fitness branches are now covered; next decide whether West Shore's arena and pool schedule branches should get dedicated parsers too."
    return f"Review primary connector `{connector}` and fallback `{fallback}` against the public venue page."


def main():
    db_path = Path(__file__).resolve().parent / "clubhub.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    partial_venues = [venue for venue in VENUE_REGISTRY if venue["status"] == "covered_partial"]

    db = SessionLocal()
    try:
        source_rows = {row.source_key: row for row in db.query(SourceSyncStatus).all()}
    finally:
        db.close()

    print("Covered Partial Audit")
    for venue in partial_venues:
        municipality = venue["municipality"]
        venue_name = venue["venue_name"]
        source_key = source_key_for_venue(venue)
        source_row = source_rows.get(source_key) if source_key else None

        total_rows = conn.execute(
            "select count(*) as count from events where municipality = ? and venue_name = ?",
            (municipality, venue_name),
        ).fetchone()["count"]

        sport_rows = conn.execute(
            "select sport_type, count(*) as count from events "
            "where municipality = ? and venue_name = ? "
            "group by sport_type order by count desc, sport_type",
            (municipality, venue_name),
        ).fetchall()
        sports = ", ".join(f"{row['sport_type']}:{row['count']}" for row in sport_rows[:8]) or "-"

        offering_rows = conn.execute(
            "select offering_type, count(*) as count from events "
            "where municipality = ? and venue_name = ? "
            "group by offering_type order by count desc, offering_type",
            (municipality, venue_name),
        ).fetchall()
        offerings = ", ".join(f"{row['offering_type']}:{row['count']}" for row in offering_rows) or "-"

        print()
        print(f"[{municipality}] {venue_name}")
        print(f"rows={total_rows} | connector={venue['connector']} | fallback={venue['fallback_connector'] or '-'} | source_health={freshness_label(source_row)}")
        print(f"sports={sports}")
        print(f"offerings={offerings}")
        print(f"coverage_note={venue['notes']}")
        print(f"next_step={next_step(venue)}")

    conn.close()


if __name__ == "__main__":
    main()
