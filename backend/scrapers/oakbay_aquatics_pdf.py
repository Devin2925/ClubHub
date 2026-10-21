import hashlib
import re
from datetime import datetime

import requests

from scrapers.base import BaseScraper
from scrapers.oakbay_grid import occurrence_dates, read_cards, schedule_range


DROPIN_PAGE_URL = "https://www.oakbay.ca/parks-recreation/programs-registration-services/drop-in-schedules/"
DROP_IN_SECTION = "Aquatics Drop-in Schedule"
AQUAFIT_SECTION = "Aquafit Schedule"
# Legend symbols printed after a session title.
FAMILY_MARK = "🞙"
CLUB_MARK = "^"
# Registered lessons and school rentals are on the chart but not open to the public.
NOT_PUBLIC_RE = re.compile(r"^swim\s+lessons$|^school\s+swim", re.I)
SWIM_WORD_RE = re.compile(r"swim|length|width|aquafit|waterworks|leisure", re.I)


class OakBayAquaticsPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__("oakbay_aquatics_pdf", "Oak Bay")
        self.venue_name = "Oak Bay Recreation Centre"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _discover_pdf_url(self) -> str:
        response = self.session.get(DROPIN_PAGE_URL, timeout=30)
        response.raise_for_status()
        matches = re.findall(r'https://www\.oakbay\.ca/wp-content/uploads/[^"\']+Aquatics-Drop-in-Schedule[^"\']+\.pdf', response.text, re.I)
        if not matches:
            raise ValueError("Could not find Oak Bay aquatics PDF")
        # Uploads are filed by year/month, so the latest path is the current schedule.
        return sorted(set(matches))[-1]

    def _title(self, section: str, raw: str) -> str:
        title = " ".join(raw.replace(FAMILY_MARK, " ").replace(CLUB_MARK, " ").split())
        title = re.sub(r"\s*&\s*", " and ", title) if title.lower().startswith("leisure &") else title
        if section == AQUAFIT_SECTION:
            return title if re.search(r"aquafit|waterworks", title, re.I) else f"{title} Aquafit"
        return title if SWIM_WORD_RE.search(title) else f"{title} Swim"

    def _description(self, raw_title: str, notes: str) -> str:
        description = "Oak Bay aquatics drop-in PDF schedule."
        if FAMILY_MARK in raw_title:
            description += " Families are welcome in the small pool."
        if CLUB_MARK in raw_title:
            description += " Clubs sharing the pool."
        # Cancellation dates are already dropped from the occurrences, so only keep
        # notes that still describe the session.
        notes = re.sub(r"\bcancel+ed\b.*$", "", notes, flags=re.I).strip()
        if notes:
            description += f" {notes}"
        return description

    def scrape(self):
        print(f"[{self.municipality}] Starting Oak Bay aquatics PDF scrape...")
        pdf_url = self._discover_pdf_url()
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        cards, page_text = read_cards(response.content, [DROP_IN_SECTION, AQUAFIT_SECTION])
        start_date, end_date = schedule_range(page_text)

        events = []
        seen_ids = set()
        for card in cards:
            title = self._title(card.section, card.title)
            if NOT_PUBLIC_RE.search(title) or re.search(r"no\s+public\s+access", card.notes, re.I):
                continue
            for day in occurrence_dates(card, start_date, end_date):
                start_dt = datetime.combine(day, card.start)
                end_dt = datetime.combine(day, card.end)
                source_key = f"{self.venue_name}|{title}|{start_dt.isoformat()}"
                source_id = f"{self.source_id_prefix}_{hashlib.md5(source_key.encode('utf-8')).hexdigest()[:16]}"
                if source_id in seen_ids:
                    continue
                seen_ids.add(source_id)
                events.append(
                    {
                        "source_id": source_id,
                        "title": title,
                        "venue_name": self.venue_name,
                        "facility_name": "Pool",
                        "start_time": start_dt,
                        "end_time": end_dt,
                        "price": "",
                        "description": self._description(card.title, card.notes),
                        "booking_url": pdf_url,
                    }
                )

        if not events:
            raise ValueError(f"Oak Bay aquatics PDF produced no sessions: {pdf_url}")
        print(f"[{self.municipality}] Oak Bay aquatics PDF normalized {len(events)} events.")
        # The chart covers the whole season, so republishing it in full drops superseded rows.
        self.replace_existing_events()
        self.save_events(events)
        return events
