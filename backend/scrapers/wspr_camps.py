import hashlib
import re
from datetime import datetime, timedelta
from html import unescape
from urllib.parse import urljoin

import requests

from scrapers.base import BaseScraper, strip_html


BASE_URL = "https://explore.wspr.ca"
CAMP_ROOT_URL = "https://explore.wspr.ca/Westshore/public/category/browse/pro_camp"
ALL_CAMPS_URL = "https://explore.wspr.ca/Westshore/public/category/browse/pro_camp_win_sa_all"


class WSPRCampsScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="wspr_camps", municipality="West Shore")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _discover_pages(self) -> list[str]:
        queue = [CAMP_ROOT_URL, ALL_CAMPS_URL]
        visited = set()
        pages = set()

        while queue:
            page_url = queue.pop(0)
            if page_url in visited:
                continue
            visited.add(page_url)

            try:
                response = self.session.get(page_url, timeout=30)
                if response.status_code >= 400:
                    continue
                text = response.text
            except Exception:
                continue

            if 'class="card mb-4"' in text and "CourseDetails" in text:
                pages.add(page_url)

            for path in re.findall(r'href="(/Westshore/public/category/browse/[^"]+)"', text):
                if "camp" not in path.lower():
                    continue
                absolute = urljoin(BASE_URL, path)
                if absolute not in visited and absolute not in queue:
                    queue.append(absolute)

        return sorted(pages)

    def _attr(self, block: str, name: str) -> str:
        match = re.search(rf'{name}="(.*?)"', block, flags=re.S)
        return unescape(match.group(1)).strip() if match else ""

    def _text(self, html: str) -> str:
        return re.sub(r"\s+", " ", strip_html(unescape(html))).strip()

    def _badge_value(self, block: str, class_name: str) -> str:
        match = re.search(
            rf'<div class="input-group {class_name}">.*?<span class="input-group-text badge-value[^"]*">(.*?)</span>',
            block,
            flags=re.S,
        )
        return self._text(match.group(1)) if match else ""

    def _parse_time_range(self, date_str: str, start_str: str, end_str: str) -> tuple[datetime, datetime] | None:
        try:
            start_time = datetime.strptime(f"{date_str} {start_str}", "%a, %d-%b-%y %I:%M %p")
            end_time = datetime.strptime(f"{date_str} {end_str}", "%a, %d-%b-%y %I:%M %p")
            if end_time <= start_time:
                end_time += timedelta(days=1)
            return start_time, end_time
        except ValueError:
            return None

    def _normalize_card(self, page_url: str, block: str) -> dict | None:
        title_match = re.search(r'<h4 class="card-title">\s*(.*?)\s*</h4>', block, flags=re.S)
        title = self._text(title_match.group(1)) if title_match else ""
        if not title or "camp" not in title.lower():
            return None

        course_id = self._badge_value(block, "d-id")
        price = self._badge_value(block, "d-price")
        spaces = self._badge_value(block, "d-spaces")
        date_str = self._badge_value(block, "d-start")

        row_match = re.search(r"<tbody>\s*<tr>\s*(.*?)\s*</tr>", block, flags=re.S)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_match.group(1), flags=re.S) if row_match else []
        if len(cells) < 6 or not date_str:
            return None

        start_str = self._text(cells[1])
        end_str = self._text(cells[2])
        location = self._text(cells[4])
        venue = self._text(cells[5]) or "West Shore Parks & Recreation"
        parsed = self._parse_time_range(date_str, start_str, end_str)
        if not parsed:
            return None

        start_time, end_time = parsed
        description = self._attr(block, "data-course-description")
        alert = self._attr(block, "data-course-alert")
        description_parts = [part for part in [description, f"Spaces: {spaces}" if spaces else "", alert] if part]

        booking_path = f"/Westshore/public/booking/CourseDetails/{course_id}" if course_id else page_url
        raw_key = "|".join([course_id, title, date_str, start_str, end_str, venue, location])
        source_hash = hashlib.md5(raw_key.encode("utf-8")).hexdigest()[:16]

        return {
            "source_id": f"{self.source_id_prefix}_{course_id or source_hash}",
            "title": title,
            "venue_name": venue,
            "facility_name": location,
            "start_time": start_time,
            "end_time": end_time,
            "price": price,
            "description": self._text(" ".join(description_parts)),
            "booking_url": urljoin(BASE_URL, booking_path),
            "source": self.source_id_prefix,
            "municipality": self.municipality,
        }

    def _parse_page(self, page_url: str) -> list[dict]:
        response = self.session.get(page_url, timeout=30)
        response.raise_for_status()
        blocks = re.split(r'<div class="card mb-4">', response.text)[1:]
        events = []
        for block in blocks:
            normalized = self._normalize_card(page_url, block)
            if normalized:
                events.append(normalized)
        return events

    def scrape(self):
        print(f"[{self.municipality}] Starting WSPR camp scrape...")
        pages = self._discover_pages()
        events = []
        seen = set()
        for page_url in pages:
            try:
                for event in self._parse_page(page_url):
                    if event["source_id"] in seen:
                        continue
                    seen.add(event["source_id"])
                    events.append(event)
            except Exception as exc:
                print(f"[{self.municipality}] WSPR camp page failed {page_url}: {exc}")

        print(f"[{self.municipality}] WSPR camps normalized {len(events)} events from {len(pages)} pages.")
        self.replace_existing_events()
        self.save_events(events)
        return events

