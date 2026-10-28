from pathlib import Path

from app.db import connect

IMAGE_DIR = Path("data/images")


def ingest() -> int:
    """Add every photo in data/images as a pending row. Returns how many were new."""
    files = sorted(p.name for p in IMAGE_DIR.glob("*.jpg"))
    added = 0
    with connect() as conn:
        for name in files:
            cur = conn.execute(
                "INSERT INTO images (filename) VALUES (%s) ON CONFLICT (filename) DO NOTHING",
                (name,),
            )
            added += cur.rowcount
    return added


if __name__ == "__main__":
    print("new images added:", ingest())
