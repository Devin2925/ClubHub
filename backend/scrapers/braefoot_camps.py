"""Braefoot Community Association school-year camps (Pro-D, winter and spring break).

Braefoot publishes dates as text on a Wix page, with registration through their own
system, so each listing links back to the page. Their summer camps page lists weekly
themes; it's parsed the same way when the summer year is still ahead.
"""
import hashlib
import html
import re
from datetime import datetime

import requests

from scrapers.base import BaseScraper
from scrapers.camp_utils import camp_row

SCHOOL_YEAR_URL = "https://www.braefoot.ca/school-year-camps"
SUMMER_URL = "https://www.braefoot.ca/summer-camps"
VENUE = "Braefoot Community Association"
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
SHORT_MONTHS = r"Jan|Feb|Mar|Apr|May|Jun|June|Jul|July|Aug|Sept|Sep|Oct|Nov|Dec"


def _page_text(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", response.text, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text)).replace("​", " ")
    return re.sub(r"\s+", " ", text)


def _hours(text: str, default=("9:00 AM", "3:00 PM")) -> tuple[str, str]:
    match = re.search(r"Camp Hours\s*(\d{1,2}(?::\d{2})?\s*[AP]M)\s*[–-]\s*(\d{1,2}(?::\d{2})?\s*[AP]M)", text, re.I)
    return (match.group(1), match.group(2)) if match else default


def _at(day: str, clock: str) -> datetime:
    clock = clock.upper().replace(" ", "")
    fmt = "%I:%M%p" if ":" in clock else "%I%p"
    return datetime.combine(datetime.strptime(day, "%B %d %Y").date(), datetime.strptime(clock, fmt).time())


class BraefootCampsScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="braefoot_camps", municipality="Saanich")

    def _row(self, title: str, first: str, last: str | None, hours: tuple[str, str], url: str, where: str, ages: str, price=""):
        start = _at(first, hours[0])
        end = _at(first, hours[1])
        last_day = _at(last, hours[1]) if last else None
        key = hashlib.md5(f"{title}|{first}".encode()).hexdigest()[:12]
        return camp_row(
            source_id=f"{self.source_id_prefix}_{key}",
            title=title,
            venue_name=VENUE,
            facility_name=where,
            start_time=start,
            end_time=end,
            last_day=last_day,
            price=price,
            description="Before care 8-9 AM and after care 3-5 PM are available. Register through Braefoot.",
            booking_url=url,
            ages=ages,
        )

    def _school_year(self) -> list[dict]:
        text = _page_text(SCHOOL_YEAR_URL)
        hours = _hours(text)
        ages = "3-12" if re.search(r"aged\s*3\s*[-–]\s*12", text) else ""
        rows = []

        pro_d = text.split("Pro-D Day Camps", 1)[-1].split("Winter Break Camp", 1)[0]
        for month, day, year in re.findall(rf"(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s*({MONTHS})\s+(\d{{1,2}})\s+(\d{{4}})", pro_d):
            rows.append(
                self._row("Braefoot Pro-D Day Camp", f"{month} {day} {year}", None, hours, SCHOOL_YEAR_URL,
                          "Braefoot and Marigold Elementary", ages)
            )

        for label, section_end in (("Winter Break Camp", "Spring Break Camp"), ("Spring Break Camp", "©")):
            section = text.split(label, 1)[-1].split(section_end, 1)[0]
            where = re.search(r"Location:\s*([A-Z][\w' ]+?)(?:\s+Register|\s*$)", section)
            for month, first, last, year in re.findall(rf"({MONTHS})\s+(\d{{1,2}})\s*[–-]\s*(\d{{1,2}})\s+(\d{{4}})", section):
                rows.append(
                    self._row(f"Braefoot {label}", f"{month} {first} {year}", f"{month} {last} {year}", hours,
                              SCHOOL_YEAR_URL, f"{where.group(1).strip()} Elementary" if where else "", ages)
                )
        return rows

    def _summer(self) -> list[dict]:
        text = _page_text(SUMMER_URL)
        year_match = re.search(r"Summer Camps (\d{4})", text)
        if not year_match:
            return []
        year = year_match.group(1)
        rows = []
        # "Week 2 - Pirates & Mermaids (July 6- July 10) - $200 Braefoot Park"
        for theme, m1, d1, m2, d2, price in re.findall(
            rf"Week\s*\d+\s*[-–]\s*([^()]+?)\s*\(\s*({SHORT_MONTHS})\w*\s+(\d{{1,2}})\s*[-–]\s*(?:({SHORT_MONTHS})\w*\s+)?(\d{{1,2}})\s*\)\s*[-–]\s*(\$\d+)",
            text,
        ):
            month_start = datetime.strptime(m1[:3], "%b").strftime("%B")
            month_end = datetime.strptime((m2 or m1)[:3], "%b").strftime("%B")
            rows.append(
                self._row(f"Braefoot Summer Camp: {theme.strip()}", f"{month_start} {d1} {year}",
                          f"{month_end} {d2} {year}", ("9:00 AM", "3:00 PM"), SUMMER_URL, "Braefoot Park", "", price)
            )
        return rows

    def scrape(self):
        print("[Saanich] Starting Braefoot camp scrape...")
        events = self._school_year()
        try:
            events += self._summer()
        except (requests.RequestException, ValueError) as exc:
            print(f"[Saanich] Braefoot summer page failed: {exc}")
        today = datetime.now().date()
        events = [
            event for event in events
            if datetime.fromisoformat(event["end_date"] or event["start_time"].date().isoformat()).date() >= today
        ]
        if not events:
            raise RuntimeError("Braefoot pages listed no upcoming camp dates")
        print(f"[Saanich] Braefoot camps normalized {len(events)} rows.")
        self.replace_existing_events()
        self.save_events(events)
        return events
