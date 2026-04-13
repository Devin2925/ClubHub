import hashlib
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests

from scrapers.base import BaseScraper


class RecDeskCalendarScraper(BaseScraper):
    def __init__(
        self,
        municipality: str,
        venue_name: str,
        base_url: str,
        location_rules: list[dict] | None = None,
    ):
        source_prefix = f"recdesk_{re.sub(r'[^a-z0-9]+', '_', venue_name.lower()).strip('_')}"
        super().__init__(source_id_prefix=source_prefix, municipality=municipality)
        self.venue_name = venue_name
        self.base_url = base_url.rstrip("/")
        self.location_rules = location_rules or []
        self.calendar_url = f"{self.base_url}/Community/Calendar"
        self.events_url = urljoin(self.calendar_url, "/Community/Calendar/GetCalendarItems")
        self.item_url = urljoin(self.calendar_url, "/Community/Calendar/GetCalendarItem")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _bootstrap(self) -> str:
        response = self.session.get(self.calendar_url, timeout=30)
        response.raise_for_status()
        return response.text

    def _fetch_events(self, start_date: datetime, end_date: datetime) -> list[dict]:
        payload = {
            "facilityId": -1,
            "startDate": f"{start_date.month}/{start_date.day}/{start_date.year}",
            "endDate": f"{end_date.month}/{end_date.day}/{end_date.year}",
            "getChildren": "false",
            "SelectedView": "month",
            "SelectedMonth": str(start_date.month),
            "SelectedYear": str(start_date.year),
        }
        response = self.session.post(
            self.events_url,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.calendar_url,
            },
            data=json.dumps(payload),
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("Events", [])

    def _normalize_event(self, event: dict) -> dict | None:
        title = (event.get("EventName") or "").strip()
        if not title or "closed" in title.lower():
            return None

        start_iso = event.get("StartTimeISO8601")
        end_iso = event.get("EndTimeISO8601")
        if not start_iso or not end_iso:
            return None

        start_time = datetime.fromisoformat(start_iso.replace("Z", "+00:00")).replace(tzinfo=None)
        end_time = datetime.fromisoformat(end_iso.replace("Z", "+00:00")).replace(tzinfo=None)
        if end_time <= start_time:
            return None

        source_key = f"{self.venue_name}|{event.get('EventId')}|{start_iso}"
        source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]

        description = (event.get("Description") or "").strip()
        booking_url = self.calendar_url
        municipality = self.municipality
        venue_name = self.venue_name

        for rule in self.location_rules:
            if re.search(rule["pattern"], title, flags=re.I):
                municipality = rule.get("municipality", municipality)
                venue_name = rule.get("venue_name", venue_name)
                break

        return {
            "source_id": f"{self.source_id_prefix}_{source_hash}",
            "title": title,
            "venue_name": venue_name,
            "facility_name": event.get("FacilityName") or "",
            "start_time": start_time,
            "end_time": end_time,
            "price": "",
            "description": description,
            "booking_url": booking_url,
            "municipality": municipality,
        }

    def scrape(self):
        print(f"[{self.municipality}] Starting RecDesk calendar scrape for {self.venue_name}...")
        try:
            self._bootstrap()
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=42)
            raw_events = self._fetch_events(start_date, end_date)
        except Exception as exc:
            print(f"[{self.municipality}] RecDesk scrape failed for {self.venue_name}: {exc}")
            return []

        normalized = []
        for event in raw_events:
            item = self._normalize_event(event)
            if item:
                normalized.append(item)

        print(f"[{self.municipality}] RecDesk normalized {len(normalized)} events for {self.venue_name}.")
        self.save_events(normalized)
        return normalized
