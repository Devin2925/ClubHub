import time
import requests
from datetime import datetime
from scrapers.base import BaseScraper, classify_sport, strip_html

API_URL = "https://anc.ca.apm.activecommunities.com/saanich/rest/onlinecalendar/multicenter/events?locale=en-US"
CALENDAR_PAGE = "https://anc.ca.apm.activecommunities.com/saanich/calendars"

HEADERS = {
    "Content-Type": "application/json",
    "Referer": CALENDAR_PAGE,
    "User-Agent": "Mozilla/5.0",
}

SAANICH_CENTERS = {
    94: "Cedar Hill Recreation Centre",
    96: "G.R. Pearkes Recreation Centre",
    74: "Saanich Commonwealth Place",
    98: "Gordon Head Recreation Centre",
    95: "Colquitz Middle School",
    97: "Gordon Head Middle School",
}

CALENDAR_IDS_TO_TRY = list(range(1, 21))


class SaanichScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="saanich", municipality="Saanich")
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _init_session(self):
        try:
            resp = self.session.get(CALENDAR_PAGE, timeout=15)
            resp.raise_for_status()
            return True
        except Exception as e:
            print(f"[Saanich] Warning: {e}")
            return False

    def _fetch_events(self, calendar_id: int, center_ids: list) -> list:
        payload = {
            "calendar_id": calendar_id,
            "center_ids": center_ids,
            "display_all": 0,
            "search_start_time": "",
            "search_end_time": "",
            "activity_category_ids": [],
            "activity_ids": [],
            "activity_max_age": None,
            "activity_min_age": None,
            "activity_sub_category_ids": [],
            "event_type_ids": [],
            "facility_ids": [],
        }
        try:
            resp = self.session.post(API_URL, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            body = data.get("body", {})
            all_events = []

            # Format 1
            for group in body.get("calendar_group_list", []):
                all_events.extend(group.get("events", []))
            
            # Format 2
            for center in body.get("center_events", []):
                all_events.extend(center.get("events", []))

            return all_events
        except Exception:
            return []

    def _normalize_event(self, raw_event: dict) -> dict:
        title = raw_event.get("title", "Unknown")
        event_item_id = raw_event.get("event_item_id", 0)

        venue_name = "Saanich"
        facility_name = ""
        center_id = None
        if raw_event.get("facilities"):
            fac = raw_event["facilities"][0]
            venue_name = fac.get("center_name", "Saanich").strip("* ")
            facility_name = fac.get("facility_name", "")
            center_id = fac.get("center_id")

        start_str = raw_event.get("start_time", "")
        end_str = raw_event.get("end_time", "")
        try:
            start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            start_time = datetime.utcnow()
            end_time = datetime.utcnow()

        price_info = raw_event.get("price", {})
        price = price_info.get("estimate_price", "")
        if price_info.get("free"):
            price = "Free"

        return {
            "source_id": f"saanich_{event_item_id}",
            "title": title,
            "sport_type": classify_sport(title),
            "venue_name": venue_name,
            "facility_name": facility_name,
            "center_id": center_id,
            "start_time": start_time,
            "end_time": end_time,
            "price": price,
            "description": strip_html(raw_event.get("description", "")),
            "booking_url": raw_event.get("activity_detail_url", ""),
        }

    def scrape(self):
        print(f"[{self.municipality}] Starting scrape...")
        if not self._init_session():
            return []

        all_events = []
        seen_ids = set()
        center_ids = list(SAANICH_CENTERS.keys())

        for cal_id in CALENDAR_IDS_TO_TRY:
            raw_events = self._fetch_events(cal_id, center_ids)
            for ev in raw_events:
                eid = ev.get("event_item_id")
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    all_events.append(self._normalize_event(ev))
            time.sleep(0.5)

        self.save_events(all_events)
        return all_events
