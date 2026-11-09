"""UBC Recreation drop-ins (Vancouver campus) from the feed behind its schedule pages.

recreation.ubc.ca's drop-in pages (Aquatic Centre, Gym Sports, Group Fitness, Studios,
Hockey & Skating) are WP FullCalendar widgets that load one JSON feed, backed by UBC's
PerfectMind account (ubc.perfectmind.com/24063):

    GET https://recreation.ubc.ca/pm-feed/?calendarname=<cal>&eventlocation=<loc>
        &services=Null&closuresonly=N&teams=&exclude=&keywords=&facilitytype=
        &start=YYYY-MM-DD&end=YYYY-MM-DD

Each row has title ("Basketball | DROP-IN"), start/end (local wall clock), location
(building), facilityname, servicename, category and a PerfectMind booking link (curl).
The calendar names and locations below are the ones each page passes (WPFC.data); if a
page's calendar changes, copy the new calname/location from its WPFC.data block.

Left out on purpose: Faculty & Staff Only sessions (the public and students can't use
them) and Open Studio room time (booked space, not an activity). Students and the public
can both use the rest; some sessions are student-only or women/2STNB-only and say so in
the title.
"""
import re
from datetime import datetime, timedelta

import requests

from scrapers.vancouver_common import VancouverScraper, classify, clean_name, html_text, start_of_today

FEED_URL = "https://recreation.ubc.ca/pm-feed/"
HORIZON_DAYS = 56

# (calendar name, location filter) as each schedule page passes them.
UBC_CALENDARS = [
    ("Aquatic Centre", "Null"),
    ("Gymnasium", "Student Recreation Centre:Rec North"),
    ("Group Fitness:Spin:Yoga & Pilates", "Null"),
    ("Studio", "Student Recreation Centre:ARC:Rec North"),
    ("Ice", "Null"),
]

# The feed's building names → venue names people search for.
UBC_VENUES = {
    "Aquatic Centre": "UBC Aquatic Centre",
    "Rec North": "UBC Recreation Centre North",
    "Student Recreation Centre": "UBC Student Recreation Centre",
    "ARC": "UBC Activities & Recreation Centre (ARC)",
    "Ponderosa Commons": "UBC Ponderosa Commons",
    "Doug Mitchell Thunderbird Sports Centre": "UBC Doug Mitchell Thunderbird Sports Centre",
}

UBC_SOURCES = {
    "ubc_recreation": {"municipality": "UBC", "display_name": "UBC Recreation drop-ins"},
}

KEEP_CATEGORIES = {"drop-in", "fitness & classes"}
# "Faculty & Staff Only" sessions; "$2 UBC Faculty and Staff" length swims are public (staff price).
NOT_PUBLIC = re.compile(r"faculty\s*(?:&|and)\s*staff\s+(?:only|sports)", re.I)
ROOM_TIME = re.compile(r"open studio", re.I)
BOOKING_TAG = re.compile(r"^(?:drop-?in|reserve|register)$", re.I)


def ubc_title(raw: str) -> str:
    """"Community Swim | Leisure Pool | DROP-IN" → "Community Swim - Leisure Pool"."""
    parts = [clean_name(part) for part in (raw or "").split("|")]
    return " - ".join(part for part in parts if part and not BOOKING_TAG.match(part))


class UBCRecreationScraper(VancouverScraper):
    def __init__(self, source_key: str, municipality: str, dry_run: bool = False, **_):
        super().__init__(source_id_prefix=source_key, municipality=municipality, dry_run=dry_run)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0 (ClubHub schedule aggregator)"

    def _feed(self, calendar: str, location: str) -> list[dict]:
        start = start_of_today()
        params = {
            "calendarname": calendar,
            "eventlocation": location,
            "services": "Null",
            "closuresonly": "N",
            "teams": "",
            "exclude": "",
            "keywords": "",
            "facilitytype": "",
            "start": f"{start:%Y-%m-%d}",
            "end": f"{start + timedelta(days=HORIZON_DAYS):%Y-%m-%d}",
        }
        response = self.session.get(FEED_URL, params=params, timeout=60)
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError(f"unexpected {type(rows).__name__} from pm-feed")
        return rows

    def _normalize(self, row: dict, calendar: str) -> dict | None:
        if (row.get("category") or "").strip().lower() not in KEEP_CATEGORIES:
            self.skipped["not_drop_in"] += 1
            return None
        raw_title = row.get("title") or ""
        service = row.get("servicename") or ""
        if NOT_PUBLIC.search(raw_title) or NOT_PUBLIC.search(service):
            self.skipped["staff_only"] += 1
            self.skipped_titles["staff_only"][ubc_title(raw_title)] += 1
            return None
        if ROOM_TIME.search(service) or ROOM_TIME.search(raw_title):
            self.skipped["room_time"] += 1
            return None
        try:
            start_time = datetime.strptime(row["start"], "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(row["end"], "%Y-%m-%d %H:%M:%S")
        except (KeyError, TypeError, ValueError):
            return None
        if end_time < start_of_today():
            return None

        title = ubc_title(raw_title)
        building = clean_name(row.get("location"))
        venue_name = UBC_VENUES.get(building, f"UBC {building}" if building else "UBC Recreation")
        facility_name = clean_name(row.get("facilityname") or row.get("facility"))
        description = html_text(row.get("description") or "")
        return {
            "source_id": f"{self.source_id_prefix}_{row.get('eventId')}_{start_time:%Y%m%d%H%M}",
            "title": title,
            "venue_name": venue_name,
            "facility_name": facility_name if facility_name and facility_name != venue_name else "",
            "start_time": start_time,
            "end_time": end_time,
            "price": "",
            "description": description,
            "booking_url": row.get("curl") or "https://recreation.ubc.ca/drop-in/",
            "availability": "",
            **classify(title, facility_name, description, calendar),
        }

    def scrape(self):
        print(f"[{self.municipality}] Starting UBC Recreation feed scrape...")
        for calendar, location in UBC_CALENDARS:
            try:
                rows = self._feed(calendar, location)
            except (requests.RequestException, ValueError) as exc:
                self.failures.append(f"{calendar}: {exc}")
                continue
            for row in rows:
                if row.get("eventId"):
                    self.keep(self._normalize(row, calendar))
        return self.finish()
