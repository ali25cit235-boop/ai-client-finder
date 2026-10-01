import json
import os
import time
import requests


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Free models.
# The agent will try each model up to 3 times.
MODELS = [
    "nvidia/nemotron-3-ultra:free",
    "inclusionai/ling-3.0-flash-fin:free",
    "qwen/qwen3.8-27b:free",
]


def clean_text(value):
    """Convert different response formats into plain text."""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        parts = []

        for item in value:
            if isinstance(item, str):
                parts.append(item)

            elif isinstance(item, dict):
                text = item.get("text")

                if isinstance(text, str):
                    parts.append(text)

        return "\n".join(parts).strip()

    return ""


def extract_json(text: str) -> dict:
    """
    Parse JSON returned by the model.
    Handles markdown code fences and extra text.
    """

    text = (text or "").strip()

    if not text:
        raise ValueError(
            "AI returned an empty response"
        )

    # Remove markdown fences.
    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    # First try complete JSON.
    try:
        result = json.loads(text)

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        pass

    # Try extracting JSON object from surrounding text.
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end > start:
        candidate = text[start:end + 1]

        try:
            result = json.loads(candidate)

            if isinstance(result, dict):
                return result

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "AI returned invalid JSON. "
        f"Response preview: {text[:700]}"
    )


def build_prompt(
    search_results: list[dict],
    max_leads: int
) -> str:

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

    return f"""
You are a local-business lead extraction assistant.

Analyze the web search results below.

Return ONLY REAL LOCAL BUSINESSES in the United States.

We need up to {max_leads} businesses that could potentially
need a website.

REJECT these:
- articles
- blog posts
- news
- legislation
- insurance companies
- directories as businesses
- job listings
- generic information pages
- "how to start a business" pages
- national corporations
- government pages
- organizations that are not local businesses

A directory page can be used as a SOURCE,
but the directory itself is NOT the business.

IMPORTANT:
- Never invent information.
- Use null when a value is unavailable.
- Only use an official_website when the result clearly indicates
  it belongs to that business.
- A missing website in search results is NOT absolute proof
  that the business has no website.
- Return ONLY JSON.
- Do not use markdown.
- Do not add explanations outside JSON.

Use exactly this structure:

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
      "evidence": "Local dental business identified in the source."
    }}
  ]
}}

SEARCH RESULTS:

{json.dumps(
    prepared_results,
    indent=2
)}
"""


def call_model(
    model: str,
    prompt: str
) -> list[dict]:

    api_key = os.environ.get(
        "OPENROUTER_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured"
        )

    payload = {
        "model": model,

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

    # Temporary/rate-limit errors should be
    # handled by the caller and retried.
    if response.status_code in (
        408,
        429,
        500,
        502,
        503,
        504
    ):
        raise RuntimeError(
            f"RETRYABLE_HTTP_{response.status_code}: "
            f"{response.text[:800]}"
        )

    # Permanent API errors.
    if response.status_code >= 400:
        raise RuntimeError(
            f"PERMANENT_HTTP_{response.status_code}: "
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

    choice = choices[0]

    finish_reason = choice.get(
        "finish_reason"
    )

    message = choice.get(
        "message",
        {}
    )

    content = clean_text(
        message.get("content")
    )

    # Empty output or truncated output:
    # try the same model again.
    if not content:
        raise RuntimeError(
            "EMPTY_RESPONSE: "
            f"finish_reason={finish_reason}"
        )

    if finish_reason == "length":
        raise RuntimeError(
            "OUTPUT_TRUNCATED: "
            "model reached its output limit"
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
            "AI response does not contain a valid leads array"
        )

    return leads


def extract_leads(
    search_results: list[dict],
    max_leads: int = 5
) -> list[dict]:

    if not search_results:
        return []

    prompt = build_prompt(
        search_results,
        max_leads
    )

    last_error = None

    for model in MODELS:

        print("")
        print(
            f"=== Trying model: {model} ==="
        )

        for attempt in range(
            1,
            4
        ):

            print(
                f"Attempt {attempt}/3"
            )

            try:
                leads = call_model(
                    model,
                    prompt
                )

                print(
                    f"SUCCESS: {model}"
                )

                return leads[:max_leads]

            except Exception as exc:

                last_error = exc

                print(
                    f"FAILED: {model} "
                    f"attempt {attempt}/3"
                )

                print(
                    f"Reason: {exc}"
                )

                # Retry this model up to 3 times.
                if attempt < 3:

                    # Small exponential backoff.
                    wait_seconds = (
                        2 ** attempt
                    )

                    print(
                        f"Retrying in "
                        f"{wait_seconds} seconds..."
                    )

                    time.sleep(
                        wait_seconds
                    )

        print("")
        print(
            f"Model failed 3 times: {model}"
        )

        print(
            "Moving to next model..."
        )

    raise RuntimeError(
        "ALL AI MODELS FAILED. "
        f"Last error: {last_error}"
    )
