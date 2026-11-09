"""City of Victoria events from victoria.ca/community-culture/events.

A Drupal FullCalendar view (see drupal_calendar_events.py). In summer it is mostly
CityVibe festival events (concerts, markets in Centennial Square and the parks);
the rest of the year it is a handful of City workshops plus civic notices.

The pages have no location field: the place is a "Location: City Hall, second
floor" line in the body text, so the venue is that line up to its first comma.
Election/voting/ballot entries and bylaw consultations are skipped.
"""
import re

from scrapers.drupal_calendar_events import DrupalCalendarEventsScraper, page_field

LOCATION_LINE = re.compile(r"\bLocation:\s*(.+?)(?=\s+(?:Cost|Price|Time|Date|Who|Register|Admission)\b|$)", re.I)


class VictoriaEventsScraper(DrupalCalendarEventsScraper):
    label = "City of Victoria"
    base_url = "https://www.victoria.ca"
    calendar_url = f"{base_url}/community-culture/events"
    default_venue = "Around Victoria"
    venue_aliases = [
        (re.compile(r"\bcity hall\b", re.I), "Victoria City Hall", ""),
        (re.compile(r"centennial square", re.I), "Centennial Square", ""),
        (re.compile(r"save[- ]on[- ]foods memorial", re.I), "Save on Foods Memorial Centre", ""),
        (re.compile(r"crystal pool", re.I), "Crystal Pool & Fitness Centre", ""),
    ]
    aliases_search_text = False
    skip_titles = re.compile(r"election|\bvoting\b|ballot|bylaw|\bworks\s*(?:&|and)\s*services\b", re.I)

    def __init__(self):
        super().__init__(source_id_prefix="victoria_events", municipality="Victoria")

    def location_from_page(self, main: str) -> str:
        match = LOCATION_LINE.search(page_field(main, "field-content-rows") or page_field(main, "field-row-content"))
        return match.group(1).split(",")[0].strip(" .") if match else ""

    def description_from_page(self, main: str) -> str:
        return page_field(main, "field-row-content") or page_field(main, "field-content-rows")
