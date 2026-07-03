import hashlib
import html
import json
import re
from datetime import datetime, timedelta

import requests

from scrapers.base import BaseScraper, strip_html


WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

MONTH_MAP = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


class FernwoodScraper(BaseScraper):
    API_URL = "https://fernwoodnrg.ca/wp-json/wp/v2/ajde_events?per_page=100&_fields=id,date,title,link,content"

    def __init__(self):
        super().__init__("fernwood", "Victoria")
        self.venue_name = "Fernwood Community Centre"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _parse_time_range(self, raw: str) -> tuple[int, int, int, int] | None:
        cleaned = raw.lower().replace("–", "-").replace("—", "-").replace(".", "")
        match = re.search(
            r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*-\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
            cleaned,
        )
        if not match:
            return None
        start_hour = int(match.group(1)) % 12
        start_minute = int(match.group(2) or 0)
        start_meridiem = match.group(3) or match.group(6)
        if start_meridiem == "pm":
            start_hour += 12
        end_hour = int(match.group(4)) % 12
        end_minute = int(match.group(5) or 0)
        if match.group(6) == "pm":
            end_hour += 12
        return start_hour, start_minute, end_hour, end_minute

    def _build_event(self, title: str, start_time: datetime, end_time: datetime, description: str, booking_url: str, facility_name: str = "") -> dict:
        source_key = f"{title}|{start_time.isoformat()}|{booking_url}"
        source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
        return {
            "source_id": f"{self.source_id_prefix}_{source_hash}",
            "title": title,
            "venue_name": self.venue_name,
            "facility_name": facility_name,
            "start_time": start_time,
            "end_time": end_time,
            "price": "",
            "description": description,
            "booking_url": booking_url,
        }

    def _weekly_occurrences(self, weekday: int, start_dt: datetime, end_dt: datetime, time_range: tuple[int, int, int, int]) -> list[tuple[datetime, datetime]]:
        occurrences = []
        cursor = start_dt
        while cursor.weekday() != weekday:
            cursor += timedelta(days=1)
        while cursor <= end_dt:
            sh, sm, eh, em = time_range
            occurrences.append(
                (
                    cursor.replace(hour=sh, minute=sm),
                    cursor.replace(hour=eh, minute=em),
                )
            )
            cursor += timedelta(days=7)
        return occurrences

    def _parse_duration_window(self, raw: str) -> tuple[datetime, datetime] | None:
        cleaned = raw.replace("–", "-").replace("—", "-")
        match = re.search(r"([A-Za-z]+)\s*-\s*([A-Za-z]+)\s+(\d{4})", cleaned)
        if not match:
            return None
        start_month = MONTH_MAP[match.group(1).lower()]
        end_month = MONTH_MAP[match.group(2).lower()]
        year = int(match.group(3))
        start_dt = datetime(year, start_month, 1)
        if end_month == 12:
            end_dt = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_dt = datetime(year, end_month + 1, 1) - timedelta(days=1)
        return start_dt, end_dt

    def _parse_single_date(self, raw: str) -> datetime | None:
        cleaned = re.sub(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*", "", raw.strip(), flags=re.I)
        for fmt in ("%B %d, %Y", "%B %d %Y", "%B %d"):
            try:
                parsed = datetime.strptime(cleaned, fmt)
                if fmt == "%B %d":
                    parsed = parsed.replace(year=datetime.utcnow().year)
                return parsed
            except ValueError:
                continue
        return None

    def _extract_field(self, text: str, label: str) -> str:
        match = re.search(rf"{label}:\s*(.+?)(?=\s+[A-Z][a-z]+:|$)", text, re.I)
        return match.group(1).strip() if match else ""

    def _normalize_item(self, item: dict) -> list[dict]:
        title = html.unescape(item["title"]["rendered"]).strip()
        if not title or "closed" in title.lower():
            return []
        rendered = html.unescape(item["content"]["rendered"])
        description = " ".join(strip_html(rendered).split())
        date_field = self._extract_field(description, "Date")
        dates_field = self._extract_field(description, "Dates")
        duration_field = self._extract_field(description, "Duration")
        time_field = self._extract_field(description, "Time")
        where_field = self._extract_field(description, "Where") or self._extract_field(description, "Meeting Point")
        facility_name = where_field[:255]
        time_range = self._parse_time_range(time_field) if time_field else None
        if not time_range:
            return []

        events = []
        if dates_field and duration_field:
            weekday_name = dates_field.rstrip("s").lower()
            weekday = WEEKDAY_MAP.get(weekday_name)
            window = self._parse_duration_window(duration_field)
            if weekday is None or not window:
                return []
            start_dt, end_dt = window
            for start_time, end_time in self._weekly_occurrences(weekday, start_dt, end_dt, time_range):
                if start_time < datetime.utcnow() - timedelta(days=1):
                    continue
                events.append(self._build_event(title, start_time, end_time, description, item["link"], facility_name))
            return events

        if date_field:
            event_date = self._parse_single_date(date_field)
        else:
            event_date = self._parse_single_date(title)
        if not event_date:
            return []
        start_time = event_date.replace(hour=time_range[0], minute=time_range[1])
        end_time = event_date.replace(hour=time_range[2], minute=time_range[3])
        if start_time < datetime.utcnow() - timedelta(days=1):
            return []
        events.append(self._build_event(title, start_time, end_time, description, item["link"], facility_name))
        return events

    def scrape(self):
        print(f"[{self.municipality}] Starting Fernwood scrape...")
        try:
            response = self.session.get(self.API_URL, timeout=30)
            response.raise_for_status()
            items = response.json()
            events = []
            for item in items:
                events.extend(self._normalize_item(item))
        except Exception as exc:
            print(f"[{self.municipality}] Fernwood scrape failed: {exc}")
            return []

        print(f"[{self.municipality}] Fernwood normalized {len(events)} events.")
        self.save_events(events)
        return events
