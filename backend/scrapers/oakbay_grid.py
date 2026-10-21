"""Shared reader for Oak Bay's weekly drop-in grid PDFs.

The racquet sports and group fitness schedules are tables with one day per column
and one session card per cell (title lines, then a time line, then optional notes).
Reading the table cells and word positions keeps neighbouring columns and stacked
cards apart, which plain layout text does not.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from io import BytesIO

import pdfplumber


DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_RE = re.compile(
    r"(\d{1,2}(?::\d{2})?)\s*(am|pm)?\s*[-–]\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)",
    re.I,
)
MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
MONTH_DAY_RE = re.compile(rf"\b({MONTHS})[a-z]*\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", re.I)
DATE_WINDOW_RE = re.compile(
    rf"\b({MONTHS})[a-z]*\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\s*[-–]\s*(?:({MONTHS})[a-z]*\.?\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\b",
    re.I,
)
SCHEDULE_RANGE_RE = re.compile(
    rf"\b({MONTHS})[a-z]*\s+(\d{{1,2}})(?:st|nd|rd|th)?\s*[-–]\s*({MONTHS})[a-z]*\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})",
    re.I,
)
# Lines under a card's time that qualify it rather than start the next card.
NOTE_LINE_RE = re.compile(rf"^(\(|no\s+session|starts?\b|ends?\b|(?:{MONTHS})[a-z]*\.?\s+\d)", re.I)
# Cells touching within this many points belong to the same stacked card.
STACK_GAP = 2.0


@dataclass
class Card:
    section: str
    weekday: int
    title: str
    start: time
    end: time
    notes: str
    raw_time: str


def _month_number(token: str) -> int:
    return datetime.strptime(token[:3].title(), "%b").month


def _clock(value: str, meridiem: str) -> time:
    if ":" not in value:
        value = f"{value}:00"
    return datetime.strptime(f"{value}{meridiem.lower()}", "%I:%M%p").time()


def _normalize(text: str) -> str:
    # Rejoin meridiems the PDF kerns apart ("7:00a m") before matching times.
    text = re.sub(r"(\d)\s*([ap])\s+m\b", r"\1\2m", text, flags=re.I)
    return " ".join(text.split())


def schedule_range(text: str) -> tuple[date, date]:
    """Read 'September 8th – December 20th, 2026' off the schedule heading."""
    match = SCHEDULE_RANGE_RE.search(_normalize(text))
    if not match:
        raise ValueError("Could not parse Oak Bay schedule date range")
    start_month, start_day, end_month, end_day, year = match.groups()
    start = date(int(year), _month_number(start_month), int(start_day))
    end = date(int(year), _month_number(end_month), int(end_day))
    if end < start:
        start = start.replace(year=start.year - 1)
    return start, end


def read_cards(pdf_bytes: bytes, sections: list[str]) -> tuple[list[Card], str]:
    """Return the session cards on page 1 and the page text."""
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        page = pdf.pages[0].dedupe_chars()
        page_text = page.extract_text() or ""
        cells = sorted({tuple(cell) for table in page.find_tables() for cell in table.cells})
        words = page.extract_words(x_tolerance=1.5, y_tolerance=2)

    # Each word belongs to the smallest cell holding its centre, so text drawn
    # across a cell edge is counted once.
    cell_words: dict[tuple, list[dict]] = {}
    for word in words:
        cx = (word["x0"] + word["x1"]) / 2
        cy = (word["top"] + word["bottom"]) / 2
        holders = [c for c in cells if c[0] <= cx <= c[2] and c[1] <= cy <= c[3]]
        if not holders:
            # Text set on a cell's bottom border still belongs to that cell.
            holders = [
                c for c in cells
                if c[0] <= cx <= c[2] and c[1] - STACK_GAP <= cy <= c[3] + STACK_GAP
            ]
        if holders:
            cell = min(holders, key=lambda c: (c[2] - c[0]) * (c[3] - c[1]))
            cell_words.setdefault(cell, []).append(word)

    def cell_text(cell) -> str:
        ordered = sorted(cell_words.get(cell, []), key=lambda w: (round(w["top"] / 3), w["x0"]))
        return _normalize(" ".join(w["text"] for w in ordered))

    texts = {cell: cell_text(cell) for cell in cells}
    headers = {}
    for cell, text in texts.items():
        if text in DAY_NAMES and text not in headers:
            headers[text] = cell
    missing = [day for day in DAY_NAMES if day not in headers]
    if missing:
        raise ValueError(f"Oak Bay grid is missing day headers: {', '.join(missing)}")
    header_bottom = min(cell[3] for cell in headers.values())

    section_marks = sorted(
        (cell[1], name)
        for cell, text in texts.items()
        for name in sections
        if text.lower() == name.lower()
    )
    if not section_marks:
        raise ValueError("Oak Bay grid has no recognised venue sections")

    def section_for(top: float) -> str | None:
        current = None
        for mark_top, name in section_marks:
            if mark_top <= top:
                current = name
        return current

    cards: list[Card] = []
    for weekday, day in enumerate(DAY_NAMES):
        hx0, _, hx1, _ = headers[day]
        width = hx1 - hx0
        column = sorted(
            (
                cell for cell in texts
                if cell[1] >= header_bottom - 1
                and hx0 - 8 <= (cell[0] + cell[2]) / 2 <= hx1 + 8
                and (cell[2] - cell[0]) <= width * 1.6
                and texts[cell] not in DAY_NAMES
            ),
            key=lambda c: c[1],
        )

        pending: list[str] = []
        last_bottom = None
        last_card: Card | None = None
        for cell in column:
            text = texts[cell]
            section = section_for(cell[1])
            contiguous = last_bottom is not None and cell[1] - last_bottom <= STACK_GAP
            if not contiguous:
                pending = []
                last_card = None
            last_bottom = cell[3]
            # Empty sub-cells sit inside stacked cards, so they keep the stack going.
            if not section or not text:
                continue

            match = TIME_RE.search(text)
            if not match:
                if last_card and NOTE_LINE_RE.search(text):
                    last_card.notes = f"{last_card.notes} {text}".strip()
                else:
                    pending.append(text)
                    last_card = None
                continue

            title = " ".join(pending + [text[: match.start()]]).replace("*", " ")
            title = " ".join(title.split())
            notes = text[match.end():].strip()
            pending = []
            if not title:
                last_card = None
                continue
            start_raw, start_mer, end_raw, end_mer = match.groups()
            start = _clock(start_raw, start_mer or end_mer)
            end = _clock(end_raw, end_mer)
            if not start_mer and start >= end:
                start = _clock(start_raw, "am")
            last_card = Card(section, weekday, title, start, end, notes, match.group(0))
            cards.append(last_card)

    return cards, page_text


def _note_dates(notes: str, year: int) -> list[date]:
    """Dates named in a 'No session Oct 6 & Dec 8' note, carrying the month forward."""
    found = []
    month = None
    for token in (m.group(0) for m in re.finditer(rf"(?:{MONTHS})[a-z]*\.?|\d{{1,2}}", notes, re.I)):
        if token.isdigit():
            if month:
                found.append(date(year, month, int(token)))
        else:
            month = _month_number(token)
    return found


def occurrence_dates(
    card: Card,
    start_date: date,
    end_date: date,
    skip_dates: set[date] = frozenset(),
) -> list[date]:
    """Dates a weekly card runs, honouring its own notes and the schedule range."""
    first = max(date.today(), start_date)
    last = end_date
    excluded = set(skip_dates)
    notes = card.notes

    no_session = re.search(r"no\s+session(.*)", notes, re.I)
    qualifiers = notes[: no_session.start()] if no_session else notes
    if no_session:
        excluded.update(_note_dates(no_session.group(1), start_date.year))
        excluded.update(d.replace(year=end_date.year) for d in _note_dates(no_session.group(1), end_date.year))

    window = DATE_WINDOW_RE.search(qualifiers)
    if window:
        s_month, s_day, e_month, e_day = window.groups()
        run_start = date(start_date.year, _month_number(s_month), int(s_day))
        run_end = date(start_date.year, _month_number(e_month or s_month), int(e_day))
        if run_end < run_start:
            run_end = run_end.replace(year=run_end.year + 1)
        first, last = max(first, run_start), min(last, run_end)
    else:
        starts = re.search(r"starts?\s+" + MONTH_DAY_RE.pattern, qualifiers, re.I)
        if starts:
            first = max(first, date(start_date.year, _month_number(starts.group(1)), int(starts.group(2))))

    dates = []
    current = first
    while current <= last:
        if current.weekday() == card.weekday and current not in excluded:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def bc_statutory_holidays(year: int) -> set[date]:
    """BC statutory holidays, for schedules that say classes do not run on them."""
    def nth_weekday(month: int, weekday: int, n: int) -> date:
        current = date(year, month, 1)
        while current.weekday() != weekday:
            current += timedelta(days=1)
        return current + timedelta(weeks=n - 1)

    def easter() -> date:
        a, b, c = year % 19, year // 100, year % 100
        d, e = b // 4, b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i, k = c // 4, c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return date(year, month, day)

    victoria_day = date(year, 5, 24)
    while victoria_day.weekday() != 0:
        victoria_day -= timedelta(days=1)

    return {
        date(year, 1, 1),
        nth_weekday(2, 0, 3),  # Family Day
        easter() - timedelta(days=2),  # Good Friday
        victoria_day,
        date(year, 7, 1),
        nth_weekday(8, 0, 1),  # BC Day
        nth_weekday(9, 0, 1),  # Labour Day
        date(year, 9, 30),  # National Day for Truth and Reconciliation
        nth_weekday(10, 0, 2),  # Thanksgiving
        date(year, 11, 11),
        date(year, 12, 25),
    }
