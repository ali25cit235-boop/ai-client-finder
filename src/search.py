import os
import requests


TAVILY_URL = "https://api.tavily.com/search"


def search_web(query: str, count: int = 10) -> list[dict]:
    """Search the web using Tavily."""

    api_key = os.environ.get("TAVILY_API_KEY")

    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": min(max(count, 1), 10),
        "include_answer": False,
        "include_raw_content": False,
    }

    response = requests.post(
        TAVILY_URL,
        json=payload,
        timeout=30,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Tavily error {response.status_code}: "
            f"{response.text[:1000]}"
        )

    data = response.json()

    results = data.get("results", [])

    if not isinstance(results, list):
        return []

    return results
