"""Camps from PerfectMind course calendars (Oak Bay, Panorama, SEAPARC, Esquimalt).

The drop-in scraper (scrapers/perfectmind.py) only reads "Classes" calendars. Camps
are "BookingCoursesPage" calendars that load through a CoursesV2 endpoint. Those
calendars refuse each site's own widget, but open under PerfectMind's default public
widget, so every request here uses that one.
"""
import re
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs, urljoin, urlparse

import requests

from scrapers.base import BaseScraper
from scrapers.camp_utils import age_range, camp_row, local_from_epoch_ms, runs_note, spots_label

PUBLIC_WIDGET = "15f6af07-39c5-473e-b053-96653f77a406"

CAMP_SITES = [
    {"subdomain": "oakbayrec", "municipality": "Oak Bay", "start_path": "/22950/Store/BookMe4?widgetId=403780fd-76ad-4aaf-9816-c964b90d626d&embed=true"},
    {"subdomain": "panoramarec", "municipality": "Panorama", "start_path": f"/22938/Clients/BookMe4?widgetId={PUBLIC_WIDGET}"},
    {"subdomain": "seaparcrecreation", "municipality": "Sooke", "start_path": f"/22953/Clients/BookMe4?widgetId={PUBLIC_WIDGET}"},
    {"subdomain": "esquimalt", "municipality": "Esquimalt", "start_path": f"/22948/Clients/BookMe4?widgetId={PUBLIC_WIDGET}"},
]

CAMP_CALENDAR = re.compile(r"camp|pro[\s-]?d|break|day programs", re.I)
NOT_A_CAMP_LIST = re.compile(r"form|info|care|\bdnu\b|do not use|^zz|^xx|archive", re.I)


class PerfectMindCampsScraper(BaseScraper):
    def __init__(self, subdomain: str, municipality: str, start_path: str):
        super().__init__(source_id_prefix=f"pm_camps_{subdomain}", municipality=municipality)
        self.subdomain = subdomain
        self.base_url = f"https://{subdomain}.perfectmind.com"
        self.start_url = urljoin(self.base_url, start_path)
        segments = urlparse(self.start_url).path.strip("/").split("/")
        self.site_path = "/".join(segments[:2])  # "22950/Store"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    @staticmethod
    def _token(page_html: str) -> str:
        match = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', page_html)
        return match.group(1) if match else ""

    def _camp_calendars(self) -> list[tuple[str, str]]:
        response = self.session.get(self.start_url, timeout=30)
        response.raise_for_status()
        categories_match = re.search(r"categoriesUrl:\s*'([^']+)'", response.text)
        token = self._token(response.text)
        if not categories_match or not token:
            raise RuntimeError(f"{self.subdomain}: no category list on the booking page")
        groups = self.session.post(
            urljoin(self.start_url, categories_match.group(1)),
            headers={"X-Requested-With": "XMLHttpRequest", "RequestVerificationToken": token, "Referer": self.start_url},
            data={"__RequestVerificationToken": token},
            timeout=30,
        ).json()

        calendars = []
        for group in groups:
            group_name = group.get("Name") or ""
            for calendar in group.get("Calendars", []):
                name = calendar.get("Name") or ""
                label = f"{group_name} / {name}"
                if not (re.search(r"camp", group_name, re.I) or CAMP_CALENDAR.search(name)):
                    continue
                if NOT_A_CAMP_LIST.search(name) or NOT_A_CAMP_LIST.search(group_name):
                    continue
                link = calendar.get("BookingLink") or ""
                if link and "BookingCoursesPage" not in link:
                    continue
                calendar_id = parse_qs(urlparse(link).query).get("calendarId", [None])[0] if link else calendar.get("Id")
                if calendar_id:
                    calendars.append((label, calendar_id))
        return calendars

    def _courses(self, calendar_id: str) -> list[dict] | None:
        page_url = (
            f"{self.base_url}/{self.site_path}/BookMe4BookingPages/BookingCoursesPage"
            f"?calendarId={calendar_id}&widgetId={PUBLIC_WIDGET}&embed=False"
        )
        response = self.session.get(page_url, timeout=30)
        events_match = re.search(r"eventsUrl:\s*'([^']+)'", response.text)
        token = self._token(response.text)
        if not events_match or not token:
            return None  # Calendar isn't published (no camps posted yet).

        today = date.today()
        courses: dict[str, dict] = {}
        for page in range(40):
            data = {
                "calendarId": calendar_id,
                "widgetId": PUBLIC_WIDGET,
                "page": page,
                "values[0][Name]": "Keyword", "values[0][Value]": "", "values[0][Value2]": "", "values[0][ValueKind]": 9,
                "values[1][Name]": "Date Range",
                "values[1][Value]": f"{today.isoformat()}T00:00:00.000Z",
                "values[1][Value2]": f"{(today + timedelta(days=365)).isoformat()}T00:00:00.000Z",
                "values[1][ValueKind]": 6,
                "values[2][Name]": "Time Range", "values[2][Value]": "", "values[2][Value2]": "", "values[2][ValueKind]": 7,
                "values[3][Name]": "Age", "values[3][Value]": 0, "values[3][Value2]": 1188, "values[3][ValueKind]": 0,
                "bookingMode": 0,
                "__RequestVerificationToken": token,
            }
            result = self.session.post(
                urljoin(self.base_url, events_match.group(1)),
                data=data,
                headers={"X-Requested-With": "XMLHttpRequest", "Referer": page_url},
                timeout=30,
            )
            result.raise_for_status()
            batch = result.json().get("courses") or []
            # Paging repeats the last page instead of ending, so stop when nothing is new.
            new = [course for course in batch if course.get("EventId") not in courses]
            for course in new:
                courses[course["EventId"]] = course
            if not new:
                break
        return list(courses.values())

    @staticmethod
    def _occurrence_bounds(course: dict) -> tuple[datetime, datetime, datetime] | None:
        def epoch(value: str | None) -> int | None:
            match = re.search(r"\((-?\d+)", value or "")
            return int(match.group(1)) if match else None

        occurrences = [
            (epoch(row.get("StartDateWithOffset")), epoch(row.get("EndDateWithOffset")))
            for row in course.get("Occurrences") or []
        ]
        occurrences = sorted((start, end) for start, end in occurrences if start and end)
        if occurrences:
            first_start = local_from_epoch_ms(occurrences[0][0])
            first_end = local_from_epoch_ms(occurrences[0][1])
            last_day = local_from_epoch_ms(occurrences[-1][0])
            return first_start, first_end, last_day

        # No occurrence list: fall back to the formatted first day and times.
        try:
            day = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", course["FormattedStartDate"])
            start = datetime.strptime(f"{day} {course['FormattedStartTime']}", "%a, %b %d, %Y %I:%M %p")
            end = datetime.strptime(f"{day} {course['FirstOccurrenceFormattedEndTime']}", "%a, %b %d, %Y %I:%M %p")
            return start, end, start
        except (KeyError, ValueError):
            return None

    def _normalize(self, course: dict, calendar_label: str) -> dict | None:
        bounds = self._occurrence_bounds(course)
        if not bounds:
            return None
        start, end, last_day = bounds

        spots = (course.get("Spots") or "").strip()
        left = re.search(r"(\d+)\s*spots?\s*left", spots, re.I)
        availability = spots_label(
            int(left.group(1)) if left else None,
            full=bool(re.search(r"full", spots, re.I)),
            waitlist=bool(re.search(r"wait", spots, re.I)),
        )

        ages = ""
        if not course.get("NoAgeRestriction"):
            ages = age_range(course.get("MinAge"), course.get("MaxAge"))

        venue = (course.get("Address") or {}).get("AddressTag") or course.get("Location") or self.municipality
        occurrence = (course.get("OccurrenceDescription") or "").replace("Every ", "")
        sessions = course.get("NumberOfSessions") or len(course.get("Occurrences") or [])
        description = runs_note(start, last_day, sessions, occurrence if occurrence.lower() != "day" else "") + (
            course.get("Details") or ""
        )

        return camp_row(
            source_id=f"{self.source_id_prefix}_{course['EventId']}",
            title=course.get("EventName") or "Camp",
            venue_name=venue.strip(),
            facility_name=(course.get("Facility") or "").strip(),
            start_time=start,
            end_time=end,
            last_day=last_day,
            price=(course.get("PriceRange") or "").strip(),
            description=description,
            booking_url=(
                f"{self.base_url}/{self.site_path}/BookMe4LandingPages/CoursesLandingPage"
                f"?courseId={course['EventId']}&widgetId={PUBLIC_WIDGET}"
            ),
            availability=availability,
            ages=ages,
        )

    def scrape(self):
        print(f"[{self.municipality}] Starting PerfectMind camp scrape ({self.subdomain})...")
        events, failures, calendars = [], [], self._camp_calendars()
        for label, calendar_id in calendars:
            try:
                courses = self._courses(calendar_id)
            except (requests.RequestException, ValueError) as exc:
                failures.append(label)
                print(f"[{self.municipality}] Camp calendar failed {label}: {exc}")
                continue
            if courses is None:
                continue
            for course in courses:
                event = self._normalize(course, label)
                if event:
                    events.append(event)

        unique = {event["source_id"]: event for event in events}
        events = list(unique.values())
        print(f"[{self.municipality}] {self.subdomain} camps: {len(events)} from {len(calendars)} calendars.")
        self.save_events(events)
        if not failures:
            self.prune_unseen_upcoming(set(unique))
        return events
