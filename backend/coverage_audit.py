import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from models import SessionLocal, SourceSyncStatus
from venue_registry import VENUE_REGISTRY

SOURCE_FRESHNESS_WARNING_HOURS = 72
SOURCE_FRESHNESS_STALE_HOURS = 168


def source_freshness(row: SourceSyncStatus) -> tuple[str, str]:
    if row.status == "running":
        return "running", "-"
    if row.status == "error":
        return "error", "-"
    if not row.last_succeeded_at:
        return "never", "-"

    age_hours = round((datetime.now(UTC).replace(tzinfo=None) - row.last_succeeded_at).total_seconds() / 3600, 1)
    freshness = "fresh"
    if age_hours >= SOURCE_FRESHNESS_STALE_HOURS:
        freshness = "stale"
    elif age_hours >= SOURCE_FRESHNESS_WARNING_HOURS:
        freshness = "warning"
    return freshness, str(age_hours)


def main():
    db_path = Path(__file__).resolve().parent / "clubhub.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    muni_counts = {
        row["municipality"]: row["count"]
        for row in conn.execute(
            "select municipality, count(*) as count from events group by municipality"
        )
    }
    venue_counts = {
        (row["municipality"], row["venue_name"]): row["count"]
        for row in conn.execute(
            "select municipality, venue_name, count(*) as count "
            "from events group by municipality, venue_name"
        )
    }

    expected_municipalities = []
    for venue in VENUE_REGISTRY:
        municipality = venue["municipality"]
        if municipality not in expected_municipalities:
            expected_municipalities.append(municipality)

    print("Municipality counts")
    for municipality in expected_municipalities:
        print(f"{municipality}: {muni_counts.get(municipality, 0)}")

    print("\nRegistry coverage")
    current = None
    for venue in VENUE_REGISTRY:
        municipality = venue["municipality"]
        if municipality != current:
            current = municipality
            print(f"\n[{municipality}]")
        count = venue_counts.get((municipality, venue["venue_name"]), 0)
        covered = "yes" if count else "no"
        fallback = venue["fallback_method"] or "-"
        sports = ",".join(venue["sports"]) or "-"
        auto = "yes" if venue["automation_ready"] else "no"
        confirmed = "yes" if venue["connector_confirmed"] else "no"
        print(
            f"{venue['venue_name']} | covered={covered} | rows={count} | "
            f"source={venue['source_system']} | preferred={venue['preferred_method']} | "
            f"connector={venue['connector']} | fallback={fallback} | "
            f"fallback_connector={venue['fallback_connector'] or '-'} | "
            f"confirmed={confirmed} | auto={auto} | group={venue['refresh_group']} | "
            f"sports={sports} | priority={venue['priority']} | status={venue['status']}"
        )

    print("\nRefresh-ready venues")
    ready = [venue for venue in VENUE_REGISTRY if venue["automation_ready"]]
    confirmed = [venue for venue in VENUE_REGISTRY if venue["connector_confirmed"]]
    blocked = [
        venue
        for venue in VENUE_REGISTRY
        if not venue["automation_ready"] and venue["refresh_group"] != "not_target"
    ]
    excluded = [venue for venue in VENUE_REGISTRY if venue["refresh_group"] == "not_target"]
    print(f"automation_ready={len(ready)}")
    print(f"connector_confirmed={len(confirmed)}")
    print(f"needs_discovery_or_manual_review={len(blocked)}")
    print(f"not_target={len(excluded)}")

    db = SessionLocal()
    try:
        source_status_rows = (
            db.query(SourceSyncStatus)
            .order_by(SourceSyncStatus.municipality.asc(), SourceSyncStatus.display_name.asc())
            .all()
        )
    finally:
        db.close()

    print("\nSource health")
    current = None
    for row in source_status_rows:
        municipality = row.municipality
        if municipality != current:
            current = municipality
            print(f"\n[{municipality}]")
        freshness, age_hours = source_freshness(row)
        print(
            f"{row.display_name} | status={row.status} | events={row.last_event_count} | "
            f"freshness={freshness} | age_hours={age_hours} | "
            f"duration_ms={row.last_duration_ms} | "
            f"last_ok={row.last_succeeded_at.isoformat() if row.last_succeeded_at else '-'} | "
            f"last_error={row.last_error or '-'}"
        )

    print("\nDiscovery queue")
    current = None
    for venue in VENUE_REGISTRY:
        if venue["automation_ready"] or venue["refresh_group"] == "not_target":
            continue
        municipality = venue["municipality"]
        if municipality != current:
            current = municipality
            print(f"\n[{municipality}]")
        fallback = venue["fallback_method"] or "-"
        sports = ",".join(venue["sports"]) or "-"
        confirmed = "yes" if venue["connector_confirmed"] else "no"
        print(
            f"{venue['venue_name']} | preferred={venue['preferred_method']} | "
            f"connector={venue['connector']} | fallback={fallback} | "
            f"fallback_connector={venue['fallback_connector'] or '-'} | "
            f"confirmed={confirmed} | sports={sports} | priority={venue['priority']} | "
            f"status={venue['status']}"
        )

    print("\nConnector inventory")
    connector_counts = {}
    for venue in VENUE_REGISTRY:
        connector_counts[venue["connector"]] = connector_counts.get(venue["connector"], 0) + 1
    for connector, count in sorted(connector_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{connector}: {count}")

    if excluded:
        print("\nExcluded from discovery")
        current = None
        for venue in excluded:
            municipality = venue["municipality"]
            if municipality != current:
                current = municipality
                print(f"\n[{municipality}]")
            print(f"{venue['venue_name']} | sports={','.join(venue['sports']) or '-'} | note={venue['notes']}")

    print("\nVenue coverage")
    venues = conn.execute(
        "select municipality, venue_name, count(*) as count "
        "from events group by municipality, venue_name order by municipality, count desc, venue_name"
    )
    current = None
    for row in venues:
        municipality = row["municipality"]
        if municipality != current:
            current = municipality
            print(f"\n[{municipality}]")
        print(f"{row['venue_name']}: {row['count']}")

    print("\nSport coverage")
    sports = conn.execute(
        "select municipality, sport_type, count(*) as count "
        "from events group by municipality, sport_type "
        "order by municipality, count desc, sport_type"
    )
    current = None
    for row in sports:
        municipality = row["municipality"]
        if municipality != current:
            current = municipality
            print(f"\n[{municipality}]")
        print(f"{row['sport_type']}: {row['count']}")

    print("\nOffering coverage")
    offerings = conn.execute(
        "select municipality, offering_type, count(*) as count "
        "from events group by municipality, offering_type "
        "order by municipality, count desc, offering_type"
    )
    current = None
    for row in offerings:
        municipality = row["municipality"]
        if municipality != current:
            current = municipality
            print(f"\n[{municipality}]")
        print(f"{row['offering_type']}: {row['count']}")

    conn.close()


if __name__ == "__main__":
    main()
