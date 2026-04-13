import hashlib
from datetime import datetime, timedelta

import requests

from scrapers.base import BaseScraper


class CalendarOnlineScraper(BaseScraper):
    def __init__(self, municipality: str, venue_name: str, capability_id: str):
        source_prefix = f"calendar_online_{capability_id[:12]}"
        super().__init__(source_prefix, municipality)
        self.venue_name = venue_name
        self.capability_id = capability_id
        self.calendar_url = "https://api.calendar.online/calendar"
        self.events_url = "https://api.calendar.online/event"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _fetch_calendar(self) -> dict:
        response = self.session.get(
            self.calendar_url,
            params={"capabilityId": self.capability_id},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _fetch_events(self, time_zone: str, start_dt: datetime, end_dt: datetime) -> list[dict]:
        response = self.session.get(
            self.events_url,
            params={
                "timeZone": time_zone,
                "startDate": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "endDate": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "capabilityId": self.capability_id,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _normalize_event(self, event: dict, subcalendar_map: dict[int, str], booking_url: str) -> dict | None:
        title = (event.get("title") or "").strip()
        if not title:
            return None

        try:
            start_time = datetime.strptime(event["start_date"], "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(event["end_date"], "%Y-%m-%d %H:%M:%S")
        except (KeyError, ValueError):
            return None

        if end_time <= start_time:
            return None

        facility_name = (event.get("where") or "").strip()
        description_parts = []
        if event.get("text"):
            description_parts.append(str(event["text"]).strip())
        if event.get("who"):
            description_parts.append(f"For: {str(event['who']).strip()}")
        if event.get("hasRegistration"):
            description_parts.append("Registration may be required.")
        sub_names = [
            subcalendar_map[sub_id]
            for sub_id in event.get("subCalendars", [])
            if sub_id in subcalendar_map
        ]
        if sub_names:
            description_parts.append(f"Calendar: {', '.join(sub_names)}")
        description = " ".join(part for part in description_parts if part)

        source_key = f"{self.capability_id}|{event.get('id')}|{event['start_date']}"
        source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]

        return {
            "source_id": f"{self.source_id_prefix}_{source_hash}",
            "title": title,
            "venue_name": self.venue_name,
            "facility_name": facility_name[:255],
            "start_time": start_time,
            "end_time": end_time,
            "price": "",
            "description": description[:4000],
            "booking_url": booking_url,
        }

    def scrape(self):
        print(f"[{self.municipality}] Starting Calendar.online scrape for {self.venue_name}...")
        try:
            calendar = self._fetch_calendar()
            time_zone = calendar.get("timeZone") or "America/Vancouver"
            booking_url = calendar.get("ics") or f"https://calendar.online/{self.capability_id}?iframe=true"
            subcalendar_map = {
                item["id"]: item.get("name", "")
                for item in calendar.get("subCalendars", [])
                if item.get("id")
            }
            start_dt = datetime.utcnow() - timedelta(days=1)
            end_dt = start_dt + timedelta(days=42)
            raw_events = self._fetch_events(time_zone, start_dt, end_dt)
        except Exception as exc:
            print(f"[{self.municipality}] Calendar.online scrape failed for {self.venue_name}: {exc}")
            return []

        events = []
        for raw_event in raw_events:
            normalized = self._normalize_event(raw_event, subcalendar_map, booking_url)
            if normalized:
                events.append(normalized)

        print(f"[{self.municipality}] Calendar.online normalized {len(events)} events for {self.venue_name}.")
        self.save_events(events)
        return events
