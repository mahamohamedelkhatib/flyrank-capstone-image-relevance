import json
import os
import time

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from app.costs import ensure_budget, log_call
from app.gemini import BASE_URL
from app.schemas import Category

load_dotenv()

PROMPT = """Read this blog post. Say what the main visual subject is: the thing a reader
would expect to see in the post's cover photo. Answer as JSON with exactly these fields:
- subject: the main thing, like "red fox"
- category: one of animal, vehicle, food, landscape, building, other
- confidence: a number from 0 to 1 for how clearly the post is about one visual subject
If the post has no clear visual subject, use category "other" and a low confidence.

POST:
"""


class PostTags(BaseModel):
    subject: str = Field(min_length=1, max_length=80)
    category: Category
    confidence: float = Field(ge=0.0, le=1.0)


def tag_post(text: str) -> PostTags:
    """Ask Gemini what a post is about. Every call is logged."""
    ensure_budget()
    model = os.environ["GEMINI_VISION_MODEL"]
    started = time.monotonic()
    usage: dict = {}
    error = None
    try:
        response = httpx.post(
            f"{BASE_URL}/models/{model}:generateContent",
            headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
            json={
                "contents": [{"parts": [{"text": PROMPT + text}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=60,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Gemini error {response.status_code}: {response.text[:300]}")
        data = response.json()
        usage = data.get("usageMetadata", {})
        return PostTags(**json.loads(data["candidates"][0]["content"]["parts"][0]["text"]))
    except Exception as e:
        error = f"{type(e).__name__}: {e}"[:500]
        raise
    finally:
        log_call(
            image_id=None, purpose="text", model=model,
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0),
            latency_ms=int((time.monotonic() - started) * 1000),
            status="error" if error else "ok", error=error,
        )


if __name__ == "__main__":
    for post in [
        "I spotted a red fox at the edge of the forest this morning, its orange fur bright against the grass.",
        "A gray wolf howling at the moon in the snowy mountains.",
        "Five tips for filing your small business taxes on time this year.",
    ]:
        print(tag_post(post))
