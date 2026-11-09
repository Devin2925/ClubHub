"""City of Surrey drop-in schedules from the PDFs on surrey.ca/dropin.

Surrey publishes a term's drop-ins as weekday-grid PDFs by activity type: Gym, Youth,
Seniors and Arena. Each PDF has, per facility, a "PROGRAM MONDAY ... SUNDAY" grid that
repeats weekly between the term dates. surrey_grid.read_surrey_grid() reads them by word
position; this scraper discovers the current PDFs, reads them and saves the sessions.

The Aquatics PDF's facility-hours rows (hot tub, sauna, fitness centre, waterslide, diving
boards) are filtered out; its swims are kept. Not read yet: the monthly Fitness calendar.

The PDF links on /dropin carry the term in their name (FALL-2026-Gym-Drop-in-Schedule.pdf),
so a new term is picked up without code changes; the grid reader takes the dates from the
PDF itself.
"""
import re

import requests

from scrapers.surrey_grid import DAY_NAMES, read_surrey_grid
from scrapers.vancouver_common import VancouverScraper, classify, clean_venue, start_of_today

DROP_IN_PAGE = "https://www.surrey.ca/dropin"
BASE = "https://www.surrey.ca"
# Activity-type PDFs this scraper reads (filename keyword → not used for filtering, just which
# links to follow). The Aquatics and Fitness PDFs are left out on purpose (see module docstring).
PDF_KINDS = ("Gym", "Youth", "Seniors", "Arena", "Aquatics")

# Aquatics PDF rows that are facility features or hours, not a drop-in activity.
NOT_AN_ACTIVITY = re.compile(
    r"fitness (centre|facility)|wellness|hot ?tub|sauna|steam room|water ?slide|diving board|"
    r"platform|gymnasium|limited|lane usage|^\*",
    re.I,
)
PDF_LINK = re.compile(r'href="(/sites/default/files/[^"]+?-(%s)-Drop-in-Schedule\.pdf)"' % "|".join(PDF_KINDS), re.I)

SURREY_SOURCES = {
    "surrey_dropin": {"municipality": "Surrey", "display_name": "City of Surrey drop-in schedules"},
}

# PDF spellings (after clean_venue title-casing) that differ from vancouver_registry.py.
VENUE_FIXES = {
    "Surrey Sport And Leisure Complex Arena": "Surrey Sport & Leisure Complex",
    "North Surrey Sport And Ice Complex": "North Surrey Sport and Ice Complex",
    "Cloverdale Sport And Ice Complex": "Cloverdale Sport and Ice Complex",
    "Newton Arena": "Newton Recreation Centre",
}


class SurreyDropInScraper(VancouverScraper):
    def __init__(self, source_key: str, municipality: str, dry_run: bool = False, **_):
        super().__init__(source_id_prefix=source_key, municipality=municipality, dry_run=dry_run)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0 (ClubHub schedule aggregator)"

    def _pdf_urls(self) -> list[str]:
        page = self.session.get(DROP_IN_PAGE, timeout=30)
        page.raise_for_status()
        urls = {BASE + match.group(1) for match in PDF_LINK.finditer(page.text)}
        if not urls:
            raise RuntimeError(f"no drop-in PDFs found on {DROP_IN_PAGE}")
        return sorted(urls)

    def scrape(self):
        print(f"[{self.municipality}] Starting Surrey drop-in PDF scrape...")
        for url in self._pdf_urls():
            try:
                pdf = self.session.get(url, timeout=60)
                pdf.raise_for_status()
                grid = read_surrey_grid(pdf.content)
            except (requests.RequestException, ValueError, RuntimeError) as exc:
                self.failures.append(f"{url.rsplit('/', 1)[-1]}: {exc}")
                continue
            for item in grid:
                self._keep_sessions(item, url)
        return self.finish()

    def _keep_sessions(self, item, url: str) -> None:
        venue = clean_venue(item.venue)
        venue = VENUE_FIXES.get(venue, venue)
        title = re.sub(r"\s+", " ", item.program).strip().rstrip("*•").strip()
        if "PROGRAM" in title.upper() or len(title) < 3:  # a header word that leaked into a cell
            return
        if NOT_AN_ACTIVITY.search(title):  # pool facility hours, not a drop-in
            return
        for day in item.dates:
            try:
                start_time = _combine(day, item.start)
                end_time = _combine(day, item.end)
            except ValueError:
                continue
            if end_time <= start_time or end_time < start_of_today():
                continue
            weekday = DAY_NAMES[item.day_index].title()
            self.keep({
                "source_id": f"{self.source_id_prefix}_{_slug(venue)}_{_slug(title)}_{start_time:%Y%m%d%H%M}",
                "title": title,
                "venue_name": venue,
                "facility_name": "",
                "start_time": start_time,
                "end_time": end_time,
                "price": "",
                "description": f"Surrey drop-in on {weekday}s this term. Schedules change; check surrey.ca/dropin.",
                "booking_url": url,
                "availability": "",
                **classify(title, venue, "", "Drop-in"),
                "offering_override": "drop-in",
            })


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _combine(day, clock: str):
    from datetime import datetime
    parsed = datetime.strptime(clock.upper(), "%I:%M%p" if ":" in clock else "%I%p")
    return datetime.combine(day, datetime.min.time()).replace(hour=parsed.hour, minute=parsed.minute)
