"""West Shore Parks & Recreation events from wspr.ca's events calendar.

wspr.ca/about-us/events-calendar is a Drupal FullCalendar view (see
drupal_calendar_events.py): hockey home games (Victoria Grizzlies and Westshore
Wolves at the Q Centre and JDF arenas), tournaments, races and seasonal events,
one calendar entry per date. Times are local (-07:00) and stored as wall-clock.

The pages have no location field, so the place comes from the title or body
("JDF Arena", "Q Centre"). Both arenas are at the Juan de Fuca Rec Centre.
"""
import re

from scrapers.drupal_calendar_events import DrupalCalendarEventsScraper, page_field

JDF = "Juan de Fuca Rec Centre"


class WSPREventsScraper(DrupalCalendarEventsScraper):
    label = "West Shore"
    base_url = "https://www.wspr.ca"
    calendar_url = f"{base_url}/about-us/events-calendar"
    default_venue = JDF
    venue_aliases = [
        (re.compile(r"\bq[- ]cent(?:re|er)\b|grizzlies", re.I), JDF, "Q Centre Arena"),
        (re.compile(r"\bjdf arena\b|juan de fuca arena", re.I), JDF, "JDF Arena"),
        (re.compile(r"fieldhouse", re.I), "Juan de Fuca Fieldhouse", ""),
        (re.compile(r"\bjdf\b|juan de fuca", re.I), JDF, ""),
    ]
    keep_unknown_location = False

    def __init__(self):
        super().__init__(source_id_prefix="wspr_events", municipality="West Shore")

    def location_from_page(self, main: str) -> str:
        return ""

    def description_from_page(self, main: str) -> str:
        return page_field(main, "body")
