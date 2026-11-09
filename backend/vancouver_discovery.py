"""Live check of the Metro Vancouver drop-in sources in vancouver_registry.py.

Pulls every ActiveNet drop-in calendar and every PerfectMind drop-in calendar we
know about and counts upcoming sessions per venue, so the registry's venue list
and statuses can be re-verified at any time. Nothing is written to the database.

    ./venv/bin/python vancouver_discovery.py              # all sources
    ./venv/bin/python vancouver_discovery.py vancouver    # one source key
    ./venv/bin/python vancouver_discovery.py --json logs/vancouver_discovery.json

ActiveNet calendars return roughly eight weeks of sessions; PerfectMind calendars
return the first page (about two weeks), so their counts are a floor.
"""
import argparse
import collections
import json
import re
import sys
import time
from urllib.parse import urljoin

import requests

from scrapers.perfectmind import PerfectMindScraper

PUBLIC_WIDGET = "15f6af07-39c5-473e-b053-96653f77a406"

ACTIVENET_TENANTS = {
    "vancouver": "Vancouver",
    "burnaby": "Burnaby",
    "cityofportcoquitlam": "Port Coquitlam",
    "langleycityrecconnect": "Langley City",
}

PERFECTMIND_SITES = {
    "cityofcoquitlam": {"municipality": "Coquitlam", "account_id": "23902", "widget_id": PUBLIC_WIDGET},
    "nvrc": {"municipality": "North Vancouver", "account_id": "23734", "widget_id": "a28b2c65-61af-407f-80d1-eaa58f30a94a"},
    "cityofnewwestminster": {"municipality": "New Westminster", "account_id": "23693", "widget_id": "50a33660-b4f7-44d9-9256-e10effec8641"},
    "cityofwhiterock": {"municipality": "White Rock", "account_id": "23697", "widget_id": PUBLIC_WIDGET},
    "richmondcity": {"municipality": "Richmond", "account_id": "23650", "widget_id": PUBLIC_WIDGET},
    "cityofportmoody": {"municipality": "Port Moody", "account_id": None, "widget_id": PUBLIC_WIDGET},
    "cityofmapleridge": {"municipality": "Maple Ridge", "account_id": None, "widget_id": PUBLIC_WIDGET},
    "cityofdelta": {"municipality": "Delta", "account_id": "24140", "widget_id": "0da93182-93fb-4314-87bd-a8ba4ee9a4c9"},
}

# A PerfectMind calendar is a drop-in schedule when its group or its own name says so.
PM_DROP_IN = re.compile(r"drop|registered visit|book a visit|public swim|schedules", re.I)
PM_NOT_DROP_IN = re.compile(
    r"^z|do not use|discontinued|archive|lesson|prereq|private|staff|volunteer|rental|admin|camp|court",
    re.I,
)


def _clean_venue(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip("* ")).strip()


def activenet_sessions(tenant: str) -> dict:
    """Sessions per centre across every public ActiveNet online calendar."""
    base = f"https://anc.ca.apm.activecommunities.com/{tenant}"
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": f"{base}/calendars", "Content-Type": "application/json"})
    session.get(f"{base}/calendars", timeout=30)
    calendars = session.get(
        f"{base}/rest/onlinecalendar/calendars?locale=en-US",
        headers={"page_info": json.dumps({"order_by": "Name", "page_number": 1, "total_records_per_page": 200})},
        timeout=30,
    ).json()["body"]["calendars"]
    calendars = [row for row in calendars if not row["hide_on_internet"] and not row["retired"]]

    venues: dict[str, dict] = {}
    for calendar in calendars:
        filters = session.post(
            f"{base}/rest/onlinecalendar/filters?locale=en-US", json={"calendar_id": calendar["calendar_id"]}, timeout=30
        ).json()["body"]
        center_ids = [row["id"] for row in filters.get("center") or []]
        for start in range(0, len(center_ids), 10):
            payload = {
                "calendar_id": calendar["calendar_id"],
                "center_ids": center_ids[start : start + 10],
                "display_all": 0,
                "search_start_time": "",
                "search_end_time": "",
                "facility_ids": [],
                "activity_category_ids": [],
                "activity_sub_category_ids": [],
                "activity_ids": [],
                "activity_min_age": None,
                "activity_max_age": None,
                "event_type_ids": [],
            }
            body = session.post(f"{base}/rest/onlinecalendar/multicenter/events?locale=en-US", json=payload, timeout=60).json().get("body") or {}
            for group in body.get("center_events") or []:
                for event in group.get("events") or []:
                    facility = (event.get("facilities") or [{}])[0]
                    name = _clean_venue(facility.get("center_name") or group.get("center_name"))
                    row = venues.setdefault(name, {"sessions": set(), "calendars": set(), "titles": collections.Counter(), "days": set()})
                    row["sessions"].add((event.get("event_item_id"), event.get("start_time")))
                    row["calendars"].add(_clean_venue(calendar["name"]))
                    row["titles"][re.sub(r"[|*]", "", event.get("title") or "").strip()] += 1
                    row["days"].add((event.get("start_time") or "")[:10])
            time.sleep(0.2)
    return {"calendars": [_clean_venue(row["name"]) for row in calendars], "venues": venues}


def perfectmind_sessions(subdomain: str, municipality: str, account_id: str | None, widget_id: str) -> dict:
    """Sessions per location across a PerfectMind widget's drop-in calendars (first page each)."""
    scraper = PerfectMindScraper(subdomain=subdomain, municipality=municipality, widget_id=widget_id, account_id=account_id)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    page = session.get(scraper.start_url, timeout=30)
    token = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', page.text)
    categories_url = re.search(r"categoriesUrl:\s*'([^']+)'", page.text)
    if not token or not categories_url:
        raise RuntimeError(f"{subdomain}: widget page refused ({page.url[:120]})")
    groups = session.post(
        urljoin(page.url, categories_url.group(1)),
        headers={"X-Requested-With": "XMLHttpRequest", "RequestVerificationToken": token.group(1), "Referer": page.url},
        data={"__RequestVerificationToken": token.group(1)},
        timeout=30,
    ).json()

    venues: dict[str, dict] = {}
    calendars = []
    for group in groups:
        group_name = group.get("Name") or ""
        if PM_NOT_DROP_IN.search(group_name):
            continue
        for calendar in group.get("Calendars") or []:
            name = calendar.get("Name") or ""
            if PM_NOT_DROP_IN.search(name) or not (PM_DROP_IN.search(name) or PM_DROP_IN.search(group_name)):
                continue
            link = calendar.get("BookingLink") or ""
            if link and "BookMe4BookingPages/Classes" not in link:
                continue
            if link:
                url = scraper._normalize_link(urljoin(scraper.base_url, link))
            elif account_id:
                url = (
                    f"{scraper.base_url}/{account_id}/Clients/BookMe4BookingPages/Classes"
                    f"?calendarId={calendar['Id']}&widgetId={widget_id}&embed=False"
                )
            else:
                continue
            events, _ = scraper._extract_page_v2_events(session, url)
            calendars.append(f"{group_name} / {name}")
            for event in events:
                venue = _clean_venue(event.get("Location")) or municipality
                row = venues.setdefault(venue, {"sessions": set(), "calendars": set(), "titles": collections.Counter(), "days": set()})
                row["sessions"].add(event.get("EventId") or (event.get("EventName"), event.get("FormattedStartDate"), event.get("FormattedStartTime")))
                row["calendars"].add(name)
                row["titles"][(event.get("EventName") or "").strip()] += 1
                row["days"].add(event.get("FormattedStartDate") or "")
    return {"calendars": calendars, "venues": venues}


def summarize(key: str, municipality: str, system: str, result: dict) -> dict:
    venues = [
        {
            "venue": name,
            "sessions": len(row["sessions"]),
            "days": len(row["days"]),
            "calendars": sorted(row["calendars"]),
            "top_titles": [title for title, _ in row["titles"].most_common(6)],
        }
        for name, row in result["venues"].items()
    ]
    venues.sort(key=lambda row: -row["sessions"])
    return {
        "source": key,
        "municipality": municipality,
        "system": system,
        "calendars": len(result["calendars"]),
        "sessions": sum(row["sessions"] for row in venues),
        "venues": venues,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sources", nargs="*", help="Source keys to check (default: all)")
    parser.add_argument("--json", help="Write the full report to this path")
    args = parser.parse_args()

    wanted = set(args.sources)
    jobs = [(key, name, "ActiveNet") for key, name in ACTIVENET_TENANTS.items()]
    jobs += [(key, site["municipality"], "PerfectMind") for key, site in PERFECTMIND_SITES.items()]
    if wanted:
        jobs = [job for job in jobs if job[0] in wanted]
        unknown = wanted - {job[0] for job in jobs}
        if unknown:
            sys.exit(f"Unknown source keys: {', '.join(sorted(unknown))}")

    report = []
    for key, municipality, system in jobs:
        try:
            if system == "ActiveNet":
                result = activenet_sessions(key)
            else:
                site = PERFECTMIND_SITES[key]
                result = perfectmind_sessions(key, site["municipality"], site["account_id"], site["widget_id"])
        except (requests.RequestException, RuntimeError, ValueError, KeyError) as exc:
            print(f"\n## {municipality} ({system}: {key}) FAILED: {exc}")
            report.append({"source": key, "municipality": municipality, "system": system, "error": str(exc)})
            continue
        summary = summarize(key, municipality, system, result)
        report.append(summary)
        print(f"\n## {municipality} ({system}: {key}) {summary['sessions']} sessions, "
              f"{len(summary['venues'])} venues, {summary['calendars']} calendars")
        for row in summary["venues"]:
            print(f"   {row['sessions']:>5}  {row['venue']}  [{', '.join(row['top_titles'][:3])}]")

    ok = [row for row in report if "error" not in row]
    print(f"\nTOTAL: {sum(row['sessions'] for row in ok)} sessions at "
          f"{sum(len(row['venues']) for row in ok)} venues from {len(ok)} of {len(report)} sources")
    if args.json:
        with open(args.json, "w") as handle:
            json.dump(report, handle, indent=1)
        print(f"Wrote {args.json}")


if __name__ == "__main__":
    main()
