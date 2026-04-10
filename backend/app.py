"""
ClubHub Backend — Flask API
Serves cached drop-in sport event data to the frontend.
"""

from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import func

from models import SessionLocal, Event, init_db
from run_sync import run_all

app = Flask(__name__)
CORS(
    app,
    origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
)


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
    - venue: filter by venue_name (partial match)
    - date: filter by date (YYYY-MM-DD)
    - from: events starting after this datetime
    - to: events starting before this datetime
    """
    db = SessionLocal()
    try:
        query = db.query(Event)

        # Sport filter
        sport = request.args.get("sport")
        if sport:
            query = query.filter(Event.sport_type == sport.lower())

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


@app.route("/api/scrape", methods=["POST"])
def trigger_scrape():
    """Manually trigger a scrape (dev/admin use)."""
    try:
        run_all()
        db = SessionLocal()
        try:
            count = db.query(Event).count()
        finally:
            db.close()
        return jsonify({"message": "Scrape complete", "count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status", methods=["GET"])
def status():
    """Health check + basic stats."""
    db = SessionLocal()
    try:
        total = db.query(Event).count()
        last_fetched = db.query(func.max(Event.last_fetched)).scalar()
        return jsonify({
            "status": "ok",
            "total_events": total,
            "last_fetched": last_fetched.isoformat() if last_fetched else None,
        })
    finally:
        db.close()


# ─── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("ClubHub API running on http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=True)
