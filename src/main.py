import json
import re
from datetime import datetime, timezone
from pathlib import Path

from search import search_web
from verify_website import verify_website
from rank_leads import rank_leads
from report import create_report

ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = ROOT / "data" / "history.json"
REPORT_FILE = ROOT / "data" / "latest_report.md"

SEARCH_QUERIES = [
    "dentists in the United States that may not have an official website",
    "med spas in the United States that may not have an official website",
    "optometrists in the United States that may not have an official website",
    "veterinary clinics in the United States that may not have an official website",
    "chiropractors in the United States that may not have an official website",
]


def make_key(name: str, location: str) -> str:
    text = f"{name} {location}".lower().strip()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {"businesses": {}}
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(
            data.get("businesses", {}), dict
        ):
            raise ValueError("Unexpected history format")
        data.setdefault("businesses", {})
        return data
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        raise RuntimeError("Cannot read history.json safely") from exc


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    history = load_history()
    seen = history["businesses"]
    new_leads = {}

    for query in SEARCH_QUERIES:
        results = search_web(query, count=10)

        for result in results:
            name = str(result.get("business_name") or "").strip()
            location = str(
                result.get("location") or "United States"
            ).strip()
            if not name:
                continue

            key = make_key(name, location)
            if not key or key in seen or key in new_leads:
                continue

            website = result.get("official_website") or ""
            website = website.strip() if isinstance(website, str) else ""

            if website:
                check = verify_website(website)
                website_status = check["status"]
                website = check.get("final_url") or website
            else:
                website_status = "not_found_in_search_needs_review"

            new_leads[key] = {
                "business_name": name,
                "category": result.get("category") or "Unknown",
                "location": location,
                "phone": result.get("phone") or "",
                "email": result.get("email") or "",
                "website": website,
                "website_status": website_status,
                "source_url": result.get("source_url") or "",
                "description": result.get("description") or "",
            }

    ranked = rank_leads(list(new_leads.values()))
    top_five = ranked[:5]
    now = datetime.now(timezone.utc).isoformat()

    # Record every new candidate, not only the top five.
    for key, lead in new_leads.items():
        seen[key] = {
            "business_name": lead["business_name"],
            "location": lead["location"],
            "first_seen_utc": now,
        }

    report = create_report(top_five)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")
    save_json(HISTORY_FILE, history)
    print(report)


if __name__ == "__main__":
    main()
