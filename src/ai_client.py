import json
import os
import requests


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/free"


def extract_json(text: str) -> dict:
    text = (text or "").strip()

    if not text:
        raise ValueError("AI returned an empty response")

    # Remove markdown fences
    if "```" in text:
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)


def extract_leads(
    search_results: list[dict],
    max_leads: int = 5
) -> list[dict]:

    api_key = os.environ.get("OPENROUTER_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured"
        )

    # Keep the input small.
    prepared_results = []

    for index, result in enumerate(
        search_results[:12],
        start=1
    ):
        prepared_results.append({
            "id": index,
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "content": result.get(
                "content", ""
            )[:1000]
        })

    prompt = f"""
You are filtering web search results for a local-business lead finder.

From the search results below, identify ONLY real independent/local
businesses in the United States.

Reject:
- articles
- blog posts
- news
- laws
- insurance companies
- directories
- directory pages as businesses
- job pages
- generic information pages
- national chains

We need up to {max_leads} businesses.

For each valid business provide:
business_name
category
location
phone
email
official_website
source_url
evidence

IMPORTANT:
- Never invent information.
- Use null if a field is unavailable.
- A directory URL is a source_url, NOT an official website.
- If you cannot verify an official website, use null.
- Return ONLY JSON.
- No markdown.
- No explanation outside the JSON.

Use EXACTLY this format:

{{
  "leads": [
    {{
      "business_name": "Example Dental",
      "category": "Dentist",
      "location": "Houston, TX",
      "phone": "123-456-7890",
      "email": null,
      "official_website": null,
      "source_url": "https://example.com/source",
      "evidence": "Local dental practice identified in source."
    }}
  ]
}}

SEARCH RESULTS:

{json.dumps(prepared_results, indent=2)}
"""

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0,
        "max_tokens": 2500
    }

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": (
                f"Bearer {api_key}"
            ),
            "Content-Type": "application/json",
            "X-Title": "AI Client Finder"
        },
        json=payload,
        timeout=90
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"OpenRouter error "
            f"{response.status_code}: "
            f"{response.text[:1000]}"
        )

    data = response.json()

    choices = data.get("choices", [])

    if not choices:
        raise RuntimeError(
            "OpenRouter returned no choices"
        )

    message = choices[0].get(
        "message",
        {}
    )

    content = message.get(
        "content",
        ""
    )

    # Some providers may return content in a list.
    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, str):
                parts.append(item)

            elif isinstance(item, dict):
                item_text = item.get("text")

                if item_text:
                    parts.append(item_text)

        content = "\n".join(parts)

    # If normal content is empty, show useful debugging information.
    if not content:
        raise RuntimeError(
            "OpenRouter returned an empty content field. "
            f"Response: {json.dumps(data)[:1500]}"
        )

    parsed = extract_json(content)

    leads = parsed.get("leads", [])

    if not isinstance(leads, list):
        raise ValueError(
            "AI response does not contain a valid leads array"
        )

    return leads[:max_leads]
