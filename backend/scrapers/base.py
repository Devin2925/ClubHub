import re
from datetime import datetime
from models import SessionLocal, Event

# ─── Common Sport Classification ──────────────────────────────────
SPORT_PATTERNS = [
    (
        r"hockey|shinny|stick\s*(&|and)\s*puck|tot\s*hockey|intro\s*to\s*hockey|"
        r"hockey\s*skills|hockey\s*social|duffer|goalies",
        "hockey",
    ),
    (r"pickleball", "pickleball"),
    (r"basketball", "basketball"),
    (r"badminton", "badminton"),
    (r"volleyball", "volleyball"),
    (r"table\s*tennis|ping\s*pong", "table-tennis"),
    (r"soccer|futsal", "soccer"),
    (r"tennis(?!\s*table)", "tennis"),
    (r"squash|racquetball", "squash"),
    (r"archery", "archery"),
    (r"skating|figure\s*skat|ice\s*play|public\s*skat|skate\s*-", "skating"),
    (r"swim|aqua|pool|water", "swimming"),
    (
        r"fitness|weight|cardio|yoga|pilates|zumba|aerobic|body\s*sculpt|hiit|"
        r"circuit|cycle\s*(fit|&|\s*and)|strength|stretch|hi\s*lo|low\s*impact|"
        r"step\s*\*|trx|partyfit|core\s*(and|&|\s*more)|conditioning|rowing|"
        r"body\s*fit|triple\s*fit",
        "fitness",
    ),
    (r"curling", "curling"),
    (r"art\s|ceramics|art\s*hive|open\s*studio", "arts"),
    (r"kindergym|childminding|kids\s*night", "kids"),
]

def classify_sport(title: str) -> str:
    """Classify an event title into a normalized sport type."""
    title_lower = title.lower()
    for pattern, sport in SPORT_PATTERNS:
        if re.search(pattern, title_lower):
            return sport
    return "other"

def strip_html(text: str) -> str:
    """Remove HTML tags from description."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()

class BaseScraper:
    def __init__(self, source_id_prefix: str, municipality: str):
        self.source_id_prefix = source_id_prefix # e.g. "saanich", "victoria"
        self.municipality = municipality         # e.g. "Saanich", "Victoria"
    
    def scrape(self):
        """Must be implemented by subclasses. Returns list of event dicts."""
        raise NotImplementedError

    def save_events(self, events: list):
        """Upsert events into the database."""
        db = SessionLocal()
        try:
            saved = 0
            updated = 0
            for ev_data in events:
                # Ensure source and municipality are set
                ev_data["source"] = self.source_id_prefix
                ev_data["municipality"] = self.municipality
                
                existing = db.query(Event).filter_by(source_id=ev_data["source_id"]).first()
                if existing:
                    for key, val in ev_data.items():
                        setattr(existing, key, val)
                    existing.last_fetched = datetime.utcnow()
                    updated += 1
                else:
                    event = Event(**ev_data)
                    db.add(event)
                    saved += 1
            db.commit()
            print(f"[{self.municipality}] DB: {saved} new, {updated} updated")
        except Exception as e:
            db.rollback()
            print(f"[{self.municipality}] DB error: {e}")
        finally:
            db.close()
