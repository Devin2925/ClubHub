"""Fernwood NRG programs from its events calendar (The Events Calendar API).

fernwoodnrg.ca (now fernwoodnh.ca) publishes everything through The Events
Calendar at /wp-json/tribe/events/v1/events: the Neighbourhood House programs
(Family Resource Drop-In, the Monday Community Meal, Best Babies, Free Bread,
Intergenerational Art, D&D night) and Community Action Events. Its older EventON
feed (wp/v2/ajde_events, read by the retired scrapers/fernwood.py) returns 404
since October 2026.

About four in five of its entries are licensed childcare for enrolled children
(3 to 5 Childcare, Infant & Toddler, Fiddleheads); those are skipped.

The API is slow (~8s a page), so it's read one window at a time.
"""
import re
from datetime import date, datetime, timedelta

import requests

from scrapers.base import BaseScraper
from scrapers.event_utils import clean_text, price_from_text

API_URL = "https://fernwoodnrg.ca/wp-json/tribe/events/v1/events"
HORIZON_DAYS = 56
NOT_PUBLIC = re.compile(r"childcare|infant\s*&\s*toddler|fiddleheads|summer break camps|school age", re.I)
NOT_PUBLIC_CATEGORY = re.compile(r"childcare", re.I)


def _normalized(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower().replace("’", "'")).strip()


def _venue(raw) -> tuple[str, str]:
    """'Multi-Purpose Room – Fernwood Neighbourhood House' -> (venue, facility)."""
    name = clean_text(raw.get("venue", "")) if isinstance(raw, dict) else ""
    facility, _, building = name.rpartition(" – ")
    building = building or name
    if re.search(r"community centre", building, re.I):
        return "Fernwood Community Centre", facility
    if re.search(r"neighbourhood house", building, re.I):
        return "Fernwood Neighbourhood House", facility
    return "Fernwood Neighbourhood House", name


class FernwoodCalendarScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="fernwood_calendar", municipality="Victoria")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _fetch(self) -> list[dict]:
        today = date.today()
        items, page = [], 1
        while True:
            response = self.session.get(
                API_URL,
                params={
                    "per_page": 50,
                    "page": page,
                    "start_date": today.isoformat(),
                    "end_date": (today + timedelta(days=HORIZON_DAYS)).isoformat(),
                },
                timeout=90,
            )
            if response.status_code == 404 and page > 1:
                break
            response.raise_for_status()
            data = response.json()
            items.extend(data.get("events") or [])
            if page >= (data.get("total_pages") or 1):
                break
            page += 1
        return items

    def scrape(self):
        print("[Victoria] Starting Fernwood NRG events calendar scrape...")
        items = self._fetch()
        if not items:
            raise RuntimeError("Fernwood NRG events calendar returned nothing")

        # A title that comes back every week is a program; a one-off is an event.
        occurrences: dict[str, int] = {}
        for item in items:
            key = _normalized(clean_text(item.get("title")))
            occurrences[key] = occurrences.get(key, 0) + 1

        events, skipped_private = [], 0
        for item in items:
            title = clean_text(item.get("title"))
            categories = " ".join(row.get("name", "") for row in item.get("categories") or [])
            if not title or NOT_PUBLIC.search(title) or NOT_PUBLIC_CATEGORY.search(categories):
                skipped_private += 1
                continue
            start = datetime.fromisoformat(item["start_date"])
            end = datetime.fromisoformat(item["end_date"])
            venue, facility = _venue(item.get("venue"))
            description = clean_text(item.get("description") or "")
            event = {
                "source_id": f"{self.source_id_prefix}_{item['id']}",
                "title": title,
                "venue_name": venue,
                "facility_name": facility,
                "start_time": start,
                "end_time": end if end.date() == start.date() else start.replace(hour=end.hour, minute=end.minute),
                "price": clean_text(item.get("cost")) or price_from_text(title, description),
                "description": description[:600],
                "booking_url": item.get("url") or "https://fernwoodnrg.ca/events/",
            }
            # Neighbourhood House programs are open drop-ins (the default classifier calls a
            # meal a "class" and "pick up free bread" a pickup game). Best Babies is a
            # registered support group.
            if occurrences.get(_normalized(title), 0) == 1 and re.search(r"community action", categories, re.I):
                event["offering_override"] = "event"
            elif re.search(r"best babies", title, re.I):
                event["offering_override"] = "class"
            else:
                event["offering_override"] = "drop-in"
            event["sport_override"] = "other"
            events.append(event)

        print(
            f"[Victoria] Fernwood NRG calendar: kept {len(events)} of {len(items)} "
            f"({skipped_private} childcare or not public)."
        )
        self.save_events(events)
        self.prune_unseen_upcoming(
            {event["source_id"] for event in events},
            end=datetime.combine(date.today() + timedelta(days=HORIZON_DAYS), datetime.min.time()),
        )
        return events
