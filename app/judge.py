import json
import os
import time

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from app.costs import ensure_budget, log_call
from app.gemini import BASE_URL

load_dotenv()

PROMPT = """A blog post is about: {post_subject}
A candidate cover image shows: {image_subject} ({caption})

Does the image show the same kind of subject the post is about?
- Different species or types are NOT the same (a fox is not a wolf, a car is not a bus).
- A more specific or more general name for the same thing IS the same
  (grizzly bear and brown bear, dog and golden retriever, wolf and gray wolf).
Answer as JSON with exactly these fields:
- same_subject: true or false
- reason: one short sentence explaining why
"""


class SubjectJudgement(BaseModel):
    same_subject: bool
    reason: str = Field(min_length=1, max_length=300)


def judge_subject(post_subject: str, image_subject: str, caption: str) -> SubjectJudgement:
    """Ask Gemini whether the post and the image are about the same kind of thing. Logged."""
    ensure_budget()
    model = os.environ["GEMINI_VISION_MODEL"]
    prompt = PROMPT.format(post_subject=post_subject, image_subject=image_subject, caption=caption)
    started = time.monotonic()
    usage: dict = {}
    error = None
    try:
        response = httpx.post(
            f"{BASE_URL}/models/{model}:generateContent",
            headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=60,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Gemini error {response.status_code}: {response.text[:300]}")
        data = response.json()
        usage = data.get("usageMetadata", {})
        return SubjectJudgement(**json.loads(data["candidates"][0]["content"]["parts"][0]["text"]))
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
    pairs = [
        ("red fox", "red fox kit", "A fox kit stands on a log."),
        ("red fox", "gray wolf", "A gray wolf stands in snow."),
        ("brown bear", "grizzly bear", "A grizzly bear walks by a river."),
        ("dog", "golden retriever", "A golden retriever sits on grass."),
        ("deer", "fallow deer", "A fallow deer in a meadow."),
        ("red fox", "fallow deer", "A fallow deer in a meadow."),
    ]
    for post_subject, image_subject, caption in pairs:
        j = judge_subject(post_subject, image_subject, caption)
        print(f"{post_subject!r} vs {image_subject!r}: same={j.same_subject}  {j.reason}")
