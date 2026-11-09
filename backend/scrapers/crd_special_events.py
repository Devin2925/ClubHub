"""Special events from the CRD's recreation sites: Panorama Recreation and SEAPARC.

Both sites run the same Drupal "calendar_view" month grid:
  panoramarecreation.ca/drop-activities/special-events
  seaparc.ca/events-parties/special-events
Each day cell lists its events as <li class="calendar-view-day__row"> with a link
to the event page and <time datetime> start/end. The "Next" pager link
(?calendar_timestamp=...) moves a month on; MONTHS_AHEAD months are read.

A multi-day event (Squash Cup, Festival of Trees) is listed in each day's cell;
consecutive days with the same hours are merged into one multi-day row (end_date),
keyed by the first listed day. All-day entries have a date-only datetime. Times
are local (-07:00) and stored as wall-clock, like every ClubHub source.

The event page's "field-event-location" names the building ("Panorama
Recreation Centre 1885 Forest Park Drive ..."), mapped onto ClubHub's venues.
"""
import html
import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

import requests

from scrapers.base import BaseScraper
from scrapers.drupal_calendar_events import USER_AGENT, page_field
from scrapers.event_utils import NOT_AN_EVENT, clean_text, event_row

MONTHS_AHEAD = 6
ROW = re.compile(r'<li[^>]*class="calendar-view-day__row"[^>]*>(.*?)</li>', re.S)
LINK = re.compile(r'<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
TIME = re.compile(r'<time datetime="([^"]+)"')
NEXT = re.compile(r'pager__next"><a href="([^"]+)"')

SITES = {
    "panorama": {
        "label": "Panorama",
        "municipality": "Panorama",
        "base_url": "https://www.panoramarecreation.ca",
        "path": "/drop-activities/special-events",
        "default_venue": "Panorama Recreation Centre",
        "venues": [
            (re.compile(r"greenglade", re.I), "Greenglade Community Centre"),
            (re.compile(r"centennial park", re.I), "Centennial Park"),
            (re.compile(r"panorama", re.I), "Panorama Recreation Centre"),
        ],
    },
    "seaparc": {
        "label": "SEAPARC",
        "municipality": "Sooke",
        "base_url": "https://www.seaparc.ca",
        "path": "/events-parties/special-events",
        "default_venue": "SEAPARC Recreation Centre",
        "venues": [(re.compile(r"seaparc", re.I), "SEAPARC Recreation Centre")],
    },
}


def _local(value: str) -> datetime:
    return datetime.fromisoformat(value[:19] if "T" in value else value[:10])


class CRDSpecialEventsScraper(BaseScraper):
    def __init__(self, site: str):
        self.site = SITES[site]
        super().__init__(source_id_prefix=f"{site}_events", municipality=self.site["municipality"])
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._details: dict[str, tuple[str, str]] = {}

    def _detail(self, url: str) -> tuple[str, str]:
        """(venue, description) from an event's own page."""
        if url not in self._details:
            venue, description = self.site["default_venue"], ""
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                page = response.text
                main = page[page.find("<main") : page.find("</main>")] or page
                location = page_field(main, "field-event-location")
                description = page_field(main, "body") or page_field(main, "field-ta-content")
                for pattern, name in self.site["venues"]:
                    if pattern.search(location):
                        venue = name
                        break
            except requests.RequestException as exc:
                print(f"[{self.site['label']}] Event page failed {url}: {exc}")
            self._details[url] = (venue, description)
        return self._details[url]

    def _months(self):
        """Yield each month page's HTML, following the pager's Next link."""
        url = urljoin(self.site["base_url"], self.site["path"])
        for _ in range(MONTHS_AHEAD):
            response = self.session.get(url, timeout=45)
            response.raise_for_status()
            yield response.text
            following = NEXT.search(response.text)
            if not following:
                return
            url = urljoin(self.site["base_url"] + self.site["path"], html.unescape(following.group(1)))

    def scrape(self):
        label = self.site["label"]
        print(f"[{label}] Starting {label} special events scrape...")
        today = date.today()
        days: dict[tuple[str, datetime], tuple[str, datetime, bool]] = {}
        for page in self._months():
            for row in ROW.findall(page):
                link, times = LINK.search(row), TIME.findall(row)
                if not link or not times:
                    continue
                title = clean_text(link.group(2))
                if not title or NOT_AN_EVENT.search(title):
                    continue
                start = _local(times[0])
                end = _local(times[1]) if len(times) > 1 else start
                # A month's grid repeats the neighbouring months' edge days; the key dedupes them.
                days[(link.group(1), start)] = (title, end, "T" not in times[0])
        if not days:
            raise RuntimeError(f"{label} special events calendar listed no events")

        # Merge each event's consecutive days that share the same hours into one run.
        runs: list[list] = []  # [path, title, first_start, last_end, all_day]
        for (path, start), (title, end, all_day) in sorted(days.items(), key=lambda item: (item[0][0], item[0][1])):
            last = runs[-1] if runs else None
            if (
                last
                and last[0] == path
                and start.date() == last[3].date() + timedelta(days=1)
                and start.time() == last[2].time()
                and end.time() == last[3].time()
            ):
                last[3] = end
            else:
                runs.append([path, title, start, end, all_day])

        events = []
        for path, title, start, end, all_day in runs:
            if end.date() < today:
                continue
            url = urljoin(self.site["base_url"], path)
            venue, description = self._detail(url)
            events.append(
                event_row(
                    source_id=f"{self.source_id_prefix}_{path.rstrip('/').rsplit('/', 1)[-1]}_{start:%Y%m%d}",
                    title=title,
                    venue_name=venue,
                    start=start,
                    end=end,
                    all_day=all_day,
                    description=description,
                    url=url,
                )
            )
        listed = len(days)
        print(f"[{label}] {label} special events: kept {len(events)} upcoming of {listed} calendar entries.")
        self.save_events(events)
        self.prune_unseen_upcoming({event["source_id"] for event in events})
        return events
