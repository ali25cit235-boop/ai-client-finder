import json
import re
from datetime import datetime, timezone
from pathlib import Path

from search import search_web
from rank_leads import rank_leads
from report import create_report

ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = ROOT / "data" / "history.json"
REPORT_FILE = ROOT / "data" / "latest_report.md"

SEARCH_QUERIES = [
    "independent dentist small business in the United States official website",
    "independent med spa in the United States business contact",
    "independent optometrist clinic in the United States contact",
    "independent veterinary clinic in the United States contact",
    "independent chiropractor clinic in the United States contact",
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
        raise RuntimeError("Cannot safely read history.json") from exc


def main() -> None:
    history = load_history()
    seen = history["businesses"]
    candidates = {}

    for query in SEARCH_QUERIES:
        for result in search_web(query, count=10):
            title = str(result.get("page_title") or "").strip()
            source_url = str(result.get("source_url") or "").strip()
            description = str(result.get("description") or "").strip()

            # Search-result titles are candidates, not verified business data.
            name = str(result.get("business_name") or title).strip()
            if not name or not source_url:
                continue

            location = str(
                result.get("location") or "United States"
            ).strip()
            key = make_key(name, location)
            if not key or key in seen or key in candidates:
                continue

            website = result.get("official_website")
            if not isinstance(website, str):
                website = ""

            candidates[key] = {
                "business_name": name,
                "category": result.get("category") or "Needs review",
                "location": location,
                "phone": result.get("phone") or "",
                "email": result.get("email") or "",
                "website": website,
                "website_status": (
                    "candidate_website_needs_verification"
                    if website
                    else "unknown_needs_manual_verification"
                ),
                "source_url": source_url,
                "description": description,
            }

    ranked = rank_leads(list(candidates.values()))
    top_five = ranked[:5]
    now = datetime.now(timezone.utc).isoformat()

    # Save all newly discovered candidates to reduce repeats.
    for key, lead in candidates.items():
        seen[key] = {
            "business_name": lead["business_name"],
            "location": lead["location"],
            "first_seen_utc": now,
            "source_url": lead["source_url"],
        }

    report = create_report(top_five)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(history, indent=2), encoding="utf-8"
    )
    print(report)


if __name__ == "__main__":
    main()
