import hashlib
import re
from datetime import date, datetime, timedelta
from io import BytesIO

import requests
from pypdf import PdfReader

from scrapers.base import BaseScraper, classify_sport


DROPIN_PAGE_URL = "https://www.oakbay.ca/parks-recreation/programs-registration-services/drop-in-schedules/"
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_TO_INDEX = {day: index for index, day in enumerate(DAY_NAMES)}
SECTION_VENUES = {
    "Henderson Recreation Centre": "Henderson Recreation Centre",
    "Neighbourhood Learning Centre": "Neighbourhood Learning Centre",
    "Oak Bay Indoor Sports Field": "Oak Bay Indoor Sports Field",
    "Monterey Recreation Centre": "Monterey Recreation Centre",
}


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
        return matches[0]

    def _fetch_layout_text(self, pdf_url: str) -> str:
        response = self.session.get(pdf_url, timeout=30)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        return reader.pages[0].extract_text(extraction_mode="layout") or ""

    def _parse_date_range(self, layout_text: str) -> tuple[date, date]:
        match = re.search(
            r"\((\w+)\s+(\d+)(?:st|nd|rd|th)\s+–\s+(\w+)\s+(\d+)(?:st|nd|rd|th),\s+(\d{4})\)",
            layout_text,
        )
        if not match:
            raise ValueError("Could not parse Oak Bay group fitness PDF date range")
        start_month, start_day, end_month, end_day, year = match.groups()
        start_date = datetime.strptime(
            f"{start_month} {start_day} {year}",
            "%B %d %Y",
        ).date()
        end_date = datetime.strptime(
            f"{end_month} {end_day} {year}",
            "%B %d %Y",
        ).date()
        return start_date, end_date

    def _day_boundaries(self, header_line: str) -> list[int]:
        positions = [header_line.index(day) for day in DAY_NAMES]
        boundaries = [0]
        for idx in range(len(positions) - 1):
            boundaries.append((positions[idx] + positions[idx + 1]) // 2)
        boundaries.append(len(header_line))
        return boundaries

    def _extract_sections(self, layout_text: str) -> dict[str, dict[str, list[str]]]:
        lines = layout_text.splitlines()
        header_index = next(i for i, line in enumerate(lines) if "Monday" in line and "Sunday" in line)
        boundaries = self._day_boundaries(lines[header_index])

        sections = {
            venue_name: {day: [] for day in DAY_NAMES}
            for venue_name in SECTION_VENUES.values()
        }
        current_section = "Henderson Recreation Centre"

        for raw_line in lines[header_index + 1 :]:
            line = raw_line.rstrip()
            compact = " ".join(line.split())
            if not compact:
                continue
            if compact.startswith("How to Register Online for Fitness Classes"):
                break
            if compact in SECTION_VENUES:
                current_section = SECTION_VENUES[compact]
                continue

            for idx, day in enumerate(DAY_NAMES):
                segment = raw_line[boundaries[idx] : boundaries[idx + 1]].strip()
                if segment:
                    sections[current_section][day].append(segment)

        return sections

    def _is_time_line(self, line: str) -> bool:
        compact = line.replace(" ", "")
        return bool(re.search(r"\d{1,2}:\d{2}(am|pm)?-\d{1,2}:\d{2}(am|pm)", compact, re.I))

    def _is_note_line(self, line: str) -> bool:
        lowered = line.lower()
        return (
            line.startswith("*")
            or line.startswith("Note:")
            or "statutory holidays" in lowered
            or "pre-registration" in lowered
            or "remains open for drop-in users" in lowered
            or "during circuit training" in lowered
        )

    def _parse_time_range(self, raw: str) -> tuple[str, str]:
        compact = raw.replace(" ", "").replace("*", "").lower()
        start_raw, end_raw = compact.split("-", 1)

        end_match = re.match(r"(\d{1,2}:\d{2})(am|pm)", end_raw)
        if not end_match:
            raise ValueError(f"Unparseable end time: {raw}")
        end_clock, end_meridiem = end_match.groups()

        start_match = re.match(r"(\d{1,2}:\d{2})(am|pm)?", start_raw)
        if not start_match:
            raise ValueError(f"Unparseable start time: {raw}")
        start_clock, start_meridiem = start_match.groups()
        if not start_meridiem:
            start_meridiem = end_meridiem

        return f"{start_clock}{start_meridiem}", f"{end_clock}{end_meridiem}"

    def _parse_day_events(self, lines: list[str]) -> list[dict]:
        events = []
        title_lines: list[str] = []

        for raw_line in lines:
            line = " ".join(raw_line.split())
            if not line:
                continue

            if self._is_note_line(line):
                if events and not title_lines:
                    events[-1]["note"] = f"{events[-1]['note']} {line}".strip()
                else:
                    title_lines.append(line)
                continue

            if self._is_time_line(line):
                if not title_lines:
                    continue
                title = " ".join(title_lines).strip()
                start_time, end_time = self._parse_time_range(line)
                events.append(
                    {
                        "title": title,
                        "start_time_str": start_time,
                        "end_time_str": end_time,
                        "note": "",
                    }
                )
                title_lines = []
                continue

            title_lines.append(line)

        return events

    def _build_occurrences(self, venue_name: str, weekday: str, events: list[dict], start_date: date, end_date: date, pdf_url: str) -> list[dict]:
        weekday_index = DAY_TO_INDEX[weekday]
        current = max(datetime.utcnow().date(), start_date)
        occurrences = []

        while current <= end_date:
            if current.weekday() == weekday_index:
                for event in events:
                    start_dt = datetime.strptime(
                        f"{current.isoformat()} {event['start_time_str']}",
                        "%Y-%m-%d %I:%M%p",
                    )
                    end_dt = datetime.strptime(
                        f"{current.isoformat()} {event['end_time_str']}",
                        "%Y-%m-%d %I:%M%p",
                    )
                    if end_dt <= start_dt:
                        end_dt += timedelta(days=1)

                    source_key = f"{venue_name}|{event['title']}|{start_dt.isoformat()}"
                    source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
                    description = "Oak Bay Group Fitness Drop-In PDF schedule."
                    if venue_name == "Monterey Recreation Centre":
                        description += " Note: drop-in programs at Monterey Recreation Centre do not offer a pre-registration option."
                    elif venue_name in {"Henderson Recreation Centre", "Neighbourhood Learning Centre"}:
                        description += " Registration opens up to four days in advance via Oak Bay PerfectMind."
                    if event["note"]:
                        description += f" {event['note']}"

                    occurrences.append(
                        {
                            "source_id": f"{self.source_id_prefix}_{source_hash}",
                            "title": event["title"],
                            "sport_type": classify_sport(event["title"]),
                            "venue_name": venue_name,
                            "facility_name": "",
                            "start_time": start_dt,
                            "end_time": end_dt,
                            "price": "",
                            "description": description.strip(),
                            "booking_url": pdf_url,
                        }
                    )
            current += timedelta(days=1)

        return occurrences

    def scrape(self):
        print(f"[{self.municipality}] Starting Oak Bay group fitness PDF scrape...")
        try:
            pdf_url = self._discover_pdf_url()
            layout_text = self._fetch_layout_text(pdf_url)
            start_date, end_date = self._parse_date_range(layout_text)
            sections = self._extract_sections(layout_text)
        except Exception as exc:
            print(f"[{self.municipality}] Oak Bay group fitness PDF failed: {exc}")
            return []

        all_events = []
        seen_ids = set()
        for venue_name, day_map in sections.items():
            for weekday, lines in day_map.items():
                events = self._parse_day_events(lines)
                for event in self._build_occurrences(venue_name, weekday, events, start_date, end_date, pdf_url):
                    if event["source_id"] in seen_ids:
                        continue
                    seen_ids.add(event["source_id"])
                    all_events.append(event)

        print(f"[{self.municipality}] Oak Bay group fitness PDF normalized {len(all_events)} events.")
        self.save_events(all_events)
        return all_events
