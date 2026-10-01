import requests
from urllib.parse import urlparse


def verify_website(url: str) -> dict:
    """Check whether a supplied website URL is reachable."""
    if not url or not url.strip():
        return {"status": "missing_url", "url": ""}

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.hostname:
        return {"status": "invalid_url", "url": url}

    try:
        response = requests.get(
            url,
            timeout=15,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ClientFinder/1.0)"
            },
        )
        return {
            "status": (
                "reachable"
                if response.status_code < 400
                else "http_error"
            ),
            "url": url,
            "final_url": response.url,
            "http_status": response.status_code,
        }
    except requests.RequestException as exc:
        return {
            "status": "unreachable_or_blocked",
            "url": url,
            "error": str(exc),
        }
