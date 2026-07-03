import hashlib
import re
from datetime import date, datetime, timedelta
from io import BytesIO
from urllib.parse import urljoin

import requests
from pypdf import PdfReader

from models import Event, SessionLocal
from scrapers.base import BaseScraper


PAGE_URL = "https://www.saanich.ca/EN/main/parks-recreation-community/recreation/schedules/swimming.html"
VENUE_NAME = "Saanich Commonwealth Place"
DAY_ORDER = ["MON", "TUES", "WED", "THURS", "FRI", "SAT", "SUN"]
TIME_RANGE_RE = re.compile(
    r"\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*-\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)",
    re.I,
)
SWIM_ROW_CONFIGS = [
    {"title": "Leisure Swims", "y_low": 120, "y_high": 145},
    {"title": "Fun Swims", "y_low": 160, "y_high": 185},
    {"title": "Open Swims", "y_low": 200, "y_high": 220},
    {"title": "Water Slide", "y_low": 220, "y_high": 255},
    {"title": "Lessons & Leisure", "y_low": 270, "y_high": 305},
]
LENGTH_ROW_CONFIGS = [
    {"title": "25m Short Course Lengths", "y_low": 170, "y_high": 210},
    {"title": "50m Long Course Lengths", "y_low": 235, "y_high": 290},
    {"title": "Teach Pool Lengths", "y_low": 340, "y_high": 380},
    {"title": "Shallow Water Walking", "y_low": 405, "y_high": 445},
    {"title": "Dive Tank Lengths", "y_low": 470, "y_high": 520},
    {"title": "Deep Water Walking", "y_low": 530, "y_high": 565},
]


class SaanichCommonwealthSwimmingPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__("saanich_commonwealth_swimming_pdf", "Saanich")
        self.venue_name = VENUE_NAME
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.last_reported_count = 0

    def _discover_pdf_urls(self) -> list[str]:
        response = self.session.get(PAGE_URL, timeout=30)
        response.raise_for_status()
        links = re.findall(r'href="([^"]+\.pdf)"', response.text, re.I)
        pdfs = []
        for link in links:
            absolute = urljoin(PAGE_URL, link)
            lowered = absolute.lower()
            if "/commonwealth_place/" not in lowered:
                continue
            if (
                "swim%20schedule" not in lowered
                and "lengths%20schedule" not in lowered
                and "swim schedule" not in lowered
                and "lengths schedule" not in lowered
            ):
                continue
            pdfs.append(absolute)
        return sorted(set(pdfs))

    def _read_pdf(self, pdf_url: str) -> tuple[str, list[tuple[float, float, str]]]:
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        page = reader.pages[0]
        plain_text = page.extract_text() or ""
        items: list[tuple[float, float, str]] = []

        def visitor(text, cm, tm, font_dict, font_size):
            token = text.strip()
            if token:
                items.append((round(tm[4], 1), round(tm[5], 1), token))

        page.extract_text(visitor_text=visitor)
        return plain_text, items

    def _parse_week_start(self, plain_text: str, pdf_url: str) -> date:
        match = re.search(r"([A-Z][a-z]+)\s+(\d{1,2})\s*-\s*(\d{1,2})", plain_text)
        if not match:
            match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\D+(\d{1,2})-(\d{1,2})", pdf_url, re.I)
        if not match:
            raise ValueError(f"Could not parse Commonwealth week window from {pdf_url}")

        month_name, start_day, _ = match.groups()
        current_year = datetime.utcnow().year
        return datetime.strptime(f"{month_name} {start_day} {current_year}", "%B %d %Y").date()

    def _day_columns(self, items: list[tuple[float, float, str]]) -> list[tuple[str, float]]:
        day_positions = []
        for x, y, text in items:
            compact = " ".join(text.split())
            match = re.fullmatch(r"(MON|TUES|WED|THURS|FRI|SAT|SUN)\s+\d{1,2}", compact)
            if match:
                day_positions.append((match.group(1), x))

        by_day = {day: x for day, x in day_positions}
        return [(day, by_day[day]) for day in DAY_ORDER if day in by_day]

    def _column_ranges(self, day_columns: list[tuple[str, float]]) -> dict[str, tuple[float, float]]:
        ranges: dict[str, tuple[float, float]] = {}
        xs = [x for _, x in day_columns]
        for index, (day, x) in enumerate(day_columns):
            left = (xs[index - 1] + x) / 2 if index > 0 else x - 40
            right = (x + xs[index + 1]) / 2 if index < len(xs) - 1 else x + 60
            ranges[day] = (left, right)
        return ranges

    def _times_for_band(
        self,
        items: list[tuple[float, float, str]],
        y_low: float,
        y_high: float,
        column_ranges: dict[str, tuple[float, float]],
    ) -> dict[str, list[str]]:
        day_times: dict[str, list[str]] = {}
        for day, (left, right) in column_ranges.items():
            fragments = [
                (y, x, text)
                for x, y, text in items
                if y_low <= y <= y_high and left <= x < right
            ]
            fragments.sort(key=lambda row: (-row[0], row[1]))
            combined = " ".join(text for _, _, text in fragments)
            matches = [re.sub(r"\s+", "", value.lower()) for value in TIME_RANGE_RE.findall(combined)]
            if matches:
                day_times[day] = matches
        return day_times

    def _parse_time_range(self, value: str) -> tuple[str, str]:
        compact = value.replace(" ", "").lower()
        start_raw, end_raw = compact.split("-", 1)
        start_match = re.fullmatch(r"(\d{1,2}(?::\d{2})?)(am|pm)", start_raw)
        end_match = re.fullmatch(r"(\d{1,2}(?::\d{2})?)(am|pm)", end_raw)
        if not start_match or not end_match:
            raise ValueError(f"Unparseable time range: {value}")
        start_clock, start_meridiem = start_match.groups()
        end_clock, end_meridiem = end_match.groups()
        if ":" not in start_clock:
            start_clock = f"{start_clock}:00"
        if ":" not in end_clock:
            end_clock = f"{end_clock}:00"
        return f"{start_clock}{start_meridiem}", f"{end_clock}{end_meridiem}"

    def _existing_keys(self, start_date: date, end_date: date) -> set[tuple[str, str, str]]:
        db = SessionLocal()
        try:
            rows = (
                db.query(Event)
                .filter(Event.venue_name == self.venue_name)
                .filter(Event.start_time >= datetime.combine(start_date, datetime.min.time()))
                .filter(Event.start_time < datetime.combine(end_date + timedelta(days=1), datetime.min.time()))
                .all()
            )
            return {
                (
                    row.venue_name,
                    row.title,
                    row.start_time.replace(microsecond=0).isoformat(sep=" "),
                )
                for row in rows
            }
        finally:
            db.close()

    def _append_missing_event(
        self,
        events: list[dict],
        existing_keys: set[tuple[str, str, str]],
        reported_keys: set[tuple[str, str, str]],
        *,
        title: str,
        start_dt: datetime,
        end_dt: datetime,
        pdf_url: str,
        description: str,
    ):
        existing_key = (
            self.venue_name,
            title,
            start_dt.replace(microsecond=0).isoformat(sep=" "),
        )
        reported_keys.add(existing_key)
        if existing_key in existing_keys:
            return

        source_key = f"{self.venue_name}|{title}|{start_dt.isoformat()}|{pdf_url}"
        source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
        events.append(
            {
                "source_id": f"{self.source_id_prefix}_{source_hash}",
                "title": title,
                "venue_name": self.venue_name,
                "facility_name": "Pool",
                "start_time": start_dt,
                "end_time": end_dt,
                "price": "",
                "description": description,
                "booking_url": pdf_url,
            }
        )
        existing_keys.add(existing_key)

    def _events_from_pdf(
        self,
        pdf_url: str,
        row_configs: list[dict],
        description: str,
        events: list[dict],
        existing_keys: set[tuple[str, str, str]],
        reported_keys: set[tuple[str, str, str]],
    ):
        plain_text, items = self._read_pdf(pdf_url)
        week_start = self._parse_week_start(plain_text, pdf_url)
        day_columns = self._day_columns(items)
        if len(day_columns) != 7:
            raise ValueError(f"Could not detect all Commonwealth day columns in {pdf_url}")

        column_ranges = self._column_ranges(day_columns)
        for row in row_configs:
            day_times = self._times_for_band(items, row["y_low"], row["y_high"], column_ranges)
            for index, day in enumerate(DAY_ORDER):
                event_date = week_start + timedelta(days=index)
                if event_date < datetime.utcnow().date():
                    continue
                for time_range in day_times.get(day, []):
                    start_raw, end_raw = self._parse_time_range(time_range)
                    start_dt = datetime.strptime(f"{event_date.isoformat()} {start_raw}", "%Y-%m-%d %I:%M%p")
                    end_dt = datetime.strptime(f"{event_date.isoformat()} {end_raw}", "%Y-%m-%d %I:%M%p")
                    if end_dt <= start_dt:
                        end_dt += timedelta(days=1)
                    self._append_missing_event(
                        events,
                        existing_keys,
                        reported_keys,
                        title=row["title"],
                        start_dt=start_dt,
                        end_dt=end_dt,
                        pdf_url=pdf_url,
                        description=description,
                    )

    def scrape(self):
        print(f"[{self.municipality}] Starting Commonwealth swimming PDF scrape...")
        pdf_urls = self._discover_pdf_urls()
        if not pdf_urls:
            raise ValueError("Could not find Commonwealth swimming PDFs")

        week_starts = []
        for pdf_url in pdf_urls:
            plain_text, _ = self._read_pdf(pdf_url)
            week_starts.append(self._parse_week_start(plain_text, pdf_url))
        start_date = min(week_starts)
        end_date = max(week_starts) + timedelta(days=6)
        existing_keys = self._existing_keys(start_date, end_date)

        events: list[dict] = []
        reported_keys: set[tuple[str, str, str]] = set()
        for pdf_url in pdf_urls:
            lowered = pdf_url.lower()
            if "lengths%20schedule" in lowered or "lengths schedule" in lowered:
                self._events_from_pdf(
                    pdf_url,
                    LENGTH_ROW_CONFIGS,
                    "Saanich Commonwealth public lengths schedule PDF.",
                    events,
                    existing_keys,
                    reported_keys,
                )
            elif "swim%20schedule" in lowered or "swim schedule" in lowered:
                self._events_from_pdf(
                    pdf_url,
                    SWIM_ROW_CONFIGS,
                    "Saanich Commonwealth public swim schedule PDF.",
                    events,
                    existing_keys,
                    reported_keys,
                )

        self.last_reported_count = len(reported_keys)
        print(
            f"[{self.municipality}] Commonwealth swimming PDF recognized {self.last_reported_count} rows, "
            f"adding {len(events)} missing events."
        )
        self.save_events(events)
        return events
