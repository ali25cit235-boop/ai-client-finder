from google import genai
from google.genai import types
import os
import json


def search_web(query: str, count: int = 10) -> list[dict]:
    """Search the web using Gemini + Google Search grounding."""

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=api_key)

    prompt = f"""
Find {count} real local businesses in the United States matching this query:

{query}

Focus on businesses that may NOT have their own official website.

For each business, return:
- business_name
- category
- location
- phone if publicly available
- email if publicly available
- official_website if you can verify one
- source_url

Important:
- Do not invent information.
- If an official website cannot be verified, set official_website to null.
- Prefer real businesses with publicly available information.
- Return ONLY a JSON array.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    google_search=types.GoogleSearch()
                )
            ]
        ),
    )

    text = response.text or "[]"

    # Remove possible Markdown code fences
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "", 1)
        text = text.replace("```", "")
        text = text.strip()

    try:
        results = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(results, list):
        return []

    return results[:count]
