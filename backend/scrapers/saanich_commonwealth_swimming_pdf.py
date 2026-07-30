import hashlib
import re
from datetime import date, datetime, timedelta
from io import BytesIO
from urllib.parse import urljoin

import requests
from pypdf import PdfReader

from models import Event, SessionLocal
from scrapers.base import BaseScraper


PAGE_URL = "https://www.saanich.ca/EN/main/parks-recreation-community/recreation/schedules/swimming.html"
VENUE_NAME = "Saanich Commonwealth Place"
DAY_ORDER = ["MON", "TUES", "WED", "THURS", "FRI", "SAT", "SUN"]
TIME_RANGE_RE = re.compile(
    r"\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*-\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)",
    re.I,
)
MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
WEEK_WINDOW_RE = re.compile(
    rf"({MONTHS})\s+(\d{{1,2}})\s*[-–]\s*(?:({MONTHS})\s+)?(\d{{1,2}})",
    re.I,
)
# Everything after any of these markers is legend/description text, not schedule grid.
STOP_RE = re.compile(
    r"(All times subject to change|Swim Descriptions|No Lengths Available)", re.I
)

# The two leading grid rows are not published as activities, but they must stay in the
# row sequence so the schedule grid stays aligned while rows are consumed in order.
LEAD_ROWS = [
    ("Pool Hours", r"Pool\s+Hours"),
    ("Special Notes", r"Special\s+Notes"),
]
SWIM_ROWS = [
    ("Leisure Swims", r"Leisure\s+Swims"),
    ("Fun Swims", r"Fun\s+Swims"),
    ("Open Swims", r"Open\s+Swims"),
    ("Water Slide", r"Water\s+Slide"),
    ("Lessons & Leisure", r"Lessons\s*&\s*Leisure"),
]
LENGTH_ROWS = [
    ("25m Short Course Lengths", r"25\s*M\s+Short\s+Course"),
    ("50m Long Course Lengths", r"50\s*M\s+Long\s+Course"),
    ("Teach Pool Lengths", r"Teach\s+Pool\s+Lengths"),
    ("Shallow Water Walking", r"Shallow\s+Water\s+Walking"),
    ("Dive Tank Lengths", r"Dive\s+Tank\s+Lengths"),
    ("Deep Water Walking", r"Deep\s+Water\s+Walking"),
]
SCHEDULE_KINDS = {
    "swim": {
        "rows": SWIM_ROWS,
        "description": "Saanich Commonwealth public swim schedule PDF.",
    },
    "lengths": {
        "rows": LENGTH_ROWS,
        "description": "Saanich Commonwealth public lengths schedule PDF.",
    },
}


class SaanichCommonwealthSwimmingPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__("saanich_commonwealth_swimming_pdf", "Saanich")
        self.venue_name = VENUE_NAME
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.last_reported_count = 0

    def _candidate_pdf_urls(self) -> list[str]:
        response = self.session.get(PAGE_URL, timeout=30)
        response.raise_for_status()
        links = re.findall(r'href="([^"]+\.pdf)"', response.text, re.I)
        pdfs = []
        for link in links:
            absolute = urljoin(PAGE_URL, link)
            if "/commonwealth_place/" in absolute.lower():
                pdfs.append(absolute)
        return sorted(set(pdfs))

    def _read_pdf(self, pdf_url: str) -> tuple[str, str]:
        """Return (reading-order text, layout-preserving text) for page 1."""
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        page = PdfReader(BytesIO(response.content)).pages[0]
        return (
            page.extract_text() or "",
            page.extract_text(extraction_mode="layout") or "",
        )

    def _classify(self, plain_text: str) -> str | None:
        """Identify the schedule type from the PDF's own heading, not its filename."""
        head = " ".join(plain_text[:400].split()).upper()
        if "LENGTHS" in head:
            return "lengths"
        if "SWIM SCHEDULE" in head:
            return "swim"
        return None

    def _parse_week_window(self, plain_text: str, pdf_url: str) -> tuple[date, date]:
        match = WEEK_WINDOW_RE.search(plain_text)
        if not match:
            raise ValueError(f"Could not parse Commonwealth week window from {pdf_url}")

        start_month, start_day, end_month, end_day = match.groups()
        end_month = end_month or start_month
        today = date.today()
        start = datetime.strptime(
            f"{start_month} {start_day} {today.year}", "%B %d %Y"
        ).date()
        end = datetime.strptime(f"{end_month} {end_day} {today.year}", "%B %d %Y").date()
        if end < start:
            end = end.replace(year=end.year + 1)
        # A schedule published across the new year can name a month already behind us.
        if (today - end).days > 180:
            start = start.replace(year=start.year + 1)
            end = end.replace(year=end.year + 1)
        return start, end

    def _day_dates(self, layout_text: str, week_start: date, pdf_url: str) -> dict[str, date]:
        """Map each day column to a real date, verified against the header day numbers."""
        header = self._header_line(layout_text, pdf_url)
        dates: dict[str, date] = {}
        for index, day in enumerate(DAY_ORDER):
            match = re.search(rf"\b{day}\s+(\d{{1,2}})\b", header)
            if not match:
                raise ValueError(f"Missing {day} column in {pdf_url}")
            event_date = week_start + timedelta(days=index)
            if event_date.day != int(match.group(1)):
                raise ValueError(
                    f"Day column {day} {match.group(1)} does not match "
                    f"expected {event_date.isoformat()} in {pdf_url}"
                )
            dates[day] = event_date
        return dates

    def _header_line(self, layout_text: str, pdf_url: str) -> str:
        for line in layout_text.splitlines():
            if re.search(r"\bMON\s+\d", line) and re.search(r"\bSUN\s+\d", line):
                return line
        raise ValueError(f"Could not locate day header row in {pdf_url}")

    def _row_sequence(self, plain_text: str, rows: list[tuple[str, str]]) -> list[tuple[str, list[str]]]:
        """Ordered (title, times) straight from reading order, which never mixes rows up."""
        flat = re.sub(r"[ \t]+", " ", plain_text)
        marks = []
        for title, pattern in rows:
            match = re.search(pattern, flat, re.I)
            if match:
                marks.append((match.start(), match.end(), title))
        if not marks:
            return []
        marks.sort()

        stop = STOP_RE.search(flat, marks[0][0])
        hard_stop = stop.start() if stop else len(flat)

        sequence = []
        for index, (_, label_end, title) in enumerate(marks):
            end = marks[index + 1][0] if index + 1 < len(marks) else hard_stop
            end = min(end, hard_stop)
            segment = flat[label_end:end] if label_end < end else ""
            sequence.append(
                (title, [self._normalize(v) for v in TIME_RANGE_RE.findall(segment)])
            )
        return sequence

    def _grid_lines(self, layout_text: str, pdf_url: str) -> list[dict[str, list[str]]]:
        """Per-line day cells, using the day header to fix column boundaries."""
        lines = layout_text.splitlines()
        header = self._header_line(layout_text, pdf_url)
        header_index = lines.index(header)

        starts = []
        for day in DAY_ORDER:
            match = re.search(rf"\b{day}\s+\d{{1,2}}\b", header)
            starts.append(match.start())
        bounds = [0]
        for index in range(len(starts) - 1):
            bounds.append((starts[index] + starts[index + 1]) // 2)
        bounds.append(len(header) + 10_000)

        grid = []
        for line in lines[header_index + 1 :]:
            if STOP_RE.search(line):
                break
            cells = {}
            for index, day in enumerate(DAY_ORDER):
                segment = line[bounds[index] : bounds[index + 1]]
                found = [self._normalize(v) for v in TIME_RANGE_RE.findall(segment)]
                if found:
                    cells[day] = found
            if cells:
                grid.append(cells)
        return grid

    def _assign_rows(
        self,
        sequence: list[tuple[str, list[str]]],
        grid: list[dict[str, list[str]]],
        pdf_url: str,
    ) -> dict[str, dict[str, list[str]]]:
        """Walk grid lines in order, consuming each row's known time count.

        Reading order fixes which row a time belongs to and the grid fixes which day,
        so a layout change that breaks the pairing raises instead of publishing
        times under the wrong pool or the wrong day.
        """
        assigned: dict[str, dict[str, list[str]]] = {title: {} for title, _ in sequence}
        row_index = 0
        remaining = list(sequence[0][1]) if sequence else []

        for cells in grid:
            count = sum(len(values) for values in cells.values())
            while row_index < len(sequence) and not remaining:
                row_index += 1
                if row_index < len(sequence):
                    remaining = list(sequence[row_index][1])
            if row_index >= len(sequence):
                raise ValueError(f"Schedule grid has more rows than expected in {pdf_url}")
            if count > len(remaining):
                raise ValueError(
                    f"Row '{sequence[row_index][0]}' expected {len(remaining)} more times "
                    f"but grid line holds {count} in {pdf_url}"
                )
            title = sequence[row_index][0]
            for day, values in cells.items():
                assigned[title].setdefault(day, []).extend(values)
            del remaining[:count]

        for title, expected in sequence:
            mapped = sum(len(values) for values in assigned[title].values())
            if mapped != len(expected):
                raise ValueError(
                    f"Row '{title}' mapped {mapped} of {len(expected)} times in {pdf_url}"
                )
        return assigned

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", "", value).lower()

    def _parse_time_range(self, value: str) -> tuple[str, str]:
        compact = value.replace(" ", "").lower()
        start_raw, end_raw = compact.split("-", 1)
        start_match = re.fullmatch(r"(\d{1,2}(?::\d{2})?)(am|pm)", start_raw)
        end_match = re.fullmatch(r"(\d{1,2}(?::\d{2})?)(am|pm)", end_raw)
        if not start_match or not end_match:
            raise ValueError(f"Unparseable time range: {value}")
        start_clock, start_meridiem = start_match.groups()
        end_clock, end_meridiem = end_match.groups()
        if ":" not in start_clock:
            start_clock = f"{start_clock}:00"
        if ":" not in end_clock:
            end_clock = f"{end_clock}:00"
        return f"{start_clock}{start_meridiem}", f"{end_clock}{end_meridiem}"

    def _existing_keys(self, start_date: date, end_date: date) -> set[tuple[str, str, str]]:
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
                (
                    row.venue_name,
                    row.title,
                    row.start_time.replace(microsecond=0).isoformat(sep=" "),
                )
                for row in rows
            }
        finally:
            db.close()

    def _append_missing_event(
        self,
        events: list[dict],
        existing_keys: set[tuple[str, str, str]],
        reported_keys: set[tuple[str, str, str]],
        *,
        title: str,
        start_dt: datetime,
        end_dt: datetime,
        pdf_url: str,
        description: str,
    ):
        existing_key = (
            self.venue_name,
            title,
            start_dt.replace(microsecond=0).isoformat(sep=" "),
        )
        reported_keys.add(existing_key)
        if existing_key in existing_keys:
            return

        source_key = f"{self.venue_name}|{title}|{start_dt.isoformat()}|{pdf_url}"
        source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
        events.append(
            {
                "source_id": f"{self.source_id_prefix}_{source_hash}",
                "title": title,
                "venue_name": self.venue_name,
                "facility_name": "Pool",
                "start_time": start_dt,
                "end_time": end_dt,
                "price": "",
                "description": description,
                "booking_url": pdf_url,
            }
        )
        existing_keys.add(existing_key)

    def _events_from_pdf(
        self,
        pdf_url: str,
        kind: str,
        plain_text: str,
        layout_text: str,
        week_start: date,
        events: list[dict],
        existing_keys: set[tuple[str, str, str]],
        reported_keys: set[tuple[str, str, str]],
    ):
        config = SCHEDULE_KINDS[kind]
        day_dates = self._day_dates(layout_text, week_start, pdf_url)
        sequence = self._row_sequence(plain_text, LEAD_ROWS + config["rows"])
        publishable = {title for title, _ in config["rows"]}
        if not any(title in publishable for title, _ in sequence):
            raise ValueError(f"No known schedule rows found in {pdf_url}")

        grid = self._grid_lines(layout_text, pdf_url)
        assigned = self._assign_rows(sequence, grid, pdf_url)
        today = date.today()

        for title in (row_title for row_title, _ in config["rows"]):
            for day, values in assigned.get(title, {}).items():
                event_date = day_dates[day]
                if event_date < today:
                    continue
                for value in values:
                    start_raw, end_raw = self._parse_time_range(value)
                    start_dt = datetime.strptime(
                        f"{event_date.isoformat()} {start_raw}", "%Y-%m-%d %I:%M%p"
                    )
                    end_dt = datetime.strptime(
                        f"{event_date.isoformat()} {end_raw}", "%Y-%m-%d %I:%M%p"
                    )
                    if end_dt <= start_dt:
                        end_dt += timedelta(days=1)
                    self._append_missing_event(
                        events,
                        existing_keys,
                        reported_keys,
                        title=title,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        pdf_url=pdf_url,
                        description=config["description"],
                    )

    def scrape(self):
        print(f"[{self.municipality}] Starting Commonwealth swimming PDF scrape...")
        today = date.today()
        schedules = []
        for pdf_url in self._candidate_pdf_urls():
            try:
                plain_text, layout_text = self._read_pdf(pdf_url)
            except Exception as exc:
                print(f"[{self.municipality}] Could not read {pdf_url}: {exc}")
                continue
            kind = self._classify(plain_text)
            if not kind:
                continue
            try:
                week_start, week_end = self._parse_week_window(plain_text, pdf_url)
            except ValueError as exc:
                print(f"[{self.municipality}] {exc}")
                continue
            if week_end < today:
                continue
            schedules.append((pdf_url, kind, plain_text, layout_text, week_start, week_end))

        if not schedules:
            raise ValueError("Could not find current Commonwealth swimming PDFs")

        start_date = min(item[4] for item in schedules)
        end_date = max(item[5] for item in schedules)
        existing_keys = self._existing_keys(start_date, end_date)

        events: list[dict] = []
        reported_keys: set[tuple[str, str, str]] = set()
        failures = []
        for pdf_url, kind, plain_text, layout_text, week_start, _ in schedules:
            try:
                self._events_from_pdf(
                    pdf_url,
                    kind,
                    plain_text,
                    layout_text,
                    week_start,
                    events,
                    existing_keys,
                    reported_keys,
                )
            except ValueError as exc:
                failures.append(str(exc))
                print(f"[{self.municipality}] Skipping schedule: {exc}")

        if not reported_keys:
            raise ValueError(
                "Commonwealth swimming PDFs produced no rows: " + "; ".join(failures)
            )

        self.last_reported_count = len(reported_keys)
        print(
            f"[{self.municipality}] Commonwealth swimming PDF recognized {self.last_reported_count} rows, "
            f"adding {len(events)} missing events."
        )
        self.save_events(events)
        return events
