"""Community events from Drupal FullCalendar views: Esquimalt, City of Victoria, WSPR.

These municipal sites embed every event their calendar has ever listed (hundreds
to 1,100+) as JSON inside the page's drupal-settings - a JSON string nested in
JSON. Each entry has title, url, start, end and allDay. Times are local
wall-clock (WSPR adds B.C.'s -07:00 offset); ClubHub stores naive local times, so
any offset is dropped.

Location and description live only on each event's own page, so upcoming events
are fetched one page each, once per URL (a weekly game night shares one page).

A site is a subclass that sets the class attributes below. To add one: point
``calendar_url`` at the page whose drupal-settings holds ``fullCalendarView``,
then map the places its pages name onto venues ClubHub already lists.
"""
import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

import requests

from scrapers.base import BaseScraper
from scrapers.event_utils import NOT_AN_EVENT, clean_text, event_row

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def calendar_events(settings) -> list[dict]:
    """The FullCalendar event list, wherever it sits in drupalSettings (it's a JSON string)."""
    if isinstance(settings, str) and settings.lstrip().startswith("{") and '"events"' in settings:
        return calendar_events(json.loads(settings))
    if isinstance(settings, dict):
        if isinstance(settings.get("events"), list):
            return settings["events"]
        for value in settings.values():
            found = calendar_events(value)
            if found:
                return found
    if isinstance(settings, list):
        for value in settings:
            found = calendar_events(value)
            if found:
                return found
    return []


def page_field(page_html: str, name: str) -> str:
    match = re.search(rf'field--name-{name}\b[^"]*"[^>]*>(.*?)</div>\s*</div>', page_html, re.S)
    return clean_text(match.group(1)) if match else ""


def parse_when(item: dict) -> tuple[datetime, datetime, bool]:
    """(start, end, all_day) as naive local times from a FullCalendar entry."""
    raw_start, raw_end = item["start"], item.get("end") or item["start"]
    all_day = bool(item.get("allDay")) or len(raw_start) == 10
    start = datetime.fromisoformat(raw_start[:19])
    end = datetime.fromisoformat(raw_end[:19])
    if all_day and len(raw_end) == 10 and end > start:
        end -= timedelta(days=1)  # FullCalendar's all-day end date is exclusive.
    return start, end, all_day


class DrupalCalendarEventsScraper(BaseScraper):
    label = ""  # log prefix, e.g. "Esquimalt"
    base_url = ""
    calendar_url = ""
    default_venue = ""  # when an event's page names no place ClubHub knows
    # (pattern, venue, facility). Matched against the page's location, then (when
    # aliases_search_text) the title and the start of the description.
    venue_aliases: list[tuple[re.Pattern, str, str]] = []
    aliases_search_text = True
    keep_unknown_location = True  # use the page's location text as the venue when no alias matches
    skip_titles: re.Pattern | None = None  # site-specific non-events, on top of NOT_AN_EVENT
    horizon_days = 240

    def __init__(self, source_id_prefix: str, municipality: str):
        super().__init__(source_id_prefix=source_id_prefix, municipality=municipality)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._details: dict[str, tuple[str, str]] = {}

    # -- per-site hooks ----------------------------------------------------------
    def location_from_page(self, main: str) -> str:
        return re.sub(r"^Event location\s*", "", page_field(main, "field-event-location"), flags=re.I)

    def description_from_page(self, main: str) -> str:
        return page_field(main, "field-event-details") or page_field(main, "field-row-content") or page_field(main, "body")

    def venue_for(self, title: str, location: str, description: str) -> tuple[str, str]:
        texts = (location, title, description[:400]) if self.aliases_search_text else (location,)
        for text in texts:
            for pattern, venue, facility in self.venue_aliases:
                if text and pattern.search(text):
                    return venue, facility
        if location and self.keep_unknown_location:
            return location, ""
        return self.default_venue, ""

    # -- shared ------------------------------------------------------------------
    def _detail(self, url: str) -> tuple[str, str]:
        """(location, description) from an event's own page."""
        if url not in self._details:
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                page = response.text
                main = page[page.find("<main") : page.find("</main>")] or page
                self._details[url] = (self.location_from_page(main), self.description_from_page(main))
            except requests.RequestException as exc:
                print(f"[{self.label}] Event page failed {url}: {exc}")
                self._details[url] = ("", "")
        return self._details[url]

    def scrape(self):
        print(f"[{self.label}] Starting {self.label} events calendar scrape...")
        response = self.session.get(self.calendar_url, timeout=60)
        response.raise_for_status()
        settings = re.search(r'data-drupal-selector="drupal-settings-json">(.*?)</script>', response.text, re.S)
        items = calendar_events(json.loads(settings.group(1))) if settings else []
        if not items:
            raise RuntimeError(f"{self.label} events calendar had no event data")

        today = date.today()
        horizon = today + timedelta(days=self.horizon_days)
        events, seen = [], set()
        for item in items:
            title = clean_text(re.sub(r"<span class=\"fc-time\">.*", "", item.get("title") or "", flags=re.S))
            if not title or NOT_AN_EVENT.search(title) or (self.skip_titles and self.skip_titles.search(title)):
                continue
            start, end, all_day = parse_when(item)
            if end.date() < today or start.date() > horizon:
                continue
            source_id = f"{self.source_id_prefix}_{item.get('eid') or item.get('id')}"
            if source_id in seen:
                continue
            seen.add(source_id)
            url = urljoin(self.base_url, item.get("url") or "")
            location, description = self._detail(url)
            venue, facility = self.venue_for(title, location, description)
            events.append(
                event_row(
                    source_id=source_id,
                    title=title,
                    venue_name=venue,
                    facility_name=facility,
                    start=start,
                    end=end,
                    all_day=all_day,
                    description=description,
                    url=url,
                )
            )

        print(f"[{self.label}] {self.label} events: kept {len(events)} upcoming of {len(items)} calendar entries.")
        self.save_events(events)
        self.prune_unseen_upcoming({event["source_id"] for event in events})
        return events
