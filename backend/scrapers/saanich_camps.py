"""Saanich day camps from the ActiveNet activity search.

The drop-in calendar (scrapers/saanich.py) never lists camps; they're registered
programs. The search API lists them by the "Day Camps - ..." categories, plus a
"camp" keyword search for sport camps filed elsewhere (power skating, volleyball,
lifesaving). Each camp's detail endpoints give the fee and its meeting days.
"""
import html
import json
import re
from datetime import datetime

import requests

from scrapers.base import BaseScraper
from scrapers.camp_utils import age_range, camp_row, runs_note, spots_label

BASE = "https://anc.ca.apm.activecommunities.com/saanich"
SEARCH_PAGE = f"{BASE}/activity/search?onlineSiteId=0&activity_select_param=2&viewMode=list"
LIST_URL = f"{BASE}/rest/activities/list?locale=en-US"
CAMP_CATEGORY_NAME = re.compile(r"^day camps", re.I)
KEYWORDS = ["camp", "pro d", "pro-d"]

VENUE_NAMES = {
    "G. R. Pearkes Rec Centre": "G. R. Pearkes Recreation Centre",
    "Cedar Hill Rec Centre": "Cedar Hill Recreation Centre",
    "Gordon Head Rec Centre": "Gordon Head Recreation Centre",
}


def _venue(label: str) -> str:
    name = html.unescape(label or "").strip("* ").strip()
    return VENUE_NAMES.get(name, re.sub(r"\bRec Centre\b", "Recreation Centre", name)) or "Saanich Recreation"


class SaanichCampsScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_id_prefix="saanich_camps", municipality="Saanich")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": SEARCH_PAGE})

    def _search(self, *, category_ids=None, keyword="") -> list[dict]:
        items = []
        for page in range(1, 20):
            payload = {
                "activity_search_pattern": {
                    "activity_select_param": 2,
                    "activity_category_ids": category_ids or [],
                    "activity_keyword": keyword,
                },
                "activity_transfer_pattern": {},
            }
            response = self.session.post(
                LIST_URL,
                json=payload,
                headers={
                    "page_info": json.dumps(
                        {"order_by": "Date range", "page_number": page, "total_records_per_page": 50}
                    )
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            items.extend(data["body"]["activity_items"])
            if page >= (data["headers"]["page_info"].get("total_page") or 1):
                break
        return items

    def _detail(self, path: str, activity_id: int) -> dict:
        response = self.session.get(f"{BASE}/rest/activity/detail/{path}{activity_id}?locale=en-US", timeout=30)
        response.raise_for_status()
        return response.json().get("body") or {}

    def _camp_category_ids(self) -> list[str]:
        response = self.session.get(f"{BASE}/rest/activities/filters?locale=en-US", timeout=30)
        response.raise_for_status()
        categories = response.json()["body"].get("categories") or []
        return [row["id"] for row in categories if CAMP_CATEGORY_NAME.search(row.get("desc", ""))]

    def _normalize(self, item: dict) -> dict | None:
        activity_id = item["id"]
        name = html.unescape(item.get("name", "")).strip(" *")
        if not re.search(r"camp|pro[\s-]?d", name, re.I) and not item.get("_from_category"):
            return None

        dates = self._detail("meetingandregistrationdates/", activity_id).get("meeting_and_registration_dates") or {}
        patterns = [row for row in dates.get("activity_patterns") or [] if row.get("pattern_dates")]
        if patterns:
            first, last = patterns[0], patterns[-1]
            times = first["pattern_dates"][0]
            start = datetime.fromisoformat(f"{first['beginning_date']} {times['starting_time']}")
            end = datetime.fromisoformat(f"{first['beginning_date']} {times['ending_time']}")
            last_day = datetime.fromisoformat(last.get("ending_date") or first["beginning_date"])
        else:
            # Some camps (power skating) have no meeting pattern, only the list's dates and hours.
            clock = re.match(r"\s*(\d{1,2}:\d{2}\s*[AP]M)\s*-\s*(\d{1,2}:\d{2}\s*[AP]M|Noon)", item.get("time_range") or "", re.I)
            day = item.get("date_range_start")
            last = item.get("date_range_end")
            if not day:
                detail = self._detail("", activity_id).get("detail") or {}
                day, last = detail.get("first_date"), detail.get("last_date")
            if not day or not clock:
                return None
            end_clock = "12:00 PM" if clock.group(2).lower() == "noon" else clock.group(2)
            start = datetime.strptime(f"{day} {clock.group(1)}", "%Y-%m-%d %I:%M %p")
            end = datetime.strptime(f"{day} {end_clock}", "%Y-%m-%d %I:%M %p")
            last_day = datetime.fromisoformat(last or day)
            times = {}

        prices = (self._detail("estimateprice/", activity_id).get("estimateprice") or {}).get("prices") or []
        fee = ""
        for price in prices:
            for detail in price.get("details") or []:
                if detail.get("price"):
                    fee = detail["price"]
                    break
            if fee:
                break

        min_age = item.get("age_min_year") or 0
        if item.get("age_min_month"):
            min_age += item["age_min_month"] / 12
        max_age = None
        if item.get("age_max_year"):
            # ActiveNet ages are "at least X but less than Y".
            max_age = item["age_max_year"] - (0 if item.get("age_max_month") else 1)

        status = (item.get("urgent_message") or {}).get("status_description") or ""
        openings = str(item.get("openings") or "")
        full = "full" in status.lower()
        open_spots = int(openings) if openings.isdigit() else None
        left = re.search(r"(\d+)\s*space", status)
        if left:
            open_spots = int(left.group(1))

        weekdays = times.get("weekdays") or ""
        description = html.unescape(re.sub(r"<[^>]+>", " ", item.get("desc") or ""))
        if patterns:
            # Count meeting days across every pattern (Mon-Wed plus a shorter Thursday is one camp).
            index = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
            sessions, names = 0, []
            for row in patterns:
                for slot in row.get("pattern_dates") or []:
                    days = [name.strip()[:3].lower() for name in (slot.get("weekdays") or "").split(",")]
                    names += [name for name in days if name in index and name not in names]
                    wanted = {index[name] for name in days if name in index}
                    day = datetime.fromisoformat(row["beginning_date"]).date()
                    stop = datetime.fromisoformat(row.get("ending_date") or row["beginning_date"]).date()
                    while day <= stop:
                        sessions += day.weekday() in wanted
                        day = day.fromordinal(day.toordinal() + 1)
                sessions -= len(row.get("exception_dates") or [])
            plural = {"fri": "Fridays", "mon": "Mondays", "tue": "Tuesdays", "wed": "Wednesdays", "thu": "Thursdays", "sat": "Saturdays", "sun": "Sundays"}
            days_text = plural[names[0]] if len(names) == 1 else ", ".join(name.title() for name in names)
            description = runs_note(start, last_day, sessions, days_text) + description

        return camp_row(
            source_id=f"{self.source_id_prefix}_{activity_id}",
            title=name,
            venue_name=_venue((item.get("location") or {}).get("label", "")),
            start_time=start,
            end_time=end,
            last_day=last_day,
            price=fee,
            description=description,
            booking_url=item.get("detail_url") or SEARCH_PAGE,
            availability=spots_label(open_spots, full=full and not open_spots),
            ages=age_range(min_age or None, max_age),
        )

    def scrape(self):
        print("[Saanich] Starting Saanich camp scrape...")
        self.session.get(SEARCH_PAGE, timeout=30)
        items: dict[int, dict] = {}
        for item in self._search(category_ids=self._camp_category_ids()):
            items[item["id"]] = {**item, "_from_category": True}
        for keyword in KEYWORDS:
            for item in self._search(keyword=keyword):
                items.setdefault(item["id"], item)

        events = []
        for item in items.values():
            try:
                event = self._normalize(item)
            except requests.RequestException as exc:
                print(f"[Saanich] Camp detail failed for {item.get('id')}: {exc}")
                continue
            if event:
                events.append(event)

        print(f"[Saanich] Saanich camps normalized {len(events)} of {len(items)} listings.")
        if not events:
            raise RuntimeError("Saanich camp search returned no camps")
        self.save_events(events)
        self.prune_unseen_upcoming({event["source_id"] for event in events})
        return events
