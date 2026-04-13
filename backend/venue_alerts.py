from app import build_venue_alert
from models import SessionLocal, VenueSyncStatus


def main():
    db = SessionLocal()
    try:
        rows = (
            db.query(VenueSyncStatus)
            .order_by(VenueSyncStatus.municipality.asc(), VenueSyncStatus.venue_name.asc())
            .all()
        )
        alerts = [alert for row in rows if (alert := build_venue_alert(row))]
    finally:
        db.close()

    print("Venue Alerts")
    if not alerts:
        print("No current venue alerts.")
        return

    for alert in alerts:
        print()
        print(
            f"[{alert['severity'].upper()}] {alert['municipality']} | {alert['venue_name']}"
        )
        print(
            f"reasons={','.join(alert['reasons'])} | current={alert['last_event_count']} | "
            f"previous={alert['previous_event_count']} | delta={alert['last_event_delta']}"
        )
        if alert["last_error"]:
            print(f"last_error={alert['last_error']}")


if __name__ == "__main__":
    main()
