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
    (r"soccer|soocer|futsal", "soccer"),
    (r"tennis(?!\s*table)", "tennis"),
    (r"squash|racquetball", "squash"),
    (r"archery", "archery"),
    (r"skating|figure\s*skat|ice\s*play|public\s*skat|adult\s*skate|skate\s*-", "skating"),
    (r"swim|aqua|pool|water|lengths|widths|family\s*swim|fun\s*and\s*features\s*swim", "swimming"),
    (
        r"fitness|weight|cardio|yoga|pilates|zumba|aerobic|body\s*sculpt|hiit|"
        r"circuit|cycle\s*(fit|&|\s*and)|strength|stretch|hi\s*lo|low\s*impact|"
        r"step\s*\*|trx|partyfit|core\s*(and|&|\s*more)|conditioning|rowing|"
        r"body\s*fit|triple\s*fit|boot\s*camp|spin|interval|fit\b|combo\s*fit|"
        r"total\s*(body|aerobic|step)\s*(challenge|workout)|abs\s*attack|"
        r"shallow\s*fit|deep\s*fit|wellness\s*centre\s*orientation|athletic\s*conditioning|"
        r"\bride\b|\blab\b|small\s*group\s*training|burn\s*&\s*balance|"
        r"total\s*body\s*transformation|best\s*abs\s*ever|welcome\s*to\s*the\s*fwc|"
        r"sun\s*to\s*stillness|crossfire|hustle\s*muscle|total\s*body\s*express|"
        r"power\s*up|indoor\s*cycling|essentrics|iyengar|tai\s*chi|qigong|"
        r"soqi|nordic\s*pole\s*walking|line\s*dance",
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


PICKUP_PATTERNS = [
    r"\bpick[\s-]?up\b",
    r"\bshinny\b",
    r"stick\s*(&|and)\s*puck",
    r"\bduffer\b",
    r"\bgoalies?\b",
    r"open\s*scrimmage",
]

DROPOIN_PATTERNS = [
    r"drop[\s-]?in",
    r"open\s*(gym|play|court|swim|skate)",
    r"public\s*(swim|skate)",
    r"\blengths\b",
    r"family\s*swim",
    r"fun\s*and\s*features\s*swim",
    r"adult\s*skate",
    r"tot\s*hockey",
    r"ice\s*play",
]

CLASS_PATTERNS = [
    r"\bclass\b",
    r"\bclasses\b",
    r"\blesson\b",
    r"\blessons\b",
    r"\bclinic\b",
    r"\bskills?\b",
    r"\btraining\b",
    r"\bworkshop\b",
    r"\bprogram\b",
    r"\bcourse\b",
    r"\byoga\b",
    r"\bpilates\b",
    r"\bzumba\b",
    r"\bcycle\b",
    r"\bfit(ness)?\b",
    r"\baqua\s*fit\b",
]

REGISTRATION_REQUIRED_PATTERNS = [
    r"reserved",
    r"advanced\s*registration",
    r"registration\s*required",
    r"available\s*to\s*reserve",
    r"book\s*online",
    r"court\s*reservation",
]

DROP_IN_ALLOWED_PATTERNS = [
    r"drop[\s-]?in",
    r"public\s*(swim|skate)",
    r"open\s*(gym|play|swim|skate)",
    r"everyone\s*welcome",
]

AGE_GROUP_PATTERNS = [
    (r"\ball\s*ages?\b", "all-ages"),
    (r"\bunder\s*\d+\b|\b\d+\s*-\s*\d+\s*yrs?\b|\bteen\b|\byouth\b|\bkids?\b", "youth"),
    (r"\b50\+\b|\b55\+\b|\b60\+\b|\bsenior", "seniors"),
    (r"\badult\b|\b19\s*yrs?\+\b|\bover\s*18\b|\bover\s*40\b|\bover\s*60\b", "adults"),
]

SKILL_LEVEL_PATTERNS = [
    (r"\bbeginner\b|\bintro\b|\bbasic\b", "beginner"),
    (r"\bintermediate\b", "intermediate"),
    (r"\badvanced\b|\bcompetitive\b", "advanced"),
    (r"\ball\s*levels?\b", "all-levels"),
]


def classify_offering_type(title: str, description: str = "") -> str:
    """Classify an event into product-facing offering types."""
    haystack = f"{title} {description}".lower()
    for pattern in PICKUP_PATTERNS:
        if re.search(pattern, haystack):
            return "pickup"
    for pattern in DROPOIN_PATTERNS:
        if re.search(pattern, haystack):
            return "drop-in"
    for pattern in CLASS_PATTERNS:
        if re.search(pattern, haystack):
            return "class"

    sport = classify_sport(title)
    if sport in {"fitness", "swimming", "arts", "kids"}:
        return "class"
    if sport in {"hockey", "pickleball", "badminton", "soccer", "basketball", "volleyball", "squash", "tennis"}:
        return "drop-in"
    return "drop-in"


def classify_registration_required(title: str, description: str = ""):
    haystack = f"{title} {description}".lower()
    for pattern in REGISTRATION_REQUIRED_PATTERNS:
        if re.search(pattern, haystack):
            return True
    for pattern in DROP_IN_ALLOWED_PATTERNS:
        if re.search(pattern, haystack):
            return False
    return None


def classify_age_group(title: str, description: str = "") -> str:
    haystack = f"{title} {description}".lower()
    for pattern, value in AGE_GROUP_PATTERNS:
        if re.search(pattern, haystack):
            return value
    return ""


def classify_skill_level(title: str, description: str = "") -> str:
    haystack = f"{title} {description}".lower()
    for pattern, value in SKILL_LEVEL_PATTERNS:
        if re.search(pattern, haystack):
            return value
    return ""

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
                ev_data.setdefault("source", self.source_id_prefix)
                ev_data.setdefault("municipality", self.municipality)
                ev_data["sport_type"] = classify_sport(ev_data.get("title", ""))
                ev_data["offering_type"] = classify_offering_type(
                    ev_data.get("title", ""),
                    ev_data.get("description", "") or "",
                )
                ev_data["registration_required"] = classify_registration_required(
                    ev_data.get("title", ""),
                    ev_data.get("description", "") or "",
                )
                ev_data["age_group"] = classify_age_group(
                    ev_data.get("title", ""),
                    ev_data.get("description", "") or "",
                )
                ev_data["skill_level"] = classify_skill_level(
                    ev_data.get("title", ""),
                    ev_data.get("description", "") or "",
                )
                
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
