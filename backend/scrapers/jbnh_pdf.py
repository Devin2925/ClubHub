import hashlib
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from io import BytesIO
from urllib.parse import urljoin

import requests
from pypdf import PdfReader
from sqlalchemy import delete

from models import Event, SessionLocal
from scrapers.base import BaseScraper


PAGE_URL = "https://www.jamesbaynewhorizons.ca/monthly-calendar.html"
# Marks a vertical gap in a cell, so a banner line is not glued onto the event above it.
LINE_BREAK = "\x00"
DAY_NAMES = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]


class JBNHPDFScraper(BaseScraper):
    def __init__(self):
        super().__init__("jbnh_pdf", "Victoria")
        self.venue_name = "James Bay New Horizons"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _discover_pdf_url(self) -> str:
        response = self.session.get(PAGE_URL, timeout=30)
        response.raise_for_status()
        match = re.search(r"/uploads/[^\"]+\.pdf", response.text)
        if not match:
            raise ValueError("Could not find James Bay New Horizons PDF")
        return urljoin(PAGE_URL, match.group(0))

    def _read_pdf(self, url: str) -> PdfReader:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return PdfReader(BytesIO(response.content))

    def _read_layout_pages(self, reader: PdfReader) -> list[str]:
        return [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]

    def _page_fragments(self, page) -> list[tuple[float, float, str]]:
        fragments = []

        def visit(text, cm, tm, font_dict, font_size):
            text = text.strip()
            if not text:
                return
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            # Text drawn inside form XObjects comes back without a usable position.
            if x == 0 and y == 0:
                return
            fragments.append((x, y, text))

        page.extract_text(visitor_text=visit)
        return fragments

    def _row_boundaries(self, ys: list[float], grid_top: float, row_count: int, row_height: float) -> list[float]:
        # The grid is a background image, so snap each nominal row edge to the widest text gap near it.
        boundaries = [grid_top]
        ordered = sorted(set(ys), reverse=True)
        for row in range(1, row_count):
            nominal = grid_top - row * row_height
            best_gap, best_mid = 0.0, nominal
            for upper, lower in zip(ordered, ordered[1:]):
                mid = (upper + lower) / 2
                if abs(mid - nominal) <= 25 and upper - lower > best_gap:
                    best_gap, best_mid = upper - lower, mid
            boundaries.append(best_mid)
        boundaries.append(0.0)
        return boundaries

    def _collect_lines_by_position(self, reader: PdfReader, month: int, year: int) -> dict[date, list[str]]:
        items = defaultdict(list)
        rows_per_page = 3

        for page in reader.pages:
            fragments = self._page_fragments(page)
            header_y = next((y for _, y, text in fragments if text.replace(" ", "") == "SUNDAY"), None)
            if header_y is None:
                continue

            column_width = float(page.mediabox.width) / 7
            grid_top = header_y - 10
            row_height = grid_top / rows_per_page
            body = [(x, y, text) for x, y, text in fragments if y < grid_top]
            boundaries = self._row_boundaries([y for _, y, _ in body], grid_top, rows_per_page, row_height)

            def locate(x: float, y: float) -> tuple[int, int] | None:
                column = int((x + 8) // column_width)
                if not 0 <= column < 7:
                    return None
                for row in range(rows_per_page):
                    if boundaries[row + 1] <= y < boundaries[row]:
                        return row, column
                return None

            # Date numbers sit right-aligned in each cell; use them to anchor each row to a week.
            week_starts: dict[int, list[date]] = defaultdict(list)
            cells: dict[tuple[int, int], list[tuple[float, float, str]]] = defaultdict(list)
            for x, y, text in body:
                cell = locate(x, y)
                if cell is None:
                    continue
                is_date_number = re.fullmatch(r"\d{1,2}", text) and (x + 8) % column_width > 90
                if is_date_number:
                    try:
                        week_starts[cell[0]].append(date(year, month, int(text)) - timedelta(days=cell[1]))
                    except ValueError:
                        pass
                    continue
                cells[cell].append((x, y, text))

            for (row, column), cell_fragments in cells.items():
                if not week_starts.get(row):
                    continue
                week_start = max(set(week_starts[row]), key=week_starts[row].count)
                cell_date = week_start + timedelta(days=column)
                if cell_date.month != month:
                    continue

                lines: list[list[tuple[float, str]]] = []
                line_ys: list[float] = []
                for x, y, text in sorted(cell_fragments, key=lambda frag: (-frag[1], frag[0])):
                    if line_ys and abs(line_ys[-1] - y) <= 1.5:
                        lines[-1].append((x, text))
                    else:
                        lines.append([(x, text)])
                        line_ys.append(y)

                for index, line in enumerate(lines):
                    if index and line_ys[index - 1] - line_ys[index] > 15:
                        items[cell_date].append(LINE_BREAK)
                    joined = ""
                    for _, text in sorted(line):
                        # "11:00" is sometimes drawn as a separate "1" glyph followed by "1:00".
                        if re.fullmatch(r"\d", joined) and text[:1].isdigit():
                            joined += text
                        else:
                            joined = f"{joined} {text}".strip()
                    items[cell_date].append(joined)

        return items

    def _parse_month_year(self, text: str) -> tuple[int, int]:
        match = re.search(r"([A-Z][a-z]+)\s+(\d{4})", text)
        if not match:
            raise ValueError("Could not parse JBNH month")
        month_name, year_str = match.groups()
        return datetime.strptime(month_name, "%B").month, int(year_str)

    def _boundaries(self, header_line: str) -> list[int]:
        positions = [header_line.index(day) for day in DAY_NAMES]
        boundaries = [0]
        for idx in range(len(positions) - 1):
            boundaries.append((positions[idx] + positions[idx + 1]) // 2)
        boundaries.append(len(header_line))
        return boundaries

    def _collect_lines_by_date(self, layout_pages: list[str], month: int, year: int) -> dict[date, list[str]]:
        items = defaultdict(list)
        for page_text in layout_pages:
            lines = page_text.splitlines()
            header_index = next((i for i, line in enumerate(lines) if "SUNDAY" in line and "SATURDAY" in line), None)
            if header_index is None:
                continue
            boundaries = self._boundaries(lines[header_index])
            current_dates: dict[int, date] = {}

            for raw_line in lines[header_index + 1 :]:
                if "CALENDAR IS SUBJECT" in raw_line:
                    break
                for idx in range(len(DAY_NAMES)):
                    segment = raw_line[boundaries[idx] : boundaries[idx + 1]].strip()
                    if not segment:
                        continue
                    match = re.match(r"^(\d{1,2})(?:\s+(.*))?$", segment)
                    if match:
                        day_number = int(match.group(1))
                        trailing = (match.group(2) or "").strip()
                        try:
                            current_dates[idx] = date(year, month, day_number)
                        except ValueError:
                            continue
                        if trailing:
                            items[current_dates[idx]].append(trailing)
                        continue
                    if idx in current_dates:
                        items[current_dates[idx]].append(segment)
        return items

    def _replace_month_events(self, month: int, year: int):
        # Only clear the month this PDF covers; the next month's calendar is posted before this one ends.
        month_start = datetime(year, month, 1)
        month_end = datetime(year + (month == 12), month % 12 + 1, 1)
        db = SessionLocal()
        try:
            deleted = db.execute(
                delete(Event).where(
                    Event.source == self.source_id_prefix,
                    Event.start_time >= month_start,
                    Event.start_time < month_end,
                )
            ).rowcount or 0
            db.commit()
            print(f"[{self.municipality}] Replaced {deleted} existing {month_start:%B} events for {self.source_id_prefix}")
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _parse_start_time(self, raw: str) -> tuple[int, int]:
        hour, minute = raw.split(":")
        hour_int = int(hour)
        minute_int = int(minute)
        if hour_int < 8:
            hour_int += 12
        return hour_int, minute_int

    def _normalize_title(self, value: str) -> str:
        title = re.sub(r"\s+", " ", value).strip(" -")
        title = title.replace("w/ ", "with ")
        title = title.replace("  ", " ")
        return title

    def _parse_events_for_date(self, event_date: date, lines: list[str], booking_url: str) -> list[dict]:
        cleaned_lines = [
            line if line == LINE_BREAK else re.sub(r"\s+", " ", line).strip()
            for line in lines
            if line == LINE_BREAK or line.strip()
        ]
        parsed = []
        current = None
        for line in cleaned_lines:
            if line == LINE_BREAK:
                if current:
                    parsed.append(current)
                current = None
                continue
            if any(token in line for token in ["JAMES BAY NEW HORIZONS", "Phone 250", "www.jamesbaynewhorizons", "Legend:"]):
                continue
            if "Centre Closed" in line:
                continue

            match = re.match(r"^(\d{1,2}:\d{2})\s+(.*)$", line)
            if match:
                if current:
                    parsed.append(current)
                current = {"time": match.group(1), "title_parts": [match.group(2).strip()]}
                continue

            if current:
                current["title_parts"].append(line)

        if current:
            parsed.append(current)

        titles = [(item["time"], self._normalize_title(" ".join(item["title_parts"]))) for item in parsed]
        events = []
        for time_str, title in titles:
            if not title:
                continue
            # Some cells overprint a corrected title ("Rotary Pack" / "Rotary Packs"); keep the longer one.
            if any(other_time == time_str and other != title and other.startswith(title) for other_time, other in titles):
                continue
            start_hour, start_minute = self._parse_start_time(time_str)
            start_dt = datetime(event_date.year, event_date.month, event_date.day, start_hour, start_minute)
            end_dt = start_dt + timedelta(hours=1)
            source_key = f"{title}|{start_dt.isoformat()}|{booking_url}"
            source_hash = hashlib.md5(source_key.encode("utf-8")).hexdigest()[:16]
            events.append(
                {
                    "source_id": f"{self.source_id_prefix}_{source_hash}",
                    "title": title,
                    "venue_name": self.venue_name,
                    "facility_name": "",
                    "start_time": start_dt,
                    "end_time": end_dt,
                    "price": "",
                    "description": "James Bay New Horizons monthly calendar PDF. The source calendar lists start times only, so event duration defaults to 60 minutes.",
                    "booking_url": booking_url,
                }
            )
        return events

    def scrape(self):
        print(f"[{self.municipality}] Starting James Bay New Horizons PDF scrape...")
        try:
            pdf_url = self._discover_pdf_url()
            reader = self._read_pdf(pdf_url)
            layout_pages = self._read_layout_pages(reader)
            month, year = self._parse_month_year(layout_pages[0])
            lines_by_date = self._collect_lines_by_position(reader, month, year)
            if not lines_by_date:
                lines_by_date = self._collect_lines_by_date(layout_pages, month, year)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 404:
                self.last_status_note = f"publisher_page_unavailable: {PAGE_URL} returned 404"
                print(
                    f"[{self.municipality}] James Bay New Horizons skipped: "
                    f"publisher page returned 404."
                )
                return []
            print(f"[{self.municipality}] James Bay New Horizons scrape failed: {exc}")
            return []
        except Exception as exc:
            print(f"[{self.municipality}] James Bay New Horizons scrape failed: {exc}")
            return []

        events = []
        cutoff = datetime.utcnow() - timedelta(days=1)
        for event_date, lines in sorted(lines_by_date.items()):
            for event in self._parse_events_for_date(event_date, lines, pdf_url):
                if event["start_time"] < cutoff:
                    continue
                events.append(event)

        print(f"[{self.municipality}] James Bay New Horizons normalized {len(events)} events.")
        if events:
            self._replace_month_events(month, year)
        self.save_events(events)
        return events
