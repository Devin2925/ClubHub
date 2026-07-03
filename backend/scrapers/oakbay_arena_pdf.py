import hashlib
import re
from datetime import date, datetime, timedelta
from io import BytesIO

import requests
from pypdf import PdfReader

from scrapers.base import BaseScraper


DROPIN_PAGE_URL = "https://www.oakbay.ca/parks-recreation/programs-registration-services/drop-in-schedules/"
DAY_TO_INDEX = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}
ROW_CONFIGS = [
    {
        "title": "Adult Skate",
        "output_title": "Adult Skate",
        "weekday": "Tuesday",
        "time": "10:00-11:30am",
        "end_note": "(ends -May 12)",
    },
    {
        "title": "Adult Skate",
        "output_title": "Adult Skate",
        "weekday": "Thursday",
        "time": "10:00-11:30am",
        "end_note": "(ends -May 14)",
    },
    {
        "title": "Everyone Welcome",
        "output_title": "Everyone Welcome",
        "weekday": "Saturday",
        "time": "3:00-4:15pm",
        "end_note": "(ends -Aug 23)",
    },
]


class OakBayArenaPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__("oakbay_arena_pdf", "Oak Bay")
        self.venue_name = "Oak Bay Recreation Centre"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _discover_pdf_url(self) -> str:
        response = self.session.get(DROPIN_PAGE_URL, timeout=30)
        response.raise_for_status()
        matches = re.findall(r'https://www\.oakbay\.ca/wp-content/uploads/[^"\']+Arena-Drop-in-Schedule[^"\']+\.pdf', response.text, re.I)
        if not matches:
            raise ValueError("Could not find Oak Bay arena PDF")
        return matches[0]

    def _fetch_text(self, pdf_url: str) -> str:
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        return reader.pages[0].extract_text() or ""

    def _parse_window(self, text: str) -> tuple[date, date]:
        match = re.search(r"\((March|April|May|June)\s+(\d{1,2})\s*-\s*(June|July|August|May)\s+(\d{1,2}),\s*(\d{4})\)", text)
        if not match:
            raise ValueError("Could not parse Oak Bay arena date window")
        start_month, start_day, end_month, end_day, year = match.groups()
        start = datetime.strptime(f"{start_month} {start_day} {year}", "%B %d %Y").date()
        end = datetime.strptime(f"{end_month} {end_day} {year}", "%B %d %Y").date()
        return start, end

    def _parse_end_date(self, note: str, year: int) -> date:
        match = re.search(r"ends\s*-?([A-Za-z]+)\s+(\d{1,2})", note, re.I)
        if not match:
            raise ValueError(f"Could not parse Oak Bay arena end date: {note}")
        month_name, day = match.groups()
        for fmt in ("%B %d %Y", "%b %d %Y"):
            try:
                return datetime.strptime(f"{month_name} {day} {year}", fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Could not parse Oak Bay arena end date: {note}")

    def _parse_time_range(self, raw: str) -> tuple[str, str]:
        compact = raw.replace(" ", "").lower()
        start_raw, end_raw = compact.split("-", 1)
        end_match = re.fullmatch(r"(\d{1,2}(?::\d{2})?)(am|pm)", end_raw)
        start_match = re.fullmatch(r"(\d{1,2}(?::\d{2})?)(am|pm)?", start_raw)
        if not start_match or not end_match:
            raise ValueError(f"Unparseable Oak Bay arena time: {raw}")
        start_clock, start_meridiem = start_match.groups()
        end_clock, end_meridiem = end_match.groups()
        if not start_meridiem:
            start_meridiem = end_meridiem
        if ":" not in start_clock:
            start_clock = f"{start_clock}:00"
        if ":" not in end_clock:
            end_clock = f"{end_clock}:00"
        return f"{start_clock}{start_meridiem}", f"{end_clock}{end_meridiem}"

    def _build_occurrences(self, weekday: str, start_date: date, end_date: date, time_range: tuple[str, str]) -> list[tuple[datetime, datetime]]:
        weekday_index = DAY_TO_INDEX[weekday]
        current = start_date
        rows = []
        while current <= end_date:
            if current.weekday() == weekday_index:
                start_dt = datetime.strptime(f"{current.isoformat()} {time_range[0]}", "%Y-%m-%d %I:%M%p")
                end_dt = datetime.strptime(f"{current.isoformat()} {time_range[1]}", "%Y-%m-%d %I:%M%p")
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                rows.append((start_dt, end_dt))
            current += timedelta(days=1)
        return rows

    def scrape(self):
        print(f"[{self.municipality}] Starting Oak Bay arena PDF scrape...")
        try:
            pdf_url = self._discover_pdf_url()
            text = self._fetch_text(pdf_url)
            window_start, _ = self._parse_window(text)
            year = window_start.year
        except Exception as exc:
            print(f"[{self.municipality}] Oak Bay arena PDF scrape failed: {exc}")
            return []

        today = datetime.utcnow().date() - timedelta(days=1)
        events = []
        for row in ROW_CONFIGS:
            end_date = self._parse_end_date(row["end_note"], year)
            effective_start = max(window_start, today)
            for start_dt, end_dt in self._build_occurrences(
                row["weekday"],
                effective_start,
                end_date,
                self._parse_time_range(row["time"]),
            ):
                source_key = f"{self.venue_name}|{row['output_title']}|{start_dt.isoformat()}"
                source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
                events.append(
                    {
                        "source_id": f"{self.source_id_prefix}_{source_hash}",
                        "title": row["output_title"],
                        "venue_name": self.venue_name,
                        "facility_name": "Arena",
                        "start_time": start_dt,
                        "end_time": end_dt,
                        "price": "",
                        "description": "Oak Bay arena drop-in PDF schedule.",
                        "booking_url": pdf_url,
                    }
                )

        print(f"[{self.municipality}] Oak Bay arena PDF normalized {len(events)} events.")
        self.save_events(events)
        return events
