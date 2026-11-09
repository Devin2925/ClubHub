"""Metro Vancouver drop-in sessions from PerfectMind (BookMe4) widgets.

Coquitlam, North Vancouver (NVRC), New Westminster, White Rock, Richmond, Port Moody,
Maple Ridge and Delta all publish drop-ins as PerfectMind "Classes" calendars. This
scraper:

1. loads the widget's category list (same call as vancouver_discovery.py),
2. keeps the calendars whose group or name says drop-in ("Drop In", "Registered Visits",
   "Public Swim", "Schedules") and skips lessons, camps, rentals, staff and archived ones,
3. pages each calendar's ClassesV2 feed with ``after=<nextKey>`` (one page is ~10 days)
   until it runs out or passes HORIZON_DAYS, and
4. filters/saves through VancouverScraper (vancouver_common.py).

Victoria's scrapers/perfectmind.py is left alone; it reads only the first page.
"""
import re
import time
from datetime import datetime, timedelta
from urllib.parse import unquote, urljoin

import requests

from scrapers.vancouver_common import (
    VancouverScraper, classify, clean_name, clean_title, clean_venue, html_text, start_of_today,
)

PUBLIC_WIDGET = "15f6af07-39c5-473e-b053-96653f77a406"
HORIZON_DAYS = 56  # about what ActiveNet's calendars show
MAX_PAGES = 15

# A calendar is a drop-in schedule when its group or its own name says so.
PM_DROP_IN = re.compile(r"drop|registered visit|book a visit|public swim|schedules", re.I)
PM_NOT_DROP_IN = re.compile(
    r"^\W*z(?:z|\s)|do not use|discontinued|archive|lesson|prereq|private|staff|volunteer|rental|admin|camp|court",
    re.I,
)

PERFECTMIND_SOURCES = {
    "coquitlam_perfectmind": {"subdomain": "cityofcoquitlam", "municipality": "Coquitlam", "account_id": "23902", "widget_id": PUBLIC_WIDGET, "display_name": "Coquitlam PerfectMind"},
    "nvrc_perfectmind": {"subdomain": "nvrc", "municipality": "North Vancouver", "account_id": "23734", "widget_id": "a28b2c65-61af-407f-80d1-eaa58f30a94a", "display_name": "North Vancouver Recreation & Culture PerfectMind"},
    "newwestminster_perfectmind": {"subdomain": "cityofnewwestminster", "municipality": "New Westminster", "account_id": "23693", "widget_id": "50a33660-b4f7-44d9-9256-e10effec8641", "display_name": "New Westminster PerfectMind"},
    "whiterock_perfectmind": {"subdomain": "cityofwhiterock", "municipality": "White Rock", "account_id": "23697", "widget_id": PUBLIC_WIDGET, "display_name": "White Rock PerfectMind"},
    "richmond_perfectmind": {"subdomain": "richmondcity", "municipality": "Richmond", "account_id": "23650", "widget_id": PUBLIC_WIDGET, "display_name": "Richmond PerfectMind"},
    "portmoody_perfectmind": {"subdomain": "cityofportmoody", "municipality": "Port Moody", "account_id": None, "widget_id": PUBLIC_WIDGET, "display_name": "Port Moody PerfectMind"},
    "mapleridge_perfectmind": {"subdomain": "cityofmapleridge", "municipality": "Maple Ridge", "account_id": None, "widget_id": PUBLIC_WIDGET, "display_name": "Maple Ridge PerfectMind"},
    "delta_perfectmind": {"subdomain": "cityofdelta", "municipality": "Delta", "account_id": "24140", "widget_id": "0da93182-93fb-4314-87bd-a8ba4ee9a4c9", "display_name": "Delta PerfectMind"},
}

TOKEN = re.compile(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"')
CATEGORIES_URL = re.compile(r"categoriesUrl:\s*'([^']+)'")
VIEW_URL = re.compile(r"view:\s*\{\s*url:\s*'([^']+)'")
CALENDAR_ID = re.compile(r'id="calendarId" value="([^"]+)"')
WIDGET_ID = re.compile(r'id="widgetId" value="([^"]+)"')


class PerfectMindDropInScraper(VancouverScraper):
    def __init__(self, source_key: str, subdomain: str, municipality: str, widget_id: str,
                 account_id: str | None = None, dry_run: bool = False, **_):
        super().__init__(source_id_prefix=source_key, municipality=municipality, dry_run=dry_run)
        self.subdomain = subdomain
        self.base_url = f"https://{subdomain}.perfectmind.com"
        self.widget_id = widget_id
        self.account_id = account_id
        prefix = f"/{account_id}" if account_id else ""
        self.start_url = f"{self.base_url}{prefix}/Clients/BookMe4?widgetId={widget_id}"
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0"

    def _normalize_link(self, link: str) -> str:
        link = unquote(link.replace("&amp;", "&")).strip()
        return link.replace("widgetId=00000000-0000-0000-0000-000000000000", f"widgetId={self.widget_id}")

    def _calendars(self) -> list[tuple[str, str]]:
        """(label, Classes page url) for every drop-in calendar on the widget."""
        page = self.session.get(self.start_url, timeout=30)
        page.raise_for_status()
        token, categories_url = TOKEN.search(page.text), CATEGORIES_URL.search(page.text)
        if not token or not categories_url:
            raise RuntimeError(f"{self.subdomain}: widget page refused ({page.url[:120]})")
        groups = self.session.post(
            urljoin(page.url, categories_url.group(1)),
            headers={"X-Requested-With": "XMLHttpRequest", "RequestVerificationToken": token.group(1), "Referer": page.url},
            data={"__RequestVerificationToken": token.group(1)},
            timeout=30,
        ).json()

        calendars = []
        for group in groups:
            group_name = group.get("Name") or ""
            if PM_NOT_DROP_IN.search(group_name):
                continue
            for calendar in group.get("Calendars") or []:
                name = calendar.get("Name") or ""
                if PM_NOT_DROP_IN.search(name) or not (PM_DROP_IN.search(name) or PM_DROP_IN.search(group_name)):
                    continue
                link = calendar.get("BookingLink") or ""
                if link and "BookMe4BookingPages/Classes" not in link:
                    continue
                if link:
                    url = self._normalize_link(urljoin(self.base_url, link))
                elif self.account_id:
                    url = (
                        f"{self.base_url}/{self.account_id}/Clients/BookMe4BookingPages/Classes"
                        f"?calendarId={calendar['Id']}&widgetId={self.widget_id}&embed=False"
                    )
                else:
                    continue
                calendars.append((f"{clean_name(group_name)} / {clean_name(name)}", url))
        return calendars

    def _classes(self, page_url: str) -> list[dict]:
        """Every class occurrence on one calendar, paging ClassesV2 by nextKey."""
        html = self.session.get(page_url, timeout=30).text
        if "calendar is not allowed for the widget" in html.lower():
            return []
        view, calendar_id = VIEW_URL.search(html), CALENDAR_ID.search(html)
        if not view or not calendar_id:
            raise RuntimeError(f"no ClassesV2 feed on {page_url[:120]}")
        widget = WIDGET_ID.search(html)
        payload = {"calendarId": calendar_id.group(1), "widgetId": widget.group(1) if widget else self.widget_id}
        headers = {"X-Requested-With": "XMLHttpRequest", "Referer": page_url}
        horizon = (datetime.now() + timedelta(days=HORIZON_DAYS)).strftime("%Y-%m-%d")

        # ``after`` returns dates strictly after it and a page can end mid-day, so ask from
        # the day before the last page's final date; keep() drops the repeats.
        classes, after, last_key = [], None, ""
        for _ in range(MAX_PAGES):
            data = self.session.post(
                urljoin(page_url, view.group(1)),
                data={**payload, **({"after": after} if after else {})},
                headers=headers,
                timeout=30,
            ).json()
            if not isinstance(data, dict):
                raise ValueError(f"unexpected {type(data).__name__} from ClassesV2")
            batch = data.get("classes") or []
            classes.extend(batch)
            next_key = data.get("nextKey") or ""
            if not batch or next_key.startswith("0001") or next_key <= last_key or next_key > horizon:
                break
            last_key = next_key
            after = (datetime.strptime(next_key, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
            time.sleep(0.2)
        return classes

    def _normalize(self, row: dict, calendar_label: str, page_url: str) -> dict | None:
        date, start_text = row.get("OccurrenceDate") or "", row.get("FormattedStartTime") or ""
        try:
            start_time = datetime.strptime(f"{date} {start_text}", "%Y%m%d %I:%M %p")
        except ValueError:
            return None
        try:
            end_time = datetime.strptime(f"{date} {row.get('FormattedEndTime')}", "%Y%m%d %I:%M %p")
            if end_time <= start_time:
                raise ValueError
        except (ValueError, TypeError):
            end_time = start_time + timedelta(minutes=row.get("DurationInMinutes") or 60)
        if end_time < start_of_today():
            return None

        title = clean_title(row.get("EventName"))
        facility_name = clean_name(row.get("Facility"))
        venue_name = clean_venue(row.get("Location")) or self.municipality
        description = html_text(row.get("Details"))
        return {
            "source_id": f"{self.source_id_prefix}_{row.get('EventId')}_{start_time:%Y%m%d%H%M}_{re.sub(r'[^a-z0-9]+', '-', facility_name.lower()).strip('-')}",
            "title": title,
            "venue_name": venue_name,
            "facility_name": facility_name if facility_name != venue_name else "",
            "start_time": start_time,
            "end_time": end_time,
            "price": row.get("PriceRange") or "",
            "description": description,
            "booking_url": page_url,
            "availability": clean_name(row.get("Spots")) if isinstance(row.get("Spots"), str) else "",
            **classify(title, facility_name, description, calendar_label),
        }

    def scrape(self):
        print(f"[{self.municipality}] Starting PerfectMind ({self.subdomain}) scrape...")
        calendars = self._calendars()
        print(f"[{self.municipality}] {len(calendars)} drop-in calendars")
        for label, url in calendars:
            try:
                rows = self._classes(url)
            except (requests.RequestException, ValueError, RuntimeError) as exc:
                self.failures.append(f"{label}: {exc}")
                continue
            for row in rows:
                if row.get("EventId"):
                    self.keep(self._normalize(row, label, url))
        return self.finish()
