import hashlib
import re
from datetime import datetime, timedelta
from html import unescape
from urllib.parse import urljoin

import requests

from scrapers.base import BaseScraper, classify_sport, strip_html


LANDING_URL = "https://explore.wspr.ca/Westshore/public/category/browse/dropin"
BASE_URL = "https://explore.wspr.ca"
OUTDOOR_PICKLEBALL_URL = "https://explore.wspr.ca/Westshore/public/booking/items/PICKLEBALLCOURTSONLINE"
WEEK_RANGE_WEEKS = 10
SCHEDULE_WINDOW_DAYS = 30
SCHEDULE_WINDOW_COUNT = 3


class WSPRScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="wspr", municipality="West Shore")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _discover_schedule_pages(self) -> list[str]:
        queue = [LANDING_URL]
        visited = set()
        pages_with_data = set()

        while queue:
            page_url = queue.pop(0)
            if page_url in visited:
                continue
            visited.add(page_url)

            response = self.session.get(page_url, timeout=30)
            if response.status_code == 404 or "Error/PageNotFound" in response.url:
                continue
            response.raise_for_status()
            text = response.text

            if (
                "data-class-name=" in text
                or 'action="/Westshore/public/category/ClassGrid"' in text
                or 'action="/Westshore/public/category/ClassSchedule"' in text
            ):
                pages_with_data.add(page_url)

            paths = set(
                re.findall(
                    r'/Westshore/public/category/browse/[A-Za-z0-9_\-]+',
                    text,
                )
            )

            for path in paths:
                lowered = path.lower()
                if any(skip in lowered for skip in ("programs", "rates_passes", "explore_facilities", "fac_")):
                    continue
                absolute = urljoin(BASE_URL, path)
                if absolute not in visited and absolute not in queue:
                    queue.append(absolute)

        return sorted(pages_with_data)

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

    def _normalize_schedule_card(
        self,
        page_url: str,
        *,
        title: str,
        date_str: str,
        time_str: str,
        venue: str,
        location: str,
        description: str,
        spaces: str,
    ) -> dict | None:
        cleaned_time = re.sub(r"\s+", " ", time_str.strip())
        if " - " not in cleaned_time:
            return None

        try:
            start_time, end_time = self._parse_datetime_range(date_str.strip(), cleaned_time)
        except ValueError:
            return None

        venue_name = venue or "Juan de Fuca Rec Centre"
        raw_key = "|".join([title, date_str, cleaned_time, venue_name, location])
        source_hash = hashlib.md5(raw_key.encode("utf-8")).hexdigest()[:16]

        description = description.strip()
        if spaces:
            description = f"{description} Spaces: {spaces}".strip()

        return {
            "source_id": f"{self.source_id_prefix}_{source_hash}",
            "title": title,
            "sport_type": classify_sport(title),
            "venue_name": venue_name,
            "facility_name": location,
            "start_time": start_time,
            "end_time": end_time,
            "price": "",
            "description": description,
            "booking_url": page_url,
            "source": self.source_id_prefix,
            "municipality": self.municipality,
        }

    def _parse_classschedule_cards(self, page_url: str, text: str) -> list[dict]:
        start_index = text.find('classTimetableSchedule">')
        end_index = text.find('<div class="modal fade" id="MoreInfoModal"')
        if start_index == -1 or end_index == -1 or end_index <= start_index:
            return []

        section = text[start_index:end_index]
        card_blocks = re.findall(r'<div class="card mb-4">(.*?)</div>\s*</div>', section, re.S)
        events = []

        for block in card_blocks:
            if "<h4>" not in block:
                continue

            title_match = re.search(r"<h4>(.*?)</h4>", block, re.S)
            date_match = re.search(r"Date:\s*</span>\s*(.*?)\s*</p>", block, re.S)
            time_match = re.search(r"Time:\s*</span>\s*(.*?)\s*(?:<span|</p>)", block, re.S)
            location_match = re.search(r'd-location.*?Location:\s*</span>\s*(.*?)\s*</p>', block, re.S)
            venue_match = re.search(r'd-venue.*?Venue:\s*</span>(.*?)</p>', block, re.S)
            spaces_match = re.search(r"Spaces:\s*</span>\s*(.*?)\s*</p>", block, re.S)
            description_match = re.search(r'data-class-description="(.*?)"', block, re.S)

            title = strip_html(title_match.group(1)) if title_match else ""
            date_str = strip_html(date_match.group(1)) if date_match else ""
            time_str = strip_html(time_match.group(1)) if time_match else ""
            location = strip_html(location_match.group(1)) if location_match else ""
            spaces = strip_html(spaces_match.group(1)) if spaces_match else ""
            description = unescape(description_match.group(1)).replace("\r", " ").replace("\n", " ").strip() if description_match else ""

            venue = ""
            if venue_match:
                venue = strip_html(re.sub(r"<a.*?</a>", " ", venue_match.group(1), flags=re.S))

            normalized = self._normalize_schedule_card(
                page_url,
                title=title,
                date_str=date_str,
                time_str=time_str,
                venue=venue,
                location=location,
                description=description,
                spaces=spaces,
            )
            if normalized:
                events.append(normalized)

        return events

    def _fetch_classschedule_result_pages(self, text: str) -> list[str]:
        pages = [text]
        seen_urls = set()

        for match in re.findall(r'href="(/Westshore/public/Category/ClassSchedule[^"#]+)#results"', text, re.I):
            absolute = urljoin(BASE_URL, match)
            if absolute in seen_urls:
                continue
            seen_urls.add(absolute)
            response = self.session.get(absolute, timeout=30)
            response.raise_for_status()
            pages.append(response.text)

        return pages

    def _parse_classschedule_page(self, page_url: str) -> list[dict]:
        response = self.session.get(page_url, timeout=30)
        response.raise_for_status()
        text = response.text

        if 'action="/Westshore/public/category/ClassSchedule"' not in text:
            return []

        token = self._extract_first(
            text,
            r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',
        )
        start_date = self._extract_first(
            text,
            r'name="StartDate"[^>]*value="([^"]+)"',
        )
        category_guid = self._extract_first(
            text,
            r'name="CategoryGUID"[^>]*value="([^"]+)"',
        )

        if not token or not start_date or not category_guid:
            return []

        try:
            base_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            return []

        events = []
        seen_ids = set()

        for window_index in range(SCHEDULE_WINDOW_COUNT):
            window_start = base_start + timedelta(days=SCHEDULE_WINDOW_DAYS * window_index)
            window_end = window_start + timedelta(days=SCHEDULE_WINDOW_DAYS)
            schedule_response = self.session.post(
                urljoin(BASE_URL, "/Westshore/public/category/ClassSchedule"),
                data={
                    "__RequestVerificationToken": token,
                    "StartDate": window_start.isoformat(),
                    "EndDate": window_end.isoformat(),
                    "CategoryGUID": category_guid,
                },
                timeout=30,
            )
            schedule_response.raise_for_status()

            for page_text in self._fetch_classschedule_result_pages(schedule_response.text):
                for normalized in self._parse_classschedule_cards(page_url, page_text):
                    if normalized["start_time"] < datetime.now() - timedelta(days=1):
                        continue
                    if normalized["source_id"] in seen_ids:
                        continue
                    seen_ids.add(normalized["source_id"])
                    events.append(normalized)

        return events

    def _extract_first(self, text: str, pattern: str) -> str:
        match = re.search(pattern, text, re.I | re.S)
        return match.group(1).strip() if match else ""

    def _parse_classgrid_page(self, page_url: str) -> list[dict]:
        response = self.session.get(page_url, timeout=30)
        response.raise_for_status()
        text = response.text

        if 'action="/Westshore/public/category/ClassGrid"' not in text:
            return []

        token = self._extract_first(
            text,
            r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',
        )
        start_date = self._extract_first(
            text,
            r'name="StartDate"[^>]*value="([^"]+)"',
        )
        category_guid = self._extract_first(
            text,
            r'name="CategoryGUID"[^>]*value="([^"]+)"',
        )

        if not token or not start_date or not category_guid:
            return []

        try:
            base_week = datetime.strptime(start_date, "%Y-%m-%d %I:%M:%S %p")
        except ValueError:
            return []

        events = []
        seen_ids = set()

        for week_index in range(WEEK_RANGE_WEEKS):
            week_start = base_week + timedelta(days=7 * week_index)
            grid_response = self.session.post(
                urljoin(BASE_URL, "/Westshore/public/category/ClassGrid"),
                data={
                    "__RequestVerificationToken": token,
                    "StartDate": week_start.strftime("%Y-%m-%d %I:%M:%S %p"),
                    "CategoryGUID": category_guid,
                },
                timeout=30,
            )
            grid_response.raise_for_status()

            blocks = re.findall(
                r"<button[^>]*data-bs-target='#classGridInfo'[^>]*>.*?</button>",
                grid_response.text,
                re.S,
            )
            if not blocks:
                continue

            for block in blocks:
                normalized = self._normalize_block(page_url, block)
                if not normalized:
                    continue
                if normalized["start_time"] < datetime.now() - timedelta(days=1):
                    continue
                if normalized["venue_name"] == "West Shore":
                    normalized["venue_name"] = "Juan de Fuca Rec Centre"
                if not normalized["facility_name"]:
                    normalized["facility_name"] = self._extract_first(
                        grid_response.text,
                        r"<title>(.*?) - Westshore</title>",
                    )
                if normalized["source_id"] in seen_ids:
                    continue
                seen_ids.add(normalized["source_id"])
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
            pages = self._discover_schedule_pages()
        except Exception as exc:
            print(f"[{self.municipality}] Source discovery failed: {exc}")
            return []

        all_events = []
        seen_ids = set()

        for page_url in pages:
            try:
                page_text = self.session.get(page_url, timeout=30).text
                if 'action="/Westshore/public/category/ClassSchedule"' in page_text:
                    page_events = self._parse_classschedule_page(page_url)
                else:
                    page_events = self._parse_page(page_url)
                if not page_events:
                    page_events = self._parse_classgrid_page(page_url)
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
