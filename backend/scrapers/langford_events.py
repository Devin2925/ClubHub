"""City of Langford community events from langford.ca/events (Modern Events Calendar).

The WordPress REST route /wp-json/wp/v2/mec-events lists the published events
(about a dozen at a time: craft fairs, markets, ceremonies, festivals) but not
their dates. Each event's page has:
  - schema.org Event JSON-LD: date, location name, description
  - an "Add to Google Calendar" link whose dates=...Z/...Z holds the exact UTC
    start and end, or dates=YYYYMMDD/YYYYMMDD for an all-day event
A repeating MEC event shows its next occurrence only, so it is saved once.
"""
import html
import json
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import unquote_plus
from zoneinfo import ZoneInfo

import requests

from scrapers.base import BaseScraper
from scrapers.drupal_calendar_events import USER_AGENT
from scrapers.event_utils import NOT_AN_EVENT, clean_text, event_row

LIST_URL = "https://langford.ca/wp-json/wp/v2/mec-events"
LOCAL = ZoneInfo("America/Vancouver")
LD_JSON = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
GCAL_DATES = re.compile(r"calendar\.google\.com/calendar/render\?[^\"']*?dates=([0-9TZ]+)(?:/|%2F)([0-9TZ]+)")

# Langford's places, spelled the way ClubHub lists them.
VENUE_ALIASES = [
    (re.compile(r"veterans memorial park", re.I), "Veterans Memorial Park"),
    (re.compile(r"city hall|877 goldstream", re.I), "Langford City Hall"),
    (re.compile(r"westhills arena|q cent(?:re|er)|juan de fuca|\bjdf\b", re.I), "Juan de Fuca Rec Centre"),
]


def _gcal_time(value: str) -> tuple[datetime, bool]:
    """A Google Calendar dates= value as a naive Pacific time, and whether it's a date only."""
    if "T" not in value:
        return datetime.strptime(value[:8], "%Y%m%d"), True
    moment = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return moment.astimezone(LOCAL).replace(tzinfo=None), False


def _event_ld(page: str) -> dict:
    for block in LD_JSON.findall(page):
        if '"startDate"' not in block:
            continue
        try:
            data = json.loads(block, strict=False)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Event":
            return data
    return {}


def _venue(location: str) -> str:
    for pattern, name in VENUE_ALIASES:
        if pattern.search(location):
            return name
    # "720 Station Avenue, Finest at Sea, Unit #113": the first part that is a name, not a
    # street address, unit or town; "103-814 Goldstream Avenue, Langford, BC" has none.
    parts = [
        re.sub(r"\s*\([^)]*$", "", part).strip()  # drop a "(Langford Branch" left unclosed by the site
        for part in re.split(r",(?![^()]*\))", location)
        if part.strip()
    ]
    named = [
        part
        for part in parts
        if not re.match(r"^[\d#]|^unit\b|^(?:langford|victoria|colwood|bc|b\.c\.|canada)$", part, re.I)
    ]
    return named[0] if named else "Around Langford"


class LangfordEventsScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="langford_events", municipality="West Shore")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _listed(self) -> list[dict]:
        items, page = [], 1
        while True:
            response = self.session.get(
                LIST_URL, params={"per_page": 100, "page": page, "_fields": "id,link,title"}, timeout=45
            )
            response.raise_for_status()
            items += response.json()
            if page >= int(response.headers.get("X-WP-TotalPages") or 1):
                return items
            page += 1

    def scrape(self):
        print("[Langford] Starting Langford events calendar scrape...")
        listed = self._listed()
        if not listed:
            raise RuntimeError("Langford events calendar listed no events")
        today = date.today()
        events = []
        for item in listed:
            title = clean_text(item.get("title", {}).get("rendered", ""))
            if not title or NOT_AN_EVENT.search(title):
                continue
            url = item["link"]
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
            except requests.RequestException as exc:
                print(f"[Langford] Event page failed {url}: {exc}")
                continue
            page = response.text
            ld = _event_ld(page)
            dates = GCAL_DATES.search(html.unescape(page))
            if dates:
                start, all_day = _gcal_time(dates.group(1))
                end, _ = _gcal_time(dates.group(2))
                if all_day and end > start:
                    end -= timedelta(days=1)  # Google's all-day end date is exclusive.
            elif ld.get("startDate"):
                start = datetime.fromisoformat(ld["startDate"][:10])
                end = datetime.fromisoformat((ld.get("endDate") or ld["startDate"])[:10])
                all_day = True
            else:
                print(f"[Langford] No date on {url}")
                continue
            if end.date() < today:
                continue
            location = clean_text(unquote_plus((ld.get("location") or {}).get("name") or ""))
            events.append(
                event_row(
                    source_id=f"{self.source_id_prefix}_{item['id']}",
                    title=title,
                    venue_name=_venue(location),
                    start=start,
                    end=end,
                    all_day=all_day,
                    description=ld.get("description") or "",
                    url=url,
                )
            )
        print(f"[Langford] Langford events: kept {len(events)} upcoming of {len(listed)} listed.")
        self.save_events(events)
        self.prune_unseen_upcoming({event["source_id"] for event in events})
        return events
