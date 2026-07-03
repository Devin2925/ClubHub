import hashlib
import re
from datetime import date, datetime, timedelta
from io import BytesIO

import requests
from pypdf import PdfReader

from scrapers.base import BaseScraper


PAGE_URL = "https://cookstreetvillageactivitycentre.com/calendar-and-programs"
DAY_NAMES = ["MONDAYS", "TUESDAYS", "WEDNESDAYS", "THURSDAYS", "FRIDAYS", "SATURDAYS"]
DAY_TO_INDEX = {
    "MONDAYS": 0,
    "TUESDAYS": 1,
    "WEDNESDAYS": 2,
    "THURSDAYS": 3,
    "FRIDAYS": 4,
    "SATURDAYS": 5,
}


class CookStreetPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__("cook_street_pdf", "Victoria")
        self.venue_name = "Cook Street Village Activity Centre"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _discover_urls(self) -> tuple[str, str]:
        response = self.session.get(PAGE_URL, timeout=30)
        response.raise_for_status()
        text = response.text
        urls = sorted(set(re.findall(r"https://storage\.googleapis\.com/[^\"]+", text)))

        calendar_url = ""
        guide_url = ""
        current = datetime.utcnow()
        current_label = current.strftime("%B %Y")
        for url in urls:
            if "Program Guide.pdf" in url:
                guide_url = url
            if f"{current_label}.pdf" in url:
                calendar_url = url

        if not calendar_url:
            for url in urls:
                if url.endswith(".pdf") and "Program Guide.pdf" not in url:
                    calendar_url = url
                    break

        if not calendar_url or not guide_url:
            raise ValueError("Could not discover Cook Street PDF URLs")
        return calendar_url, guide_url

    def _read_pdf_layout(self, url: str, page_index: int = 0) -> str:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        return reader.pages[page_index].extract_text(extraction_mode="layout") or ""

    def _parse_month_window(self, text: str) -> tuple[int, int, date, date]:
        match = re.search(r"([A-Z][a-z]+)\s+(\d{4})", text)
        if not match:
            raise ValueError("Could not parse Cook Street month")
        month_name, year_str = match.groups()
        month = datetime.strptime(month_name, "%B").month
        year = int(year_str)
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        return month, year, start_date, end_date

    def _boundaries(self, header_line: str) -> list[int]:
        positions = [header_line.index(day) for day in DAY_NAMES]
        boundaries = [0]
        for idx in range(len(positions) - 1):
            boundaries.append((positions[idx] + positions[idx + 1]) // 2)
        boundaries.append(len(header_line))
        return boundaries

    def _extract_columns(self, layout_text: str) -> dict[str, list[str]]:
        lines = layout_text.splitlines()
        header_index = next(i for i, line in enumerate(lines) if "MONDAYS" in line and "SATURDAYS" in line)
        boundaries = self._boundaries(lines[header_index])
        columns = {day: [] for day in DAY_NAMES}

        for raw_line in lines[header_index + 1 :]:
            if not raw_line.strip():
                continue
            for idx, day in enumerate(DAY_NAMES):
                segment = raw_line[boundaries[idx] : boundaries[idx + 1]].strip()
                if segment:
                    columns[day].append(" ".join(segment.split()))
        return columns

    def _is_time_line(self, value: str) -> bool:
        return bool(re.search(r"\d{1,2}:\d{2}\s*(?:am|pm)\s*[–-]\s*\d{1,2}:\d{2}\s*(?:am|pm)", value, re.I))

    def _parse_time_range(self, value: str) -> tuple[str, str] | None:
        cleaned = value.lower().replace("–", "-").replace("—", "-").replace(".", "")
        match = re.search(
            r"(\d{1,2}:\d{2})\s*(am|pm)\s*-\s*(\d{1,2}:\d{2})\s*(am|pm)",
            cleaned,
        )
        if not match:
            return None
        return f"{match.group(1)}{match.group(2)}", f"{match.group(3)}{match.group(4)}"

    def _normalize_title(self, value: str) -> str:
        title = value.replace("*New-", "").replace("*New –", "").replace("*New-", "")
        title = re.sub(r"\s+-\s+[RF]\b", "", title)
        title = title.replace("Pickle Ball", "Pickleball")
        title = re.sub(r"\s+", " ", title).strip(" -*")
        return title

    def _normalize_note(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _parse_entries(self, lines: list[str]) -> list[dict]:
        entries = []
        title_parts: list[str] = []
        note_parts: list[str] = []

        for line in lines:
            if self._is_time_line(line):
                time_range = self._parse_time_range(line)
                title = self._normalize_title(" ".join(title_parts))
                note = self._normalize_note(" ".join(note_parts))
                if title and time_range:
                    entries.append({"title": title, "note": note, "time_range": time_range})
                title_parts = []
                note_parts = []
                continue

            if line.startswith("*") or "April" in line or "Every Wednesday" in line:
                note_parts.append(line)
                continue

            title_parts.append(line)

        return entries

    def _weekday_dates(self, weekday_index: int, start_date: date, end_date: date) -> list[date]:
        cursor = start_date
        dates = []
        while cursor <= end_date:
            if cursor.weekday() == weekday_index:
                dates.append(cursor)
            cursor += timedelta(days=1)
        return dates

    def _dates_from_note(self, note: str, weekday_index: int, start_date: date, end_date: date) -> list[date]:
        if not note:
            return self._weekday_dates(weekday_index, start_date, end_date)

        explicit_days = [int(day) for day in re.findall(rf"{start_date.strftime('%B')}\s+(\d{{1,2}})", note, re.I)]
        if explicit_days:
            return [
                date(start_date.year, start_date.month, day)
                for day in explicit_days
                if start_date.day <= day <= end_date.day
            ]

        return self._weekday_dates(weekday_index, start_date, end_date)

    def _build_event(self, title: str, note: str, start_dt: datetime, end_dt: datetime, booking_url: str) -> dict:
        source_key = f"{title}|{start_dt.isoformat()}|{booking_url}"
        source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
        description = "Cook Street Village Activity Centre monthly PDF schedule."
        if note:
            description += f" {note}"
        return {
            "source_id": f"{self.source_id_prefix}_{source_hash}",
            "title": title,
            "venue_name": self.venue_name,
            "facility_name": "",
            "start_time": start_dt,
            "end_time": end_dt,
            "price": "",
            "description": description.strip(),
            "booking_url": booking_url,
        }

    def scrape(self):
        print(f"[{self.municipality}] Starting Cook Street PDF scrape...")
        try:
            calendar_url, _ = self._discover_urls()
            layout_text = self._read_pdf_layout(calendar_url, 0)
            _, _, start_date, end_date = self._parse_month_window(layout_text)
            columns = self._extract_columns(layout_text)
        except Exception as exc:
            print(f"[{self.municipality}] Cook Street scrape failed: {exc}")
            return []

        today = datetime.utcnow().date() - timedelta(days=1)
        events = []
        for day_name, lines in columns.items():
            weekday_index = DAY_TO_INDEX[day_name]
            for entry in self._parse_entries(lines):
                dates = self._dates_from_note(entry["note"], weekday_index, start_date, end_date)
                for event_date in dates:
                    if event_date < today:
                        continue
                    start_dt = datetime.strptime(
                        f"{event_date.isoformat()} {entry['time_range'][0]}",
                        "%Y-%m-%d %I:%M%p",
                    )
                    end_dt = datetime.strptime(
                        f"{event_date.isoformat()} {entry['time_range'][1]}",
                        "%Y-%m-%d %I:%M%p",
                    )
                    if end_dt <= start_dt:
                        end_dt += timedelta(days=1)
                    events.append(self._build_event(entry["title"], entry["note"], start_dt, end_dt, calendar_url))

        print(f"[{self.municipality}] Cook Street normalized {len(events)} events.")
        self.save_events(events)
        return events
