import hashlib
import re
from datetime import datetime

import requests

from scrapers.base import BaseScraper, classify_sport
from scrapers.oakbay_grid import occurrence_dates, read_cards, schedule_range


DROPIN_PAGE_URL = "https://www.oakbay.ca/parks-recreation/programs-registration-services/drop-in-schedules/"
TARGET_SPORTS = {"pickleball", "badminton", "table-tennis", "squash"}
SECTIONS = ["Henderson Recreation Centre", "Monterey Middle School"]


class OakBayPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="oakbay_pdf", municipality="Oak Bay")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _discover_pdf_url(self) -> str:
        response = self.session.get(DROPIN_PAGE_URL, timeout=30)
        response.raise_for_status()
        matches = re.findall(r'https://www\.oakbay\.ca/wp-content/uploads/[^"\']+RacquetSports[^"\']+\.pdf', response.text, re.I)
        if not matches:
            raise ValueError("Could not find Oak Bay racquet PDF")
        # Uploads are filed by year/month, so the latest path is the current schedule.
        return sorted(set(matches))[-1]

    def _should_include_event(self, title: str) -> bool:
        sport_type = classify_sport(title)
        if sport_type not in TARGET_SPORTS:
            return False
        if "lesson" in title.lower():
            return False
        return True

    def scrape(self):
        print(f"[{self.municipality}] Starting Oak Bay PDF scrape...")
        pdf_url = self._discover_pdf_url()
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        cards, page_text = read_cards(response.content, SECTIONS)
        start_date, end_date = schedule_range(page_text)

        all_events = []
        seen_ids = set()
        for card in cards:
            if not self._should_include_event(card.title):
                continue
            for day in occurrence_dates(card, start_date, end_date):
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
                        "description": f"Oak Bay racquet sports PDF schedule. {card.notes}".strip(),
                        "booking_url": pdf_url,
                    }
                )

        if not all_events:
            raise ValueError(f"Oak Bay racquet PDF produced no sessions: {pdf_url}")
        print(f"[{self.municipality}] Oak Bay PDF normalized {len(all_events)} events.")
        # The PDF is the whole season, so republishing it in full drops superseded rows.
        self.replace_existing_events()
        self.save_events(all_events)
        return all_events
