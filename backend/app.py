"""
ClubHub Backend — Flask API
Serves cached drop-in sport event data to the frontend.
"""

import os
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import func

from models import SessionLocal, Event, SourceSyncStatus, VenueSyncStatus, init_db
from run_sync import list_sync_targets, run_all

app = Flask(__name__)


def get_allowed_origins() -> list[str]:
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    extra = [
        origin.strip()
        for origin in os.getenv("CLUBHUB_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    ordered: list[str] = []
    for origin in defaults + extra:
        if origin not in ordered:
            ordered.append(origin)
    return ordered


CORS(app, origins=get_allowed_origins())

SOURCE_FRESHNESS_WARNING_HOURS = 72
SOURCE_FRESHNESS_STALE_HOURS = 168
ADMIN_TOKEN = os.getenv("CLUBHUB_ADMIN_TOKEN", "").strip()


def serialize_source_status(row: SourceSyncStatus) -> dict:
    data = row.to_dict()
    age_hours = None
    freshness = "never"
    if row.last_succeeded_at:
        age_hours = round((datetime.utcnow() - row.last_succeeded_at).total_seconds() / 3600, 1)
        freshness = "fresh"
        if age_hours >= SOURCE_FRESHNESS_STALE_HOURS:
            freshness = "stale"
        elif age_hours >= SOURCE_FRESHNESS_WARNING_HOURS:
            freshness = "warning"
    if row.status == "error":
        freshness = "error"
    elif row.status == "running":
        freshness = "running"
    data["age_hours"] = age_hours
    data["freshness"] = freshness
    data["is_stale"] = freshness in {"stale", "error"}
    return data


def build_source_alert(row: SourceSyncStatus) -> dict | None:
    payload = serialize_source_status(row)
    reasons = []
    severity = "info"

    previous = payload.get("previous_event_count") or 0
    current = payload.get("last_event_count") or 0
    delta = payload.get("last_event_delta") or 0

    if payload["freshness"] == "error":
        severity = "error"
        reasons.append("source_sync_failed")
    if payload["freshness"] == "stale":
        severity = "warning" if severity != "error" else severity
        reasons.append("source_sync_stale")
    if previous > 0 and current == 0:
        severity = "error"
        reasons.append("returned_zero_after_previous_data")
    elif previous >= 20 and current <= previous * 0.5:
        if severity != "error":
            severity = "warning"
        reasons.append("event_count_dropped_sharply")

    if not reasons:
        return None

    return {
        "source_key": row.source_key,
        "display_name": row.display_name,
        "municipality": row.municipality,
        "severity": severity,
        "reasons": reasons,
        "last_event_count": current,
        "previous_event_count": previous,
        "last_event_delta": delta,
        "freshness": payload["freshness"],
        "last_error": row.last_error,
        "last_succeeded_at": payload["last_succeeded_at"],
    }


def build_venue_alert(row: VenueSyncStatus) -> dict | None:
    reasons = []
    severity = "info"

    previous = row.previous_event_count or 0
    current = row.last_event_count or 0
    delta = row.last_event_delta or 0

    if row.status == "warning" and previous > 0 and current == 0:
        severity = "error"
        reasons.append("venue_returned_zero_after_previous_data")
    elif previous >= 10 and current <= previous * 0.5:
        severity = "warning"
        reasons.append("venue_event_count_dropped_sharply")

    if not reasons:
        return None

    return {
        "venue_key": row.venue_key,
        "municipality": row.municipality,
        "venue_name": row.venue_name,
        "severity": severity,
        "reasons": reasons,
        "last_event_count": current,
        "previous_event_count": previous,
        "last_event_delta": delta,
        "last_error": row.last_error,
        "last_succeeded_at": row.last_succeeded_at.isoformat() if row.last_succeeded_at else None,
    }


def is_admin_request() -> bool:
    remote_addr = request.remote_addr or ""
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    provided_token = request.headers.get("X-Clubhub-Admin-Token", "")

    if remote_addr in {"127.0.0.1", "::1"}:
        return True
    if forwarded_for.startswith("127.0.0.1") or forwarded_for.startswith("::1"):
        return True
    if ADMIN_TOKEN and provided_token == ADMIN_TOKEN:
        return True
    return False


# ─── Helper ───────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Routes ───────────────────────────────────────────────────────
@app.route("/api/events", methods=["GET"])
def get_events():
    """
    Get all events, with optional filters:
    - sport: filter by sport_type (e.g., hockey, pickleball)
    - offering_type: filter by pickup, drop-in, or class
    - venue: filter by venue_name (partial match)
    - date: filter by date (YYYY-MM-DD)
    - from: events starting after this datetime
    - to: events starting before this datetime
    """
    db = SessionLocal()
    try:
        query = db.query(Event)

        include_past = request.args.get("include_past", "").lower() in {"1", "true", "yes"}
        if not include_past:
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(Event.start_time >= today_start)

        # Sport filter
        sport = request.args.get("sport")
        if sport:
            query = query.filter(Event.sport_type == sport.lower())

        offering_type = request.args.get("offering_type")
        if offering_type:
            query = query.filter(Event.offering_type == offering_type.lower())

        # Venue filter
        venue = request.args.get("venue")
        if venue:
            query = query.filter(Event.venue_name.ilike(f"%{venue}%"))

        # Date filter (specific day)
        date_str = request.args.get("date")
        if date_str:
            try:
                day = datetime.strptime(date_str, "%Y-%m-%d")
                next_day = day + timedelta(days=1)
                query = query.filter(Event.start_time >= day, Event.start_time < next_day)
            except ValueError:
                pass

        # Date range filters
        from_str = request.args.get("from")
        if from_str:
            try:
                from_dt = datetime.fromisoformat(from_str)
                query = query.filter(Event.start_time >= from_dt)
            except ValueError:
                pass

        to_str = request.args.get("to")
        if to_str:
            try:
                to_dt = datetime.fromisoformat(to_str)
                query = query.filter(Event.start_time <= to_dt)
            except ValueError:
                pass

        # Order by start time
        query = query.order_by(Event.start_time.asc())

        events = query.all()
        return jsonify({
            "count": len(events),
            "events": [e.to_dict() for e in events],
        })
    finally:
        db.close()


@app.route("/api/events/<int:event_id>", methods=["GET"])
def get_event(event_id):
    """Get a single event by ID."""
    db = SessionLocal()
    try:
        event = db.query(Event).filter_by(id=event_id).first()
        if not event:
            return jsonify({"error": "Event not found"}), 404
        return jsonify(event.to_dict())
    finally:
        db.close()


@app.route("/api/sports", methods=["GET"])
def get_sports():
    """Get all available sport types with event counts."""
    db = SessionLocal()
    try:
        results = (
            db.query(Event.sport_type, func.count(Event.id))
            .group_by(Event.sport_type)
            .order_by(func.count(Event.id).desc())
            .all()
        )
        sports = [{"sport": sport, "count": count} for sport, count in results]
        return jsonify({"sports": sports})
    finally:
        db.close()


@app.route("/api/offering-types", methods=["GET"])
def get_offering_types():
    """Get all available offering types with event counts."""
    db = SessionLocal()
    try:
        results = (
            db.query(Event.offering_type, func.count(Event.id))
            .group_by(Event.offering_type)
            .order_by(func.count(Event.id).desc())
            .all()
        )
        offering_types = [{"offering_type": value, "count": count} for value, count in results]
        return jsonify({"offering_types": offering_types})
    finally:
        db.close()


@app.route("/api/venues", methods=["GET"])
def get_venues():
    """Get all venues with event counts."""
    db = SessionLocal()
    try:
        results = (
            db.query(Event.venue_name, func.count(Event.id))
            .group_by(Event.venue_name)
            .order_by(Event.venue_name.asc())
            .all()
        )
        venues = [{"venue": venue, "count": count} for venue, count in results]
        return jsonify({"venues": venues})
    finally:
        db.close()


@app.route("/api/venue-status", methods=["GET"])
def get_venue_status():
    db = SessionLocal()
    try:
        rows = (
            db.query(VenueSyncStatus)
            .order_by(VenueSyncStatus.municipality.asc(), VenueSyncStatus.venue_name.asc())
            .all()
        )
        serialized = [row.to_dict() for row in rows]
        return jsonify(
            {
                "venues": serialized,
                "summary": {
                    "total": len(serialized),
                    "warnings": len([row for row in serialized if row["status"] == "warning"]),
                    "ok": len([row for row in serialized if row["status"] == "ok"]),
                },
            }
        )
    finally:
        db.close()


@app.route("/api/sync-targets", methods=["GET"])
def get_sync_targets():
    return jsonify(list_sync_targets())


@app.route("/api/scrape", methods=["POST"])
def trigger_scrape():
    """Manually trigger a scrape (dev/admin use)."""
    if not is_admin_request():
        return jsonify({"error": "admin access required"}), 403
    try:
        payload = request.get_json(silent=True) or {}
        source_keys = payload.get("source_keys")
        municipalities = payload.get("municipalities")
        run_all(source_keys=source_keys, municipalities=municipalities)
        db = SessionLocal()
        try:
            count = db.query(Event).count()
        finally:
            db.close()
        return jsonify(
            {
                "message": "Scrape complete",
                "count": count,
                "source_keys": source_keys or [],
                "municipalities": municipalities or [],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status", methods=["GET"])
def status():
    """Health check + basic stats."""
    db = SessionLocal()
    try:
        total = db.query(Event).count()
        last_fetched = db.query(func.max(Event.last_fetched)).scalar()
        source_rows = db.query(SourceSyncStatus).all()
        venue_rows = db.query(VenueSyncStatus).all()
        stale_sources = 0
        running_sources = 0
        error_sources = 0
        healthy_sources = 0
        latest_completed_at = None
        changed_sources = 0
        for row in source_rows:
            payload = serialize_source_status(row)
            if row.last_completed_at and (latest_completed_at is None or row.last_completed_at > latest_completed_at):
                latest_completed_at = row.last_completed_at
            if payload["freshness"] == "running":
                running_sources += 1
            elif payload["freshness"] == "error":
                error_sources += 1
            elif payload["is_stale"]:
                stale_sources += 1
            else:
                healthy_sources += 1
            if (row.last_event_delta or 0) != 0:
                changed_sources += 1
        source_alerts = [alert for row in source_rows if (alert := build_source_alert(row))]
        venue_alerts = [alert for row in venue_rows if (alert := build_venue_alert(row))]
        return jsonify({
            "status": "ok",
            "admin_access": is_admin_request(),
            "total_events": total,
            "last_fetched": last_fetched.isoformat() if last_fetched else None,
            "latest_sync_completed_at": latest_completed_at.isoformat() if latest_completed_at else None,
            "source_summary": {
                "total": len(source_rows),
                "healthy": healthy_sources,
                "running": running_sources,
                "error": error_sources,
                "stale": stale_sources,
            },
            "venue_summary": {
                "total": len(venue_rows),
                "alerts": len(venue_alerts),
            },
            "rerun_summary": {
                "changed_sources": changed_sources,
                "source_alerts": len(source_alerts),
                "venue_alerts": len(venue_alerts),
                "latest_completed_at": latest_completed_at.isoformat() if latest_completed_at else None,
            },
        })
    finally:
        db.close()


@app.route("/api/sources", methods=["GET"])
def get_sources():
    """Return source freshness and last sync health."""
    db = SessionLocal()
    try:
        rows = (
            db.query(SourceSyncStatus)
            .order_by(SourceSyncStatus.municipality.asc(), SourceSyncStatus.display_name.asc())
            .all()
        )
        serialized = [serialize_source_status(row) for row in rows]
        return jsonify(
            {
                "sources": serialized,
                "summary": {
                    "total": len(serialized),
                    "healthy": len([row for row in serialized if row["freshness"] == "fresh"]),
                    "warning": len([row for row in serialized if row["freshness"] == "warning"]),
                    "stale": len([row for row in serialized if row["freshness"] == "stale"]),
                    "error": len([row for row in serialized if row["freshness"] == "error"]),
                    "running": len([row for row in serialized if row["freshness"] == "running"]),
                },
            }
        )
    finally:
        db.close()


@app.route("/api/source-alerts", methods=["GET"])
def get_source_alerts():
    """Return sources that look unhealthy or unusually low after a rerun."""
    db = SessionLocal()
    try:
        rows = (
            db.query(SourceSyncStatus)
            .order_by(SourceSyncStatus.municipality.asc(), SourceSyncStatus.display_name.asc())
            .all()
        )
        alerts = [alert for row in rows if (alert := build_source_alert(row))]
        return jsonify(
            {
                "alerts": alerts,
                "summary": {
                    "total": len(alerts),
                    "errors": len([row for row in alerts if row["severity"] == "error"]),
                    "warnings": len([row for row in alerts if row["severity"] == "warning"]),
                },
            }
        )
    finally:
        db.close()


@app.route("/api/venue-alerts", methods=["GET"])
def get_venue_alerts():
    db = SessionLocal()
    try:
        rows = (
            db.query(VenueSyncStatus)
            .order_by(VenueSyncStatus.municipality.asc(), VenueSyncStatus.venue_name.asc())
            .all()
        )
        alerts = [alert for row in rows if (alert := build_venue_alert(row))]
        return jsonify(
            {
                "alerts": alerts,
                "summary": {
                    "total": len(alerts),
                    "errors": len([row for row in alerts if row["severity"] == "error"]),
                    "warnings": len([row for row in alerts if row["severity"] == "warning"]),
                },
            }
        )
    finally:
        db.close()


# ─── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("ClubHub API running on http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=True)
