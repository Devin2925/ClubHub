"""Shared rules for ClubHub Vancouver scrapers (ActiveNet and PerfectMind alike).

* ``skip_reason`` decides what isn't a drop-in: private lessons, rentals, closures.
* ``classify`` fills sport/offering when the title alone doesn't say.
* ``VancouverScraper`` saves into clubhub_vancouver.db, records what each filter dropped,
  and prunes only after a run where every fetch succeeded.

When a new source brings junk these rules miss, add a pattern here and re-run
``vancouver_sync.py --dry-run --skipped <source>`` to check what it catches.
"""
import collections
import re
from datetime import datetime

from scrapers.base import BaseScraper, classify_offering_type, classify_sport_fields
from vancouver_db import VancouverDBMixin

# --- What isn't a drop-in -------------------------------------------------------------

PRIVATE_TITLE = re.compile(
    r"\bprivate\b|\bindividual\b.*\blessons?\b|\b1\s*-?\s*on\s*-?\s*1\b|\bone[- ]on[- ]one\b|\bpersonal\s+training\b",
    re.I,
)
PRIVATE_DESCRIPTION = re.compile(
    r"\bprivate\s+(?:[\w/&]+\s+){0,3}lessons?\b(?!\s+(?:are\s+)?available)"  # "a private Guitar or Ukulele lesson"
    r"|\b\d{2}[- ]minute\s+private\s+lessons?\b"     # "Each 30 minute private lesson"
    r"|\bprivate\s+\d{2}[- ]minute\s+lessons?\b"     # "Private 30 minute lessons"
    r"|\b(?:a|each)\s+\d{2}[- ]minute\s+lesson\b"    # "take a 60 minute lesson"
    r"|\beach\s+(?:class\s+)?session\s+is\s+(?:15|20|30)\s+minutes\b",  # one-to-one music slots
    re.I,
)
# "No private lessons or teaching permitted", "No outside private lessons", "External
# private lessons not permitted" are rules, not offers of one.
NEGATED_BEFORE = re.compile(r"\b(no|not|without)(\s+(outside|external|other))?\s*$|prohibit", re.I)
NEGATED_AFTER = re.compile(r"^\s*(are\s+|is\s+)?(not\b|prohibited)", re.I)
# A drop-in's description can mention lessons on the side ("Table Tennis ... Private
# lessons available for $7.14/15 minutes"); the description rule never drops those.
DROP_IN_DESCRIPTION = re.compile(r"\bdrop[- ]?ins?\b", re.I)
RENTAL_TITLE = re.compile(
    r"(?<!skate )(?<!equipment )\brentals?\b|\b(?:court|table)\s+(?:booking|reservation)s?\b",
    re.I,
)
# Booking one court/table for your group: Richmond "BADMINTON BOOKING - COURT 1 - ADULTS"
# ($12.15 a court), Port Coquitlam "Pickleball - PCCC Reserve Court #1". A rental unless the
# description calls it a drop-in (Burnaby's per-court squash slots are drop-in admission).
COURT_BOOKING_TITLE = re.compile(
    r"\bbooking\s*[-–:]\s*(?:court|table)\b|\breserve\s+(?:court|table)\b|\b(?:court|table)\s+booking\b",
    re.I,
)
CLOSURE_TITLE = re.compile(r"\bclosures?\b|\bclosed\b|\bcancell?ed\b", re.I)


def skip_reason(title: str, description: str) -> str | None:
    """Why a calendar row is not a drop-in session, or None to keep it."""
    if CLOSURE_TITLE.search(title):
        return "closure"
    if RENTAL_TITLE.search(title):
        return "rental"
    if PRIVATE_TITLE.search(title):
        return "private_lesson"
    if DROP_IN_DESCRIPTION.search(description):
        return None
    if COURT_BOOKING_TITLE.search(title):
        return "rental"
    for match in PRIVATE_DESCRIPTION.finditer(description):
        before = description[max(0, match.start() - 24) : match.start()]
        if re.search(r"\b(outside|external)\s*$", before, re.I):
            before = description[max(0, match.start() - 40) : match.start()]
        if NEGATED_BEFORE.search(before) or NEGATED_AFTER.search(description[match.end() : match.end() + 20]):
            continue
        return "private_lesson"
    return None


# Kept titles that are worth a human look when a new source is added (--skipped lists them).
REVIEW_TITLE = re.compile(
    r"lesson|piano|guitar|violin|drum|voice|vocal|ukul|tutor|rental|\brent\b|\bbook(ing)?\b|reserv|clos|cancel|"
    r"\bstaff\b|\badmin\b|\bhold\b|maintenance|private|\bpart(y|ies)\b|meeting",
    re.I,
)

# --- Cleanup ----------------------------------------------------------------------------

# Source venue name → the name vancouver_registry.py uses, when a source spells it
# differently. vancouver_sync.py's registry check ("NOT IN REGISTRY") says when to add one.
VENUE_ALIASES = {
    ("New Westminster", "School District #40"): "New Westminster schools (SD40)",
}

# Rink rows read "Hillcrest Arena - Public Hockey - Wednesday 11:45am"; the venue and the
# time are already on the session.
ARENA_PREFIX = re.compile(r"^[A-Z][\w .']*?\bArena\s*-\s*")
DAY_TIME_SUFFIX = re.compile(
    r"\s*-\s*(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?\s+\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?$", re.I
)
# Burnaby: "Reserve In Advance: Badminton Adult" (a drop-in you may book ahead).
RESERVE_PREFIX = re.compile(r"^reserve\s+in\s+advance\s*:\s*", re.I)
# Burnaby "Bonsor Recreation Complex (BON)"; Langley City "TIMMS COMMUNITY CENTRE - 20399 DOUGLAS CRS".
VENUE_CODE_SUFFIX = re.compile(r"\s*\([A-Z]{2,5}\)$")
VENUE_ADDRESS_SUFFIX = re.compile(r"\s+-\s+\d+\s.*$")
# Times baked into titles: Delta "Badminton 18+ 2pm Mon", NVRC "... Lions Gate Friday 9:30-11:30am".
_DAY = r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?"
_TIME = r"\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?\s*-\s*\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?|\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?"
WHEN_SUFFIX = re.compile(rf"(?:(?:\s+|\s*[-,]\s*)(?:{_DAY}|{_TIME}))+$", re.I)
SMALL_WORDS = {"a", "an", "and", "or", "of", "the", "to", "in", "on", "at", "for", "with", "w/"}
STICK_AND_PUCK = re.compile(r"\bstick\b[\s,&and]*\bpuck\b", re.I)
CLASS_IN_POOL_OR_RINK = re.compile(r"aqua\s*fit|aquafit|\bfit\b|fitness|\blearn\s+to\b", re.I)

# Sport to use when the title alone doesn't say ("Multi-Use" on the swim calendar).
# Matched against the calendar label ("Public Swimming", "Drop In / Skating").
CALENDAR_SPORT = [
    (re.compile(r"swim|aquatic|pool", re.I), "swimming"),
    (re.compile(r"skat", re.I), "skating"),
    (re.compile(r"basketball", re.I), "basketball"),
    (re.compile(r"soccer", re.I), "soccer"),
    (re.compile(r"volleyball", re.I), "volleyball"),
    (re.compile(r"fitness", re.I), "fitness"),
    (re.compile(r"parent\s+and\s+tot", re.I), "kids"),
]
# Every row on these calendars is public time; "Lessons" on Vancouver's swim calendar
# means public swim while lessons run ("Recreational swim for all ages ...").
PUBLIC_TIME_CALENDARS = re.compile(r"public\s+(swim|skat)|drop[- ]?in\b.*\b(swim|skat)", re.I)


def clean_name(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[|*\[\]]", " ", text or "")).strip(" -")


def clean_title(title: str) -> str:
    original = clean_name(title)
    short = DAY_TIME_SUFFIX.sub("", ARENA_PREFIX.sub("", RESERVE_PREFIX.sub("", original))).strip(" -")
    when = WHEN_SUFFIX.search(short)
    if when and re.search(r"\d", when.group()) and when.start() > 0:
        short = short[: when.start()].strip(" -,")
    letters = [c for c in short if c.isalpha()]
    if len(letters) > 4 and sum(c.isupper() for c in letters) / len(letters) > 0.8:  # Richmond: "BADMINTON BOOKING - COURT 1"
        words = short.lower().split()
        short = " ".join(w if i and w in SMALL_WORDS else w[:1].upper() + w[1:] for i, w in enumerate(words))
    return short or original


def clean_venue(name: str) -> str:
    venue = VENUE_ADDRESS_SUFFIX.sub("", VENUE_CODE_SUFFIX.sub("", clean_name(name)))
    if venue.isupper():
        venue = " ".join(word.capitalize() for word in venue.split())
    return venue


def html_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'")
    return re.sub(r"\s+", " ", text).strip()


def classify(title: str, facility_name: str, description: str, calendar_label: str) -> dict:
    """sport_override / offering_override for an event (BaseScraper.save_events honours both)."""
    overrides = {}
    sport = classify_sport_fields(title, facility_name)
    if sport == "other":
        sport = next((value for pattern, value in CALENDAR_SPORT if pattern.search(calendar_label)), sport)
    if STICK_AND_PUCK.search(title):
        # "Stick, Puck & Ring" misses base.py's "stick & puck" pattern.
        sport = "hockey"
        overrides["offering_override"] = "pickup"
    # Decided here, with the raw facility name, since the saved facility_name may be blank.
    overrides["sport_override"] = sport
    if (
        "offering_override" not in overrides
        and PUBLIC_TIME_CALENDARS.search(calendar_label)
        and classify_offering_type(title, description) == "class"
        and not CLASS_IN_POOL_OR_RINK.search(title)
    ):
        overrides["offering_override"] = "drop-in"
    return overrides


def start_of_today() -> datetime:
    return datetime.combine(datetime.now().date(), datetime.min.time())


class VancouverScraper(VancouverDBMixin, BaseScraper):
    """Base for Vancouver sources: filter, save to clubhub_vancouver.db, prune, report."""

    def __init__(self, source_id_prefix: str, municipality: str, dry_run: bool = False):
        super().__init__(source_id_prefix=source_id_prefix, municipality=municipality)
        self.dry_run = dry_run  # fetch and filter only; write nothing
        self.skipped = collections.Counter()
        self.skipped_titles = collections.defaultdict(collections.Counter)
        self.failures = []
        self.events = {}

    def keep(self, event: dict | None) -> None:
        """Add a normalized event unless it's a duplicate or not a drop-in."""
        if not event or event["source_id"] in self.events:
            return
        event["venue_name"] = VENUE_ALIASES.get((self.municipality, event["venue_name"]), event["venue_name"])
        reason = skip_reason(event["title"], event.get("description") or "")
        if reason:
            self.skipped[reason] += 1
            self.skipped_titles[reason][event["title"]] += 1
            return
        self.events[event["source_id"]] = event

    def review_titles(self) -> collections.Counter:
        return collections.Counter(e["title"] for e in self.events.values() if REVIEW_TITLE.search(e["title"]))

    def finish(self) -> list[dict]:
        if not self.events:
            raise RuntimeError(f"{self.municipality}: no drop-in sessions found; " + "; ".join(self.failures[:3]))
        saved = list(self.events.values())
        if not self.dry_run:
            self.save_events(saved)
            if self.failures:
                print(f"[{self.municipality}] {len(self.failures)} fetch(es) failed; not pruning: {self.failures[:3]}")
            else:
                self.prune_unseen_upcoming(self.events.keys())

        skipped = ", ".join(f"{count} {reason.replace('_', ' ')}" for reason, count in self.skipped.most_common())
        self.last_reported_count = len(saved)
        notes = []
        if self.failures:
            notes.append(f"{len(self.failures)} fetch failures (first: {self.failures[0]})")
        if skipped:
            notes.append(f"Skipped {skipped}")
        self.last_status_note = "; ".join(notes) or None
        print(f"[{self.municipality}] {len(saved)} drop-in sessions kept; skipped {skipped or 'none'}")
        return saved
