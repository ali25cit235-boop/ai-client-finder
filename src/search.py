import os
import requests


def search_web(query: str, count: int = 10) -> list[dict]:
    """Search the web using Tavily Search API."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": min(max(count, 1), 20),
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    results = []
    for item in payload.get("results", []):
        results.append({
            "business_name": "",
            "category": "",
            "location": "United States",
            "phone": "",
            "email": "",
            "official_website": None,
            "source_url": item.get("url", ""),
            "description": item.get("content", ""),
            "page_title": item.get("title", ""),
        })

    return results
