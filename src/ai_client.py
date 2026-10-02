
import json
import os
import time
import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODELS = [
    "nvidia/nemotron-3-ultra:free",
    "qwen/qwen3.8-27b:free",
]


def parse_json(text):
    text = (text or "").strip()

    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        result = json.loads(text[start:end + 1])
        if isinstance(result, dict):
            return result

    raise ValueError("AI returned invalid JSON")


def build_prompt(search_results, max_leads):
    results = []

    for item in search_results[:10]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", "")[:700]
        })

    return f"""
Find up to {max_leads} REAL independent local businesses
in the United States that may need a website.

STRICT RULES:
- Reject a business if its official website is identified.
- Prefer businesses listed on directories or social platforms.
- Never treat a directory as the business itself.
- Never invent names, phone numbers, emails or URLs.
- Email is optional. Phone is useful but optional.
- If information is unknown, use null.
- If the business's website status is uncertain, use
  website_status "uncertain".
- Do not claim that a business has no website merely
  because a search result does not show one.
- Return only valid JSON, without markdown.

Use this exact structure:
{{
  "leads": [
    {{
      "business_name": "Example Dental",
      "category": "Dentist",
      "location": "Houston, TX",
      "phone": "123-456-7890",
      "email": null,
      "official_website": null,
      "website_status": "not_found_in_sources",
      "source_url": "https://directory.example/business",
      "evidence": "Listed in a local business directory."
    }}
  ]
}}

SEARCH RESULTS:
{json.dumps(results, ensure_ascii=False)}
"""


def request_model(model, prompt):
    key = os.getenv("OPENROUTER_API_KEY")

    if not key:
        raise RuntimeError("OPENROUTER_API_KEY secret is missing")

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-Title": "AI Client Finder",
        },
        json={
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0,
            "max_tokens": 3500,
        },
        timeout=90,
    )

    if response.status_code >= 400:
        message = response.text[:800]

        if response.status_code in (400, 401, 403, 404):
            raise ValueError(
                f"PERMANENT HTTP {response.status_code}: {message}"
            )

        raise RuntimeError(
            f"HTTP {response.status_code}: {message}"
        )

    data = response.json()
    choices = data.get("choices", [])

    if not choices:
        raise RuntimeError("Model returned no choices")

    choice = choices[0]
    message = choice.get("message", {})
    content = message.get("content")

    if isinstance(content, list):
        content = "\n".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict)
        )

    if not content:
        raise RuntimeError(
            f"Empty response: {choice.get('finish_reason')}"
        )

    if choice.get("finish_reason") == "length":
        raise RuntimeError("Response was truncated")

    result = parse_json(content)
    leads = result.get("leads", [])

    if not isinstance(leads, list):
        raise ValueError("Invalid leads array")

    return leads


def extract_leads(search_results, max_leads=5):
    if not search_results:
        return []

    prompt = build_prompt(search_results, max_leads)
    last_error = None

    for model in MODELS:
        print(f"Trying model: {model}")

        for attempt in range(1, 4):
            print(f"Attempt {attempt}/3")

            try:
                leads = request_model(model, prompt)
                print(f"Success: {model}")
                return leads[:max_leads]

            except ValueError as exc:
                # Invalid model IDs and other permanent errors
                # should not be retried.
                last_error = exc
                print(f"Permanent error: {exc}")
                break

            except Exception as exc:
                last_error = exc
                print(f"Attempt failed: {exc}")

                if attempt < 3:
                    time.sleep(2 * attempt)

        print("Trying the next model...")

    raise RuntimeError(
        f"All configured models failed. Last error: {last_error}"
    )
    
