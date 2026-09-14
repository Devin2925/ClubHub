import argparse
import json
import re
from datetime import datetime, timezone

import requests

from camp_sources import CAMP_SOURCES


KEYWORD_RE = re.compile(
    r"\b(camp|camps|summer|spring\s+break|winter\s+break|pro[-\s]?d|kids?|children|youth|teen)\b",
    re.I,
)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def audit_source(source: dict, timeout: int = 20) -> dict:
    url = source.get("registration_url") or source.get("primary_url")
    result = {
        "source_key": source["source_key"],
        "name": source["name"],
        "municipality": source["municipality"],
        "automation_status": source["automation_status"],
        "scrape_strategy": source["scrape_strategy"],
        "url": url,
        "ok": False,
        "status_code": None,
        "final_url": "",
        "title": "",
        "keyword_hits": 0,
        "error": "",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    if not url:
        result["error"] = "No URL configured."
        return result

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 ClubHub camp source audit"},
            timeout=timeout,
            allow_redirects=True,
        )
        text = response.text or ""
        title_match = TITLE_RE.search(text)
        result.update(
            {
                "ok": response.status_code < 400,
                "status_code": response.status_code,
                "final_url": response.url,
                "title": _clean_text(title_match.group(1)) if title_match else "",
                "keyword_hits": len(KEYWORD_RE.findall(text)),
            }
        )
    except Exception as exc:
        result["error"] = str(exc)

    return result


def audit_sources(timeout: int = 20) -> list[dict]:
    return [audit_source(source, timeout=timeout) for source in CAMP_SOURCES]


def main():
    parser = argparse.ArgumentParser(description="Audit configured Victoria-area camp source URLs.")
    parser.add_argument("--output", help="Optional JSON output file.")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds.")
    args = parser.parse_args()

    results = audit_sources(timeout=args.timeout)
    payload = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "ok": len([row for row in results if row["ok"]]),
        "failed": len([row for row in results if not row["ok"]]),
        "sources": results,
    }
    text = json.dumps(payload, indent=2, sort_keys=True)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")
    print(text)


if __name__ == "__main__":
    main()

