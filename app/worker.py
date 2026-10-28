import json
import os
import sys
import time
from pathlib import Path

from app.costs import log_call
from app.db import connect
from app.gemini import call_gemini
from app.jobs import claim_next, save_failure, save_success
from app.schemas import ImageTags

IMAGE_DIR = Path("data/images")
LOW_CONFIDENCE = 0.5
BLUR_WORDS = ("blur", "out of focus", "bokeh")


def should_flag(tags: ImageTags) -> bool:
    """Flag when the model is unsure, or when its own tags say the photo is blurry."""
    if tags.confidence < LOW_CONFIDENCE:
        return True
    about_photo = [a.lower() for a in tags.attributes if "background" not in a.lower()]
    text = " ".join(about_photo)
    return any(word in text for word in BLUR_WORDS)


def _log(image_id: int, usage: dict, started: float, status: str, error: str | None) -> None:
    """Record one Gemini call. Thinking tokens, if any, are billed as output."""
    output_tokens = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
    log_call(
        image_id=image_id,
        purpose="vision",
        model=os.environ["GEMINI_VISION_MODEL"],
        input_tokens=usage.get("promptTokenCount", 0),
        output_tokens=output_tokens,
        latency_ms=int((time.monotonic() - started) * 1000),
        status=status,
        error=error,
    )


def process_one() -> str | None:
    """Tag one pending image. Returns a log line, or None if nothing was due."""
    with connect() as conn:
        claimed = claim_next(conn)
    if claimed is None:
        return None

    image_id, filename, attempts = claimed
    started = time.monotonic()
    usage: dict = {}
    try:
        raw, usage = call_gemini(str(IMAGE_DIR / filename))
        tags = ImageTags(**json.loads(raw))
    except Exception as e:
        message = f"{type(e).__name__}: {e}"[:500]
        _log(image_id, usage, started, "error", message)
        with connect() as conn:
            save_failure(conn, image_id, attempts, message)
        return f"{filename}: ERROR attempt {attempts} ({type(e).__name__})"

    _log(image_id, usage, started, "ok", None)
    flagged = should_flag(tags)
    with connect() as conn:
        save_success(conn, image_id, tags, flagged)
    label = "FLAGGED" if flagged else "done"
    return f"{filename}: {label} ({tags.subject}, confidence {tags.confidence})"


def pending_left() -> int:
    with connect() as conn:
        return conn.execute("SELECT count(*) FROM images WHERE status = 'pending'").fetchone()[0]


def run_batch(limit: int | None = None) -> None:
    processed = 0
    while limit is None or processed < limit:
        result = process_one()
        if result:
            print(result)
            processed += 1
            continue
        if pending_left() == 0:
            break
        time.sleep(2)  # some images are waiting for their retry time


if __name__ == "__main__":
    run_batch(int(sys.argv[1]) if len(sys.argv) > 1 else None)
