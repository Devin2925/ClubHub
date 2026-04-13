from app import build_source_alert
from models import SessionLocal, SourceSyncStatus


def main():
    db = SessionLocal()
    try:
        rows = (
            db.query(SourceSyncStatus)
            .order_by(SourceSyncStatus.municipality.asc(), SourceSyncStatus.display_name.asc())
            .all()
        )
        alerts = [alert for row in rows if (alert := build_source_alert(row))]
    finally:
        db.close()

    print("Source Alerts")
    if not alerts:
        print("No current source alerts.")
        return

    for alert in alerts:
        print()
        print(
            f"[{alert['severity'].upper()}] {alert['municipality']} | {alert['display_name']}"
        )
        print(
            f"reasons={','.join(alert['reasons'])} | current={alert['last_event_count']} | "
            f"previous={alert['previous_event_count']} | delta={alert['last_event_delta']}"
        )
        if alert["last_error"]:
            print(f"last_error={alert['last_error']}")


if __name__ == "__main__":
    main()
