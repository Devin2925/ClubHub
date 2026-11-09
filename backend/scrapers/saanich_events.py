"""Saanich community events: the District's events calendar plus rec "Social - Events".

saanich.ca publishes its events calendar as an RSS feed, which mixes council and
committee meetings in with community events and only carries publish dates. Each
event page embeds the real times for its "add to calendar" button
(``var calendarEvent = { start: new Date(2026, 10, 22, 10, 0, 0), ... }``, months
from 0), and names the place in its text, which is matched to a rec centre.

The rec department also lists ticketed events (Storytime with Santa) in its
ActiveNet "Social - Events" category; market vendor-table rentals there are skipped.
"""
import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from scrapers.base import BaseScraper
from scrapers.event_utils import NOT_AN_EVENT, clean_text, event_row
from scrapers.saanich_camps import BASE as ACTIVENET_BASE, LIST_URL, SEARCH_PAGE, _venue as activenet_venue

RSS_URL = "https://www.saanich.ca/EN/main/news-events/events-list/data/events.rss"
EVENT_CATEGORY = re.compile(r"^social\s*-\s*events", re.I)
NOT_FOR_THE_PUBLIC = re.compile(r"\btable\b|vendor|volunteer", re.I)

# Places named in event text, mapped to the venue names ClubHub lists.
SAANICH_VENUES = [
    (re.compile(r"cedar hill rec", re.I), "Cedar Hill Recreation Centre"),
    (re.compile(r"pearkes", re.I), "G. R. Pearkes Recreation Centre"),
    (re.compile(r"commonwealth place", re.I), "Saanich Commonwealth Place"),
    (re.compile(r"gordon head rec", re.I), "Gordon Head Recreation Centre"),
    (re.compile(r"municipal hall", re.I), "Saanich Municipal Hall"),
    (re.compile(r"cenotaph", re.I), "Saanich Cenotaph"),
]

JS_DATE = re.compile(r"(start|end):\s*new Date\((\d{4}),\s*(\d{1,2}),\s*(\d{1,2}),\s*(\d{1,2}),\s*(\d{1,2})")


def _venue_from_text(text: str) -> str:
    # Prefer an explicit "Location:" line, then any place named on the page.
    location = re.search(r"Location:\s*([^.\n]{3,120})", text)
    for candidate in ([location.group(1)] if location else []) + [text]:
        for pattern, name in SAANICH_VENUES:
            if pattern.search(candidate):
                return name
    if location:
        return location.group(1).split(":")[0].split(",")[0].strip()
    return "Around Saanich"


class SaanichEventsScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="saanich_events", municipality="Saanich")
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
        )

    # --- saanich.ca events calendar -------------------------------------------------
    def _calendar_events(self) -> list[dict]:
        response = self.session.get(RSS_URL, timeout=30)
        response.raise_for_status()
        items = ET.fromstring(response.content).findall(".//item")
        events = []
        for item in items:
            title = clean_text(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            if not title or not link or NOT_AN_EVENT.search(title) or "council-committee" in link:
                continue
            if NOT_FOR_THE_PUBLIC.search(title):
                continue
            try:
                page = self.session.get(link, timeout=30)
                page.raise_for_status()
            except requests.RequestException as exc:
                print(f"[Saanich] Event page failed {link}: {exc}")
                continue
            times = {
                name: datetime(int(y), int(mo) + 1, int(d), int(h), int(mi))
                for name, y, mo, d, h, mi in JS_DATE.findall(page.text)
            }
            if "start" not in times:
                continue
            # The event's own heading; the page's first <h1> can be a site-wide banner.
            start_at = page.text.find('class="content-heading"')
            start_at = page.text.find(">", start_at) + 1 if start_at >= 0 else 0
            body = page.text[start_at : page.text.find("share_links-heading")]
            text = clean_text(body)
            # Drop the heading, "Date & Time" and "Category ... (See all events in this category)".
            description = re.sub(r"^.*?events in this category\s*\)?\s*", "", text, flags=re.I)
            description = re.sub(r"^Location:.{0,140}?(?:B\.C\.|\bBC\b)\s*", "", description)
            slug = re.sub(r"\.html$", "", link.rsplit("/", 1)[-1])
            events.append(
                event_row(
                    source_id=f"{self.source_id_prefix}_{slug}",
                    title=title,
                    venue_name=_venue_from_text(text),
                    start=times["start"],
                    end=times.get("end") or times["start"],
                    description=description,
                    url=link,
                )
            )
        return events

    # --- ActiveNet "Social - Events" ------------------------------------------------
    def _activenet_events(self) -> list[dict]:
        self.session.get(SEARCH_PAGE, timeout=30)
        filters = self.session.get(f"{ACTIVENET_BASE}/rest/activities/filters?locale=en-US", timeout=30).json()["body"]
        category_ids = [row["id"] for row in filters.get("categories") or [] if EVENT_CATEGORY.search(row.get("desc", ""))]
        if not category_ids:
            return []
        response = self.session.post(
            LIST_URL,
            json={
                "activity_search_pattern": {"activity_select_param": 2, "activity_category_ids": category_ids},
                "activity_transfer_pattern": {},
            },
            headers={
                "Referer": SEARCH_PAGE,
                "page_info": json.dumps({"order_by": "Date range", "page_number": 1, "total_records_per_page": 100}),
            },
            timeout=30,
        )
        response.raise_for_status()
        events = []
        for item in response.json()["body"]["activity_items"]:
            name = html.unescape(item.get("name") or "").strip(" *")
            day = item.get("date_range_start")
            clock = re.match(
                r"\s*(\d{1,2}:\d{2}\s*[AP]M|Noon)\s*-\s*(\d{1,2}:\d{2}\s*[AP]M|Noon)", item.get("time_range") or "", re.I
            )
            if not name or NOT_FOR_THE_PUBLIC.search(name) or not day or not clock:
                continue
            start_clock, end_clock = (("12:00 PM" if part.lower() == "noon" else part) for part in clock.groups())
            events.append(
                event_row(
                    source_id=f"{self.source_id_prefix}_an_{item['id']}",
                    title=name,
                    venue_name=activenet_venue((item.get("location") or {}).get("label", "")),
                    start=datetime.strptime(f"{day} {start_clock}", "%Y-%m-%d %I:%M %p"),
                    end=datetime.strptime(f"{item.get('date_range_end') or day} {end_clock}", "%Y-%m-%d %I:%M %p"),
                    description=item.get("desc") or "",
                    url=item.get("detail_url") or SEARCH_PAGE,
                )
            )
        return events

    def scrape(self):
        print("[Saanich] Starting Saanich community events scrape...")
        events = self._calendar_events()
        try:
            events += self._activenet_events()
        except (requests.RequestException, ValueError, KeyError) as exc:
            # The calendar half still stands; skip pruning so ActiveNet rows aren't dropped.
            print(f"[Saanich] ActiveNet events failed: {exc}")
            self.save_events(events)
            return events
        print(f"[Saanich] Saanich community events: {len(events)}.")
        self.save_events(events)
        self.prune_unseen_upcoming({event["source_id"] for event in events})
        return events
