import hashlib
import re
from datetime import date, datetime, timedelta
from io import BytesIO

import requests
from pypdf import PdfReader

from scrapers.base import BaseScraper, classify_sport


RACQUET_PDF_URL = "https://www.oakbay.ca/wp-content/uploads/2026/03/RacquetSports-Drop-in-Schedule-Spring-2026.pdf"
TARGET_SPORTS = {"pickleball", "badminton", "table-tennis", "squash"}
DAY_TO_INDEX = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}


class OakBayPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="oakbay_pdf", municipality="Oak Bay")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _fetch_layout_text(self) -> str:
        response = self.session.get(RACQUET_PDF_URL, timeout=30)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        return reader.pages[0].extract_text(extraction_mode="layout") or ""

    def _split_day_columns(self, layout_text: str) -> dict[str, list[str]]:
        lines = layout_text.splitlines()
        header_index = next(i for i, line in enumerate(lines) if "Monday" in line and "Sunday" in line)
        header_line = lines[header_index]

        days = list(DAY_TO_INDEX.keys())
        positions = [header_line.index(day) for day in days]
        boundaries = [0]
        for idx in range(len(positions) - 1):
            boundaries.append((positions[idx] + positions[idx + 1]) // 2)
        boundaries.append(len(header_line))

        columns = {day: [] for day in days}
        for line in lines[header_index + 1 :]:
            if "Monterey Middle School" in line:
                break
            for idx, day in enumerate(days):
                start = boundaries[idx]
                end = boundaries[idx + 1]
                segment = line[start:end].strip()
                if segment:
                    columns[day].append(segment)

        return columns

    def _is_time_line(self, line: str) -> bool:
        compact = line.replace(" ", "")
        return bool(re.search(r"\d{1,2}:\d{2}(am|pm)?-\d{1,2}:\d{2}(am|pm)\*?", compact, re.I))

    def _is_note_line(self, line: str) -> bool:
        compact = " ".join(line.split())
        return (
            compact.startswith("(")
            or compact.startswith("*")
            or "May & June" in compact
            or "Ends June" in compact
            or "Friday, May 1" in compact
        )

    def _parse_time_range(self, raw: str) -> tuple[str, str]:
        compact = raw.replace(" ", "").replace("*", "").lower()
        start_raw, end_raw = compact.split("-", 1)

        end_match = re.match(r"(\d{1,2}:\d{2})(am|pm)", end_raw)
        if not end_match:
            raise ValueError(f"Unparseable end time: {raw}")
        end_clock, end_meridiem = end_match.groups()

        start_match = re.match(r"(\d{1,2}:\d{2})(am|pm)?", start_raw)
        if not start_match:
            raise ValueError(f"Unparseable start time: {raw}")
        start_clock, start_meridiem = start_match.groups()
        if not start_meridiem:
            start_meridiem = end_meridiem

        return f"{start_clock}{start_meridiem}", f"{end_clock}{end_meridiem}"

    def _parse_day_events(self, lines: list[str]) -> list[dict]:
        events = []
        title_lines: list[str] = []

        for raw_line in lines:
            line = " ".join(raw_line.split())
            if not line:
                continue

            if self._is_note_line(line):
                if events and not title_lines:
                    events[-1]["note"] = f"{events[-1]['note']} {line}".strip()
                else:
                    title_lines.append(line)
                continue

            if self._is_time_line(line):
                if not title_lines:
                    continue
                title = " ".join(title_lines).strip()
                start_time, end_time = self._parse_time_range(line)
                events.append(
                    {
                        "title": title,
                        "start_time_str": start_time,
                        "end_time_str": end_time,
                        "note": "",
                        "raw_time": line,
                    }
                )
                title_lines = []
                continue

            title_lines.append(line)

        return events

    def _should_include_event(self, title: str) -> bool:
        sport_type = classify_sport(title)
        if sport_type not in TARGET_SPORTS:
            return False
        if "lesson" in title.lower():
            return False
        return True

    def _apply_note_rules(self, occurrence_date: date, note: str, raw_time: str) -> bool:
        note = note.lower()
        if "may & june" in note and occurrence_date.month < 5:
            return False

        ends_match = re.search(r"ends june (\d+)", note)
        if ends_match:
            end_date = date(occurrence_date.year, 6, int(ends_match.group(1)))
            if occurrence_date > end_date:
                return False

        if "friday, may 1" in note and occurrence_date == date(occurrence_date.year, 5, 1):
            return False

        if "*" in raw_time and occurrence_date == date(occurrence_date.year, 5, 1):
            return False

        return True

    def _build_occurrences(self, weekday: str, events: list[dict]) -> list[dict]:
        today = datetime.utcnow().date()
        horizon = today + timedelta(days=35)
        weekday_index = DAY_TO_INDEX[weekday]

        occurrences = []
        current = today
        while current <= horizon:
            if current.weekday() == weekday_index:
                for event in events:
                    if not self._should_include_event(event["title"]):
                        continue
                    if not self._apply_note_rules(current, event["note"], event["raw_time"]):
                        continue

                    start_dt = datetime.strptime(
                        f"{current.isoformat()} {event['start_time_str']}",
                        "%Y-%m-%d %I:%M%p",
                    )
                    end_dt = datetime.strptime(
                        f"{current.isoformat()} {event['end_time_str']}",
                        "%Y-%m-%d %I:%M%p",
                    )
                    if end_dt <= start_dt:
                        end_dt += timedelta(days=1)

                    source_key = f"Henderson Recreation Centre|{event['title']}|{start_dt.isoformat()}"
                    source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
                    occurrences.append(
                        {
                            "source_id": f"{self.source_id_prefix}_{source_hash}",
                            "title": event["title"],
                            "sport_type": classify_sport(event["title"]),
                            "venue_name": "Henderson Recreation Centre",
                            "facility_name": "",
                            "start_time": start_dt,
                            "end_time": end_dt,
                            "price": "",
                            "description": f"Oak Bay racquet sports PDF schedule. {event['note']}".strip(),
                            "booking_url": RACQUET_PDF_URL,
                        }
                    )
            current += timedelta(days=1)

        return occurrences

    def scrape(self):
        print(f"[{self.municipality}] Starting Oak Bay PDF scrape...")
        try:
            layout_text = self._fetch_layout_text()
            columns = self._split_day_columns(layout_text)
        except Exception as exc:
            print(f"[{self.municipality}] Oak Bay PDF discovery failed: {exc}")
            return []

        all_events = []
        seen_ids = set()

        for weekday, lines in columns.items():
            day_events = self._parse_day_events(lines)
            for event in self._build_occurrences(weekday, day_events):
                if event["source_id"] in seen_ids:
                    continue
                seen_ids.add(event["source_id"])
                all_events.append(event)

        print(f"[{self.municipality}] Oak Bay PDF normalized {len(all_events)} events.")
        self.save_events(all_events)
        return all_events
