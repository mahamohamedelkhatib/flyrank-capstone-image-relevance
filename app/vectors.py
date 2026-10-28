import os
import time

from app.costs import log_call
from app.db import connect
from app.embed import embed_text


def image_text(subject: str, caption: str, tags: list[str]) -> str:
    """The text we embed for an image: what it shows, in words."""
    return f"{subject}. {caption} Details: {', '.join(sorted(tags))}."


def embed_logged(text: str, image_id: int | None = None) -> list[float]:
    """Embed text and write one row to the call log, whether it works or not."""
    model = os.environ["GEMINI_EMBED_MODEL"]
    tokens = max(1, len(text) // 4)  # Gemini does not report embed tokens: this is an estimate
    started = time.monotonic()
    error = None
    try:
        return embed_text(text)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"[:500]
        raise
    finally:
        log_call(
            image_id=image_id, purpose="embedding", model=model,
            input_tokens=tokens, output_tokens=0,
            latency_ms=int((time.monotonic() - started) * 1000),
            status="error" if error else "ok", error=error,
        )


def embed_images() -> int:
    """Embed every tagged image that has no vector yet. Returns how many were added."""
    model = os.environ["GEMINI_EMBED_MODEL"]
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT i.id, i.subject, i.caption FROM images i
            LEFT JOIN image_vectors v ON v.image_id = i.id
            WHERE i.status IN ('done', 'flagged') AND v.image_id IS NULL
            ORDER BY i.id
            """
        ).fetchall()
    added = 0
    for image_id, subject, caption in rows:
        with connect() as conn:
            tags = [r[0] for r in conn.execute("SELECT tag FROM tags WHERE image_id = %s", (image_id,))]
        text = image_text(subject, caption, tags)
        try:
            vector = embed_logged(text, image_id)
        except Exception as e:
            print(f"image {image_id}: ERROR {type(e).__name__}, run again to retry")
            continue
        with connect() as conn:
            conn.execute(
                "INSERT INTO image_vectors (image_id, model, source_text, vector) VALUES (%s, %s, %s, %s::real[])",
                (image_id, model, text, vector),
            )
        added += 1
    return added


if __name__ == "__main__":
    print("images embedded:", embed_images())
