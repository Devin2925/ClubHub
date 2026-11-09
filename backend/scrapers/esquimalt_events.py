"""Esquimalt community events from the Township's events calendar.

esquimalt.ca/culture-heritage/community-events-calendar is a Drupal FullCalendar
view (1,100+ entries); see drupal_calendar_events.py. The location lives only on
each event's page ("Event location: Archie Browning Sports Centre").
"""
import re

from scrapers.drupal_calendar_events import DrupalCalendarEventsScraper


class EsquimaltEventsScraper(DrupalCalendarEventsScraper):
    label = "Esquimalt"
    base_url = "https://www.esquimalt.ca"
    calendar_url = f"{base_url}/culture-heritage/community-events-calendar"
    default_venue = "Around Esquimalt"
    # Event pages spell the same place several ways; use the names ClubHub already lists.
    venue_aliases = [
        (re.compile(r"^esquimalt rec(?:reation)? cent(?:re|er)\b", re.I), "Esquimalt Recreation Centre", ""),
        (re.compile(r"archie browning", re.I), "Archie Browning Sports Centre", ""),
        (re.compile(r"gorge park pavilion", re.I), "Esquimalt Gorge Park Pavilion", ""),
    ]
    aliases_search_text = False

    def __init__(self):
        super().__init__(source_id_prefix="esquimalt_events", municipality="Esquimalt")
