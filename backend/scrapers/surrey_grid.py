"""Shared reader for Surrey's drop-in schedule PDFs (surrey.ca/dropin).

Each PDF (Gym, Aquatics, Arena, Seniors, Youth) lays out, per facility, a weekday grid:
an all-caps venue heading beside a table whose header is "PROGRAM MONDAY ... SUNDAY" and
whose cells hold a time range under each day a program runs. The whole schedule repeats
weekly between the term dates printed on the PDF ("SEP 8 – DEC 18").

We read word positions (not flattened text) so a time range lands under the right day:
- venue headings are the larger all-caps words in the left column,
- each "PROGRAM ... SUNDAY" row gives that grid's day-column x-centres,
- program rows pair a left-column label with time ranges placed under days.

read_surrey_grid() yields one Session per (venue, program, day, time range), with the
dates it falls on. If the term dates or day columns can't be read, it raises rather than
guessing.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from io import BytesIO

import pdfplumber

DAY_NAMES = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
MONTHS = "JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC"
TIME_RE = re.compile(r"^(\d{1,2}(?::\d{2})?)(am|pm)?[-–](\d{1,2}(?::\d{2})?)(am|pm)$", re.I)
TERM_RE = re.compile(
    rf"({MONTHS})[A-Z]*\.?\s+(\d{{1,2}})\s*[-–]\s*({MONTHS})[A-Z]*\.?\s+(\d{{1,2}})(?:,?\s*(\d{{4}}))?",
    re.I,
)
HEADING_RE = re.compile(r"^[A-Z0-9][A-Z0-9 &'./+-]+$")
# Headings in the left column that aren't a facility (legends, banners, callouts).
NOT_VENUE = re.compile(
    r"DROP-?IN|SCHEDULE|ADMISSION|PASS|ETIQUETTE|ADVANCE|OTHERS|GYMNASIUM$|ALL GYMNASIUMS|UNLEASH|VERIFY|"
    r"ACCOUNT|REMINDER|LOCATIONS|ATHLETE|WITHDRAW|CHANCE|KNOW|^PASS$|^SS$|HEALTH|POLICY|RESPECT|SECURITY",
    re.I,
)


@dataclass
class Session:
    venue: str
    program: str
    day_index: int
    start: str  # "6:30pm"
    end: str    # "8pm"
    dates: list[date] = field(default_factory=list)


def _month_day(month: str, day: str, year: int) -> date:
    return datetime.strptime(f"{year} {month[:3].title()} {day}", "%Y %b %d").date()


def _term_dates(text: str, default_year: int) -> tuple[date, date]:
    match = TERM_RE.search(text)
    if not match:
        raise ValueError("no term dates (e.g. 'SEP 8 – DEC 18') on the Surrey PDF")
    year = int(match.group(5)) if match.group(5) else default_year
    start = _month_day(match.group(1), match.group(2), year)
    end = _month_day(match.group(3), match.group(4), year)
    if end < start:
        end = _month_day(match.group(3), match.group(4), year + 1)
    return start, end


def _dates_for(day_index: int, start: date, end: date, horizon_days: int) -> list[date]:
    today = date.today()
    first = max(start, today)
    last = min(end, today + timedelta(days=horizon_days))
    out = []
    day = first
    while day <= last:
        if day.weekday() == day_index:
            out.append(day)
        day += timedelta(days=1)
    return out


def _lines(words, size_min, size_max, tol=3):
    """Group words into lines of similar vertical position, left to right."""
    rows: list[list] = []
    for word in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if not (size_min <= round(word["size"]) <= size_max):
            continue
        if rows and abs(word["top"] - rows[-1][0]["top"]) <= tol:
            rows[-1].append(word)
        else:
            rows.append([word])
    return rows


def read_surrey_grid(pdf_bytes: bytes, horizon_days: int = 56) -> list[Session]:
    sessions: list[Session] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        default_year = date.today().year
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        term_start, term_end = _term_dates(full_text, default_year)

        for page in pdf.pages:
            words = page.extract_words(extra_attrs=["size"])
            headers = [w for w in words if w["text"] == "PROGRAM" and round(w["size"]) == 7]
            # Venue headings sit just above each grid, aligned with its left edge (same x as
            # "PROGRAM"), in all caps at size ~11.
            headings = []
            for line in _lines([w for w in words if round(w["size"]) == 11], 11, 11):
                text = " ".join(w["text"] for w in line).strip()
                if HEADING_RE.match(text) and not NOT_VENUE.search(text) and len(text) > 5:
                    headings.append((line[0]["top"], line[0]["x0"], text))

            for header in headers:
                day_line = sorted(
                    (w for w in words if abs(w["top"] - header["top"]) < 3 and w["text"] in DAY_NAMES),
                    key=lambda w: w["x0"],
                )
                if len(day_line) < 5:
                    continue
                centres = {DAY_NAMES.index(w["text"]): (w["x0"] + w["x1"]) / 2 for w in day_line}
                first_day_x = min(w["x0"] for w in day_line)
                grid_left = header["x0"] - 6
                grid_right = max(centres.values()) + 60
                # Venue = the nearest all-caps heading above this grid at its left edge; a grid
                # with no heading right above it continues the previous facility.
                above = [h for h in headings if h[0] < header["top"] - 2 and abs(h[1] - header["x0"]) < 24]
                venue = max(above, key=lambda h: h[0], default=(None, None, "Surrey"))[2]

                # Next header below this one bounds the grid's rows.
                lower = min((h["top"] for h in headers if h["top"] > header["top"] + 5), default=page.height)
                body = [
                    w for w in words
                    if header["top"] + 6 < w["top"] < lower and grid_left < w["x0"] < grid_right and round(w["size"]) == 8
                ]
                program = ""
                for line in _lines(body, 8, 8):
                    labels = [w["text"] for w in line if w["x1"] < first_day_x - 2 and not TIME_RE.match(w["text"])]
                    times = [w for w in line if TIME_RE.match(w["text"])]
                    if labels:
                        program = " ".join(labels)
                    if not program:
                        continue
                    for word in times:
                        match = TIME_RE.match(word["text"])
                        day_index = min(centres, key=lambda d: abs(centres[d] - (word["x0"] + word["x1"]) / 2))
                        start_text = match.group(1) + (match.group(2) or match.group(4)).lower()
                        end_text = match.group(3) + match.group(4).lower()
                        dates = _dates_for(day_index, term_start, term_end, horizon_days)
                        if dates:
                            sessions.append(Session(venue, program, day_index, start_text, end_text, dates))
    return sessions
