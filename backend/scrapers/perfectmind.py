import re
import json
import asyncio
from datetime import datetime, timedelta
from urllib.parse import urljoin, unquote
import requests
from playwright.async_api import async_playwright

from scrapers.base import BaseScraper, classify_sport, strip_html

class PerfectMindScraper(BaseScraper):
    def __init__(
        self,
        subdomain: str,
        municipality: str,
        widget_id: str,
        account_id: str | None = "23902",
        start_path: str | None = None,
        seed_urls: list[str] | None = None,
        use_playwright: bool = True,
    ):
        super().__init__(source_id_prefix=f"pm_{subdomain}", municipality=municipality)
        self.subdomain = subdomain
        self.base_url = f"https://{subdomain}.perfectmind.com"
        self.widget_id = widget_id
        self.account_id = account_id
        self.use_playwright = use_playwright
        self.seed_urls = {self._normalize_link(url) for url in (seed_urls or [])}

        if start_path:
            self.start_url = urljoin(f"{self.base_url}/", start_path.lstrip("/"))
        elif account_id:
            self.start_url = f"{self.base_url}/{account_id}/Clients/BookMe4?widgetId={widget_id}"
        else:
            self.start_url = f"{self.base_url}/Clients/BookMe4?widgetId={widget_id}"

    def _normalize_link(self, link: str) -> str:
        normalized = unquote(link.replace("&amp;", "&")).strip()
        return normalized.replace(
            "widgetId=00000000-0000-0000-0000-000000000000",
            f"widgetId={self.widget_id}",
        )

    def _extract_category_links(self) -> set[str]:
        links = set()

        try:
            session = requests.Session()
            response = session.get(self.start_url, timeout=30)
            response.raise_for_status()
            html = response.text

            categories_match = re.search(r"categoriesUrl:\s*'([^']+)'", html)
            token_match = re.search(
                r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"',
                html,
            )

            if not categories_match or not token_match:
                return links

            categories_url = urljoin(self.start_url, categories_match.group(1))
            token = token_match.group(1)
            ajax_headers = {
                "X-Requested-With": "XMLHttpRequest",
                "RequestVerificationToken": token,
                "Referer": self.start_url,
            }
            categories_response = session.post(
                categories_url,
                headers=ajax_headers,
                data={"__RequestVerificationToken": token},
                timeout=30,
            )
            categories_response.raise_for_status()
            categories_data = categories_response.json()

            for group in categories_data:
                for calendar in group.get("Calendars", []):
                    booking_link = calendar.get("BookingLink")
                    if not booking_link:
                        continue

                    normalized = self._normalize_link(urljoin(self.base_url, booking_link))
                    if any(
                        marker in normalized
                        for marker in (
                            "/BookMe4BookingPages/Classes",
                            "/BookMe4FacilityList/List",
                        )
                    ):
                        links.add(normalized)
        except Exception:
            return links

        return links

    def _extract_page_v2_events(self, session: requests.Session, page_url: str) -> tuple[list[dict], bool]:
        try:
            response = session.get(page_url, timeout=30)
            response.raise_for_status()
            html = response.text
        except Exception:
            return [], False

        if "calendar is not allowed for the widget" in html.lower():
            return [], True

        view_match = re.search(r"view:\s*\{\s*url:\s*'([^']+)'", html)
        calendar_match = re.search(r'id="calendarId" value="([^"]+)"', html)
        widget_match = re.search(r'id="widgetId" value="([^"]+)"', html)

        if not view_match or not calendar_match:
            return [], False

        view_url = urljoin(page_url, view_match.group(1))
        payload = {
            "calendarId": calendar_match.group(1),
            "widgetId": widget_match.group(1) if widget_match else self.widget_id,
        }
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": page_url,
        }

        try:
            events_response = session.post(view_url, data=payload, headers=headers, timeout=30)
            events_response.raise_for_status()
            data = events_response.json()
        except Exception:
            return [], False

        if isinstance(data, dict) and isinstance(data.get("classes"), list):
            return data["classes"], True

        return [], False

    def _extract_direct_page_events(self, categories: set[str]) -> tuple[list[dict], set[str]]:
        session = requests.Session()
        all_events = []
        handled_urls = set()

        for page_url in sorted(categories):
            if "/BookMe4BookingPages/Classes" not in page_url:
                continue

            events, handled = self._extract_page_v2_events(session, page_url)
            if handled:
                handled_urls.add(page_url)
            if events:
                all_events.extend(events)

        return all_events, handled_urls

    async def _collect_widget_links(self, page):
        selectors = ["a[href]", "iframe[src]", "object[data]"]
        links = set()

        for selector in selectors:
            attr = "href"
            if selector.endswith("[src]"):
                attr = "src"
            elif selector.endswith("[data]"):
                attr = "data"

            discovered = await page.eval_on_selector_all(
                selector,
                f"""elements => elements
                    .map(el => el.getAttribute('{attr}'))
                    .filter(value => value && (
                        value.includes('BookMe4BookingPages/Classes') ||
                        value.includes('BookMe4FacilityList/List') ||
                        value.includes('/BookMe4?') ||
                        value.includes('/Store/BookMe4?') ||
                        value.includes('calendarId=')
                    ))""",
            )
            for link in discovered:
                links.add(self._normalize_link(urljoin(self.base_url, link)))

        return links

    async def _async_scrape(self):
        print(f"[{self.municipality}] Starting Playwright scrape...")
        all_events_raw = []
        categories = set(self.seed_urls)
        categories.update(self._extract_category_links())
        direct_events, handled_urls = self._extract_direct_page_events(categories)
        all_events_raw.extend(direct_events)
        if direct_events:
            print(f"[{self.municipality}] Direct page extraction found {len(direct_events)} events.")

        if not self.use_playwright:
            return all_events_raw

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            page.set_default_timeout(20000)

            async def handle_response(response):
                if "GetCategoriesData" in response.url or "GetCategoriesDataV2" in response.url:
                    try:
                        text = await response.text()
                        data = json.loads(text)
                        for cat in data:
                            for cal in cat.get("Calendars", []):
                                link = cal.get("BookingLink")
                                if link:
                                    categories.add(self._normalize_link(urljoin(self.base_url, link)))
                    except Exception:
                        pass
                elif "Classes" in response.url or "Calendar" in response.url or "Event" in response.url:
                    try:
                        text = await response.text()
                        if text.startswith('{') or text.startswith('['):
                            data = json.loads(text)
                            if 'classes' in data and len(data['classes']) > 0:
                                all_events_raw.extend(data['classes'])
                            elif isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict) and 'classes' in item and item['classes']:
                                        all_events_raw.extend(item['classes'])
                    except Exception:
                        pass

            page.on("response", handle_response)

            print(f"[{self.municipality}] Loading widget...")
            await page.goto(self.start_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(1500)

            for link in await self._collect_widget_links(page):
                categories.add(link)

            if not categories and (
                "BookMe4BookingPages/Classes" in self.start_url or "calendarId=" in self.start_url
            ):
                categories.add(self.start_url)

            print(f"[{self.municipality}] Found {len(categories)} calendars to scan.")

            for full_url in sorted(categories):
                if full_url in handled_urls:
                    continue
                try:
                    await page.goto(full_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(1000)
                    for link in await self._collect_widget_links(page):
                        categories.add(link)
                except Exception:
                    print(f"[{self.municipality}] Timeout visiting calendar: {full_url}")

            await browser.close()

        return all_events_raw

    def scrape(self):
        raw_events = asyncio.run(self._async_scrape())
        
        normalized_events = []
        seen_ids = set()
        
        for e in raw_events:
            ev_id = e.get("EventId")
            if not ev_id or ev_id in seen_ids:
                continue
            seen_ids.add(ev_id)
            
            try:
                time_str = e.get("FormattedStartTime", "")
                occ_date = e.get("OccurrenceDate")
                if occ_date and len(occ_date) == 8:
                    y, m, d = int(occ_date[:4]), int(occ_date[4:6]), int(occ_date[6:8])
                    t_obj = datetime.strptime(time_str, "%I:%M %p").time()
                    start_time = datetime(y, m, d, t_obj.hour, t_obj.minute)
                    duration = e.get("DurationInMinutes", 60)
                    end_time = start_time + timedelta(minutes=duration)
                else:
                    start_time = datetime.utcnow()
                    end_time = datetime.utcnow()
            except Exception:
                start_time = datetime.utcnow()
                end_time = datetime.utcnow()
                
            title = e.get("EventName", "Unknown")
                
            normalized = {
                "source_id": f"{self.source_id_prefix}_{ev_id}",
                "title": title,
                "sport_type": classify_sport(title),
                "venue_name": e.get("Location", self.municipality),
                "facility_name": e.get("Facility", ""),
                "start_time": start_time,
                "end_time": end_time,
                "price": e.get("PriceRange", ""),
                "description": strip_html(e.get("Details", "")),
                "booking_url": self.start_url
            }
            normalized_events.append(normalized)

        print(f"[{self.municipality}] Normalized {len(normalized_events)} events.")
        self.save_events(normalized_events)
        return normalized_events
