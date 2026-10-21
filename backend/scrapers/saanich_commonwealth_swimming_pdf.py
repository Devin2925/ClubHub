import hashlib
import re
from datetime import date, datetime, timedelta
from io import BytesIO
from urllib.parse import urljoin

import pdfplumber
import requests

from models import Event, SessionLocal
from scrapers.base import BaseScraper, strip_html


PAGE_URL = "https://www.saanich.ca/EN/main/parks-recreation-community/recreation/schedules/swimming.html"
VENUE_NAME = "Saanich Commonwealth Place"
DAY_ORDER = ["MON", "TUES", "WED", "THURS", "FRI", "SAT", "SUN"]
MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
MONTH_ALIASES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
WEEK_WINDOW_RE = re.compile(
    rf"({MONTHS}|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{{1,2}})\s*[-–]\s*(?:({MONTHS}|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+)?(\d{{1,2}})",
    re.I,
)
# A start time may omit am/pm ("10:15-3:30pm"); asterisks mark lane counts or cell notes.
TIME_RE = re.compile(
    r"(\*{0,2})\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)?\s*[-–]\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)\s*(\*{0,2})",
    re.I,
)
# Rows at or below these labels are legend text, not schedule grid.
STOP_RE = re.compile(r"Swim\s+Descriptions|No\s+Lengths\s+Available", re.I)

# Grid rows that are not published as activities.
SKIPPED_ROWS_RE = re.compile(r"Special\s+Notes", re.I)

SWIM_ROWS = [
    ("Leisure Swims", r"Leisure\s+Swims"),
    ("Fun Swims", r"Fun\s+Swims"),
    ("Open Swims", r"Open\s+Swims"),
    ("Water Slide", r"Water\s+Slide"),
    ("Lessons & Leisure", r"Lessons\s*&\s*Leisure"),
]
# Order matters: "Teach Pool Lengths" must not be taken for a shared walking row.
LENGTH_ROWS = [
    ("25m Short Course Lengths", r"25\s*m\s+Short\s+Course"),
    ("50m Long Course Lengths", r"50\s*m\s+Long\s+Course"),
    ("Shallow Water Walking", r"Shallow\s+Water\s+Walking"),
    ("Deep Water Walking", r"Deep\s+Water\s+Walking"),
    ("Teach Pool Lengths", r"Teach\s+Pool"),
    ("Dive Tank Lengths", r"Dive\s+Tank"),
]
SCHEDULE_KINDS = {
    "swim": {
        "rows": SWIM_ROWS,
        "description": "Public swim session from the Saanich Commonwealth Place weekly swim schedule.",
    },
    "lengths": {
        "rows": LENGTH_ROWS,
        "description": "Lane swimming from the Saanich Commonwealth Place weekly lengths schedule.",
    },
}
LANE_NOTES = {"*": "1-2 lanes", "**": "3-4 lanes", "": "5+ lanes"}
# Leaves room for doubled rules and small gaps where a ruling line is drawn in segments.
FULL_RULE_COVERAGE = 0.9


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

    def _current_closure_window(self) -> tuple[date, date] | None:
        response = self.session.get(PAGE_URL, timeout=30)
        response.raise_for_status()
        text = " ".join(strip_html(response.text).split())
        match = re.search(
            r"([A-Z][a-z]+)\s+(\d{1,2})\s*[-–]\s*(?:([A-Z][a-z]+)\s+)?(\d{1,2})\s*[-–]\s*Annual Maintenance Closure",
            text,
        )
        if not match:
            return None
        start_month, start_day, end_month, end_day = match.groups()
        today = date.today()
        start = date(today.year, MONTH_ALIASES[start_month.lower()], int(start_day))
        end = date(today.year, MONTH_ALIASES[(end_month or start_month).lower()], int(end_day))
        if end < start:
            end = end.replace(year=end.year + 1)
        if start <= today <= end:
            return start, end
        return None

    def _read_pdf(self, pdf_url: str) -> dict:
        """Return page 1's plain text, positioned words, and full-width ruling lines."""
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        with pdfplumber.open(BytesIO(response.content)) as pdf:
            page = pdf.pages[0]
            return {
                "text": page.extract_text() or "",
                "words": page.extract_words(x_tolerance=1.5, y_tolerance=2),
                "rules": self._full_width_rules(page),
            }

    @staticmethod
    def _full_width_rules(page) -> list[float]:
        """Y positions of horizontal lines spanning the table, which separate grid rows."""
        segments: dict[int, list[tuple[float, float]]] = {}
        for edge in page.horizontal_edges:
            segments.setdefault(round(edge["top"]), []).append((edge["x0"], edge["x1"]))
        spans = {y: (min(a for a, _ in segs), max(b for _, b in segs)) for y, segs in segments.items()}
        table_left = min(left for left, _ in spans.values())
        table_right = max(right for _, right in spans.values())
        width = table_right - table_left

        rules = []
        for y, segs in segments.items():
            covered, reach = 0.0, table_left
            for start, end in sorted(segs):
                start = max(start, reach)
                if end > start:
                    covered += end - start
                    reach = end
            if covered >= width * FULL_RULE_COVERAGE:
                rules.append(float(y))
        return sorted(rules)

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
        start = date(today.year, MONTH_ALIASES[start_month.lower()], int(start_day))
        end = date(today.year, MONTH_ALIASES[end_month.lower()], int(end_day))
        if end < start:
            end = end.replace(year=end.year + 1)
        # A schedule published across the new year can name a month already behind us.
        if (today - end).days > 180:
            start = start.replace(year=start.year + 1)
            end = end.replace(year=end.year + 1)
        return start, end

    def _day_columns(self, words: list[dict], week_start: date, pdf_url: str):
        """Locate the day header, verify its day numbers, and return per-day column bounds."""
        by_line: dict[int, list[dict]] = {}
        for word in words:
            by_line.setdefault(round(word["top"]), []).append(word)

        for line in by_line.values():
            line = sorted(line, key=lambda w: w["x0"])
            texts = [w["text"].upper() for w in line]
            if "MON" not in texts or "SUN" not in texts:
                continue
            centers, dates = [], {}
            for index, day in enumerate(DAY_ORDER):
                if day not in texts:
                    raise ValueError(f"Missing {day} column in {pdf_url}")
                position = texts.index(day)
                number_word = line[position + 1] if position + 1 < len(line) else None
                expected = week_start + timedelta(days=index)
                if not number_word or number_word["text"] != str(expected.day):
                    raise ValueError(
                        f"Day column {day} does not match expected {expected.isoformat()} in {pdf_url}"
                    )
                dates[day] = expected
                centers.append((line[position]["x0"] + number_word["x1"]) / 2)

            gaps = [b - a for a, b in zip(centers, centers[1:])]
            bounds = [centers[0] - gaps[0] / 2]
            bounds += [(a + b) / 2 for a, b in zip(centers, centers[1:])]
            bounds.append(centers[-1] + gaps[-1] / 2)
            return dates, bounds, line[0]["bottom"]

        raise ValueError(f"Could not locate day header row in {pdf_url}")

    @staticmethod
    def _column_for(word: dict, bounds: list[float]) -> int | None:
        center = (word["x0"] + word["x1"]) / 2
        for index in range(len(bounds) - 1):
            if bounds[index] <= center < bounds[index + 1]:
                return index
        return None

    def _pool_hours_line(self, words: list[dict], bounds: list[float], header_bottom: float):
        """The first line under the day header holds one opening-hours range per day."""
        lines: dict[int, list[dict]] = {}
        for word in words:
            if word["top"] >= header_bottom - 1:
                lines.setdefault(round(word["top"]), []).append(word)
        for top in sorted(lines):
            line = [w for w in lines[top] if TIME_RE.fullmatch(w["text"].strip())]
            if len(line) < len(DAY_ORDER) - 2:
                continue
            hours = {}
            for word in line:
                column = self._column_for(word, bounds)
                if column is not None:
                    hours[column] = self._pool_hours(word["text"])
            return hours, {id(w) for w in line}
        return {}, set()

    def _grid_cells(self, pdf: dict, bounds: list[float], header_bottom: float, pdf_url: str, skip_ids=frozenset()):
        """Yield (row label, {day index: cell text}) for each ruled row below the header."""
        rules = [y for y in pdf["rules"] if y >= header_bottom - 1]
        if len(rules) < 2:
            raise ValueError(f"Could not find ruled grid rows in {pdf_url}")

        for top, bottom in zip(rules, rules[1:]):
            band = [
                w for w in pdf["words"]
                if top <= (w["top"] + w["bottom"]) / 2 < bottom and id(w) not in skip_ids
            ]
            if not band:
                continue
            band.sort(key=lambda w: (round(w["top"]), w["x0"]))
            label = " ".join(w["text"] for w in band if w["x1"] <= bounds[0] + 2)
            if STOP_RE.search(label):
                return
            cells: dict[int, list[str]] = {}
            for word in band:
                if word["x1"] <= bounds[0] + 2:
                    continue
                column = self._column_for(word, bounds)
                if column is None:
                    continue
                cells.setdefault(column, []).append(word["text"])
            yield label, {day: " ".join(parts) for day, parts in cells.items()}

    def _match_row(self, label: str, rows: list[tuple[str, str]]) -> str | None:
        for title, pattern in rows:
            if re.search(pattern, label, re.I):
                return title
        return None

    @staticmethod
    def _clock(value: str, meridiem: str) -> datetime:
        if ":" not in value:
            value = f"{value}:00"
        return datetime.strptime(f"{value}{meridiem.lower()}", "%I:%M%p")

    def _resolve_times(self, start_raw, start_mer, end_raw, end_mer, hours):
        """Resolve a range to clock times, fixing a missing or mistyped meridiem
        against the day's pool hours (e.g. "3:30-9am" between afternoon slots)."""
        candidates = []
        if start_mer:
            candidates.append((start_mer, end_mer))
        else:
            candidates += [(end_mer, end_mer), ("am", end_mer)]
        candidates.append(("pm", "pm"))

        for s_mer, e_mer in candidates:
            start = self._clock(start_raw, s_mer)
            end = self._clock(end_raw, e_mer)
            if end <= start:
                continue
            if hours and not (hours[0] <= start.time() and end.time() <= hours[1]):
                continue
            return start.time(), end.time()
        return None

    def _pool_hours(self, cell: str):
        match = TIME_RE.search(cell or "")
        if not match:
            return None
        _, start_raw, start_mer, end_raw, end_mer, _ = match.groups()
        start = self._clock(start_raw, start_mer or end_mer)
        end = self._clock(end_raw, end_mer)
        return (start.time(), end.time()) if end > start else None

    def _sessions_from_pdf(self, pdf: dict, kind: str, week_start: date, pdf_url: str):
        config = SCHEDULE_KINDS[kind]
        day_dates, bounds, header_bottom = self._day_columns(pdf["words"], week_start, pdf_url)
        pool_hours, pool_hour_ids = self._pool_hours_line(pdf["words"], bounds, header_bottom)
        if not pool_hours:
            raise ValueError(f"Could not find pool hours under the day header in {pdf_url}")
        sessions = []
        matched_rows = set()

        for label, cells in self._grid_cells(pdf, bounds, header_bottom, pdf_url, pool_hour_ids):
            if SKIPPED_ROWS_RE.search(label):
                continue
            has_times = any(TIME_RE.search(text) for text in cells.values())
            if not has_times:
                continue
            title = self._match_row(label, config["rows"])
            if not title:
                if has_times:
                    raise ValueError(f"Unrecognized schedule row '{label}' in {pdf_url}")
                continue
            matched_rows.add(title)

            for day_index, text in cells.items():
                event_date = day_dates[DAY_ORDER[day_index]]
                notes = " ".join(TIME_RE.sub(" ", text).replace("*", " ").split())
                for match in TIME_RE.finditer(text):
                    lead, start_raw, start_mer, end_raw, end_mer, trail = match.groups()
                    marker = lead or trail
                    if kind == "swim" and marker and re.search(r"no\s+leisure\s+space", notes, re.I):
                        continue
                    resolved = self._resolve_times(
                        start_raw, start_mer, end_raw, end_mer, pool_hours.get(day_index)
                    )
                    if not resolved:
                        print(
                            f"[{self.municipality}] Skipping unreadable time '{match.group(0).strip()}' "
                            f"for {title} on {event_date.isoformat()}"
                        )
                        continue
                    description = config["description"]
                    if kind == "lengths":
                        description = f"{description} {LANE_NOTES.get(marker, '5+ lanes')} available."
                    elif marker and notes:
                        description = f"{notes}. {description}"
                    sessions.append(
                        {
                            "title": title,
                            "start": datetime.combine(event_date, resolved[0]),
                            "end": datetime.combine(event_date, resolved[1]),
                            "description": description,
                        }
                    )

        if not matched_rows:
            raise ValueError(f"No known schedule rows found in {pdf_url}")
        return sessions

    def _other_source_keys(self, start_date: date, end_date: date) -> set[tuple[str, datetime]]:
        """Sessions already published by another source (Active Communities) for this venue."""
        db = SessionLocal()
        try:
            rows = (
                db.query(Event)
                .filter(Event.venue_name == self.venue_name)
                .filter(Event.source != self.source_id_prefix)
                .filter(Event.start_time >= datetime.combine(start_date, datetime.min.time()))
                .filter(Event.start_time < datetime.combine(end_date + timedelta(days=1), datetime.min.time()))
                .all()
            )
            return {(row.title, row.start_time.replace(microsecond=0)) for row in rows}
        finally:
            db.close()

    def scrape(self):
        print(f"[{self.municipality}] Starting Commonwealth swimming PDF scrape...")
        today = date.today()
        schedules = []
        for pdf_url in self._candidate_pdf_urls():
            try:
                pdf = self._read_pdf(pdf_url)
            except Exception as exc:
                print(f"[{self.municipality}] Could not read {pdf_url}: {exc}")
                continue
            kind = self._classify(pdf["text"])
            if not kind:
                continue
            try:
                week_start, week_end = self._parse_week_window(pdf["text"], pdf_url)
            except ValueError as exc:
                print(f"[{self.municipality}] {exc}")
                continue
            if week_end < today:
                continue
            schedules.append((pdf_url, kind, pdf, week_start, week_end))

        if not schedules:
            closure = self._current_closure_window()
            if closure:
                start, end = closure
                print(
                    f"[{self.municipality}] Commonwealth swimming PDF skipped: "
                    f"maintenance closure {start.isoformat()} to {end.isoformat()}."
                )
                self.last_reported_count = 0
                self.last_status_note = (
                    f"planned_closure: maintenance closure {start.isoformat()} to {end.isoformat()}"
                )
                self.replace_existing_events()
                return []
            raise ValueError("Could not find current Commonwealth swimming PDFs")

        start_date = min(item[3] for item in schedules)
        end_date = max(item[4] for item in schedules)
        other_keys = self._other_source_keys(start_date, end_date)

        events: list[dict] = []
        seen: set[tuple[str, datetime]] = set()
        failures = []
        for pdf_url, kind, pdf, week_start, _ in schedules:
            try:
                sessions = self._sessions_from_pdf(pdf, kind, week_start, pdf_url)
            except ValueError as exc:
                failures.append(str(exc))
                print(f"[{self.municipality}] Skipping schedule: {exc}")
                continue
            for session in sessions:
                if session["start"].date() < today:
                    continue
                key = (session["title"], session["start"])
                if key in seen or key in other_keys:
                    continue
                seen.add(key)
                source_key = f"{self.venue_name}|{session['title']}|{session['start'].isoformat()}"
                source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
                events.append(
                    {
                        "source_id": f"{self.source_id_prefix}_{source_hash}",
                        "title": session["title"],
                        "venue_name": self.venue_name,
                        "facility_name": "Pool",
                        "start_time": session["start"],
                        "end_time": session["end"],
                        "price": "",
                        "description": session["description"],
                        "booking_url": pdf_url,
                    }
                )

        if not events:
            raise ValueError(
                "Commonwealth swimming PDFs produced no rows: " + "; ".join(failures)
            )

        self.last_reported_count = len(events)
        print(
            f"[{self.municipality}] Commonwealth swimming PDF parsed {len(events)} sessions "
            f"from {len(schedules) - len(failures)} of {len(schedules)} schedules."
        )
        # Each run republishes the current weekly PDFs in full, so stale sessions drop out.
        self.replace_existing_events()
        self.save_events(events)
        return events
