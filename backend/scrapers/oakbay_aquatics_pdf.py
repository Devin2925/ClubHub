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
    {"title": "Early Bird Swim", "weekday": day, "time": "6:00-9:00am"} for day in DAY_TO_INDEX
] + [
    {"title": "Leisure and Lengths", "weekday": "Monday", "time": "9:00am-3:00pm"},
    {"title": "Leisure and Widths", "weekday": "Tuesday", "time": "10:30-11:30am"},
    {"title": "Leisure and Lengths", "weekday": "Tuesday", "time": "11:30am-1:30pm"},
    {"title": "50 & Better Swim", "weekday": "Tuesday", "time": "1:30-3:00pm"},
    {"title": "Adult Lengths", "weekday": "Tuesday", "time": "7:00-8:30pm"},
    {"title": "Leisure and Lengths", "weekday": "Tuesday", "time": "8:30-10:00pm"},
    {"title": "Leisure and Lengths", "weekday": "Wednesday", "time": "10:30am-3:00pm"},
    {"title": "Everyone Welcome Swim", "weekday": "Wednesday", "time": "3:00-5:00pm"},
    {"title": "Adult Lengths", "weekday": "Wednesday", "time": "5:00-6:30pm"},
    {"title": "Everyone Welcome Swim", "weekday": "Wednesday", "time": "6:30-8:30pm"},
    {"title": "Leisure and Lengths", "weekday": "Wednesday", "time": "8:30-10:00pm"},
    {"title": "Leisure and Widths", "weekday": "Thursday", "time": "10:30-11:30am"},
    {"title": "Leisure and Lengths", "weekday": "Thursday", "time": "11:30am-1:30pm"},
    {"title": "50 & Better Swim", "weekday": "Thursday", "time": "1:30-3:00pm"},
    {"title": "Adult Lengths", "weekday": "Thursday", "time": "7:00-8:30pm"},
    {"title": "Leisure and Lengths", "weekday": "Thursday", "time": "8:30-10:00pm"},
    {"title": "Leisure and Lengths", "weekday": "Friday", "time": "9:00am-1:00pm"},
    {"title": "Everyone Welcome Swim", "weekday": "Friday", "time": "3:00-5:00pm"},
    {"title": "Adult Lengths", "weekday": "Friday", "time": "5:00-6:30pm"},
    {"title": "Everyone Welcome Swim", "weekday": "Friday", "time": "6:30-8:30pm"},
    {"title": "Leisure and Lengths", "weekday": "Friday", "time": "8:30-10:00pm"},
    {"title": "Integrated Swim", "weekday": "Saturday", "time": "11:30am-1:00pm"},
    {"title": "Kids Fun Swim", "weekday": "Saturday", "time": "1:00-4:30pm"},
    {"title": "Adult Lengths", "weekday": "Saturday", "time": "4:30-6:30pm"},
    {"title": "Everyone Welcome Swim", "weekday": "Saturday", "time": "6:30-8:30pm"},
    {"title": "Leisure and Lengths", "weekday": "Saturday", "time": "8:30-10:00pm"},
    {"title": "Kids Fun Swim", "weekday": "Sunday", "time": "1:00-4:30pm"},
    {"title": "Adult Lengths", "weekday": "Sunday", "time": "4:30-6:30pm"},
    {"title": "Everyone Welcome Swim", "weekday": "Sunday", "time": "6:30-8:30pm"},
    {"title": "Leisure and Lengths", "weekday": "Sunday", "time": "8:30-10:00pm"},
    {"title": "Deep/Shallow Water Aquafit", "weekday": "Monday", "time": "7:45-8:45am"},
    {"title": "Shallow Water Aquafit", "weekday": "Monday", "time": "9:00-10:00am"},
    {"title": "Waterworks", "weekday": "Monday", "time": "10:00-11:00am"},
    {"title": "50 & Better Aquafit", "weekday": "Monday", "time": "11:15am-12:15pm"},
    {"title": "Shallow Water Aquafit", "weekday": "Monday", "time": "12:45-1:45pm"},
    {"title": "Deep Water Aquafit", "weekday": "Monday", "time": "7:00-8:00pm", "starts_on": "2026-04-06"},
    {"title": "Shallow Water Aquafit", "weekday": "Tuesday", "time": "7:45-8:45am"},
    {"title": "50 & Better Aquafit", "weekday": "Tuesday", "time": "1:45-2:45pm"},
    {"title": "Deep/Shallow Water Aquafit", "weekday": "Wednesday", "time": "7:45-8:45am"},
    {"title": "Waterworks", "weekday": "Wednesday", "time": "10:15-11:15am"},
    {"title": "50 & Better Aquafit", "weekday": "Wednesday", "time": "11:15am-12:15pm"},
    {"title": "Shallow Water Aquafit", "weekday": "Wednesday", "time": "12:45-1:45pm"},
    {"title": "Deep Water Aquafit", "weekday": "Wednesday", "time": "7:00-8:00pm", "starts_on": "2026-04-06"},
    {"title": "Shallow Water Aquafit", "weekday": "Thursday", "time": "7:45-8:45am"},
    {"title": "50 & Better Aquafit", "weekday": "Thursday", "time": "1:45-2:45pm"},
    {"title": "Shallow Water Aquafit", "weekday": "Friday", "time": "7:45-8:45am"},
    {"title": "Shallow Water Aquafit", "weekday": "Friday", "time": "9:00-10:00am"},
    {"title": "Waterworks", "weekday": "Friday", "time": "10:00-11:00am"},
    {"title": "50 & Better Aquafit", "weekday": "Friday", "time": "11:15am-12:15pm"},
    {"title": "Shallow Water Aquafit", "weekday": "Saturday", "time": "7:45-8:45am"},
    {"title": "Deep/Shallow Water Aquafit", "weekday": "Sunday", "time": "7:45-8:45am"},
]


class OakBayAquaticsPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__("oakbay_aquatics_pdf", "Oak Bay")
        self.venue_name = "Oak Bay Recreation Centre"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _discover_pdf_url(self) -> str:
        response = self.session.get(DROPIN_PAGE_URL, timeout=30)
        response.raise_for_status()
        matches = re.findall(r'https://www\.oakbay\.ca/wp-content/uploads/[^"\']+Aquatics-Drop-in-Schedule[^"\']+\.pdf', response.text, re.I)
        if not matches:
            raise ValueError("Could not find Oak Bay aquatics PDF")
        return matches[0]

    def _fetch_text(self, pdf_url: str) -> str:
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        return reader.pages[0].extract_text() or ""

    def _parse_window(self, text: str) -> tuple[date, date]:
        match = re.search(r"\((March|April|May|June)\s+(\d{1,2})\s*[–-]\s*(June|July|August|May)\s+(\d{1,2}),\s*(\d{4})\)", text)
        if not match:
            raise ValueError("Could not parse Oak Bay aquatics date window")
        start_month, start_day, end_month, end_day, year = match.groups()
        start = datetime.strptime(f"{start_month} {start_day} {year}", "%B %d %Y").date()
        end = datetime.strptime(f"{end_month} {end_day} {year}", "%B %d %Y").date()
        return start, end

    def _parse_time_range(self, raw: str) -> tuple[str, str]:
        compact = raw.replace(" ", "").lower()
        start_raw, end_raw = compact.split("-", 1)
        end_match = re.fullmatch(r"(\d{1,2}(?::\d{2})?)(am|pm)", end_raw)
        start_match = re.fullmatch(r"(\d{1,2}(?::\d{2})?)(am|pm)?", start_raw)
        if not start_match or not end_match:
            raise ValueError(f"Unparseable Oak Bay aquatics time: {raw}")
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
        print(f"[{self.municipality}] Starting Oak Bay aquatics PDF scrape...")
        try:
            pdf_url = self._discover_pdf_url()
            text = self._fetch_text(pdf_url)
            window_start, window_end = self._parse_window(text)
        except Exception as exc:
            print(f"[{self.municipality}] Oak Bay aquatics PDF scrape failed: {exc}")
            return []

        today = datetime.utcnow().date() - timedelta(days=1)
        events = []
        for row in ROW_CONFIGS:
            effective_start = max(window_start, today)
            if row.get("starts_on"):
                effective_start = max(effective_start, datetime.strptime(row["starts_on"], "%Y-%m-%d").date())
            for start_dt, end_dt in self._build_occurrences(
                row["weekday"],
                effective_start,
                window_end,
                self._parse_time_range(row["time"]),
            ):
                source_key = f"{self.venue_name}|{row['title']}|{start_dt.isoformat()}"
                source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
                events.append(
                    {
                        "source_id": f"{self.source_id_prefix}_{source_hash}",
                        "title": row["title"],
                        "venue_name": self.venue_name,
                        "facility_name": "Pool",
                        "start_time": start_dt,
                        "end_time": end_dt,
                        "price": "",
                        "description": "Oak Bay aquatics drop-in PDF schedule.",
                        "booking_url": pdf_url,
                    }
                )

        print(f"[{self.municipality}] Oak Bay aquatics PDF normalized {len(events)} events.")
        self.save_events(events)
        return events
