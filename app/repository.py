from app.db import connect
from app.post_tags import PostTags


def insert_post(title: str, body: str, tags: PostTags) -> int:
    with connect() as conn:
        return conn.execute(
            "INSERT INTO posts (title, body, subject, category, confidence) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (title, body, tags.subject, tags.category, tags.confidence),
        ).fetchone()[0]


def insert_post_vector(post_id: int, model: str, vector: list[float]) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO post_vectors (post_id, model, vector) VALUES (%s, %s, %s::real[])",
            (post_id, model, vector),
        )


def get_post(post_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, title, body, subject, category, confidence FROM posts WHERE id = %s",
            (post_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(zip(("id", "title", "body", "subject", "category", "confidence"), row))


def get_post_vector(post_id: int) -> list[float] | None:
    with connect() as conn:
        row = conn.execute("SELECT vector FROM post_vectors WHERE post_id = %s", (post_id,)).fetchone()
    return row[0] if row else None


def save_suggestions(post_id: int, items: list[dict]) -> None:
    """Store the system's decision for each image it looked at. Safe to repeat."""
    with connect() as conn:
        for rank, item in enumerate(items, start=1):
            conn.execute(
                """
                INSERT INTO suggestions (post_id, image_id, rank, score, decision, rule, reason)
                SELECT %s, id, %s, %s, %s, %s, %s FROM images WHERE filename = %s
                ON CONFLICT (post_id, image_id) DO UPDATE
                SET rank = EXCLUDED.rank, score = EXCLUDED.score, decision = EXCLUDED.decision,
                    rule = EXCLUDED.rule, reason = EXCLUDED.reason
                """,
                (post_id, rank, item["score"], item["decision"], item["rule"],
                 item["reason"], item["filename"]),
            )


def list_suggestions(post_id: int) -> list[dict]:
    """The stored suggestions for a post, best first, with the latest human review."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.rank, i.filename, s.score, s.decision, s.rule, s.reason,
                   (SELECT r.verdict FROM reviews r WHERE r.suggestion_id = s.id
                    ORDER BY r.id DESC LIMIT 1)
            FROM suggestions s JOIN images i ON i.id = s.image_id
            WHERE s.post_id = %s ORDER BY s.rank
            """,
            (post_id,),
        ).fetchall()
    keys = ("id", "rank", "filename", "score", "decision", "rule", "reason", "review")
    return [dict(zip(keys, row)) for row in rows]
