"""Metro Vancouver drop-in sessions from ActiveNet online calendars.

One scraper for every city on ActiveNet's anc.ca.apm.activecommunities.com calendars
(Vancouver Park Board, Burnaby, Port Coquitlam, Langley City). Modelled on saanich.py
(same multicenter/events API), with these differences:

* Calendars and centres are read from the API (``rest/onlinecalendar/calendars`` and
  ``.../filters``) instead of hard-coded.
* ``event_item_id`` is the activity, not the session (one id can carry 90+ dates), so a
  session's source_id is the id plus its start time.
* Private lessons, rentals and closures are dropped by the rules in vancouver_common.py;
  the API has no flag for them (event_type is always 0).

Rows go to clubhub_vancouver.db (vancouver_db.py), never Victoria's clubhub.db.
"""
import json
import time
from datetime import datetime

import requests

from scrapers.vancouver_common import (
    VancouverScraper, classify, clean_name, clean_title, clean_venue, html_text, start_of_today,
)

CENTERS_PER_REQUEST = 10

# key → ActiveNet tenant (the path after activecommunities.com/) and municipality.
ACTIVENET_SOURCES = {
    "vancouver_activenet": {"tenant": "vancouver", "municipality": "Vancouver", "display_name": "Vancouver Park Board ActiveNet"},
    "burnaby_activenet": {"tenant": "burnaby", "municipality": "Burnaby", "display_name": "Burnaby ActiveNet"},
    "portcoquitlam_activenet": {"tenant": "cityofportcoquitlam", "municipality": "Port Coquitlam", "display_name": "Port Coquitlam ActiveNet"},
    "langleycity_activenet": {"tenant": "langleycityrecconnect", "municipality": "Langley City", "display_name": "Langley City ActiveNet"},
}


class ActiveNetCalendarScraper(VancouverScraper):
    def __init__(self, source_key: str, tenant: str, municipality: str, dry_run: bool = False, **_):
        super().__init__(source_id_prefix=source_key, municipality=municipality, dry_run=dry_run)
        self.tenant = tenant
        self.base_url = f"https://anc.ca.apm.activecommunities.com/{tenant}"
        self.calendar_page = f"{self.base_url}/calendars"
        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "Referer": self.calendar_page, "User-Agent": "Mozilla/5.0"}
        )

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
            f"{self.base_url}/rest/onlinecalendar/calendars?locale=en-US",
            headers={"page_info": json.dumps({"order_by": "Name", "page_number": 1, "total_records_per_page": 200})},
        )
        return [row for row in body.get("calendars") or [] if not row.get("hide_on_internet") and not row.get("retired")]

    def _center_ids(self, calendar_id: int) -> list[int]:
        body = self._request(
            "POST", f"{self.base_url}/rest/onlinecalendar/filters?locale=en-US", json={"calendar_id": calendar_id}
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
        body = self._request("POST", f"{self.base_url}/rest/onlinecalendar/multicenter/events?locale=en-US", json=payload)
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
        if end_time < start_of_today():
            return None

        facility = next((row for row in raw.get("facilities") or [] if isinstance(row, dict)), {})
        venue_name = clean_venue(facility.get("center_name")) or self.municipality
        facility_name = clean_name(facility.get("facility_name"))
        title = clean_title(raw.get("title") or "")
        description = html_text(raw.get("description"))

        price_info = raw.get("price") if isinstance(raw.get("price"), dict) else {}
        price = "Free" if price_info.get("free") else (price_info.get("estimate_price") or "")

        return {
            "source_id": f"{self.tenant}_{raw.get('event_item_id')}_{start_time:%Y%m%d%H%M}",
            "title": title,
            "venue_name": venue_name,
            "facility_name": facility_name if facility_name != venue_name else "",
            "center_id": facility.get("center_id"),
            "start_time": start_time,
            "end_time": end_time,
            "price": price,
            "description": description,
            "booking_url": raw.get("activity_detail_url") or self.calendar_page,
            **classify(title, facility_name, description, calendar_name),
        }

    def scrape(self):
        print(f"[{self.municipality}] Starting ActiveNet ({self.tenant}) scrape...")
        self.session.get(self.calendar_page, timeout=30).raise_for_status()

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
                    self.keep(self._normalize_event(raw, calendar_name))
                time.sleep(0.3)
        return self.finish()
