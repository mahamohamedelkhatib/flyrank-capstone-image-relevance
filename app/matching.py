import sys

from app.db import connect
from app.embed import cosine
from app.vectors import embed_logged


def rank_vector(query: list[float], limit: int = 5) -> list[tuple]:
    """Rank images by similarity to a vector: (score, filename, subject, category, status)."""
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


def rank(post_text: str, limit: int = 5) -> list[tuple]:
    """Embed the text, then rank images against it."""
    return rank_vector(embed_logged(post_text), limit)


if __name__ == "__main__":
    for score, filename, subject, category, status in rank(" ".join(sys.argv[1:])):
        print(f"{score:.3f}  {filename:16} {subject} ({category}, {status})")
