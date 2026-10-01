import json
import os
import requests


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/free"


def _parse_json(text: str) -> dict:
    text = (text or "").strip()

    if text.startswith("```"):
        text = text.replace("```json", "", 1)
        text = text.replace("```", "", 1)
        text = text.strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("AI did not return valid JSON")

    return json.loads(text[start:end + 1])


def extract_leads(search_results: list[dict], max_leads: int = 15) -> list[dict]:
    """Use an OpenRouter free model to extract real business leads."""

    api_key = os.environ.get("OPENROUTER_API_KEY")

    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    prepared_results = []

    for index, result in enumerate(search_results, start=1):
        prepared_results.append({
            "result_number": index,
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "content": result.get("content", "")[:1800],
        })

    prompt = f"""
You are a business lead extraction assistant.

I will give you web search results.

Your job is to identify ONLY real individual/local businesses
that could be potential website-design clients.

IMPORTANT RULES:

1. Do NOT return articles.
2. Do NOT return news stories.
3. Do NOT return laws or legislation.
4. Do NOT return insurance companies.
5. Do NOT return directories themselves.
6. Do NOT return blog posts.
7. Do NOT return generic "how to start a business" pages.
8. Do NOT invent business information.
9. A Yelp/Facebook/YellowPages/etc. page is a SOURCE, not the business website.
10. Only put a URL in official_website if the source clearly indicates
    it is the business's own official website.
11. If an official website cannot be verified from these results,
    use null for official_website.
12. Only return businesses located in the United States.
13. Prefer independent/local businesses rather than large national brands.

Return ONLY this JSON object:

{{
  "leads": [
    {{
      "business_name": "Example Dental",
      "category": "Dentist",
      "location": "Austin, Texas",
      "phone": "public phone or null",
      "email": "public email or null",
      "official_website": "https://example.com or null",
      "source_url": "URL of the source page",
      "evidence": "Short explanation of why this appears to be a real business and whether an official website was found"
    }}
  ]
}}

Maximum {max_leads} leads.

SEARCH RESULTS:
{json.dumps(prepared_results, indent=2)}
"""

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0.1,
        "max_tokens": 5000,
        "response_format": {
            "type": "json_object"
        },
    }

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"OpenRouter error {response.status_code}: "
            f"{response.text[:1000]}"
        )

    data = response.json()

    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    parsed = _parse_json(content)

    leads = parsed.get("leads", [])

    if not isinstance(leads, list):
        return []

    return leads[:max_leads]
