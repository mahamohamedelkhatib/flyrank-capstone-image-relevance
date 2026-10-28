from app.schemas import ImageTags

MAX_ATTEMPTS = 3


def claim_next(conn):
    """Take one pending image that is due, mark it processing. None if nothing is due."""
    return conn.execute(
        """
        UPDATE images
        SET status = 'processing', attempts = attempts + 1, updated_at = now()
        WHERE id = (
            SELECT id FROM images
            WHERE status = 'pending' AND next_try_at <= now()
            ORDER BY id
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, filename, attempts
        """
    ).fetchone()


def save_success(conn, image_id: int, tags: ImageTags, flagged: bool) -> None:
    """Store the tags. Status is flagged if we do not trust the result, else done."""
    status = "flagged" if flagged else "done"
    conn.execute(
        """
        UPDATE images
        SET status = %s, subject = %s, category = %s, caption = %s,
            confidence = %s, last_error = NULL, updated_at = now()
        WHERE id = %s
        """,
        (status, tags.subject, tags.category, tags.caption, tags.confidence, image_id),
    )
    conn.execute("DELETE FROM tags WHERE image_id = %s", (image_id,))
    for tag in set(tags.attributes):
        conn.execute(
            "INSERT INTO tags (image_id, tag) VALUES (%s, %s)", (image_id, tag.lower())
        )


def save_failure(conn, image_id: int, attempts: int, error: str) -> None:
    """Retry later with backoff while attempts remain, otherwise mark failed."""
    if attempts >= MAX_ATTEMPTS:
        conn.execute(
            "UPDATE images SET status = 'failed', last_error = %s, updated_at = now() WHERE id = %s",
            (error, image_id),
        )
    else:
        delay_seconds = 5 * 2 ** (attempts - 1)
        conn.execute(
            """
            UPDATE images
            SET status = 'pending', last_error = %s, updated_at = now(),
                next_try_at = now() + make_interval(secs => %s)
            WHERE id = %s
            """,
            (error, delay_seconds, image_id),
        )
