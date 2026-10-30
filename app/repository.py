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


def get_suggestion(suggestion_id: int) -> dict | None:
    """One suggestion with the image's tags and all human reviews, for inspection."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT s.id, s.post_id, s.rank, s.score, s.decision, s.rule, s.reason,
                   i.id, i.filename, i.status, i.subject, i.category, i.caption, i.confidence
            FROM suggestions s JOIN images i ON i.id = s.image_id
            WHERE s.id = %s
            """,
            (suggestion_id,),
        ).fetchone()
        if row is None:
            return None
        tags = [r[0] for r in conn.execute(
            "SELECT tag FROM tags WHERE image_id = %s ORDER BY tag", (row[7],))]
        reviews = conn.execute(
            "SELECT id, verdict, note, created_at FROM reviews WHERE suggestion_id = %s ORDER BY id",
            (suggestion_id,),
        ).fetchall()
    return {
        "id": row[0], "post_id": row[1], "rank": row[2], "score": row[3],
        "decision": row[4], "rule": row[5], "reason": row[6],
        "image": {"id": row[7], "filename": row[8], "status": row[9], "subject": row[10],
                  "category": row[11], "caption": row[12], "confidence": row[13], "tags": tags},
        "reviews": [{"id": r[0], "verdict": r[1], "note": r[2], "created_at": r[3]} for r in reviews],
    }


def add_review(suggestion_id: int, verdict: str, note: str | None) -> int:
    with connect() as conn:
        return conn.execute(
            "INSERT INTO reviews (suggestion_id, verdict, note) VALUES (%s, %s, %s) RETURNING id",
            (suggestion_id, verdict, note),
        ).fetchone()[0]


def get_image(image_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, filename, status, subject, category, caption, confidence "
            "FROM images WHERE id = %s",
            (image_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(zip(("id", "filename", "status", "subject", "category", "caption", "confidence"), row))


def get_image_vector(image_id: int) -> list[float] | None:
    with connect() as conn:
        row = conn.execute("SELECT vector FROM image_vectors WHERE image_id = %s", (image_id,)).fetchone()
    return row[0] if row else None


def count_pending_images() -> int:
    with connect() as conn:
        return conn.execute("SELECT count(*) FROM images WHERE status = 'pending'").fetchone()[0]


def has_running_job() -> bool:
    """A job still marked running after an hour is treated as stale (the server was restarted)."""
    with connect() as conn:
        return conn.execute(
            "SELECT EXISTS (SELECT 1 FROM jobs WHERE status = 'running' "
            "AND created_at > now() - interval '1 hour')"
        ).fetchone()[0]


def create_job(kind: str, total: int) -> int:
    with connect() as conn:
        return conn.execute(
            "INSERT INTO jobs (kind, status, total) VALUES (%s, 'running', %s) RETURNING id",
            (kind, total),
        ).fetchone()[0]


def get_job(job_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, kind, status, total, done, failed, error, created_at, finished_at "
            "FROM jobs WHERE id = %s",
            (job_id,),
        ).fetchone()
    if row is None:
        return None
    keys = ("id", "kind", "status", "total", "done", "failed", "error", "created_at", "finished_at")
    return dict(zip(keys, row))


def refresh_job_progress(job_id: int) -> None:
    """Count the images this job has finished or given up on since it started."""
    with connect() as conn:
        conn.execute(
            """
            UPDATE jobs j SET
                done = (SELECT count(*) FROM images i
                        WHERE i.status IN ('done', 'flagged') AND i.updated_at >= j.created_at),
                failed = (SELECT count(*) FROM images i
                          WHERE i.status = 'failed' AND i.updated_at >= j.created_at)
            WHERE j.id = %s
            """,
            (job_id,),
        )


def finish_job(job_id: int, error: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE jobs SET status = %s, error = %s, finished_at = now() WHERE id = %s",
            ("failed" if error else "done", error, job_id),
        )
