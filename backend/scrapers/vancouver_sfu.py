"""SFU Recreation drop-in sports (Burnaby campus) from its weekly HTML schedule.

https://www.sfu.ca/recreation/sports/dropinsport/drop-in-schedule.html has a heading like
"DROP-IN Sports Schedule FALL 2026 (Sept 14 - Dec 4)" and one Sport / Time / Location table
per weekday (MONDAY ... Friday). The same week repeats for the whole term, so this expands
each weekday's rows onto every matching date from today until the term ends (or
HORIZON_DAYS), skipping university holidays.

When SFU posts the next term the heading's dates change and this follows them. If the
heading can't be read, the scrape fails rather than guessing dates.
"""
import html
import re
from datetime import date, datetime, timedelta

import requests

from scrapers.vancouver_common import VancouverScraper, classify, start_of_today

SCHEDULE_URL = "https://www.sfu.ca/recreation/sports/dropinsport/drop-in-schedule.html"
HORIZON_DAYS = 56
VENUE_NAME = "SFU Recreation (Burnaby campus)"

SFU_SOURCES = {
    "sfu_recreation": {"municipality": "SFU", "display_name": "SFU Recreation drop-in sports"},
}

# SFU is closed on these days (university holidays inside teaching terms).
SFU_CLOSED = {date(2026, 11, 11), date(2027, 2, 16), date(2027, 4, 3)}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
TERM = re.compile(
    r"(?:FALL|SPRING|SUMMER|WINTER)\s+(\d{4})\s*\(\s*([A-Za-z]+)\.?\s+(\d{1,2})\s*[-–]\s*([A-Za-z]+)\.?\s+(\d{1,2})\s*\)",
    re.I,
)
TIME_RANGE = re.compile(r"(\d{1,2}(?::\d{2})?\s*[AP]M)\s*[-–]\s*(\d{1,2}(?::\d{2})?\s*[AP]M)", re.I)


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).replace("\xa0", " ").strip()


def _month_day(year: int, month: str, day: str) -> date:
    return datetime.strptime(f"{year} {month[:3]} {day}", "%Y %b %d").date()


def _clock(text: str) -> tuple[int, int]:
    text = text.upper().replace(" ", "")
    parsed = datetime.strptime(text, "%I:%M%p" if ":" in text else "%I%p")
    return parsed.hour, parsed.minute


def parse_schedule(page: str) -> tuple[date, date, dict[int, list[tuple[str, str, str]]]]:
    """(term start, term end, {weekday index: [(sport, time range, location)]})."""
    clean = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    term = TERM.search(_text(clean))
    if not term:
        raise ValueError("no term dates (e.g. 'FALL 2026 (Sept 14 - Dec 4)') on the schedule page")
    year = int(term.group(1))
    first, last = _month_day(year, term.group(2), term.group(3)), _month_day(year, term.group(4), term.group(5))
    if last < first:  # a winter term that runs into the next year
        last = _month_day(year + 1, term.group(4), term.group(5))

    week: dict[int, list[tuple[str, str, str]]] = {}
    for table in re.finditer(r"<table.*?</table>", clean, re.S):
        before = _text(clean[max(0, table.start() - 2000): table.start()]).lower()
        day = max(((before.rfind(name), index) for index, name in enumerate(WEEKDAYS)), default=(-1, -1))
        if day[0] < 0:
            continue
        rows = []
        for row in re.findall(r"<tr.*?</tr>", table.group(0), re.S):
            cells = [_text(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            if len(cells) >= 3 and TIME_RANGE.search(cells[1]):
                rows.append((cells[0], cells[1], cells[2]))
        if rows:
            week[day[1]] = rows
    if not week:
        raise ValueError("no weekday tables on the schedule page")
    return first, last, week


class SFURecreationScraper(VancouverScraper):
    def __init__(self, source_key: str, municipality: str, dry_run: bool = False, **_):
        super().__init__(source_id_prefix=source_key, municipality=municipality, dry_run=dry_run)

    def scrape(self):
        print(f"[{self.municipality}] Starting SFU drop-in schedule scrape...")
        response = requests.get(SCHEDULE_URL, headers={"User-Agent": "Mozilla/5.0 (ClubHub schedule aggregator)"}, timeout=30)
        response.raise_for_status()
        first, last, week = parse_schedule(response.text)
        today = start_of_today().date()
        day = max(first, today)
        stop = min(last, today + timedelta(days=HORIZON_DAYS))
        while day <= stop:
            if day not in SFU_CLOSED:
                for sport, times, location in week.get(day.weekday(), []):
                    match = TIME_RANGE.search(times)
                    (sh, sm), (eh, em) = _clock(match.group(1)), _clock(match.group(2))
                    start = datetime.combine(day, datetime.min.time()).replace(hour=sh, minute=sm)
                    end = datetime.combine(day, datetime.min.time()).replace(hour=eh, minute=em)
                    title = f"Drop-in {sport}"
                    self.keep({
                        "source_id": f"{self.source_id_prefix}_{re.sub(r'[^a-z0-9]+', '-', sport.lower())}_{start:%Y%m%d%H%M}_{re.sub(r'[^a-z0-9]+', '-', location.lower())}",
                        "title": title,
                        "venue_name": VENUE_NAME,
                        "facility_name": location,
                        "start_time": start,
                        "end_time": end,
                        "price": "",
                        "description": "SFU Recreation drop-in sport: staff organize casual games for players of all abilities. Check SFU Recreation for who can drop in and any fees.",
                        "booking_url": SCHEDULE_URL,
                        "availability": "",
                        **classify(title, location, "", "Drop-in Sports"),
                        "offering_override": "drop-in",
                    })
            day += timedelta(days=1)
        return self.finish()
