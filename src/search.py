import os
import requests


def search_web(query: str, count: int = 10) -> list[dict]:
    """Search the web using the Brave Search API."""
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if not api_key:
        raise RuntimeError("BRAVE_SEARCH_API_KEY is not configured")

    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={
            "X-Subscription-Token": api_key,
            "Accept": "application/json",
        },
        params={"q": query, "count": min(max(count, 1), 20)},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    results = []
    for item in payload.get("web", {}).get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
        })
    return results
