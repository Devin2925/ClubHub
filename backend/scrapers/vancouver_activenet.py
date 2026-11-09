"""Vancouver Park Board drop-in sessions from its ActiveNet online calendars.

Modelled on saanich.py (same multicenter/events API), with three Vancouver differences:

* Calendars and centres are read from the API (``rest/onlinecalendar/calendars`` and
  ``.../filters``) instead of hard-coded; Vancouver has ~24 calendars and ~40 centres.
* ``event_item_id`` is the activity, not the session (one id can carry 90+ dates), so a
  session's source_id is the id plus its start time.
* The calendars mix in private music lessons, personal training, court rentals and
  "Pool Closure" blocks. The API has no flag for any of them (event_type is always 0),
  so they are dropped by title, and by description for private lessons with plain titles
  ("Forte Piano": "join Alexandra for a private piano lesson").

Rows go to clubhub_vancouver.db (vancouver_db.py), never Victoria's clubhub.db.
"""
import collections
import json
import re
import time
from datetime import datetime

import requests

from scrapers.base import BaseScraper, classify_offering_type, classify_sport_fields
from vancouver_db import VancouverDBMixin

BASE_URL = "https://anc.ca.apm.activecommunities.com/vancouver"
CALENDAR_PAGE = f"{BASE_URL}/calendars"
CENTERS_PER_REQUEST = 10

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
# "No private lessons or teaching permitted" (rentals) is not an offer of one.
NEGATED = re.compile(r"\b(no|not|without)\s*$|prohibit", re.I)
# A drop-in's description can mention lessons on the side ("Table Tennis ... Private
# lessons available for $7.14/15 minutes"); the description rule never drops those.
DROP_IN_DESCRIPTION = re.compile(r"\bdrop[- ]?ins?\b", re.I)
RENTAL_TITLE = re.compile(
    r"(?<!skate )(?<!equipment )\brentals?\b|\b(?:court|table)\s+(?:booking|reservation)s?\b",
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
    for match in PRIVATE_DESCRIPTION.finditer(description):
        if not NEGATED.search(description[max(0, match.start() - 12) : match.start()]):
            return "private_lesson"
    return None


# --- Cleanup ----------------------------------------------------------------------------

# Rink rows read "Hillcrest Arena - Public Hockey - Wednesday 11:45am"; the venue and the
# time are already on the session.
ARENA_PREFIX = re.compile(r"^[A-Z][\w .']*?\bArena\s*-\s*")
DAY_TIME_SUFFIX = re.compile(
    r"\s*-\s*(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?\s+\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?$", re.I
)
STICK_AND_PUCK = re.compile(r"\bstick\b[\s,&and]*\bpuck\b", re.I)
CLASS_IN_POOL_OR_RINK =re.compile(r"aqua\s*fit|aquafit|\bfit\b|fitness|\blearn\s+to\b", re.I)

# Sport to use when the title alone doesn't say ("Multi-Use" on the swim calendar).
CALENDAR_SPORT = [
    (re.compile(r"public\s+swimming", re.I), "swimming"),
    (re.compile(r"public\s+skating", re.I), "skating"),
    (re.compile(r"basketball", re.I), "basketball"),
    (re.compile(r"soccer", re.I), "soccer"),
    (re.compile(r"volleyball", re.I), "volleyball"),
    (re.compile(r"^fitness:", re.I), "fitness"),
    (re.compile(r"parent\s+and\s+tot", re.I), "kids"),
]
# Every row on these calendars is public time; "Lessons" on the swim calendar means
# public swim while lessons run ("Recreational swim for all ages ...").
PUBLIC_TIME_CALENDARS = re.compile(r"public\s+swimming|public\s+skating", re.I)


def clean_name(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[|*\[\]]", " ", text or "")).strip(" -")


def clean_title(title: str) -> str:
    original = clean_name(title)
    short = DAY_TIME_SUFFIX.sub("", ARENA_PREFIX.sub("", original)).strip(" -")
    return short or original


def html_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


class VancouverActiveNetScraper(VancouverDBMixin, BaseScraper):
    def __init__(self, dry_run: bool = False):
        super().__init__(source_id_prefix="vancouver_activenet", municipality="Vancouver")
        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "Referer": CALENDAR_PAGE, "User-Agent": "Mozilla/5.0"}
        )
        self.skipped = collections.Counter()
        self.skipped_titles = collections.defaultdict(collections.Counter)
        self.failures = []
        self.dry_run = dry_run  # fetch and filter only; write nothing

    def _request(self, method: str, url: str, **kwargs) -> dict:
        for attempt in range(2):
            try:
                resp = self.session.request(method, url, timeout=60, **kwargs)
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    raise ValueError(f"unexpected {type(data).__name__} response")
                return data.get("body") or {}
            except (requests.RequestException, ValueError):
                if attempt:
                    raise
                time.sleep(2)

    def _calendars(self) -> list[dict]:
        body = self._request(
            "GET",
            f"{BASE_URL}/rest/onlinecalendar/calendars?locale=en-US",
            headers={"page_info": json.dumps({"order_by": "Name", "page_number": 1, "total_records_per_page": 200})},
        )
        return [row for row in body.get("calendars") or [] if not row.get("hide_on_internet") and not row.get("retired")]

    def _center_ids(self, calendar_id: int) -> list[int]:
        body = self._request(
            "POST", f"{BASE_URL}/rest/onlinecalendar/filters?locale=en-US", json={"calendar_id": calendar_id}
        )
        return [row["id"] for row in body.get("center") or [] if row.get("id") is not None]

    def _fetch_events(self, calendar_id: int, center_ids: list[int]) -> list[dict]:
        payload = {
            "calendar_id": calendar_id,
            "center_ids": center_ids,
            "display_all": 0,
            "search_start_time": "",
            "search_end_time": "",
            "activity_category_ids": [],
            "activity_ids": [],
            "activity_max_age": None,
            "activity_min_age": None,
            "activity_sub_category_ids": [],
            "event_type_ids": [],
            "facility_ids": [],
        }
        body = self._request("POST", f"{BASE_URL}/rest/onlinecalendar/multicenter/events?locale=en-US", json=payload)
        events = []
        for key in ("center_events", "calendar_group_list"):
            for group in body.get(key) or []:
                if isinstance(group, dict):
                    events.extend(event for event in group.get("events") or [] if isinstance(event, dict))
        return events

    def _normalize_event(self, raw: dict, calendar_name: str) -> dict | None:
        try:
            start_time = datetime.strptime(raw.get("start_time") or "", "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(raw.get("end_time") or "", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
        # The API's window starts the day before; yesterday's rows would just be pruned again.
        if end_time < datetime.combine(datetime.now().date(), datetime.min.time()):
            return None

        facility =next((row for row in raw.get("facilities") or [] if isinstance(row, dict)), {})
        venue_name = clean_name(facility.get("center_name")) or "Vancouver"
        facility_name = clean_name(facility.get("facility_name"))
        title = clean_title(raw.get("title") or "")
        description = html_text(raw.get("description"))

        price_info = raw.get("price") if isinstance(raw.get("price"), dict) else {}
        price = "Free" if price_info.get("free") else (price_info.get("estimate_price") or "")

        event = {
            "source_id": f"vancouver_{raw.get('event_item_id')}_{start_time:%Y%m%d%H%M}",
            "title": title,
            "venue_name": venue_name,
            "facility_name": facility_name if facility_name != venue_name else "",
            "center_id": facility.get("center_id"),
            "start_time": start_time,
            "end_time": end_time,
            "price": price,
            "description": description,
            "booking_url": raw.get("activity_detail_url") or CALENDAR_PAGE,
        }

        # Decide the sport here, with the raw facility name ("*Kerrisdale Pool"), since the
        # saved facility_name is blank when it just repeats the venue.
        sport = classify_sport_fields(title, facility_name)
        if sport == "other":
            sport = next((value for pattern, value in CALENDAR_SPORT if pattern.search(calendar_name)), sport)
        if STICK_AND_PUCK.search(title):
            # "Stick, Puck & Ring" misses base.py's "stick & puck" pattern.
            sport = "hockey"
            event["offering_override"] = "pickup"
        event["sport_override"] = sport
        if "offering_override" not in event and (
            PUBLIC_TIME_CALENDARS.search(calendar_name)
            and classify_offering_type(title, description) == "class"
            and not CLASS_IN_POOL_OR_RINK.search(title)
        ):
            event["offering_override"] = "drop-in"
        return event

    def scrape(self):
        print(f"[{self.municipality}] Starting Park Board ActiveNet scrape...")
        self.session.get(CALENDAR_PAGE, timeout=30).raise_for_status()

        events = {}
        for calendar in self._calendars():
            calendar_id = calendar["calendar_id"]
            calendar_name = clean_name(calendar.get("name"))
            try:
                center_ids = self._center_ids(calendar_id)
            except (requests.RequestException, ValueError) as exc:
                self.failures.append(f"{calendar_name}: {exc}")
                continue
            for start in range(0, len(center_ids), CENTERS_PER_REQUEST):
                try:
                    raw_events = self._fetch_events(calendar_id, center_ids[start : start + CENTERS_PER_REQUEST])
                except (requests.RequestException, ValueError) as exc:
                    self.failures.append(f"{calendar_name} (centres {start + 1}+): {exc}")
                    continue
                for raw in raw_events:
                    event = self._normalize_event(raw, calendar_name)
                    if not event or event["source_id"] in events:
                        continue
                    reason = skip_reason(event["title"], event["description"])
                    if reason:
                        self.skipped[reason] += 1
                        self.skipped_titles[reason][event["title"]] += 1
                        continue
                    events[event["source_id"]] = event
                time.sleep(0.3)

        if not events:
            raise RuntimeError("Vancouver ActiveNet returned no drop-in sessions: " + "; ".join(self.failures[:3]))

        saved = list(events.values())
        if not self.dry_run:
            self.save_events(saved)
            if self.failures:
                print(f"[{self.municipality}] {len(self.failures)} fetch(es) failed; not pruning: {self.failures[:3]}")
            else:
                self.prune_unseen_upcoming(events.keys())

        skipped = ", ".join(f"{count} {reason.replace('_', ' ')}" for reason, count in self.skipped.most_common())
        self.last_reported_count = len(saved)
        self.last_status_note = f"Skipped {skipped}" if skipped else None
        if self.failures:
            self.last_status_note = f"{len(self.failures)} fetch failures; " + (self.last_status_note or "")
        print(f"[{self.municipality}] {len(saved)} drop-in sessions kept; skipped {skipped or 'none'}")
        return saved
