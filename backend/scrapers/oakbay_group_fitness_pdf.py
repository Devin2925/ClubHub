import hashlib
import re
from datetime import datetime

import requests

from scrapers.base import BaseScraper, classify_sport
from scrapers.oakbay_grid import bc_statutory_holidays, occurrence_dates, read_cards, schedule_range


DROPIN_PAGE_URL = "https://www.oakbay.ca/parks-recreation/programs-registration-services/drop-in-schedules/"
SECTIONS = [
    "Henderson Recreation Centre",
    "Neighbourhood Learning Centre",
    "Oak Bay Indoor Sports Field",
    "Monterey Recreation Centre",
]


class OakBayGroupFitnessPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="oakbay_group_fitness_pdf", municipality="Oak Bay")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _discover_pdf_url(self) -> str:
        response = self.session.get(DROPIN_PAGE_URL, timeout=30)
        response.raise_for_status()
        matches = re.findall(r'https://www\.oakbay\.ca/wp-content/uploads/[^"\']+Fitness-Drop-in-Schedule[^"\']+\.pdf', response.text, re.I)
        if not matches:
            raise ValueError("Could not find Oak Bay group fitness PDF")
        # Uploads are filed by year/month, so the latest path is the current schedule.
        return sorted(set(matches))[-1]

    def _description(self, venue_name: str, notes: str) -> str:
        description = "Oak Bay Group Fitness Drop-In PDF schedule."
        if venue_name == "Monterey Recreation Centre":
            description += " Note: drop-in programs at Monterey Recreation Centre do not offer a pre-registration option."
        elif venue_name in {"Henderson Recreation Centre", "Neighbourhood Learning Centre"}:
            description += " Registration opens up to four days in advance via Oak Bay PerfectMind."
        if notes:
            description += f" {notes}"
        return description

    def scrape(self):
        print(f"[{self.municipality}] Starting Oak Bay group fitness PDF scrape...")
        pdf_url = self._discover_pdf_url()
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        cards, page_text = read_cards(response.content, SECTIONS)
        start_date, end_date = schedule_range(page_text)

        skip_dates = set()
        # The note sits beside the grid, so other columns' text can land mid-sentence.
        if re.search(r"not\s+run\s+on\s+statutory\b.{0,80}?\bholidays", " ".join(page_text.split()), re.I):
            for year in {start_date.year, end_date.year}:
                skip_dates |= bc_statutory_holidays(year)

        all_events = []
        seen_ids = set()
        for card in cards:
            for day in occurrence_dates(card, start_date, end_date, skip_dates):
                start_dt = datetime.combine(day, card.start)
                end_dt = datetime.combine(day, card.end)
                source_key = f"{card.section}|{card.title}|{start_dt.isoformat()}"
                source_id = f"{self.source_id_prefix}_{hashlib.md5(source_key.encode('utf-8')).hexdigest()[:16]}"
                if source_id in seen_ids:
                    continue
                seen_ids.add(source_id)
                all_events.append(
                    {
                        "source_id": source_id,
                        "title": card.title,
                        "sport_type": classify_sport(card.title),
                        "venue_name": card.section,
                        "facility_name": "",
                        "start_time": start_dt,
                        "end_time": end_dt,
                        "price": "",
                        "description": self._description(card.section, card.notes),
                        "booking_url": pdf_url,
                    }
                )

        if not all_events:
            raise ValueError(f"Oak Bay group fitness PDF produced no sessions: {pdf_url}")
        print(f"[{self.municipality}] Oak Bay group fitness PDF normalized {len(all_events)} events.")
        # The PDF is the whole season, so republishing it in full drops superseded rows.
        self.replace_existing_events()
        self.save_events(all_events)
        return all_events
