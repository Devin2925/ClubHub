import hashlib
import re
from datetime import date, datetime, timedelta
from io import BytesIO
from urllib.parse import urljoin

import requests
from pypdf import PdfReader

from models import Event, SessionLocal
from scrapers.base import BaseScraper


PAGE_URL = "https://www.saanich.ca/EN/main/parks-recreation-community/recreation/schedules/skating.html"
DAY_TO_INDEX = {
    "MON": 0,
    "TUES": 1,
    "WED": 2,
    "THURS": 3,
    "FRI": 4,
    "SAT": 5,
    "SUN": 6,
}
ROW_CONFIG = {
    "Skate - Everyone Welcome": {
        "start": "Everyone",
        "end": "Adult and Child",
        "days": ["MON", "WED", "FRI", "SAT", "SUN"],
    },
    "Skate - Parent & Child Hockey Social 5-10yrs": {
        "start": "Adult and Child",
        "end": "Adult and Tot Ice",
        "days": ["MON"],
    },
    "Skate - Adult and Tot Ice Play 1-6yrs": {
        "start": "Adult and Tot Ice",
        "end": "Adult Skate",
        "days": ["WED", "WED", "FRI", "SAT"],
    },
    "Skate - Adult Skate Drop In 19yrs+": {
        "start": "Adult Skate",
        "end": "Adult Figure",
        "days": ["MON", "TUES", "THURS", "SAT", "SUN"],
    },
    "Skate - Adult Figure Skate Drop In 19yrs+": {
        "start": "Adult Figure",
        "end": "**Stick & Puck",
        "days": ["MON", "WED"],
    },
}


class PearkesPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__("saanich_pearkes_pdf", "Saanich")
        self.venue_name = "G. R. Pearkes Recreation Centre"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _discover_pdf_url(self) -> str:
        response = self.session.get(PAGE_URL, timeout=30)
        response.raise_for_status()
        links = re.findall(r'href="([^"]+\.pdf)"', response.text, re.I)
        candidates = []
        month_name = datetime.utcnow().strftime("%B").lower()
        month_abbr = datetime.utcnow().strftime("%b").lower()
        for link in links:
            absolute = urljoin(PAGE_URL, link)
            lowered = absolute.lower()
            if "dropin" not in lowered and "dropinskating" not in lowered:
                continue
            if "prks_" not in lowered:
                continue
            score = 0
            if "updateddropin" in lowered:
                score += 3
            if month_name in lowered or month_abbr in lowered:
                score += 2
            candidates.append((score, absolute))

        if not candidates:
            raise ValueError("Could not find Pearkes skating PDF")

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates[0][1]

    def _fetch_text(self, pdf_url: str) -> str:
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        return reader.pages[0].extract_text() or ""

    def _fetch_layout_text(self, pdf_url: str) -> str:
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        return reader.pages[0].extract_text(extraction_mode="layout") or ""

    def _parse_month_window(self, text: str) -> tuple[date, date]:
        match = re.search(r"([A-Z][a-z]+)\s+(\d{1,2})-(\d{1,2}),\s+(\d{4})", text)
        if not match:
            raise ValueError("Could not parse Pearkes PDF month window")
        month_name, start_day, end_day, year = match.groups()
        month = datetime.strptime(month_name, "%B").month
        return date(int(year), month, int(start_day)), date(int(year), month, int(end_day))

    def _lines(self, text: str) -> list[str]:
        return [" ".join(line.split()) for line in text.splitlines() if line.split()]

    def _row_lines(self, lines: list[str], start_marker: str, end_marker: str) -> list[str]:
        start_index = next(i for i, line in enumerate(lines) if line.startswith(start_marker))
        end_index = next(i for i, line in enumerate(lines[start_index + 1 :], start_index + 1) if line.startswith(end_marker))
        return lines[start_index:end_index]

    def _time_pattern(self) -> re.Pattern[str]:
        return re.compile(r"\d{1,2}(?::\d{2})?(?:am|pm)?-\d{1,2}(?::\d{2})?(?:am|pm)", re.I)

    def _expand_line(self, line: str) -> list[str]:
        parts = []
        cursor = 0
        for match in self._time_pattern().finditer(line):
            before = line[cursor : match.start()].strip()
            if before:
                parts.append(before)
            parts.append(match.group(0))
            cursor = match.end()
        after = line[cursor:].strip()
        if after:
            parts.append(after)
        return parts or [line]

    def _time_tokens(self, row_lines: list[str]) -> list[str]:
        tokens = []
        for line in row_lines:
            for part in self._expand_line(line):
                if part:
                    tokens.append(part)
        return tokens

    def _parse_time_range(self, value: str) -> tuple[str, str]:
        compact = value.replace(" ", "").lower()
        start_raw, end_raw = compact.split("-", 1)

        end_match = re.fullmatch(r"(\d{1,2}(?::\d{2})?)(am|pm)", end_raw)
        if not end_match:
            raise ValueError(f"Unparseable Pearkes end time: {value}")
        end_clock, end_meridiem = end_match.groups()

        start_match = re.fullmatch(r"(\d{1,2}(?::\d{2})?)(am|pm)?", start_raw)
        if not start_match:
            raise ValueError(f"Unparseable Pearkes start time: {value}")
        start_clock, start_meridiem = start_match.groups()
        if not start_meridiem:
            start_hour = int(start_clock.split(":", 1)[0])
            end_hour = int(end_clock.split(":", 1)[0])
            if end_meridiem == "pm" and start_hour != 12 and (end_hour == 12 or start_hour > end_hour):
                start_meridiem = "am"
            else:
                start_meridiem = end_meridiem

        if ":" not in start_clock:
            start_clock = f"{start_clock}:00"
        if ":" not in end_clock:
            end_clock = f"{end_clock}:00"
        return f"{start_clock}{start_meridiem}", f"{end_clock}{end_meridiem}"

    def _group_entries(self, tokens: list[str], days: list[str]) -> list[dict]:
        time_regex = self._time_pattern()
        cleaned = [token for token in tokens if token not in {"---"}]
        groups = []
        current = None

        for token in cleaned:
            if time_regex.fullmatch(token):
                if current:
                    groups.append(current)
                current = {"time": token, "note_parts": []}
                continue
            if current:
                current["note_parts"].append(token)

        if current:
            groups.append(current)

        entries = []
        for day, group in zip(days, groups):
            entries.append(
                {
                    "day": day,
                    "time_range": self._parse_time_range(group["time"]),
                    "note": " ".join(group["note_parts"]).strip(),
                }
            )
        return entries

    def _weekday_dates(self, weekday_index: int, start_date: date, end_date: date) -> list[date]:
        cursor = start_date
        dates = []
        while cursor <= end_date:
            if cursor.weekday() == weekday_index:
                dates.append(cursor)
            cursor += timedelta(days=1)
        return dates

    def _days_from_note(self, note: str) -> list[int]:
        match = re.search(r"(?:Apr|April)\s+(\d[\d,\s&]*)", note, re.I)
        if not match:
            return []
        return [int(value) for value in re.findall(r"\d{1,2}", match.group(1))]

    def _apply_note_to_dates(self, dates: list[date], note: str) -> list[date]:
        lowered = note.lower()
        explicit_days = self._days_from_note(note)

        if "only" in lowered and explicit_days:
            return [dt for dt in dates if dt.day in explicit_days]

        if "except" in lowered and explicit_days:
            excluded = set(explicit_days)
            return [dt for dt in dates if dt.day not in excluded]

        return dates

    def _existing_keys(self, start_date: date, end_date: date) -> set[tuple[str, str]]:
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
                (row.title, row.start_time.replace(microsecond=0).isoformat(sep=" "))
                for row in rows
            }
        finally:
            db.close()

    def _append_missing_event(
        self,
        events: list[dict],
        existing: set[tuple[str, str]],
        *,
        title: str,
        start_dt: datetime,
        end_dt: datetime,
        pdf_url: str,
        note: str,
    ):
        existing_key = (title, start_dt.replace(microsecond=0).isoformat(sep=" "))
        if existing_key in existing:
            return

        source_key = f"{title}|{start_dt.isoformat()}|{pdf_url}"
        source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
        description = "Saanich Pearkes skating PDF fallback."
        if note:
            description += f" {note}"
        events.append(
            {
                "source_id": f"{self.source_id_prefix}_{source_hash}",
                "title": title,
                "venue_name": self.venue_name,
                "facility_name": "",
                "start_time": start_dt,
                "end_time": end_dt,
                "price": "",
                "description": description.strip(),
                "booking_url": pdf_url,
            }
        )
        existing.add(existing_key)

    def _supplement_stick_and_puck(
        self,
        events: list[dict],
        existing: set[tuple[str, str]],
        *,
        pdf_url: str,
        layout_text: str,
        start_date: date,
        end_date: date,
    ):
        lines = [line.rstrip() for line in layout_text.splitlines()]
        try:
            start_index = next(i for i, line in enumerate(lines) if "**Stick & Puck" in line)
            end_index = next(i for i, line in enumerate(lines[start_index + 1 :], start_index + 1) if "Notes &" in line)
        except StopIteration:
            return

        block = [re.split(r"\s{2,}", line.strip()) for line in lines[start_index:end_index] if line.strip()]
        if len(block) < 7:
            return

        extra_slots = []

        monday_time_start = block[4][0] if len(block[4]) > 0 else ""
        monday_time_end = block[5][0] if len(block[5]) > 0 else ""
        monday_note = block[6][0] if len(block[6]) > 0 else ""
        if monday_time_start and monday_time_end and monday_note:
            extra_slots.append(("MON", f"{monday_time_start}{monday_time_end}", monday_note))

        if len(block[4]) > 1 and len(block[5]) > 1:
            extra_slots.append(("TUES", block[4][1], block[5][1]))
        if len(block[4]) > 2 and len(block[5]) > 2:
            extra_slots.append(("THURS", block[4][2], block[5][2]))
        if len(block[4]) > 3 and len(block[5]) > 3:
            extra_slots.append(("FRI", block[4][3], block[5][3]))

        titles = [
            "Skate - Stick & Puck Reserved Drop In 19yrs+",
            "Skate - Stick & Puck Reserved Drop In 19yrs+ Goalie",
        ]

        for day_name, time_range, note in extra_slots:
            try:
                parsed_start, parsed_end = self._parse_time_range(time_range)
            except ValueError:
                continue

            dates = self._weekday_dates(DAY_TO_INDEX[day_name], start_date, end_date)
            for event_date in self._apply_note_to_dates(dates, note):
                start_dt = datetime.strptime(
                    f"{event_date.isoformat()} {parsed_start}",
                    "%Y-%m-%d %I:%M%p",
                )
                end_dt = datetime.strptime(
                    f"{event_date.isoformat()} {parsed_end}",
                    "%Y-%m-%d %I:%M%p",
                )
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                for title in titles:
                    self._append_missing_event(
                        events,
                        existing,
                        title=title,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        pdf_url=pdf_url,
                        note=note,
                    )

    def scrape(self):
        print(f"[{self.municipality}] Starting Pearkes PDF fallback scrape...")
        try:
            pdf_url = self._discover_pdf_url()
            text = self._fetch_text(pdf_url)
            layout_text = self._fetch_layout_text(pdf_url)
            start_date, end_date = self._parse_month_window(text)
            lines = self._lines(text)
        except Exception as exc:
            print(f"[{self.municipality}] Pearkes PDF scrape failed: {exc}")
            return []

        existing = self._existing_keys(start_date, end_date)
        events = []

        for title, config in ROW_CONFIG.items():
            row_lines = self._row_lines(lines, config["start"], config["end"])
            tokens = self._time_tokens(row_lines)
            entries = self._group_entries(tokens, config["days"])
            for entry in entries:
                dates = self._weekday_dates(DAY_TO_INDEX[entry["day"]], start_date, end_date)
                for event_date in self._apply_note_to_dates(dates, entry["note"]):
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
                    self._append_missing_event(
                        events,
                        existing,
                        title=title,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        pdf_url=pdf_url,
                        note=entry["note"],
                    )

        self._supplement_stick_and_puck(
            events,
            existing,
            pdf_url=pdf_url,
            layout_text=layout_text,
            start_date=start_date,
            end_date=end_date,
        )

        print(f"[{self.municipality}] Pearkes PDF normalized {len(events)} missing events.")
        self.save_events(events)
        return events
