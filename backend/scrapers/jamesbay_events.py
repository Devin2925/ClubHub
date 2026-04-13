import hashlib
import html
import re
from datetime import datetime, timedelta

import requests

from scrapers.base import BaseScraper


class JamesBayEventsScraper(BaseScraper):
    PAGE_URL = "https://www.jamesbaycentre.ca/jb-events/"
    WP_API_URL = "https://www.jamesbaycentre.ca/wp-json/wp/v2/pages"
    MEALS_PAGE_SLUG = "55-dinners-cafe"

    def __init__(self):
        super().__init__("james_bay_events", "Victoria")
        self.venue_name = "James Bay Community School Centre"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _extract_lines(self, text: str) -> list[str]:
        match = re.search(r"<section class=\"entry-content\".*?</section>", text, re.S)
        chunk = match.group(0) if match else text
        chunk = re.sub(r"(?is)<(script|style).*?</\1>", " ", chunk)
        chunk = re.sub(r"(?i)<br\s*/?>", "\n", chunk)
        chunk = re.sub(r"(?i)</(p|h2|h3|li)>", "\n", chunk)
        chunk = re.sub(r"<[^>]+>", " ", chunk)
        chunk = html.unescape(chunk)
        lines = [" ".join(line.split()) for line in chunk.splitlines()]
        return [line for line in lines if line]

    def _parse_date(self, value: str) -> datetime | None:
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    def _fetch_wp_page(self, slug: str) -> dict | None:
        response = self.session.get(self.WP_API_URL, params={"slug": slug}, timeout=30)
        response.raise_for_status()
        pages = response.json()
        return pages[0] if pages else None

    def _normalize_events(self, lines: list[str]) -> list[dict]:
        events = []
        date_pattern = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}$")
        skip_titles = {
            "UPCOMING EVENTS",
            "Events are listed in date order",
            "CONTENTS",
        }

        i = 0
        while i < len(lines) - 1:
            title = lines[i]
            if title in skip_titles:
                i += 1
                continue
            if date_pattern.match(lines[i + 1]):
                start_date = self._parse_date(lines[i + 1])
                if not start_date:
                    i += 1
                    continue
                description_lines = []
                j = i + 2
                while j < len(lines):
                    if date_pattern.match(lines[j]):
                        break
                    if j + 1 < len(lines) and date_pattern.match(lines[j + 1]):
                        break
                    description_lines.append(lines[j])
                    j += 1
                description = " ".join(description_lines).strip()
                if description and "register" in description.lower():
                    booking_url = self.PAGE_URL
                else:
                    booking_url = self.PAGE_URL
                start_time = start_date.replace(hour=9, minute=0)
                end_time = start_time + timedelta(hours=8)
                source_key = f"{title}|{start_date.date().isoformat()}"
                source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
                events.append(
                    {
                        "source_id": f"{self.source_id_prefix}_{source_hash}",
                        "title": title,
                        "venue_name": self.venue_name,
                        "facility_name": "",
                        "start_time": start_time,
                        "end_time": end_time,
                        "price": "",
                        "description": description or "Time was not listed on the source page.",
                        "booking_url": booking_url,
                    }
                )
                i = j
                continue
            i += 1
        return events

    def _extract_meal_order_links(self, rendered_html: str) -> list[str]:
        links = re.findall(r'href="([^"]+)"', rendered_html)
        return [
            link
            for link in links
            if "jamesbaycentre.ca" in link and ("meals" in link or "order-form" in link)
        ]

    def _parse_meal_time(self, value: str) -> tuple[str, str] | None:
        cleaned = value.replace(" ", "").lower()
        match = re.search(r"(\d{1,2}:\d{2})(am|pm)(?:-(\d{1,2}:\d{2})(am|pm))?", cleaned)
        if not match:
            return None
        start_clock, start_meridiem, end_clock, end_meridiem = match.groups()
        if end_clock and end_meridiem:
            return f"{start_clock}{start_meridiem}", f"{end_clock}{end_meridiem}"
        start_dt = datetime.strptime(f"{start_clock}{start_meridiem}", "%I:%M%p")
        end_dt = start_dt + timedelta(hours=1)
        return (
            start_dt.strftime("%I:%M%p").lstrip("0").lower(),
            end_dt.strftime("%I:%M%p").lstrip("0").lower(),
        )

    def _normalize_meal_pages(self) -> list[dict]:
        meals_page = self._fetch_wp_page(self.MEALS_PAGE_SLUG)
        if not meals_page:
            return []

        order_form_links = self._extract_meal_order_links(meals_page["content"]["rendered"])
        events = []
        seen = set()

        for order_link in order_form_links:
            slug = order_link.rstrip("/").split("/")[-1]
            page = self._fetch_wp_page(slug)
            if not page:
                continue

            rendered = html.unescape(page["content"]["rendered"])
            text = re.sub(r"(?is)<(script|style).*?</\1>", " ", rendered)
            text = re.sub(r"(?i)<br\s*/?>", "\n", text)
            text = re.sub(r"(?i)</(p|h1|h2|h3|h4|h5|li)>", "\n", text)
            text = re.sub(r"<[^>]+>", " ", text)
            text = "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())

            pattern = re.compile(
                r"(Tuesday|Thursday),\s+([A-Z][a-z]+)\s+(\d{1,2})\s*"
                r"\((Pickup Dinner|Sit Down Lunch)\s+(\d{1,2}:\d{2}(?:am|pm)(?:-\d{1,2}:\d{2}(?:am|pm))?)\)\s*-\s*"
                r"([A-Za-z0-9&'’\-\+\/\., ]+?)\s+Please indicate below",
                re.I,
            )

            for match in pattern.finditer(text):
                weekday, month_name, day_str, meal_type, time_text, meal_name = match.groups()
                event_date = datetime.strptime(
                    f"{month_name} {day_str} {datetime.utcnow().year}",
                    "%B %d %Y",
                ).date()
                time_range = self._parse_meal_time(time_text)
                if not time_range:
                    continue
                start_dt = datetime.strptime(
                    f"{event_date.isoformat()} {time_range[0]}",
                    "%Y-%m-%d %I:%M%p",
                )
                end_dt = datetime.strptime(
                    f"{event_date.isoformat()} {time_range[1]}",
                    "%Y-%m-%d %I:%M%p",
                )
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)

                title = f"55+ {meal_type} - {meal_name.strip()}"
                source_key = f"{title}|{start_dt.isoformat()}|{order_link}"
                source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
                if source_hash in seen:
                    continue
                seen.add(source_hash)

                events.append(
                    {
                        "source_id": f"{self.source_id_prefix}_{source_hash}",
                        "title": title,
                        "venue_name": self.venue_name,
                        "facility_name": "",
                        "start_time": start_dt,
                        "end_time": end_dt,
                        "price": "",
                        "description": f"James Bay 55+ meals order form. {weekday} meal service.",
                        "booking_url": order_link,
                    }
                )

        return events

    def scrape(self):
        print(f"[{self.municipality}] Starting James Bay events scrape...")
        try:
            response = self.session.get(self.PAGE_URL, timeout=30)
            response.raise_for_status()
            lines = self._extract_lines(response.text)
            events = self._normalize_events(lines)
            events.extend(self._normalize_meal_pages())
        except Exception as exc:
            print(f"[{self.municipality}] James Bay scrape failed: {exc}")
            return []

        deduped = {}
        for event in events:
            deduped[event["source_id"]] = event
        events = list(deduped.values())

        print(f"[{self.municipality}] James Bay normalized {len(events)} events.")
        self.save_events(events)
        return events
