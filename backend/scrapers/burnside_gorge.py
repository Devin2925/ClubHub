import hashlib
import html
import re
from datetime import datetime, timedelta

import requests

from scrapers.base import BaseScraper


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


class BurnsideGorgeScraper(BaseScraper):
    HEALTH_URL = "https://burnsidegorge.ca/health-and-wellness/"
    YOUTH_URL = "https://burnsidegorge.ca/youth-drop-in/"
    TENNIS_URL = "https://burnsidegorge.ca/kats-tennis/"

    def __init__(self):
        super().__init__("burnside_gorge", "Victoria")
        self.venue_name = "Burnside Gorge Community Centre"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _clean_text(self, value: str) -> str:
        value = re.sub(r"(?i)<br\s*/?>", "\n", value)
        value = re.sub(r"<[^>]+>", " ", value)
        return " ".join(html.unescape(value).split())

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

    def _nth_weekday_occurrences(
        self,
        weekday: int,
        ordinal: int,
        start_dt: datetime,
        end_dt: datetime,
        time_range: tuple[int, int, int, int],
    ) -> list[tuple[datetime, datetime]]:
        occurrences = []
        cursor = datetime(start_dt.year, start_dt.month, 1)
        while cursor <= end_dt:
            first = cursor
            offset = (weekday - first.weekday()) % 7
            day = 1 + offset + (ordinal - 1) * 7
            try:
                event_date = datetime(cursor.year, cursor.month, day)
            except ValueError:
                event_date = None
            if event_date and start_dt.date() <= event_date.date() <= end_dt.date():
                sh, sm, eh, em = time_range
                start_time = event_date.replace(hour=sh, minute=sm)
                end_time = event_date.replace(hour=eh, minute=em)
                occurrences.append((start_time, end_time))
            if cursor.month == 12:
                cursor = datetime(cursor.year + 1, 1, 1)
            else:
                cursor = datetime(cursor.year, cursor.month + 1, 1)
        return occurrences

    def _weekly_occurrences(
        self,
        weekday: int,
        start_dt: datetime,
        end_dt: datetime,
        time_range: tuple[int, int, int, int],
    ) -> list[tuple[datetime, datetime]]:
        occurrences = []
        cursor = start_dt
        while cursor.weekday() != weekday:
            cursor += timedelta(days=1)
        while cursor <= end_dt:
            sh, sm, eh, em = time_range
            start_time = cursor.replace(hour=sh, minute=sm)
            end_time = cursor.replace(hour=eh, minute=em)
            occurrences.append((start_time, end_time))
            cursor += timedelta(days=7)
        return occurrences

    def _range_to_dates(self, raw: str, weekday: int) -> tuple[datetime, datetime] | None:
        cleaned = raw.replace("–", "-").replace("—", "-")
        match = re.search(r"([A-Za-z]+)\s+(\d{1,2})\s*-\s*([A-Za-z]+)?\s*(\d{1,2})", cleaned)
        if not match:
            return None
        start_month = MONTH_MAP[match.group(1).lower()]
        start_day = int(match.group(2))
        end_month_name = match.group(3) or match.group(1)
        end_month = MONTH_MAP[end_month_name.lower()]
        end_day = int(match.group(4))
        year = datetime.utcnow().year
        start_dt = datetime(year, start_month, start_day)
        end_dt = datetime(year, end_month, end_day)
        if end_dt < start_dt:
            end_dt = datetime(year + 1, end_month, end_day)
        while start_dt.weekday() != weekday:
            start_dt += timedelta(days=1)
        while end_dt.weekday() != weekday:
            end_dt -= timedelta(days=1)
        return start_dt, end_dt

    def _build_event(self, title: str, start_time: datetime, end_time: datetime, description: str, booking_url: str) -> dict:
        source_key = f"{title}|{start_time.isoformat()}|{booking_url}"
        source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
        return {
            "source_id": f"{self.source_id_prefix}_{source_hash}",
            "title": title,
            "venue_name": self.venue_name,
            "facility_name": "",
            "start_time": start_time,
            "end_time": end_time,
            "price": "",
            "description": description,
            "booking_url": booking_url,
        }

    def _scrape_youth_drop_in(self) -> list[dict]:
        response = self.session.get(self.YOUTH_URL, timeout=30)
        response.raise_for_status()
        text = response.text
        match = re.search(
            r"<span[^>]*><strong>When:</strong></span>\s*Every\s+(\d)(?:st|nd|rd|th)\s+Thursday\s+of\s+the\s+Month\s+from\s+([\d:\.\sapm]+)\s*to\s*([\d:\.\sapm]+)",
            text,
            re.I,
        )
        if not match:
            return []
        ordinal = int(match.group(1))
        time_range = self._parse_time_range(f"{match.group(2)} - {match.group(3)}")
        if not time_range:
            return []
        now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = now + timedelta(days=180)
        description = (
            "Youth drop-in for ages 9 to 14. Free. No registration required. "
            "Hosted in the Youth Centre at Burnside Gorge Community Centre."
        )
        events = []
        for start_time, end_time in self._nth_weekday_occurrences(3, ordinal, now, end_dt, time_range):
            events.append(self._build_event("Youth Drop-In", start_time, end_time, description, self.YOUTH_URL))
        return events

    def _scrape_health_and_wellness(self) -> list[dict]:
        response = self.session.get(self.HEALTH_URL, timeout=30)
        response.raise_for_status()
        text = response.text
        pattern = re.compile(
            r"<p>\s*<(?:strong|b)>([^<]+)</(?:strong|b)>\s*</p>(.*?)<table>(.*?)</table>",
            re.S | re.I,
        )
        events = []
        for title, details_html, table_html in pattern.findall(text):
            title = self._clean_text(title)
            details = self._clean_text(details_html)
            rows = re.findall(r"<tr>(.*?)</tr>", table_html, re.S | re.I)
            for row in rows:
                cols = [self._clean_text(col) for col in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
                if len(cols) < 3:
                    continue
                weekday_name, date_range, time_raw = cols[:3]
                weekday = WEEKDAY_MAP.get(weekday_name.lower().rstrip("s"))
                time_range = self._parse_time_range(time_raw)
                if weekday is None or not time_range:
                    continue
                date_window = self._range_to_dates(date_range, weekday)
                if not date_window:
                    continue
                start_dt, end_dt = date_window
                price = cols[3] if len(cols) > 3 else ""
                description = details
                if price:
                    description = f"{description} Price: {price}".strip()
                for start_time, end_time in self._weekly_occurrences(weekday, start_dt, end_dt, time_range):
                    event = self._build_event(title, start_time, end_time, description, self.HEALTH_URL)
                    event["price"] = price
                    events.append(event)
        return events

    def _scrape_kats_tennis(self) -> list[dict]:
        response = self.session.get(self.TENNIS_URL, timeout=30)
        response.raise_for_status()
        text = response.text
        year = datetime.utcnow().year
        title_matches = list(
            re.finditer(
                r"<p><span[^>]*><b><u>(Tennis\s+\d+\s+[^\<]+)</u></b><br\s*/?>\s*</span></p>(.*?)(?=<p><b><u>|$)",
                text,
                re.S | re.I,
            )
        )
        events = []
        for match in title_matches:
            title = self._clean_text(match.group(1))
            block = match.group(2)
            time_match = re.search(r"Time:</b></u>\s*([\d:\.\sapm]+)\s*[–-]\s*([\d:\.\sapm]+)", block, re.I)
            if not time_match:
                continue
            time_range = self._parse_time_range(f"{time_match.group(1)} - {time_match.group(2)}")
            if not time_range:
                continue
            date_pairs = re.findall(r"<div>(?:<span[^>]*>)?([A-Za-z]+):\s*(?:</span>)?([^<]+)</div>", block, re.I)
            description = "Free KATS tennis lessons."
            for month_name, day_list in date_pairs:
                month_num = MONTH_MAP.get(month_name.lower())
                if not month_num:
                    continue
                for day_raw in day_list.split(","):
                    day_raw = day_raw.strip()
                    if not day_raw.isdigit():
                        continue
                    start_time = datetime(year, month_num, int(day_raw), time_range[0], time_range[1])
                    end_time = datetime(year, month_num, int(day_raw), time_range[2], time_range[3])
                    if start_time < datetime.utcnow() - timedelta(days=1):
                        continue
                    events.append(self._build_event(title, start_time, end_time, description, self.TENNIS_URL))
        return events

    def scrape(self):
        print(f"[{self.municipality}] Starting Burnside Gorge scrape...")
        try:
            events = []
            events.extend(self._scrape_health_and_wellness())
            events.extend(self._scrape_youth_drop_in())
            events.extend(self._scrape_kats_tennis())
        except Exception as exc:
            print(f"[{self.municipality}] Burnside Gorge scrape failed: {exc}")
            return []

        print(f"[{self.municipality}] Burnside Gorge normalized {len(events)} events.")
        self.save_events(events)
        return events
