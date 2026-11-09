"""Oak Bay community events from the District's events calendar.

oakbay.ca/whats-happening/community-events/events-calendar/ is The Events Calendar
(WordPress), which publishes a JSON API. The listings are one-off community
events - concerts in the Sports View Lounge, Monterey talks and markets, the
Remembrance Day ceremony, tennis tournaments - saved through event_utils.
"""
import re
from datetime import date, datetime, timedelta

import requests

from scrapers.base import BaseScraper
from scrapers.event_utils import NOT_AN_EVENT, clean_text, event_row

API_URL = "https://www.oakbay.ca/wp-json/tribe/events/v1/events"
CALENDAR_URL = "https://www.oakbay.ca/whats-happening/community-events/events-calendar/"

# The calendar's venue names, mapped onto the venues ClubHub already lists.
REC_VENUES = [
    (re.compile(r"monterey", re.I), "Monterey Recreation Centre"),
    (re.compile(r"henderson", re.I), "Henderson Recreation Centre"),
    (re.compile(r"oak bay recreation centre", re.I), "Oak Bay Recreation Centre"),
    (re.compile(r"windsor pavilion", re.I), "Windsor Pavilion"),
]


def _venue(raw: dict | list | None) -> tuple[str, str]:
    """(venue_name, facility_name) for a calendar venue."""
    name = clean_text(raw.get("venue", "")) if isinstance(raw, dict) else ""
    if not name:
        return "Around Oak Bay", ""
    for pattern, venue in REC_VENUES:
        if pattern.search(name):
            # "Oak Bay Recreation Centre, Sports View Lounge" -> facility "Sports View Lounge"
            return venue, name.split(",", 1)[1].strip() if "," in name else ""
    return name, ""


class OakBayEventsScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="oakbay_events", municipality="Oak Bay")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _fetch(self) -> list[dict]:
        today = date.today()
        events, page = [], 1
        while True:
            response = self.session.get(
                API_URL,
                params={
                    "per_page": 50,
                    "page": page,
                    "start_date": today.isoformat(),
                    "end_date": (today + timedelta(days=240)).isoformat(),
                },
                timeout=30,
            )
            # The API answers past the last page with a 404 "no events" error.
            if response.status_code == 404 and page > 1:
                break
            response.raise_for_status()
            data = response.json()
            events.extend(data.get("events") or [])
            if page >= (data.get("total_pages") or 1):
                break
            page += 1
        return events

    def _normalize(self, item: dict) -> dict | None:
        title = clean_text(item.get("title"))
        if not title or NOT_AN_EVENT.search(title):
            return None
        venue_name, facility = _venue(item.get("venue"))
        # start_date/end_date are Oak Bay wall-clock times (the API's own timezone label is wrong).
        return event_row(
            source_id=f"{self.source_id_prefix}_{item['id']}",
            title=title,
            venue_name=venue_name,
            facility_name=facility,
            start=datetime.fromisoformat(item["start_date"]),
            end=datetime.fromisoformat(item["end_date"]),
            all_day=bool(item.get("all_day")),
            price=clean_text(item.get("cost")),
            description=item.get("description") or "",
            url=item.get("url") or CALENDAR_URL,
        )

    def scrape(self):
        print("[Oak Bay] Starting Oak Bay events calendar scrape...")
        items = self._fetch()
        if not items:
            raise RuntimeError("Oak Bay events calendar returned nothing")
        events = [event for event in (self._normalize(item) for item in items) if event]
        print(f"[Oak Bay] Oak Bay events: kept {len(events)} of {len(items)} calendar entries.")
        self.save_events(events)
        self.prune_unseen_upcoming({event["source_id"] for event in events})
        return events
