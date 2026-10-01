import requests
from urllib.parse import urlparse


NON_OFFICIAL_DOMAINS = {
    "yelp.com",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "yellowpages.com",
    "mapquest.com",
    "bbb.org",
    "healthgrades.com",
    "zocdoc.com",
    "webmd.com",
}


def normalize_url(url: str) -> str:
    if not url:
        return ""

    url = url.strip()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def is_non_official_domain(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    hostname = hostname.removeprefix("www.")

    for domain in NON_OFFICIAL_DOMAINS:
        if hostname == domain or hostname.endswith("." + domain):
            return True

    return False


def verify_website(url: str) -> dict:
    """Verify whether a candidate URL is reachable and likely official."""

    url = normalize_url(url)

    if not url:
        return {
            "status": "not_found",
            "url": "",
        }

    parsed = urlparse(url)

    if not parsed.hostname:
        return {
            "status": "invalid_url",
            "url": url,
        }

    if is_non_official_domain(url):
        return {
            "status": "non_official_source",
            "url": url,
        }

    try:
        response = requests.get(
            url,
            timeout=15,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ClientFinder/1.0)"
            },
        )

        if response.status_code < 400:
            return {
                "status": "reachable",
                "url": url,
                "final_url": response.url,
                "http_status": response.status_code,
            }

        return {
            "status": "http_error",
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
