"""Esquimalt community events from the Township's events calendar.

esquimalt.ca/culture-heritage/community-events-calendar is a Drupal FullCalendar
view that embeds every event it has ever listed (1,100+) as JSON in the page's
drupal-settings. The location lives only on each event's own page
("Event location: Archie Browning Sports Centre"), so upcoming events are
fetched one page each, once per URL (a weekly market shares one page).
"""
import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

import requests

from scrapers.base import BaseScraper
from scrapers.event_utils import NOT_AN_EVENT, clean_text, event_row

BASE_URL = "https://www.esquimalt.ca"
CALENDAR_URL = f"{BASE_URL}/culture-heritage/community-events-calendar"
HORIZON_DAYS = 240

# Event pages spell the same place several ways; use the names ClubHub already lists.
VENUE_ALIASES = [
    (re.compile(r"^esquimalt rec(?:reation)? cent(?:re|er)\b", re.I), "Esquimalt Recreation Centre"),
    (re.compile(r"archie browning", re.I), "Archie Browning Sports Centre"),
    (re.compile(r"gorge park pavilion", re.I), "Esquimalt Gorge Park Pavilion"),
]


def _venue_name(location: str) -> str:
    for pattern, name in VENUE_ALIASES:
        if pattern.search(location):
            return name
    return location or "Around Esquimalt"


def _calendar_events(settings) -> list[dict]:
    """The FullCalendar event list, wherever it sits in drupalSettings (it's a JSON string)."""
    if isinstance(settings, str) and settings.lstrip().startswith("{") and '"events"' in settings:
        return _calendar_events(json.loads(settings))
    if isinstance(settings, dict):
        if isinstance(settings.get("events"), list):
            return settings["events"]
        for value in settings.values():
            found = _calendar_events(value)
            if found:
                return found
    if isinstance(settings, list):
        for value in settings:
            found = _calendar_events(value)
            if found:
                return found
    return []


def _field(page_html: str, name: str) -> str:
    match = re.search(
        rf'field--name-{name}\b[^"]*"[^>]*>(.*?)</div>\s*</div>', page_html, re.S
    )
    return clean_text(match.group(1)) if match else ""


class EsquimaltEventsScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="esquimalt_events", municipality="Esquimalt")
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
        )
        self._details: dict[str, tuple[str, str]] = {}

    def _detail(self, url: str) -> tuple[str, str]:
        """(location, description) from an event's own page."""
        if url not in self._details:
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                page = response.text
                main = page[page.find("<main") : page.find("</main>")] or page
                location = re.sub(r"^Event location\s*", "", _field(main, "field-event-location"), flags=re.I)
                description = _field(main, "field-event-details") or _field(main, "field-row-content") or _field(main, "body")
                self._details[url] = (location, description)
            except requests.RequestException as exc:
                print(f"[Esquimalt] Event page failed {url}: {exc}")
                self._details[url] = ("", "")
        return self._details[url]

    @staticmethod
    def _parse_when(item: dict) -> tuple[datetime, datetime, bool]:
        all_day = bool(item.get("allDay")) or len(item.get("start") or "") == 10
        start = datetime.fromisoformat(item["start"])
        end = datetime.fromisoformat(item.get("end") or item["start"])
        if all_day and len(item.get("end") or "") == 10:
            end -= timedelta(days=1)  # FullCalendar's all-day end date is exclusive.
        return start, end, all_day

    def scrape(self):
        print("[Esquimalt] Starting Esquimalt events calendar scrape...")
        response = self.session.get(CALENDAR_URL, timeout=45)
        response.raise_for_status()
        settings = re.search(r'data-drupal-selector="drupal-settings-json">(.*?)</script>', response.text, re.S)
        items = _calendar_events(json.loads(settings.group(1))) if settings else []
        if not items:
            raise RuntimeError("Esquimalt events calendar had no event data")

        today = date.today()
        horizon = today + timedelta(days=HORIZON_DAYS)
        events = []
        for item in items:
            title = clean_text(re.sub(r"<span class=\"fc-time\">.*", "", item.get("title") or "", flags=re.S))
            if not title or NOT_AN_EVENT.search(title):
                continue
            start, end, all_day = self._parse_when(item)
            if end.date() < today or start.date() > horizon:
                continue
            url = urljoin(BASE_URL, item.get("url") or "")
            location, description = self._detail(url)
            events.append(
                event_row(
                    source_id=f"{self.source_id_prefix}_{item.get('eid') or item.get('id')}",
                    title=title,
                    venue_name=_venue_name(location),
                    start=start,
                    end=end,
                    all_day=all_day,
                    description=description,
                    url=url,
                )
            )

        print(f"[Esquimalt] Esquimalt events: kept {len(events)} upcoming of {len(items)} calendar entries.")
        self.save_events(events)
        self.prune_unseen_upcoming({event["source_id"] for event in events})
        return events
