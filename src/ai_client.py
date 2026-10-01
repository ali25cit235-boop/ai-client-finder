import json
import os
import time
import requests


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Current free models.
# Each model gets up to 3 attempts for temporary failures.
MODELS = [
    "stealth/space-bunny-alpha:free",
    "nvidia/nemotron-3-ultra-550b-a55b-20260604:free",
    "poolside/laguna-s-2.1:free",
]


def clean_content(content) -> str:
    """Convert OpenRouter content into plain text."""

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


def extract_json(text: str) -> dict:
    """Parse JSON even when the model adds markdown."""

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

    # Direct JSON parse.
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
        f"Preview: {text[:700]}"
    )


def build_prompt(
    search_results: list[dict],
    max_leads: int
) -> str:

    prepared_results = []

    # Keep the prompt small so free models
    # do not waste output on unnecessary text.
    for index, result in enumerate(
        search_results[:10],
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
            )[:800]
        })

    return f"""
You are a business lead extraction assistant.

Analyze the web search results below.

Find up to {max_leads} REAL LOCAL BUSINESSES
in the United States.

ONLY return actual businesses that could potentially
need a website.

REJECT:
- articles
- blog posts
- news
- laws
- legislation
- insurance companies
- directories themselves
- generic information pages
- job listings
- government pages
- national corporations
- "how to start a business" pages

A directory page may be used as a SOURCE,
but the directory is NOT the business.

RULES:
- Never invent information.
- Use null when information is unavailable.
- official_website must be null if it cannot be verified.
- source_url must be the actual source page.
- Missing website is NOT absolute proof that no website exists.
- Keep evidence very short.
- Return ONLY JSON.
- No markdown.
- No explanation outside JSON.

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
      "evidence": "Local dental practice found in source."
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

        # Enough for a small 5-lead JSON response.
        "max_tokens": 5000
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

    status = response.status_code

    # Temporary errors: retry this model.
    if status in (
        408,
        429,
        500,
        502,
        503,
        504
    ):
        raise RuntimeError(
            f"RETRYABLE_HTTP_{status}: "
            f"{response.text[:800]}"
        )

    # 404 / 400 etc. are usually model/config issues.
    # Do NOT waste 3 attempts on them.
    if status >= 400:
        raise ValueError(
            f"PERMANENT_HTTP_{status}: "
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

    content = clean_content(
        message.get("content")
    )

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
            "Invalid leads array"
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
            f"========== {model} =========="
        )

        for attempt in range(1, 4):

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

            except ValueError as exc:

                # Permanent error such as 404.
                last_error = exc

                print(
                    f"PERMANENT FAILURE: "
                    f"{exc}"
                )

                print(
                    "Skipping this model."
                )

                break

            except Exception as exc:

                last_error = exc

                print(
                    f"TEMPORARY FAILURE: "
                    f"{exc}"
                )

                if attempt < 3:

                    wait_seconds = (
                        3 * attempt
                    )

                    print(
                        f"Retrying in "
                        f"{wait_seconds} seconds..."
                    )

                    time.sleep(
                        wait_seconds
                    )

        print(
            f"Trying next model..."
        )

    raise RuntimeError(
        "ALL FREE AI MODELS FAILED. "
        f"Last error: {last_error}"
    )
