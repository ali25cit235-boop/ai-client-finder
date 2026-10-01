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
                    "business_name": {"type": "string"},
                    "category": {"type": "string"},
                    "location": {"type": "string"},
                    "phone": {"type": ["string", "null"]},
                    "email": {"type": ["string", "null"]},
                    "official_website": {"type": ["string", "null"]},
                    "source_url": {"type": "string"},
                    "evidence": {"type": "string"}
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


def recover_complete_leads(text: str) -> list[dict]:
    """
    Recover complete lead objects if the AI response
    was cut off before the final JSON braces.
    """

    text = (text or "").strip()

    marker = '"leads"'

    marker_pos = text.find(marker)

    if marker_pos == -1:
        return []

    array_start = text.find("[", marker_pos)

    if array_start == -1:
        return []

    decoder = json.JSONDecoder()

    position = array_start + 1
    recovered = []

    while position < len(text):

        # Skip spaces/newlines/commas
        while position < len(text) and text[position] in " \t\r\n,":
            position += 1

        if position >= len(text):
            break

        if text[position] == "]":
            break

        try:
            obj, consumed = decoder.raw_decode(
                text[position:]
            )

            if isinstance(obj, dict):
                recovered.append(obj)

            position += consumed

        except json.JSONDecodeError:
            # Current object is incomplete.
            break

    return recovered


def parse_json_response(text: str) -> dict:
    text = (text or "").strip()

    if not text:
        raise ValueError(
            "AI returned an empty response"
        )

    # Remove markdown fences if present.
    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    # Normal JSON parsing first.
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # Try recovering complete lead objects
    # from an incomplete JSON response.
    recovered = recover_complete_leads(text)

    if recovered:
        return {
            "leads": recovered
        }

    raise ValueError(
        "AI returned incomplete or invalid JSON. "
        f"Response preview: {text[:800]}"
    )


def extract_leads(
    search_results: list[dict],
    max_leads: int = 8
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
        search_results,
        start=1
    ):
        prepared_results.append({
            "result_number": index,
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
            )[:1200]
        })

    prompt = f"""
You are a business lead filtering assistant.

Analyze these web search results.

Return ONLY REAL LOCAL BUSINESSES
located in the United States.

Reject:
- articles
- blog posts
- news
- legislation
- insurance companies
- directories
- generic information pages
- "how to start a business" pages
- job listings
- large national corporations

A directory page can be used as a SOURCE,
but it is NOT the business's official website.

Do not invent information.

If an official website cannot be verified,
use null for official_website.

Return a maximum of {max_leads} businesses.

Return ONLY the requested JSON structure.

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

        "max_tokens": 3000,

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

    refusal = message.get(
        "refusal"
    )

    if refusal:
        raise RuntimeError(
            f"AI refused the request: {refusal}"
        )

    content = clean_content(
        message.get(
            "content"
        )
    )

    parsed = parse_json_response(
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
        return []

    return leads[:max_leads]
