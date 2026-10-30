from app.db import connect
from app.ingest import ingest
from app.vectors import embed_images
from app.worker import run_batch


def seed() -> None:
    """Load the demo data: add the images, tag them, embed them. Safe to run again."""
    print("new images added:", ingest())
    run_batch()
    print("images embedded:", embed_images())
    with connect() as conn:
        rows = conn.execute(
            "SELECT status, count(*) FROM images GROUP BY status ORDER BY status"
        ).fetchall()
    print("image statuses:", dict(rows))


if __name__ == "__main__":
    seed()
