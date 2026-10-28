import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def connect() -> psycopg.Connection:
    """Open a new connection to Postgres using DATABASE_URL from .env."""
    return psycopg.connect(os.environ["DATABASE_URL"])


if __name__ == "__main__":
    with connect() as conn:
        count = conn.execute("SELECT count(*) FROM images").fetchone()[0]
        print("connected, images rows:", count)
