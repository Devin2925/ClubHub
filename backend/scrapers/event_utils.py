"""Shared shaping for community-event rows (Oak Bay, Esquimalt, Saanich calendars).

Community events are one-offs - concerts, markets, ceremonies, Santa skates - so
they're saved as offering "event" under the "other" (Community) sport, which
keeps a tennis tournament out of the tennis drop-ins.

Like camps, a multi-day event is one row: start/end_time hold the first day's
hours and end_date the last day. All-day events are stored as 00:00-23:59 so the
site can label them "All day".
"""
import html
import re
from datetime import datetime, timedelta

# Calendar entries that are notices or civic meetings rather than something to go to.
NOT_AN_EVENT = re.compile(
    r"registration\s+opens|guide\s+(?:is\s+)?available|available\s+for\s+viewing|"
    r"^council\b|council\s+meeting|committee\s+of\s+the\s+whole|public\s+hearing|board\s+of\s+variance|"
    r"advisory\s+(?:design\s+)?panel|"
    r"closure|\bclosed\b|\bagm\b|annual\s+general\s+meeting",
    re.I,
)

# "FREE" / "Free Talks", but not "gluten-free", "free parking" or "free of charge for members".
FREE = re.compile(r"(?<![-\w])free\b(?![-\w]|\s+parking)", re.I)


def clean_text(value: str) -> str:
    """Plain text from an HTML fragment, entities decoded, whitespace collapsed."""
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", " ", value or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(html.unescape(text))
    text = re.sub(r"https?://\S+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def price_from_text(title: str, description: str) -> str:
    return "Free" if FREE.search(f"{title} {description[:300]}") else ""


def event_row(
    *,
    source_id: str,
    title: str,
    venue_name: str,
    start: datetime,
    end: datetime,
    all_day: bool = False,
    facility_name: str = "",
    price: str = "",
    description: str = "",
    url: str = "",
) -> dict:
    """One event row. ``end`` is the real end; a later date makes it multi-day."""
    if all_day:
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        first_end = start.replace(hour=23, minute=59)
    else:
        # A timed multi-day event keeps the same hours each day ("12-4pm, Nov 14-15").
        first_end = start.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
        if first_end <= start:
            first_end = start + timedelta(hours=1)
    description = clean_text(description)
    return {
        "source_id": source_id,
        "title": clean_text(title),
        "venue_name": venue_name,
        "facility_name": facility_name,
        "start_time": start,
        "end_time": first_end,
        "end_date": end.date().isoformat() if end.date() > start.date() else "",
        "price": price or price_from_text(title, description),
        "description": description[:600],
        "booking_url": url,
        "offering_override": "event",
        "sport_override": "other",
    }
