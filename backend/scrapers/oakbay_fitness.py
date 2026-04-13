import hashlib
import re
from datetime import datetime, timedelta

import requests

from scrapers.base import BaseScraper


FITNESS_URL = "https://www.oakbay.ca/parks-recreation/programs-registration-services/registered-programs/fitness-wellness/"
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_TO_INDEX = {day: index for index, day in enumerate(DAY_ORDER)}

TABLES = [
    {
        "venue_name": "Henderson Recreation Centre",
        "facility_name": "Fitness Centre",
        "table_id": "20393",
        "title": "Fitness Centre Drop-In",
        "note": "Closed Mondays and Wednesdays from 8:00 to 9:15 a.m., and Tuesdays and Thursdays from 12:00 to 1:15 p.m. for registered Circuit classes.",
    },
    {
        "venue_name": "Oak Bay Recreation Centre",
        "facility_name": "Fitness Centre",
        "table_id": "20399",
        "title": "Fitness Centre Drop-In",
        "note": "",
    },
]


class OakBayFitnessScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="oakbay_fitness", municipality="Oak Bay")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _fetch_html(self) -> str:
        response = self.session.get(FITNESS_URL, timeout=30)
        response.raise_for_status()
        return response.text

    def _extract_table(self, html: str, table_id: str) -> str:
        match = re.search(
            rf'<table[^>]+id="footable_{re.escape(table_id)}".*?</table>',
            html,
            re.S,
        )
        if not match:
            raise ValueError(f"Could not find table {table_id}")
        return match.group(0)

    def _parse_dropin_row(self, table_html: str) -> dict[str, str]:
        headers = re.findall(r"<th[^>]*>(.*?)</th>", table_html, re.S)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", table_html, re.S)
        headers = [self._clean_text(value) for value in headers]
        cells = [self._clean_text(value) for value in cells]

        if not headers or not cells or cells[0] != "Drop-in":
            raise ValueError("Unexpected fitness table layout")

        day_headers = headers[1:]
        day_values = cells[1 : 1 + len(day_headers)]
        return dict(zip(day_headers, day_values))

    def _clean_text(self, html_fragment: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html_fragment)
        text = (
            text.replace("–", "-")
            .replace("&nbsp;", " ")
            .replace("&#8211;", "-")
            .replace("&#8217;", "'")
        )
        return " ".join(text.split())

    def _split_ranges(self, raw: str) -> list[tuple[str, str]]:
        if not raw or raw == "-":
            return []
        chunks = re.split(r"\s*(?:and|,)\s*", raw)
        ranges = []
        for chunk in chunks:
            chunk = chunk.strip()
            if "-" not in chunk:
                continue
            start_raw, end_raw = chunk.split("-", 1)
            start = self._normalize_clock(start_raw, end_raw)
            end = self._normalize_clock(end_raw, end_raw)
            ranges.append((start, end))
        return ranges

    def _normalize_clock(self, value: str, fallback: str) -> str:
        value = value.strip().lower().replace(" ", "")
        fallback = fallback.strip().lower().replace(" ", "")
        match = re.match(r"(\d{1,2}:\d{2})(am|pm)?", value)
        if not match:
            raise ValueError(f"Unparseable time value: {value}")
        clock, meridiem = match.groups()
        if not meridiem:
            fallback_match = re.search(r"(am|pm)", fallback)
            meridiem = fallback_match.group(1) if fallback_match else "am"
        return f"{clock}{meridiem}"

    def _build_events(self, venue_name: str, facility_name: str, title: str, note: str, ranges_by_day: dict[str, str]) -> list[dict]:
        today = datetime.utcnow().date()
        horizon = today + timedelta(days=35)
        current = today
        events = []

        while current <= horizon:
            weekday = DAY_ORDER[current.weekday()]
            for start_str, end_str in self._split_ranges(ranges_by_day.get(weekday, "")):
                start_dt = datetime.strptime(
                    f"{current.isoformat()} {start_str}",
                    "%Y-%m-%d %I:%M%p",
                )
                end_dt = datetime.strptime(
                    f"{current.isoformat()} {end_str}",
                    "%Y-%m-%d %I:%M%p",
                )
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)

                source_key = f"{venue_name}|{title}|{start_dt.isoformat()}"
                source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
                description = "Oak Bay Fitness & Wellness page drop-in hours."
                if note:
                    description = f"{description} {note}"
                events.append(
                    {
                        "source_id": f"{self.source_id_prefix}_{source_hash}",
                        "title": title,
                        "venue_name": venue_name,
                        "facility_name": facility_name,
                        "start_time": start_dt,
                        "end_time": end_dt,
                        "price": "",
                        "description": description.strip(),
                        "booking_url": FITNESS_URL,
                    }
                )
            current += timedelta(days=1)
        return events

    def scrape(self):
        print(f"[{self.municipality}] Starting Oak Bay fitness scrape...")
        try:
            html = self._fetch_html()
        except Exception as exc:
            print(f"[{self.municipality}] Oak Bay fitness fetch failed: {exc}")
            return []

        all_events = []
        for table in TABLES:
            try:
                table_html = self._extract_table(html, table["table_id"])
                ranges_by_day = self._parse_dropin_row(table_html)
                all_events.extend(
                    self._build_events(
                        venue_name=table["venue_name"],
                        facility_name=table["facility_name"],
                        title=table["title"],
                        note=table["note"],
                        ranges_by_day=ranges_by_day,
                    )
                )
            except Exception as exc:
                print(f"[{self.municipality}] Oak Bay fitness parse failed for {table['venue_name']}: {exc}")

        print(f"[{self.municipality}] Oak Bay fitness normalized {len(all_events)} events.")
        self.save_events(all_events)
        return all_events
