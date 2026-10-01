
import os
import json
import time

from google import genai
from google.genai import types
from google.genai import errors


# Models are tried in this order.
MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
]


def search_web(query: str, count: int = 10) -> list[dict]:
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=api_key)

    prompt = f"""
Search Google for real businesses in the United States matching:
{query}

Find up to {count} businesses that may not have an official website.

Return a JSON array. Each object should contain:
business_name, category, location, phone, email,
official_website, source_url, description.

Do not invent details.
Use null when information cannot be verified.
A missing website in search results is not proof that no website exists.
Return only the JSON array.
"""

    last_error = None

    for model in MODELS:
        for attempt in range(1, 4):
            try:
                print(
                    f"Trying model {model}, "
                    f"attempt {attempt}/3"
                )

                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[
                            types.Tool(
                                google_search=types.GoogleSearch()
                            )
                        ]
                    ),
                )

                text = (response.text or "").strip()

                if text.startswith("```"):
                    text = text.replace("```json", "", 1)
                    text = text.replace("```", "").strip()

                results = json.loads(text)

                if not isinstance(results, list):
                    raise ValueError("Gemini did not return a JSON array")

                return results[:count]

            except errors.APIError as exc:
                last_error = exc
                status = getattr(exc, "code", None)

                print(f"API error: {exc}")

                # Retry temporary failures only.
                if status not in (408, 429, 500, 502, 503, 504):
                    print(
                        f"Non-retryable error for {model}; "
                        "trying next model."
                    )
                    break

                if attempt < 3:
                    time.sleep(2 ** attempt)

            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                print(f"Invalid response: {exc}")
                break

            except Exception as exc:
                last_error = exc
                print(f"Unexpected error: {exc}")
                break

    raise RuntimeError(
        f"All configured model attempts failed. Last error: {last_error}"
    )
