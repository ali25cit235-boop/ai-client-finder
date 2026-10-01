import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from search import search_web
from ai_client import extract_leads
from verify_website import verify_website
from rank_leads import rank_leads
from report import create_report


ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = ROOT / "data" / "history.json"
REPORT_FILE = ROOT / "data" / "latest_report.md"


SEARCH_TARGETS = [
    ("dentist", "Houston, Texas"),
    ("med spa", "Phoenix, Arizona"),
    ("optometrist", "Columbus, Ohio"),
    ("veterinary clinic", "Charlotte, North Carolina"),
    ("chiropractor", "Indianapolis, Indiana"),
    ("dentist", "Nashville, Tennessee"),
    ("med spa", "Tampa, Florida"),
    ("optometrist", "Kansas City, Missouri"),
    ("veterinary clinic", "Oklahoma City, Oklahoma"),
    ("chiropractor", "Richmond, Virginia"),
    ("dentist", "Albuquerque, New Mexico"),
    ("med spa", "Sacramento, California"),
    ("optometrist", "Louisville, Kentucky"),
    ("veterinary clinic", "Birmingham, Alabama"),
    ("chiropractor", "Boise, Idaho"),
    ("dentist", "Raleigh, North Carolina"),
    ("med spa", "Las Vegas, Nevada"),
    ("optometrist", "Omaha, Nebraska"),
    ("veterinary clinic", "Tulsa, Oklahoma"),
    ("chiropractor", "Memphis, Tennessee"),
]


def normalize_text(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        (value or "").lower(),
    ).strip()


def normalize_domain(url: str) -> str:
    if not url:
        return ""

    parsed = urlparse(
        url if "://" in url else "https://" + url
    )

    hostname = (parsed.hostname or "").lower()
    return hostname.removeprefix("www.")


def make_business_key(name: str, location: str) -> str:
    return normalize_text(f"{name} {location}")


def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {
            "search_cursor": 0,
            "businesses": {},
        }

    try:
        data = json.loads(
            HISTORY_FILE.read_text(encoding="utf-8")
        )

        if not isinstance(data, dict):
            raise ValueError("History must be an object")

        data.setdefault("search_cursor", 0)
        data.setdefault("businesses", {})

        if not isinstance(data["businesses"], dict):
            raise ValueError("Businesses history must be an object")

        return data

    except (json.JSONDecodeError, OSError, ValueError) as exc:
        raise RuntimeError(
            "Cannot safely read history.json"
        ) from exc


def save_history(history: dict) -> None:
    HISTORY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    HISTORY_FILE.write_text(
        json.dumps(history, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    history = load_history()
    seen = history["businesses"]

    cursor = int(history.get("search_cursor", 0))
    selected_targets = []

    for offset in range(2):
        index = (cursor + offset) % len(SEARCH_TARGETS)
        selected_targets.append(SEARCH_TARGETS[index])

    history["search_cursor"] = (
        cursor + len(selected_targets)
    ) % len(SEARCH_TARGETS)

    print("Selected searches:")

    raw_results = []

    for category, location in selected_targets:
        query = (
            f"independent {category} in {location} "
            f"local business directory contact "
            f"official website"
        )

        print(f"Searching: {query}")

        results = search_web(
            query,
            count=10,
        )

        for result in results:
            result["search_query"] = query

        raw_results.extend(results)

    print(f"Raw search results: {len(raw_results)}")

    if not raw_results:
        raise RuntimeError(
            "Tavily returned no search results"
        )

    ai_leads = extract_leads(
        raw_results,
        max_leads=15,
    )

    print(f"AI extracted leads: {len(ai_leads)}")

    candidates = {}

    for lead in ai_leads:
        name = str(
            lead.get("business_name") or ""
        ).strip()

        location = str(
            lead.get("location") or ""
        ).strip()

        source_url = str(
            lead.get("source_url") or ""
        ).strip()

        if not name or not location or not source_url:
            continue

        key = make_business_key(
            name,
            location,
        )

        if not key or key in seen or key in candidates:
            continue

        website = lead.get("official_website")

        if isinstance(website, str):
            website = website.strip()
        else:
            website = ""

        if website:
            website_check = verify_website(
                website
            )

            if website_check["status"] == "reachable":
                website_status = "verified_reachable"
                website = (
                    website_check.get("final_url")
                    or website
                )

            elif website_check["status"] == "non_official_source":
                website = ""
                website_status = "not_found_in_sources"

            else:
                website_status = (
                    website_check["status"]
                )

        else:
            website_status = "not_found_in_sources"

        candidates[key] = {
            "business_name": name,
            "category": str(
                lead.get("category") or "Unknown"
            ).strip(),
            "location": location,
            "phone": str(
                lead.get("phone") or ""
            ).strip(),
            "email": str(
                lead.get("email") or ""
            ).strip(),
            "website": website,
            "website_status": website_status,
            "source_url": source_url,
            "evidence": str(
                lead.get("evidence") or ""
            ).strip(),
        }

    ranked = rank_leads(
        list(candidates.values())
    )

    top_five = ranked[:5]

    now = datetime.now(
        timezone.utc
    ).isoformat()

    for key, lead in candidates.items():
        seen[key] = {
            "business_name": lead["business_name"],
            "location": lead["location"],
            "first_seen_utc": now,
            "source_url": lead["source_url"],
        }

    report = create_report(top_five)

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_FILE.write_text(
        report,
        encoding="utf-8",
    )

    save_history(history)

    print("")
    print(report)


if __name__ == "__main__":
    main()
