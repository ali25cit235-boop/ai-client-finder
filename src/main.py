import json
from pathlib import Path
from urllib.parse import urlparse

from search import search_web
from rank_leads import rank_leads
from report import create_report

ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = ROOT / "data" / "history.json"
REPORT_FILE = ROOT / "data" / "latest_report.md"

SEARCH_QUERIES = [
    'dentist "contact" "United States"',
    'med spa "contact" "United States"',
    'optometrist "contact" "United States"',
    'veterinary clinic "contact" "United States"',
    'chiropractor "contact" "United States"',
]


def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {"businesses": {}}
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raise RuntimeError(
            "history.json could not be read; refusing to overwrite it"
        )


def save_history(history: dict) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(history, indent=2), encoding="utf-8"
    )


def normalize_domain(url: str) -> str:
    if not url:
        return ""
    host = (
        urlparse(url if "://" in url else "https://" + url).hostname or ""
    )
    return host.lower().removeprefix("www.")


def main() -> None:
    history = load_history()
    seen = history.setdefault("businesses", {})
    candidates = []

    for query in SEARCH_QUERIES:
        for result in search_web(query, count=10):
            url = result.get("url", "")
            domain = normalize_domain(url)
            if not domain or domain in seen:
                continue

            # Search results are candidates, not proof of no website.
            candidates.append({
                "business_name": result.get("title", "").strip(),
                "category": query.split()[0].strip('"'),
                "location": "United States",
                "website": url,
                "website_status": "candidate_page_needs_review",
                "source_url": url,
                "description": result.get("description", ""),
                "domain": domain,
            })

    ranked = rank_leads(candidates)
    top_five = ranked[:5]

    for lead in top_five:
        key = lead.get("domain") or lead.get("business_name", "").lower()
        seen[key] = {
            "business_name": lead.get("business_name", ""),
            "first_seen": "",
        }

    report = create_report(top_five)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")
    save_history(history)
    print(report)


if __name__ == "__main__":
    main()
