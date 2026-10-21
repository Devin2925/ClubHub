import hashlib
import re
from datetime import date, datetime, time, timedelta
from io import BytesIO
from urllib.parse import urljoin

import pdfplumber
import requests

from models import Event, SessionLocal
from scrapers.base import BaseScraper
from scrapers.saanich_commonwealth_swimming_pdf import SaanichCommonwealthSwimmingPDFScraper


PAGE_URL = "https://www.saanich.ca/EN/main/parks-recreation-community/recreation/schedules/skating.html"
VENUE_NAME = "G. R. Pearkes Recreation Centre"
DAY_ORDER = ["MON", "TUES", "WED", "THURS", "FRI", "SAT", "SUN"]
MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
TIME_RE = re.compile(
    r"(\*{0,2})(\d{1,2}(?::\d{2})?)\s*(am|pm)?\s*[-–]\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)",
    re.I,
)
MONTH_DAY_RE = re.compile(rf"\b({MONTHS})[a-z]*\.?\s+(\d{{1,2}})\b", re.I)
RANGE_RE = re.compile(
    rf"\b({MONTHS})[a-z]*\.?\s+(\d{{1,2}})\s*[-–]\s*({MONTHS})[a-z]*\.?\s+(\d{{1,2}}),?\s+(\d{{4}})",
    re.I,
)
UPDATED_RE = re.compile(rf"updated\s+({MONTHS})[a-z]*\s+(\d{{1,2}})", re.I)

# (row label pattern, published titles, family pattern used to spot the same
# session already published by Active Communities under a slightly different title)
ROWS = [
    (r"Everyone\s+Welcome", ["Skate - Everyone Welcome"], r"everyone\s+welcome"),
    (r"Adult\s+and\s+Child\s+Hockey", ["Skate - Parent & Child Hockey Social 5-10yrs"], r"hockey\s+social"),
    (r"Adult\s+and\s+Tot", ["Skate - Adult and Tot Ice Play 1-6yrs"], r"ice\s+play"),
    (r"Adult\s+Skate\s+19", ["Skate - Adult Skate Drop In 19yrs+"], r"adult\s+skate"),
    (r"Adult\s+Figure\s+Skate", ["Skate - Adult Figure Skate Drop In 19yrs+"], r"figure\s+skate"),
    (
        r"Stick\s*&\s*Puck",
        [
            "Skate - Stick & Puck Reserved Drop In 19yrs+ SKATER",
            "Skate - Stick & Puck Reserved Drop In 19yrs+ GOALIE",
        ],
        r"stick\s*&\s*puck",
    ),
    (r"Adult\s+Hockey\s+Scrimmage", ["Skate - Adult Hockey Scrimmage 19yrs+"], r"scrimmage"),
]
# Rows that only carry date notes (themed nights during another session).
SKIPPED_ROWS_RE = re.compile(r"Theme\s+Skates", re.I)
STOP_RE = re.compile(r"Reservations\s+are\s+required|Notes\s*&", re.I)
RESERVATION_NOTE = "Reservation required; bookings open seven days in advance at 7:30am."


def _month(token: str) -> int:
    return datetime.strptime(token[:3].title(), "%b").month


def _clock(value: str, meridiem: str) -> time:
    if ":" not in value:
        value = f"{value}:00"
    return datetime.strptime(f"{value}{meridiem.lower()}", "%I:%M%p").time()


class PearkesPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__("saanich_pearkes_pdf", "Saanich")
        self.venue_name = VENUE_NAME
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.last_reported_count = 0

    def _fetch_pdf(self, pdf_url: str) -> dict:
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        with pdfplumber.open(BytesIO(response.content)) as pdf:
            page = pdf.pages[0].dedupe_chars()
            return {
                "text": page.extract_text() or "",
                "words": page.extract_words(x_tolerance=1.5, y_tolerance=2),
                "rules": SaanichCommonwealthSwimmingPDFScraper._full_width_rules(page),
            }

    def _parse_range(self, text: str) -> tuple[date, date]:
        match = RANGE_RE.search(" ".join(text.split()))
        if not match:
            raise ValueError("Could not parse Pearkes skating schedule dates")
        start_month, start_day, end_month, end_day, year = match.groups()
        start = date(int(year), _month(start_month), int(start_day))
        end = date(int(year), _month(end_month), int(end_day))
        if end < start:
            start = start.replace(year=start.year - 1)
        return start, end

    def _discover_pdf(self) -> tuple[str, dict, date, date]:
        """Pick the current drop-in skating PDF, preferring the latest 'updated' revision."""
        response = self.session.get(PAGE_URL, timeout=30)
        response.raise_for_status()
        candidates = []
        for link in set(re.findall(r'href="([^"]+\.pdf)"', response.text, re.I)):
            absolute = urljoin(PAGE_URL, link)
            lowered = absolute.lower()
            if "dropinskating" not in lowered.replace(" ", "").replace("%20", ""):
                continue
            try:
                pdf = self._fetch_pdf(absolute)
                start, end = self._parse_range(pdf["text"])
            except Exception as exc:
                print(f"[{self.municipality}] Could not read {absolute}: {exc}")
                continue
            if end < date.today():
                continue
            updated = UPDATED_RE.search(absolute.replace("%20", " "))
            revision = (
                date(start.year, _month(updated.group(1)), int(updated.group(2)))
                if updated
                else (date.min if "updated" not in lowered else date.min + timedelta(days=1))
            )
            candidates.append((revision, start, absolute, pdf, end))

        if not candidates:
            raise ValueError("Could not find a current Pearkes skating PDF")
        revision, start, url, pdf, end = max(candidates, key=lambda item: (item[0], item[1], item[2]))
        return url, pdf, start, end

    def _columns(self, words: list[dict]) -> tuple[list[float], float]:
        lines: dict[int, list[dict]] = {}
        for word in words:
            lines.setdefault(round(word["top"]), []).append(word)
        for line in lines.values():
            by_text = {w["text"].upper(): w for w in line}
            if all(day in by_text for day in DAY_ORDER):
                centers = [(by_text[d]["x0"] + by_text[d]["x1"]) / 2 for d in DAY_ORDER]
                gaps = [b - a for a, b in zip(centers, centers[1:])]
                bounds = [centers[0] - gaps[0] / 2]
                bounds += [(a + b) / 2 for a, b in zip(centers, centers[1:])]
                bounds.append(centers[-1] + gaps[-1] / 2)
                return bounds, max(w["bottom"] for w in line)
        raise ValueError("Could not locate Pearkes day header row")

    @staticmethod
    def _resolve(start_raw, start_mer, end_raw, end_mer) -> tuple[time, time] | None:
        options = [start_mer] if start_mer else [end_mer, "am"]
        end = _clock(end_raw, end_mer)
        for meridiem in options:
            start = _clock(start_raw, meridiem)
            if start < end:
                return start, end
        return None

    def _note_rules(self, note: str, year: int) -> tuple[set[date], date | None]:
        excluded: set[date] = set()
        starting = None
        for clause in re.split(r"(?=\bExcept\b|\bStarting\b)", note, flags=re.I):
            dates = []
            month = None
            for token in re.finditer(rf"(?:{MONTHS})[a-z]*\.?|\d{{1,2}}", clause, re.I):
                value = token.group(0)
                if value.isdigit():
                    if month:
                        dates.append(date(year, month, int(value)))
                else:
                    month = _month(value)
            if re.match(r"\s*except", clause, re.I):
                excluded.update(dates)
            elif re.match(r"\s*starting", clause, re.I) and dates:
                starting = dates[0]
        return excluded, starting

    def _sessions(self, pdf: dict, start_date: date, end_date: date):
        bounds, header_bottom = self._columns(pdf["words"])
        rules = [y for y in pdf["rules"] if y >= header_bottom - 1]
        sessions = []
        matched = 0

        for top, bottom in zip(rules, rules[1:]):
            band = [w for w in pdf["words"] if top <= (w["top"] + w["bottom"]) / 2 < bottom]
            if not band:
                continue
            band.sort(key=lambda w: (round(w["top"] / 3), w["x0"]))
            label = " ".join(w["text"] for w in band if w["x1"] <= bounds[0] + 2)
            if STOP_RE.search(label):
                break
            row = next((r for r in ROWS if re.search(r[0], label, re.I)), None)
            cells: dict[int, list[list[dict]]] = {}
            for word in band:
                if word["x1"] <= bounds[0] + 2:
                    continue
                center = (word["x0"] + word["x1"]) / 2
                column = next(
                    (i for i in range(len(DAY_ORDER)) if bounds[i] <= center < bounds[i + 1]), None
                )
                if column is None:
                    continue
                lines = cells.setdefault(column, [])
                if lines and abs(lines[-1][0]["top"] - word["top"]) <= 3:
                    lines[-1].append(word)
                else:
                    lines.append([word])

            has_times = any(
                TIME_RE.search(" ".join(w["text"] for w in line))
                for lines in cells.values() for line in lines
            )
            if not has_times or SKIPPED_ROWS_RE.search(label):
                continue
            if not row:
                raise ValueError(f"Unrecognized Pearkes schedule row '{label}'")
            matched += 1
            _, titles, _ = row
            reserved = label.lstrip().startswith("**")

            for column, lines in cells.items():
                # Each time owns the note lines under it; a note above the first time
                # belongs to that first time.
                slots: list[dict] = []
                leading: list[str] = []
                for line in lines:
                    text = " ".join(w["text"] for w in line)
                    matches = list(TIME_RE.finditer(text))
                    if matches:
                        for match in matches:
                            slots.append({"match": match, "notes": list(leading)})
                            leading = []
                    elif slots:
                        slots[-1]["notes"].append(text)
                    else:
                        leading.append(text)

                weekday = column
                for slot in slots:
                    marker, start_raw, start_mer, end_raw, end_mer = slot["match"].groups()
                    resolved = self._resolve(start_raw, start_mer, end_raw, end_mer)
                    if not resolved:
                        print(f"[{self.municipality}] Skipping unreadable Pearkes time '{slot['match'].group(0)}'")
                        continue
                    note = " ".join(slot["notes"])
                    excluded, starting = self._note_rules(note, start_date.year)
                    description = "G. R. Pearkes drop-in skating PDF schedule."
                    if reserved:
                        description += f" {RESERVATION_NOTE}"
                    if marker == "*":
                        description += " Adult Skate and coffee social."
                    if note:
                        description += f" {note}."
                    first = max(date.today(), start_date, starting or start_date)
                    current = first
                    while current <= end_date:
                        if current.weekday() == weekday and current not in excluded:
                            for title in titles:
                                sessions.append(
                                    {
                                        "title": title,
                                        "start": datetime.combine(current, resolved[0]),
                                        "end": datetime.combine(current, resolved[1]),
                                        "description": description,
                                        "family": row[2],
                                    }
                                )
                        current += timedelta(days=1)

        if not matched:
            raise ValueError("No known Pearkes schedule rows found")
        return sessions

    def _other_source_keys(self, start_date: date, end_date: date) -> set[tuple[str, datetime]]:
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
            keys = set()
            for row in rows:
                for _, titles, family in ROWS:
                    if re.search(family, row.title, re.I):
                        goalie = "goalie" in row.title.lower()
                        keys.add((family, goalie, row.start_time.replace(microsecond=0)))
            return keys
        finally:
            db.close()

    def scrape(self):
        print(f"[{self.municipality}] Starting Pearkes PDF fallback scrape...")
        pdf_url, pdf, start_date, end_date = self._discover_pdf()
        sessions = self._sessions(pdf, start_date, end_date)
        other_keys = self._other_source_keys(start_date, end_date)

        events = []
        seen = set()
        for session in sessions:
            goalie = "goalie" in session["title"].lower()
            if (session["family"], goalie, session["start"]) in other_keys:
                continue
            key = (session["title"], session["start"])
            if key in seen:
                continue
            seen.add(key)
            source_key = f"{self.venue_name}|{session['title']}|{session['start'].isoformat()}"
            events.append(
                {
                    "source_id": f"{self.source_id_prefix}_{hashlib.md5(source_key.encode('utf-8')).hexdigest()[:16]}",
                    "title": session["title"],
                    "venue_name": self.venue_name,
                    "facility_name": "Arena",
                    "start_time": session["start"],
                    "end_time": session["end"],
                    "price": "",
                    "description": session["description"],
                    "booking_url": pdf_url,
                }
            )

        self.last_reported_count = len(sessions)
        print(
            f"[{self.municipality}] Pearkes PDF parsed {len(sessions)} sessions from {pdf_url}, "
            f"adding {len(events)} not already published by Active Communities."
        )
        # The PDF covers the whole season, so republishing it in full drops superseded rows.
        self.replace_existing_events()
        self.save_events(events)
        return events
