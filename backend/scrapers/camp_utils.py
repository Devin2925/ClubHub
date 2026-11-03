"""Shared shaping for camp rows.

A camp is saved as one row: ``start_time``/``end_time`` hold the first day's hours
and ``end_date`` the last day of the run, so a Dec 21-24 camp is one listing, not
four schedule entries. Camps are filed under the "kids" sport so they don't show
up in drop-in basketball or swim schedules.
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

VICTORIA_TZ = ZoneInfo("America/Vancouver")


def camp_row(
    *,
    source_id: str,
    title: str,
    venue_name: str,
    start_time: datetime,
    end_time: datetime,
    last_day: datetime | None = None,
    facility_name: str = "",
    price: str = "",
    description: str = "",
    booking_url: str = "",
    availability: str = "",
    ages: str = "",
    municipality: str | None = None,
) -> dict:
    row = {
        "source_id": source_id,
        "title": tidy_title(title),
        "venue_name": venue_name,
        "facility_name": facility_name,
        "start_time": start_time,
        "end_time": end_time,
        "end_date": last_day.date().isoformat() if last_day and last_day.date() > start_time.date() else "",
        "price": price,
        "description": re.sub(r"\s+", " ", description or "").strip()[:800],
        "booking_url": booking_url,
        "availability": availability,
        "ages": ages,
        "offering_override": "camp",
        "sport_override": "kids",
    }
    if municipality:
        row["municipality"] = municipality
    return row


def runs_note(start: datetime, last_day: datetime | None, sessions: int, days_text: str) -> str:
    """'Runs Fridays, 6 sessions. ' when a camp skips weekdays in its date range; '' otherwise."""
    if not last_day or last_day.date() <= start.date() or not sessions:
        return ""
    weekdays = 0
    day = start.date()
    while day <= last_day.date():
        weekdays += day.weekday() < 5
        day = day.fromordinal(day.toordinal() + 1)
    if sessions >= weekdays:
        return ""
    return f"Runs {days_text}, {sessions} sessions. " if days_text else f"{sessions} sessions. "


def tidy_title(title: str) -> str:
    """Oak Bay lists camps in capitals; show them like everyone else's."""
    title = re.sub(r"\s+", " ", title or "").strip()
    letters = [ch for ch in title if ch.isalpha()]
    if letters and sum(ch.isupper() for ch in letters) / len(letters) > 0.8:
        title = title.title()
        title = re.sub(r"\b(Yrs?|Years)\b", lambda m: m.group(0).lower(), title)
        title = re.sub(r"\bLego\b", "LEGO", title)
        title = re.sub(r"\bWedo\b", "WeDo", title)
        title = re.sub(r"'S\b", "'s", title)
        title = re.sub(r"(?<=\S )(And|Of|The|For|With|In|At)\b", lambda m: m.group(1).lower(), title)
    return title


def age_range(min_age: float | None, max_age: float | None) -> str:
    """'5-11', '13+' or '' from inclusive bounds."""
    def fmt(value: float) -> str:
        whole = int(value)
        return f"{whole}½" if value - whole >= 0.5 else str(whole)

    if min_age is None and max_age is None:
        return ""
    if max_age is None or max_age >= 18:
        return f"{fmt(min_age or 0)}+" if min_age else ""
    if not min_age:
        return f"Up to {fmt(max_age)}"
    if int(min_age) == int(max_age):
        return fmt(min_age)
    return f"{fmt(min_age)}-{fmt(max_age)}"


def ages_from_title(title: str) -> str:
    """Pull an age or grade range out of a camp name: '(6-9 years)', 'Grade 1-5', 'KGs'."""
    text = title or ""
    match = re.search(r"(\d{1,2})\s*(?:\.5|½)?\s*[-–to]+\s*(\d{1,2})\s*(?:yrs?|years|y\b)", text, re.I)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    match = re.search(r"(?:grades?|gr\.?)\s*(\d{1,2})\s*[-–]\s*(\d{1,2})", text, re.I)
    if match:
        return f"Grades {match.group(1)}-{match.group(2)}"
    match = re.search(r"\b(?:K|KG|KGs|Kindergarten)\s*[-–]\s*(?:grade\s*)?(\d{1,2})\b", text, re.I)
    if match:
        return f"K-Grade {match.group(1)}"
    if re.search(r"\bKGs?\b|\bkindergarten\b", text, re.I):
        return "Kindergarten"
    match = re.search(r"\bG(?:rade)?\s*(\d)s?\b", text)
    if match:
        return f"Grade {match.group(1)}"
    match = re.search(r"\(\s*(\d{1,2})\s*[-–]\s*(\d{1,2})\s*\)", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return ""


def spots_label(open_spots: int | None, full: bool = False, waitlist: bool = False) -> str:
    if full or open_spots == 0:
        return "Full - waitlist" if waitlist else "Full"
    if open_spots is None:
        return ""
    return f"{open_spots} spot left" if open_spots == 1 else f"{open_spots} spots left"


def local_from_epoch_ms(value: int) -> datetime:
    """A UTC timestamp in milliseconds as a naive Victoria wall-clock time."""
    return datetime.fromtimestamp(value / 1000, tz=VICTORIA_TZ).replace(tzinfo=None)
