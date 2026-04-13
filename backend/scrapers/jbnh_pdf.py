import hashlib
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from io import BytesIO
from urllib.parse import urljoin

import requests
from pypdf import PdfReader

from scrapers.base import BaseScraper


PAGE_URL = "https://jamesbaynewhorizons.weebly.com/monthly-calendar.html"
DAY_NAMES = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]


class JBNHPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__("jbnh_pdf", "Victoria")
        self.venue_name = "James Bay New Horizons"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _discover_pdf_url(self) -> str:
        response = self.session.get(PAGE_URL, timeout=30)
        response.raise_for_status()
        match = re.search(r"/uploads/[^\"]+\.pdf", response.text)
        if not match:
            raise ValueError("Could not find James Bay New Horizons PDF")
        return urljoin(PAGE_URL, match.group(0))

    def _read_layout_pages(self, url: str) -> list[str]:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        return [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]

    def _parse_month_year(self, text: str) -> tuple[int, int]:
        match = re.search(r"([A-Z][a-z]+)\s+(\d{4})", text)
        if not match:
            raise ValueError("Could not parse JBNH month")
        month_name, year_str = match.groups()
        return datetime.strptime(month_name, "%B").month, int(year_str)

    def _boundaries(self, header_line: str) -> list[int]:
        positions = [header_line.index(day) for day in DAY_NAMES]
        boundaries = [0]
        for idx in range(len(positions) - 1):
            boundaries.append((positions[idx] + positions[idx + 1]) // 2)
        boundaries.append(len(header_line))
        return boundaries

    def _collect_lines_by_date(self, layout_pages: list[str], month: int, year: int) -> dict[date, list[str]]:
        items = defaultdict(list)
        for page_text in layout_pages:
            lines = page_text.splitlines()
            header_index = next((i for i, line in enumerate(lines) if "SUNDAY" in line and "SATURDAY" in line), None)
            if header_index is None:
                continue
            boundaries = self._boundaries(lines[header_index])
            current_dates: dict[int, date] = {}

            for raw_line in lines[header_index + 1 :]:
                if "CALENDAR IS SUBJECT" in raw_line:
                    break
                for idx in range(len(DAY_NAMES)):
                    segment = raw_line[boundaries[idx] : boundaries[idx + 1]].strip()
                    if not segment:
                        continue
                    match = re.match(r"^(\d{1,2})(?:\s+(.*))?$", segment)
                    if match:
                        day_number = int(match.group(1))
                        trailing = (match.group(2) or "").strip()
                        try:
                            current_dates[idx] = date(year, month, day_number)
                        except ValueError:
                            continue
                        if trailing:
                            items[current_dates[idx]].append(trailing)
                        continue
                    if idx in current_dates:
                        items[current_dates[idx]].append(segment)
        return items

    def _parse_start_time(self, raw: str) -> tuple[int, int]:
        hour, minute = raw.split(":")
        hour_int = int(hour)
        minute_int = int(minute)
        if hour_int < 8:
            hour_int += 12
        return hour_int, minute_int

    def _normalize_title(self, value: str) -> str:
        title = re.sub(r"\s+", " ", value).strip(" -")
        title = title.replace("w/ ", "with ")
        title = title.replace("  ", " ")
        return title

    def _parse_events_for_date(self, event_date: date, lines: list[str], booking_url: str) -> list[dict]:
        cleaned_lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in lines
            if line.strip()
        ]
        parsed = []
        current = None
        for line in cleaned_lines:
            if any(token in line for token in ["JAMES BAY NEW HORIZONS", "Phone 250", "www.jamesbaynewhorizons", "Legend:"]):
                continue
            if "Centre Closed" in line:
                continue

            match = re.match(r"^(\d{1,2}:\d{2})\s+(.*)$", line)
            if match:
                if current:
                    parsed.append(current)
                current = {"time": match.group(1), "title_parts": [match.group(2).strip()]}
                continue

            if current:
                current["title_parts"].append(line)

        if current:
            parsed.append(current)

        events = []
        for item in parsed:
            title = self._normalize_title(" ".join(item["title_parts"]))
            if not title:
                continue
            start_hour, start_minute = self._parse_start_time(item["time"])
            start_dt = datetime(event_date.year, event_date.month, event_date.day, start_hour, start_minute)
            end_dt = start_dt + timedelta(hours=1)
            source_key = f"{title}|{start_dt.isoformat()}|{booking_url}"
            source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
            events.append(
                {
                    "source_id": f"{self.source_id_prefix}_{source_hash}",
                    "title": title,
                    "venue_name": self.venue_name,
                    "facility_name": "",
                    "start_time": start_dt,
                    "end_time": end_dt,
                    "price": "",
                    "description": "James Bay New Horizons monthly calendar PDF. The source calendar lists start times only, so event duration defaults to 60 minutes.",
                    "booking_url": booking_url,
                }
            )
        return events

    def scrape(self):
        print(f"[{self.municipality}] Starting James Bay New Horizons PDF scrape...")
        try:
            pdf_url = self._discover_pdf_url()
            layout_pages = self._read_layout_pages(pdf_url)
            month, year = self._parse_month_year(layout_pages[0])
            lines_by_date = self._collect_lines_by_date(layout_pages, month, year)
        except Exception as exc:
            print(f"[{self.municipality}] James Bay New Horizons scrape failed: {exc}")
            return []

        events = []
        cutoff = datetime.utcnow() - timedelta(days=1)
        for event_date, lines in sorted(lines_by_date.items()):
            for event in self._parse_events_for_date(event_date, lines, pdf_url):
                if event["start_time"] < cutoff:
                    continue
                events.append(event)

        print(f"[{self.municipality}] James Bay New Horizons normalized {len(events)} events.")
        self.save_events(events)
        return events
