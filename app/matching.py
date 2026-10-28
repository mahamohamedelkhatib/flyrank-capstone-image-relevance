import sys

from app.db import connect
from app.embed import cosine
from app.vectors import embed_logged


def rank(post_text: str, limit: int = 5) -> list[tuple]:
    """Return the best-matching images as (score, filename, subject, category, status)."""
    query = embed_logged(post_text)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT i.filename, i.subject, i.category, i.status, v.vector
            FROM image_vectors v JOIN images i ON i.id = v.image_id
            """
        ).fetchall()
    scored = [
        (cosine(query, vector), filename, subject, category, status)
        for filename, subject, category, status, vector in rows
    ]
    scored.sort(reverse=True)
    return scored[:limit]


if __name__ == "__main__":
    for score, filename, subject, category, status in rank(" ".join(sys.argv[1:])):
        print(f"{score:.3f}  {filename:16} {subject} ({category}, {status})")
