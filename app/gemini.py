import base64
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from app.schemas import ImageTags

load_dotenv()

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

PROMPT = """Look at this image and describe it as JSON with exactly these fields:
- subject: the main thing in the picture, like "red fox"
- category: one of animal, vehicle, food, landscape, building, other
- attributes: a short list of visual details
- caption: one sentence describing the image
- confidence: a number from 0 to 1 for how sure you are
Confidence means how sure you are that the main subject is clearly visible and identifiable. If the image is blurry, out of focus or abstract so that no clear subject can be identified, give a confidence below 0.3."""


def call_gemini(image_path: str) -> tuple[str, dict]:
    """Send one image to Gemini. Returns (raw answer text, usage numbers)."""
    model = os.environ["GEMINI_VISION_MODEL"]
    key = os.environ["GEMINI_API_KEY"]
    image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode()

    body = {
        "contents": [{
            "parts": [
                {"text": PROMPT},
                {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
            ]
        }],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    response = httpx.post(
        f"{BASE_URL}/models/{model}:generateContent",
        headers={"x-goog-api-key": key},
        json=body,
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Gemini error {response.status_code}: {response.text[:300]}")

    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return text, data.get("usageMetadata", {})


if __name__ == "__main__":
    path = sys.argv[1]
    raw, usage = call_gemini(path)
    print("RAW ANSWER:", raw)
    print("USAGE:", usage)
    tags = ImageTags(**json.loads(raw))
    print("VALID TAGS:", tags)
