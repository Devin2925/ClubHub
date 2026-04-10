import hashlib
import re
from datetime import datetime, timedelta
from html import unescape
from urllib.parse import urljoin

import requests

from scrapers.base import BaseScraper, classify_sport, strip_html


LANDING_URL = "https://explore.wspr.ca/Westshore/public/category/browse/DROP_SPORTS"
BASE_URL = "https://explore.wspr.ca"
OUTDOOR_PICKLEBALL_URL = "https://explore.wspr.ca/Westshore/public/booking/items/PICKLEBALLCOURTSONLINE"


class WSPRScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="wspr", municipality="West Shore")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _fetch_sport_pages(self) -> list[str]:
        response = self.session.get(LANDING_URL, timeout=30)
        response.raise_for_status()
        text = response.text

        paths = sorted(
            set(
                re.findall(
                    r'/Westshore/public/category/browse/'
                    r'(?:drop-in_sports_[A-Za-z0-9_\-]+|dropin_sport_[A-Za-z0-9_\-]+|drop_sport_[A-Za-z0-9_\-]+)',
                    text,
                )
            )
        )
        return [urljoin(BASE_URL, path) for path in paths]

    def _extract_attr(self, block: str, name: str) -> str:
        match = re.search(rf"{name}='(.*?)'", block, re.S)
        return unescape(match.group(1)).strip() if match else ""

    def _clean_location_html(self, value: str) -> str:
        text = strip_html(value)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"(Location:|Venue:)", "", text)
        return text.strip(" -")

    def _parse_datetime_range(self, date_str: str, time_str: str) -> tuple[datetime, datetime]:
        start_str, end_str = [part.strip() for part in time_str.split("-", 1)]
        start_time = datetime.strptime(f"{date_str} {start_str}", "%a, %d-%b-%y %I:%M %p")
        end_time = datetime.strptime(f"{date_str} {end_str}", "%a, %d-%b-%y %I:%M %p")
        if end_time < start_time:
            end_time = end_time + timedelta(days=1)
        return start_time, end_time

    def _normalize_block(self, page_url: str, block: str) -> dict | None:
        title = self._extract_attr(block, "data-class-name")
        date_str = self._extract_attr(block, "data-class-date")
        time_str = self._extract_attr(block, "data-class-time")

        if not title or not date_str or not time_str:
            return None

        try:
            start_time, end_time = self._parse_datetime_range(date_str, time_str)
        except ValueError:
            return None

        description = self._extract_attr(block, "data-class-description")
        location = self._clean_location_html(self._extract_attr(block, "data-class-location"))
        venue = self._clean_location_html(self._extract_attr(block, "data-class-venue"))
        spaces = self._extract_attr(block, "data-class-spaces")

        raw_key = "|".join([title, date_str, time_str, venue, location])
        source_hash = hashlib.md5(raw_key.encode("utf-8")).hexdigest()[:16]

        return {
            "source_id": f"{self.source_id_prefix}_{source_hash}",
            "title": title,
            "sport_type": classify_sport(title),
            "venue_name": venue or "West Shore",
            "facility_name": location,
            "start_time": start_time,
            "end_time": end_time,
            "price": "",
            "description": strip_html(description),
            "booking_url": page_url,
            "source": self.source_id_prefix,
            "municipality": self.municipality,
        }

    def _normalize_outdoor_slot(
        self,
        page_url: str,
        date_str: str,
        time_str: str,
        court_name: str,
    ) -> dict | None:
        try:
            start_time, end_time = self._parse_datetime_range(date_str, time_str)
        except ValueError:
            return None

        title = "Outdoor Pickleball Drop-In"
        raw_key = "|".join([title, date_str, time_str, court_name])
        source_hash = hashlib.md5(raw_key.encode("utf-8")).hexdigest()[:16]

        return {
            "source_id": f"{self.source_id_prefix}_{source_hash}",
            "title": title,
            "sport_type": classify_sport(title),
            "venue_name": "Juan de Fuca Outdoor Facilities",
            "facility_name": court_name,
            "start_time": start_time,
            "end_time": end_time,
            "price": "",
            "description": "Outdoor pickleball drop-in only court availability.",
            "booking_url": page_url,
            "source": self.source_id_prefix,
            "municipality": self.municipality,
        }

    def _parse_page(self, page_url: str) -> list[dict]:
        response = self.session.get(page_url, timeout=30)
        response.raise_for_status()
        text = response.text

        blocks = re.findall(
            r"<button[^>]*data-bs-target='#classGridInfo'[^>]*>.*?</button>",
            text,
            re.S,
        )

        events = []
        for block in blocks:
            normalized = self._normalize_block(page_url, block)
            if normalized:
                events.append(normalized)
        return events

    def _extract_outdoor_date_range(self, text: str) -> list[str]:
        match = re.search(
            r'"minValue":"(\d{4}-\d{2}-\d{2})".*?"maxValue":"(\d{4}-\d{2}-\d{2})"',
            text,
            re.S,
        )
        if not match:
            return []

        start_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
        end_date = datetime.strptime(match.group(2), "%Y-%m-%d").date()
        days = []
        current = start_date
        while current <= end_date:
            days.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        return days

    def _extract_outdoor_slots_from_html(self, text: str, date_str: str) -> list[dict]:
        thead_match = re.search(r"<thead.*?</thead>", text, re.S)
        tbody_match = re.search(r"<tbody>(.*?)</tbody>", text, re.S)
        if not thead_match or not tbody_match:
            return []

        headers = re.findall(r"<th[^>]*>(.*?)</th>", thead_match.group(0), re.S)
        headers = [self._clean_location_html(header) for header in headers]
        court_headers = headers[1:]

        rows = re.findall(r"<tr>(.*?)</tr>", tbody_match.group(1), re.S)
        events = []

        for row in rows:
            time_match = re.search(r"<th[^>]*>(.*?)</th>", row, re.S)
            if not time_match:
                continue
            time_text = strip_html(time_match.group(1))
            time_text = re.sub(r"\s+", " ", time_text).strip()

            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            for court_name, cell in zip(court_headers, cells):
                if "drop in only" not in court_name.lower():
                    continue
                if "Available" not in cell:
                    continue
                start_clock = datetime.strptime(time_text, "%I:%M %p")
                end_clock = start_clock + timedelta(minutes=120)
                normalized = self._normalize_outdoor_slot(
                    OUTDOOR_PICKLEBALL_URL,
                    datetime.strptime(date_str, "%Y-%m-%d").strftime("%a, %d-%b-%y"),
                    f"{time_text} - {end_clock.strftime('%I:%M %p')}",
                    court_name,
                )
                if normalized:
                    events.append(normalized)

        return events

    def _parse_outdoor_pickleball(self) -> list[dict]:
        response = self.session.get(OUTDOOR_PICKLEBALL_URL, timeout=30)
        response.raise_for_status()
        text = response.text

        action_match = re.search(
            r'<form action="([^"]+/booking/checkavailability/[^"]+)"[^>]*method="post">',
            text,
            re.I,
        )
        token_match = re.search(
            r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"',
            text,
        )
        if not action_match or not token_match:
            return []

        action_url = urljoin(BASE_URL, action_match.group(1))
        token = token_match.group(1)
        dates = self._extract_outdoor_date_range(text)
        if not dates:
            return []

        all_events = []
        for date_str in dates:
            response = self.session.post(
                action_url,
                data={
                    "__RequestVerificationToken": token,
                    "StartDate": date_str,
                    "TimeRangeStart": "",
                    "TimeRangeEnd": "",
                    "Quantity": "1",
                    "Duration": "119",
                    "SortResultsBy": "Time",
                },
                timeout=30,
            )
            response.raise_for_status()
            all_events.extend(self._extract_outdoor_slots_from_html(response.text, date_str))

        return all_events

    def scrape(self):
        print(f"[{self.municipality}] Starting scrape...")
        try:
            pages = self._fetch_sport_pages()
        except Exception as exc:
            print(f"[{self.municipality}] Source discovery failed: {exc}")
            return []

        all_events = []
        seen_ids = set()

        for page_url in pages:
            try:
                page_events = self._parse_page(page_url)
            except Exception as exc:
                print(f"[{self.municipality}] Failed page {page_url}: {exc}")
                continue

            for event in page_events:
                if event["source_id"] in seen_ids:
                    continue
                seen_ids.add(event["source_id"])
                all_events.append(event)

        try:
            outdoor_events = self._parse_outdoor_pickleball()
        except Exception as exc:
            print(f"[{self.municipality}] Failed outdoor pickleball: {exc}")
            outdoor_events = []

        for event in outdoor_events:
            if event["source_id"] in seen_ids:
                continue
            seen_ids.add(event["source_id"])
            all_events.append(event)

        print(f"[{self.municipality}] Normalized {len(all_events)} events.")
        self.save_events(all_events)
        return all_events
