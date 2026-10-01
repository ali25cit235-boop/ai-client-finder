import os
from google import genai


def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is missing"
        )
    return genai.Client(api_key=api_key)


def generate_text(
    prompt: str,
    model: str = "gemini-2.5-flash"
) -> str:
    client = get_gemini_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    return response.text or ""
