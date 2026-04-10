import sqlite3
from venue_registry import VENUE_REGISTRY


def main():
    conn = sqlite3.connect("clubhub.db")
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
        print(
            f"{venue['venue_name']} | covered={covered} | rows={count} | "
            f"source={venue['source_system']} | primary={venue['primary_method']} | "
            f"fallback={fallback} | priority={venue['priority']} | status={venue['status']}"
        )

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

    conn.close()


if __name__ == "__main__":
    main()
