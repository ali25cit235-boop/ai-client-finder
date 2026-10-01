import json
import os
import requests


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/free"


LEAD_SCHEMA = {
    "type": "object",
    "properties": {
        "leads": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "business_name": {
                        "type": "string"
                    },
                    "category": {
                        "type": "string"
                    },
                    "location": {
                        "type": "string"
                    },
                    "phone": {
                        "type": ["string", "null"]
                    },
                    "email": {
                        "type": ["string", "null"]
                    },
                    "official_website": {
                        "type": ["string", "null"]
                    },
                    "source_url": {
                        "type": "string"
                    },
                    "evidence": {
                        "type": "string"
                    }
                },
                "required": [
                    "business_name",
                    "category",
                    "location",
                    "phone",
                    "email",
                    "official_website",
                    "source_url",
                    "evidence"
                ],
                "additionalProperties": False
            }
        }
    },
    "required": ["leads"],
    "additionalProperties": False
}


def clean_content(content) -> str:
    """Convert different OpenRouter content formats into plain text."""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)

        return "\n".join(parts).strip()

    return ""


def parse_json_response(text: str) -> dict:
    """Parse JSON even if a model adds markdown fences."""

    text = (text or "").strip()

    if not text:
        raise ValueError("AI returned an empty response")

    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    # First try the complete response
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # Try extracting an object from surrounding text
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end > start:
        candidate = text[start:end + 1]

        try:
            parsed = json.loads(candidate)

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "AI did not return valid JSON. "
        f"Response preview: {text[:500]}"
    )


def extract_leads(
    search_results: list[dict],
    max_leads: int = 15
) -> list[dict]:

    api_key = os.environ.get("OPENROUTER_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured"
        )

    prepared_results = []

    for index, result in enumerate(
        search_results,
        start=1
    ):
        prepared_results.append({
            "result_number": index,
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "content": result.get(
                "content",
                ""
            )[:2000],
        })

    prompt = f"""
You are a business lead extraction assistant.

Analyze the web search results below.

Return ONLY REAL LOCAL BUSINESSES in the United States
that could potentially need a website.

Reject:
- articles
- blog posts
- news pages
- legislation
- insurance companies
- large national corporations
- directories as businesses
- "how to start a business" pages
- informational pages
- job listings
- generic search pages

IMPORTANT:

A directory page such as Yelp, Facebook, YellowPages,
Healthgrades, etc. can be used as a SOURCE for a business.

It must NOT be treated as the business's official website.

Do not invent business information.

If you cannot verify an official website,
set official_website to null.

Return at most {max_leads} businesses.

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

        "max_tokens": 6000,

        "provider": {
            "require_parameters": True
        },

        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "business_leads",
                "strict": True,
                "schema": LEAD_SCHEMA
            }
        }
    }

    response = requests.post(
        OPENROUTER_URL,

        headers={
            "Authorization": (
                f"Bearer {api_key}"
            ),
            "Content-Type": "application/json"
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

    content = clean_content(
        message.get("content")
    )

    # Some responses may expose parsed/refusal information
    # differently, so handle refusal clearly.
    refusal = message.get("refusal")

    if refusal:
        raise RuntimeError(
            f"OpenRouter model refused the request: "
            f"{refusal}"
        )

    parsed = parse_json_response(
        content
    )

    leads = parsed.get(
        "leads",
        []
    )

    if not isinstance(leads, list):
        raise ValueError(
            "AI JSON does not contain a valid leads array"
        )

    return leads[:max_leads]
