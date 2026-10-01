import json
import os
import requests


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Fixed free model.
MODEL = "qwen/qwen3.8-27b:free"


def extract_json(text: str) -> dict:
    text = (text or "").strip()

    if not text:
        raise ValueError(
            "AI returned an empty response"
        )

    if "```" in text:
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end > start:
        candidate = text[start:end + 1]

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError(
        "AI returned invalid JSON. "
        f"Preview: {text[:500]}"
    )


def extract_leads(
    search_results: list[dict],
    max_leads: int = 5
) -> list[dict]:

    api_key = os.environ.get(
        "OPENROUTER_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured"
        )

    prepared_results = []

    for index, result in enumerate(
        search_results[:12],
        start=1
    ):
        prepared_results.append({
            "id": index,
            "title": result.get(
                "title",
                ""
            ),
            "url": result.get(
                "url",
                ""
            ),
            "content": result.get(
                "content",
                ""
            )[:1000]
        })

    prompt = f"""
You are a business lead filtering assistant.

Analyze the web search results below.

Return ONLY REAL LOCAL BUSINESSES
located in the United States.

Reject:
- articles
- blog posts
- news
- laws
- insurance companies
- directories as businesses
- job listings
- generic information pages
- national corporations
- informational websites

A directory page can be used as a SOURCE,
but it is NOT the business's official website.

Do not invent information.

We need a maximum of {max_leads} businesses.

For every business return:

business_name
category
location
phone
email
official_website
source_url
evidence

Use null when a field is unavailable.

If an official website cannot be verified,
official_website must be null.

Return ONLY valid JSON.
Do NOT use markdown.
Do NOT add explanations.

Use exactly:

{{
  "leads": [
    {{
      "business_name": "Example Dental",
      "category": "Dentist",
      "location": "Houston, TX",
      "phone": "123-456-7890",
      "email": null,
      "official_website": null,
      "source_url": "https://source.com/page",
      "evidence": "Local business identified in source."
    }}
  ]
}}

SEARCH RESULTS:

{json.dumps(
    prepared_results,
    indent=2
)}
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

        # Keep the response comfortably sized.
        "max_tokens": 4000,

        # Important: prevent reasoning from
        # consuming the whole completion budget.
        "reasoning": {
            "enabled": False
        },

        # Ask for JSON directly.
        "response_format": {
            "type": "json_object"
        }
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

    choices = data.get(
        "choices",
        []
    )

    if not choices:
        raise RuntimeError(
            "OpenRouter returned no choices"
        )

    message = choices[0].get(
        "message",
        {}
    )

    content = message.get(
        "content"
    )

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

    if not content:
        raise RuntimeError(
            "OpenRouter returned empty content. "
            f"Finish reason: "
            f"{choices[0].get('finish_reason')}"
        )

    parsed = extract_json(
        content
    )

    leads = parsed.get(
        "leads",
        []
    )

    if not isinstance(
        leads,
        list
    ):
        raise ValueError(
            "AI response does not contain "
            "a valid leads array"
        )

    return leads[:max_leads]
