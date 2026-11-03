import hashlib
import re
from datetime import datetime, time, timedelta
from html import unescape
from urllib.parse import urljoin

import requests

from scrapers.base import BaseScraper, strip_html


PAGE_CONFIGS = [
    {
        "key": "drop-in",
        "url": "https://www.vikesrec.ca/drop-in",
        "label": "Drop In",
    },
    {
        "key": "group-fitness",
        "offering": "class",
        "url": "https://www.vikesrec.ca/group-fitness",
        "label": "Group Fitness",
    },
    {
        "key": "registered-fitness",
        "offering": "class",
        "url": "https://www.vikesrec.ca/registered-fitness",
        "label": "Registered Fitness",
    },
    {
        "key": "yoga",
        "url": "https://www.vikesrec.ca/yoga",
        "label": "Yoga",
        # Class names like "Yang to Yin" or "Steady Fire Flow" don't say yoga.
        "sport": "yoga",
        "offering": "class",
    },
    {
        "key": "pickleball",
        "url": "https://www.vikesrec.ca/pickleball",
        "label": "Pickleball",
    },
]

SQUASH_CLUB_URL = "https://www.vikesrec.ca/clubs/squash"

DAY_NAME_TO_INDEX = {
    "Mon.": 0,
    "Tue.": 1,
    "Wed.": 2,
    "Thu.": 3,
    "Fri.": 4,
    "Sat.": 5,
    "Sun.": 6,
}

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


class VikesRecScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="uvic_vikesrec", municipality="UVic")
        self.venue_name = "CARSA / Vikes Recreation"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _fetch(self, url: str) -> str:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    def _extract_range_labels(self, html: str) -> list[str]:
        labels = re.findall(r'<span class="scheduledate">\((.*?)\)</span>', html, flags=re.I | re.S)
        if not labels:
            labels = re.findall(r'scheduledate">\(([^<]+)\)', html, flags=re.I | re.S)
        return [unescape(label).replace("\u2009", " ").strip() for label in labels]

    def _parse_range_label(self, label: str) -> tuple[datetime, datetime] | None:
        normalized = re.sub(r"^upcoming\s+for\s+", "", label, flags=re.I).strip()
        normalized = normalized.replace("&ndash;", "-").replace("–", "-").replace("—", "-")
        match = re.search(
            r"([A-Za-z]+)\.?\s+(\d+)\s*-\s*([A-Za-z]+)\.?\s+(\d+)",
            normalized,
            flags=re.I,
        )
        if not match:
            return None

        start_month = MONTHS[match.group(1)[:3].lower()]
        start_day = int(match.group(2))
        end_month = MONTHS[match.group(3)[:3].lower()]
        end_day = int(match.group(4))

        today = datetime.now()
        year = today.year
        start_dt = datetime(year, start_month, start_day)
        end_year = year
        if end_month < start_month:
            end_year += 1
        end_dt = datetime(end_year, end_month, end_day, 23, 59, 59)
        if end_dt < start_dt:
            start_dt = datetime(year - 1, start_month, start_day)
        return start_dt, end_dt

    def _extract_holidays(self, html: str) -> set[tuple[int, int]]:
        # e.g. "Note: There are no programs on Sep. 30, Oct. 12, Nov. 11 due to holidays."
        note = re.search(r"no\s+programs\s+on\s+(.*?)\s+due\s+to\s+holiday", unescape(html), flags=re.I | re.S)
        if not note:
            return set()
        return {
            (MONTHS[month[:3].lower()], int(day))
            for month, day in re.findall(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})", note.group(1))
            if month[:3].lower() in MONTHS
        }

    def _extract_prices(self, html: str) -> dict[str, str]:
        # Class description cards: <h4 id="beginner-yoga">Beginner Yoga</h4><h6>$20 <span>included with membership</span></h6>
        prices = {}
        for anchor, price_html in re.findall(r'<h4 id="([^"]+)">.*?</h4>\s*<h6>(.*?)</h6>', html, flags=re.I | re.S):
            text = " ".join(re.sub(r"<[^>]+>", " ", unescape(price_html)).replace("*", "").split())
            if text.startswith("$"):
                prices[anchor] = text.replace(" included with membership", " drop-in, included with membership")
            elif re.match(r"(no charge|free)\b", text, flags=re.I) and re.search(r"student", text, flags=re.I):
                prices[anchor] = "Free for UVic students & members"
        return prices

    def _extract_class_notes(self, html: str) -> dict[str, str]:
        """The class card under the schedule, cut to what someone deciding needs:
        "A fun, energizing blend of ballet-inspired movements... All levels welcome. Youth 13+."
        """
        notes = {}
        for anchor, body in re.findall(r'<h4 id="([^"]+)">.*?</h4>(.*?)(?=<h4 id=|<!--)', html, flags=re.I | re.S):
            body = re.sub(r"^\s*<h6>.*?</h6>", "", body, count=1, flags=re.I | re.S)  # the price line
            text = " ".join(re.sub(r"<[^>]+>", " ", unescape(body)).split()).replace("..", ".")
            text = re.sub(r"^\*+\s*", "", text)
            youth = re.search(r"Youth welcome\s*:\s*(\d+\+?)", text, flags=re.I)
            text = re.split(r"\b(?:Youth welcome|Equipment|Instructor|Location|Program availability)\s*:", text, maxsplit=1)[0].strip()
            if len(text) > 240:
                cut = text[:240].rsplit(". ", 1)[0]
                text = (cut if len(cut) > 80 else text[:237].rsplit(" ", 1)[0]) .rstrip(".") + "."
            if youth:
                text = f"{text} Ages {youth.group(1)}." if text else f"Ages {youth.group(1)}."
            if text:
                notes[anchor] = text
        return notes

    def _extract_tab_html(self, html: str, tab_number: int) -> str:
        start_marker = f"<!-- tab {tab_number} - current schedule starts -->"
        if tab_number == 2:
            start_marker = "<!-- tab 2 - upcoming schedule starts -->"
        start_idx = html.find(start_marker)
        if start_idx == -1 and tab_number == 1:
            simple_start = html.find("<!-- simple schedule -->")
            if simple_start == -1:
                return ""
            simple_end = html.find("<!-- end simple schedule -->", simple_start)
            if simple_end == -1:
                simple_end = len(html)
            return html[simple_start:simple_end]
        if start_idx == -1:
            return ""
        if tab_number == 1:
            end_idx = html.find("<!-- tab 2 - upcoming schedule starts -->", start_idx)
        else:
            end_idx = html.find("<!-- end tabbed content -->", start_idx)
        if end_idx == -1:
            end_idx = len(html)
        return html[start_idx:end_idx]

    def _extract_day_blocks(self, tab_html: str) -> list[tuple[int, str]]:
        blocks = []
        for day_name, day_idx in DAY_NAME_TO_INDEX.items():
            pattern = re.compile(
                rf"<!-- .*? -->\s*<div>\s*<h4>{re.escape(day_name)}</h4>(.*?)</div>\s*<!-- end .*? -->",
                flags=re.I | re.S,
            )
            match = pattern.search(tab_html)
            if match:
                blocks.append((day_idx, match.group(1)))
        return blocks

    def _extract_entries(self, day_html: str, page_url: str, page_label: str) -> list[dict]:
        entries = []
        parts = re.split(r'<p class="prog-sched-line"[^>]*>.*?</p>', day_html, flags=re.I | re.S)
        for chunk in parts:
            title_match = re.search(r"<h5>(.*?)</h5>", chunk, flags=re.I | re.S)
            time_match = re.search(r"<p>(.*?)</p>", chunk, flags=re.I | re.S)
            if not title_match or not time_match:
                continue

            title_html = title_match.group(1)
            title = re.sub(r"<[^>]+>", "", unescape(title_html)).strip()
            if not title:
                continue

            time_text = re.sub(r"<[^>]+>", "", unescape(time_match.group(1))).strip()
            facility_match = re.search(r"<h6>(.*?)</h6>", chunk, flags=re.I | re.S)
            facility = ""
            if facility_match:
                facility = re.sub(r"<[^>]+>", "", unescape(facility_match.group(1))).strip()

            register_match = re.search(
                r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:Register|Reserve(?:\s+(?:a|your))?\s+spot)\s*</a>',
                chunk,
                flags=re.I | re.S,
            )
            detail_match = re.search(r'<h5>\s*<a[^>]+href="([^"]+)"', chunk, flags=re.I | re.S)
            anchor = ""
            if detail_match and "#" in detail_match.group(1):
                anchor = unescape(detail_match.group(1)).rpartition("#")[2]
            booking_url = page_url
            if register_match:
                booking_url = unescape(register_match.group(1))
            elif detail_match:
                booking_url = urljoin(page_url, unescape(detail_match.group(1)))

            # "Badminton (Starts Sep.14)": hold sessions until the start date, drop the note.
            starts = None
            starts_match = re.search(r"\s*\(\s*starts?\s+([A-Za-z]{3})[a-z]*\.?\s*(\d{1,2})\s*\)", title, flags=re.I)
            if starts_match and starts_match.group(1)[:3].lower() in MONTHS:
                starts = (MONTHS[starts_match.group(1)[:3].lower()], int(starts_match.group(2)))
                title = (title[: starts_match.start()] + title[starts_match.end():]).strip()

            entries.append(
                {
                    "anchor": anchor,
                    "starts": starts,
                    "title": title,
                    "time_text": time_text,
                    "facility_name": facility,
                    "booking_url": booking_url,
                    "description": f"UVic Vikes Recreation {page_label} public schedule.",
                }
            )
        return entries

    @staticmethod
    def _before_start(event_date: datetime, starts: tuple[int, int]) -> bool:
        month, day = starts
        # A September start seen in spring belongs to the coming fall; otherwise this school year.
        year = event_date.year if month <= event_date.month + 6 else event_date.year - 1
        try:
            return event_date.date() < datetime(year, month, day).date()
        except ValueError:
            return False

    @staticmethod
    def _facility_for_day(facility: str, weekday: int) -> str:
        """'Thursday: Elevate Studio ; Friday: Gwynne Excel Studio' -> the room for that day."""
        facility = re.sub(r"\bGywnne\b", "Gwynne", facility)
        parts = re.findall(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?\s*:\s*([^;]+)", facility, flags=re.I)
        if not parts:
            return facility
        day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][weekday]
        for name, room in parts:
            if name[:3].lower() == day:
                return room.strip()
        return facility

    def _parse_time_range(self, event_date: datetime, time_text: str) -> tuple[datetime, datetime] | None:
        normalized = (
            unescape(time_text)
            .replace("&ndash;", "-")
            .replace("–", "-")
            .replace("—", "-")
            .replace(" ", "")
        )
        if "-" not in normalized:
            return None
        start_str, end_str = normalized.split("-", 1)
        for fmt in ("%I:%M%p", "%I%p"):
            try:
                start_t = datetime.strptime(start_str, fmt).time()
                break
            except ValueError:
                start_t = None
        for fmt in ("%I:%M%p", "%I%p"):
            try:
                end_t = datetime.strptime(end_str, fmt).time()
                break
            except ValueError:
                end_t = None
        if not start_t or not end_t:
            return None

        start_dt = datetime.combine(event_date.date(), start_t)
        end_dt = datetime.combine(event_date.date(), end_t)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        return start_dt, end_dt

    def _dates_for_weekday(self, start_dt: datetime, end_dt: datetime, weekday: int) -> list[datetime]:
        current = max(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0), start_dt)
        days_ahead = (weekday - current.weekday()) % 7
        first = current + timedelta(days=days_ahead)
        dates = []
        while first <= end_dt:
            dates.append(first)
            first += timedelta(days=7)
        return dates

    def _events_from_page(self, page: dict) -> list[dict]:
        html = self._fetch(page["url"])
        range_labels = self._extract_range_labels(html)
        tab_ranges = [self._parse_range_label(label) for label in range_labels]
        holidays = self._extract_holidays(html)
        prices = self._extract_prices(html)
        notes = self._extract_class_notes(html)

        events = []
        for index, date_range in enumerate(tab_ranges, start=1):
            if not date_range:
                continue
            tab_html = self._extract_tab_html(html, index)
            if not tab_html:
                continue
            day_blocks = self._extract_day_blocks(tab_html)
            for weekday, day_html in day_blocks:
                entries = self._extract_entries(day_html, page["url"], page["label"])
                if not entries:
                    continue
                for event_date in self._dates_for_weekday(date_range[0], date_range[1], weekday):
                    if (event_date.month, event_date.day) in holidays:
                        continue
                    for entry in entries:
                        if entry["starts"] and self._before_start(event_date, entry["starts"]):
                            continue
                        parsed = self._parse_time_range(event_date, entry["time_text"])
                        if not parsed:
                            continue
                        start_dt, end_dt = parsed
                        facility = self._facility_for_day(entry["facility_name"], weekday)
                        source_key = "|".join(
                            [
                                page["key"],
                                entry["title"],
                                entry["facility_name"],
                                start_dt.isoformat(),
                            ]
                        )
                        source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
                        event = {
                            "source_id": f"{self.source_id_prefix}_{source_hash}",
                            "title": entry["title"],
                            "venue_name": self.venue_name,
                            "facility_name": facility,
                            "start_time": start_dt,
                            "end_time": end_dt,
                            "price": prices.get(entry["anchor"], ""),
                            "description": notes.get(entry["anchor"], entry["description"]),
                            "booking_url": entry["booking_url"],
                            "municipality": self.municipality,
                        }
                        if page.get("sport"):
                            event["sport_override"] = page["sport"]
                        if page.get("offering"):
                            # Class descriptions mention "drop-in" pricing; these are still classes.
                            event["offering_override"] = page["offering"]
                        events.append(event)
        return events

    def _parse_clock_time(self, value: str) -> time | None:
        value = value.strip().upper().replace(" ", "")
        for fmt in ("%I:%M%p", "%I%p"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
        return None

    def _parse_squash_club_events(self) -> list[dict]:
        html = self._fetch(SQUASH_CLUB_URL)
        text = re.sub(r"\s+", " ", unescape(strip_html(html)))
        when_match = re.search(
            r"When\s*:?\s*September-April\s+on\s+Tuesday\s*&\s*Thursday\s+([0-9:]+(?:AM|PM)?)\s*-\s*([0-9:]+(?:AM|PM)?)",
            text,
            flags=re.I,
        )
        if not when_match:
            return []

        start_raw = when_match.group(1)
        end_raw = when_match.group(2)
        if not re.search(r"[AP]M$", start_raw, flags=re.I) and re.search(r"[AP]M$", end_raw, flags=re.I):
            start_raw = f"{start_raw}{re.search(r'([AP]M)$', end_raw, flags=re.I).group(1)}"

        start_t = self._parse_clock_time(start_raw)
        end_t = self._parse_clock_time(end_raw)
        if not start_t or not end_t:
            return []

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        season_end = datetime(today.year, 4, 30)
        if today.month > 4:
            season_end = datetime(today.year + 1, 4, 30)

        events = []
        for weekday in (1, 3):  # Tuesday, Thursday
            current = today + timedelta(days=(weekday - today.weekday()) % 7)
            while current <= season_end:
                start_dt = datetime.combine(current.date(), start_t)
                end_dt = datetime.combine(current.date(), end_t)
                source_key = f"squash-club|{start_dt.isoformat()}"
                source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
                events.append(
                    {
                        "source_id": f"{self.source_id_prefix}_{source_hash}",
                        "title": "Squash Club Drop-In",
                        "venue_name": self.venue_name,
                        "facility_name": "CARSA squash courts",
                        "start_time": start_dt,
                        "end_time": end_dt,
                        "price": "",
                        "description": "Public UVic Squash Club page lists Tuesday and Thursday evening club sessions September-April.",
                        "booking_url": SQUASH_CLUB_URL,
                        "municipality": self.municipality,
                    }
                )
                current += timedelta(days=7)
        return events

    def scrape(self):
        print(f"[{self.municipality}] Starting UVic Vikes Recreation scrape...")
        events = []
        complete = True
        for page in PAGE_CONFIGS:
            try:
                page_events = self._events_from_page(page)
                print(f"[{self.municipality}] {page['label']}: {len(page_events)} events")
                events.extend(page_events)
            except Exception as exc:
                complete = False
                print(f"[{self.municipality}] Failed {page['label']} page: {exc}")

        try:
            squash_events = self._parse_squash_club_events()
            print(f"[{self.municipality}] Squash Club: {len(squash_events)} events")
            events.extend(squash_events)
        except Exception as exc:
            complete = False
            print(f"[{self.municipality}] Failed Squash Club page: {exc}")

        deduped = {event["source_id"]: event for event in events}
        normalized = list(deduped.values())
        self.save_events(normalized)
        # Rows from earlier runs that the schedule no longer lists are cancelled or
        # retimed sessions; only clear them when every page was read.
        if complete and normalized:
            self.prune_unseen_upcoming(deduped.keys())
        return normalized
