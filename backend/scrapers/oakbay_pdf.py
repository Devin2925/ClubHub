import hashlib
import re
from datetime import date, datetime, timedelta
from io import BytesIO

import requests
from pypdf import PdfReader

from scrapers.base import BaseScraper, classify_sport


DROPIN_PAGE_URL = "https://www.oakbay.ca/parks-recreation/programs-registration-services/drop-in-schedules/"
TARGET_SPORTS = {"pickleball", "badminton", "table-tennis", "squash"}
TIME_RANGE_RE = re.compile(
    r"(\d{1,2}:\d{2})\s*(am|pm)?\s*-\s*(\d{1,2}:\d{2})\s*(am|pm)",
    re.I,
)
MONTH_TOKEN = r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
DATE_WINDOW_RE = re.compile(
    rf"({MONTH_TOKEN})[a-z]*\.?\s+(\d{{1,2}})\s*[-–]\s*(?:({MONTH_TOKEN})[a-z]*\.?\s+)?(\d{{1,2}})",
    re.I,
)
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

    def _discover_pdf_url(self) -> str:
        response = self.session.get(DROPIN_PAGE_URL, timeout=30)
        response.raise_for_status()
        matches = re.findall(r'https://www\.oakbay\.ca/wp-content/uploads/[^"\']+RacquetSports[^"\']+\.pdf', response.text, re.I)
        if not matches:
            raise ValueError("Could not find Oak Bay racquet PDF")
        return matches[0]

    def _fetch_layout_text(self, pdf_url: str) -> str:
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        return reader.pages[0].extract_text(extraction_mode="layout") or ""

    def _split_day_columns(self, layout_text: str) -> dict[str, list[str]]:
        lines = layout_text.splitlines()
        header_index = next(i for i, line in enumerate(lines) if "Monday" in line and "Sunday" in line)
        header_line = lines[header_index]

        days = list(DAY_TO_INDEX.keys())
        # Split on the midpoint between column centres. Splitting on the midpoint
        # between the header word starts drifts right of the real column edge and
        # slices a character off the neighbouring cell.
        centres = [header_line.index(day) + len(day) / 2 for day in days]
        boundaries = [0]
        for idx in range(len(centres) - 1):
            boundaries.append(int((centres[idx] + centres[idx + 1]) // 2))
        # Content lines can run past the header, so let the last column absorb the rest.
        boundaries.append(max(len(line) for line in lines) + 1)

        columns = {day: [] for day in days}
        for line in lines[header_index + 1 :]:
            if "Monterey Middle School" in line:
                break
            for idx, day in enumerate(days):
                start = boundaries[idx]
                end = boundaries[idx + 1]
                # Keep blank segments: a vertical gap in a column ends that cell,
                # and dropping them lets one cell's text run into the next one.
                columns[day].append(line[start:end].strip())

        return {day: self._join_split_times(segments) for day, segments in columns.items()}

    def _join_split_times(self, segments: list[str]) -> list[str]:
        """Rejoin a time range that the PDF wrapped across two lines ("11:15am-" / "12:15pm")."""
        joined: list[str] = []
        index = 0
        while index < len(segments):
            current = segments[index]
            if (
                re.search(r"\d{1,2}:\d{2}\s*(?:am|pm)?\s*-$", current, re.I)
                and index + 1 < len(segments)
                and re.match(r"^\d{1,2}:\d{2}\s*(?:am|pm)", segments[index + 1], re.I)
            ):
                joined.append(f"{current} {segments[index + 1]}")
                index += 2
                continue
            joined.append(current)
            index += 1
        return joined

    def _time_match(self, line: str):
        return TIME_RANGE_RE.search(line.replace("*", ""))

    def _is_time_line(self, line: str) -> bool:
        return self._time_match(line) is not None

    def _is_note_line(self, line: str) -> bool:
        compact = " ".join(line.split())
        return (
            compact.startswith("(")
            or compact.startswith("*")
            or "May & June" in compact
            or "Ends June" in compact
            or "Friday, May 1" in compact
            or bool(DATE_WINDOW_RE.fullmatch(compact))
        )

    def _parse_date_window(self, note: str, year: int) -> tuple[date, date] | None:
        """Read a 'Aug 9-Sept 6' style run-window off a cell note."""
        match = DATE_WINDOW_RE.search(note)
        if not match:
            return None
        start_month, start_day, end_month, end_day = match.groups()
        try:
            start = datetime.strptime(f"{start_month[:3]} {start_day} {year}", "%b %d %Y").date()
            end = datetime.strptime(
                f"{(end_month or start_month)[:3]} {end_day} {year}", "%b %d %Y"
            ).date()
        except ValueError:
            return None
        if end < start:
            end = end.replace(year=end.year + 1)
        return start, end

    def _parse_time_range(self, raw: str) -> tuple[str, str]:
        # Pull the range out of the cell rather than assuming the cell is only a
        # time, so a stray character from an adjacent column cannot break the row.
        match = self._time_match(raw)
        if not match:
            raise ValueError(f"Unparseable time range: {raw}")

        start_clock, start_meridiem, end_clock, end_meridiem = match.groups()
        end_meridiem = end_meridiem.lower()
        start_meridiem = (start_meridiem or end_meridiem).lower()

        return f"{start_clock}{start_meridiem}", f"{end_clock}{end_meridiem}"

    def _parse_day_events(self, lines: list[str]) -> list[dict]:
        events = []
        title_lines: list[str] = []

        for raw_line in lines:
            line = " ".join(raw_line.split())
            if not line:
                # A gap closes the current cell, so partial text above it never
                # gets glued onto the next activity's title.
                title_lines = []
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
        window = self._parse_date_window(note, occurrence_date.year)
        if window and not (window[0] <= occurrence_date <= window[1]):
            return False

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

    def _build_occurrences(self, weekday: str, events: list[dict], pdf_url: str) -> list[dict]:
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

                    try:
                        start_dt = datetime.strptime(
                            f"{current.isoformat()} {event['start_time_str']}",
                            "%Y-%m-%d %I:%M%p",
                        )
                        end_dt = datetime.strptime(
                            f"{current.isoformat()} {event['end_time_str']}",
                            "%Y-%m-%d %I:%M%p",
                        )
                    except ValueError:
                        # The published PDF carries the occasional impossible clock
                        # time (e.g. 6:60pm); drop that row instead of the whole run.
                        print(
                            f"[{self.municipality}] Skipping invalid Oak Bay time "
                            f"'{event['raw_time'].strip()}' for {event['title']}"
                        )
                        continue
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
                            "booking_url": pdf_url,
                        }
                    )
            current += timedelta(days=1)

        return occurrences

    def scrape(self):
        print(f"[{self.municipality}] Starting Oak Bay PDF scrape...")
        try:
            pdf_url = self._discover_pdf_url()
            layout_text = self._fetch_layout_text(pdf_url)
            columns = self._split_day_columns(layout_text)
        except Exception as exc:
            print(f"[{self.municipality}] Oak Bay PDF discovery failed: {exc}")
            return []

        all_events = []
        seen_ids = set()

        for weekday, lines in columns.items():
            day_events = self._parse_day_events(lines)
            for event in self._build_occurrences(weekday, day_events, pdf_url):
                if event["source_id"] in seen_ids:
                    continue
                seen_ids.add(event["source_id"])
                all_events.append(event)

        print(f"[{self.municipality}] Oak Bay PDF normalized {len(all_events)} events.")
        self.save_events(all_events)
        return all_events
