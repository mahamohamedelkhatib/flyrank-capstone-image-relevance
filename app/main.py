from fastapi import FastAPI, Query
from pydantic import BaseModel

from app import service
from app.db import connect

app = FastAPI(title="Image Relevance and Auto-Tagging")


@app.get("/costs")
def costs(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    """The cost of every AI call, newest first, with totals by purpose."""
    with connect() as conn:
        totals = conn.execute(
            """
            SELECT purpose, count(*), coalesce(sum(input_tokens), 0),
                   coalesce(sum(output_tokens), 0), coalesce(sum(cost_usd), 0)
            FROM ai_calls GROUP BY purpose ORDER BY purpose
            """
        ).fetchall()
        calls = conn.execute(
            """
            SELECT id, image_id, purpose, model, input_tokens, output_tokens,
                   cost_usd, latency_ms, status, error, created_at
            FROM ai_calls ORDER BY id DESC LIMIT %s OFFSET %s
            """,
            (limit, offset),
        ).fetchall()
    return {
        "total_cost_usd": float(sum(t[4] for t in totals)),
        "by_purpose": [
            {"purpose": p, "calls": n, "input_tokens": i, "output_tokens": o, "cost_usd": float(c)}
            for p, n, i, o, c in totals
        ],
        "calls": [
            {"id": r[0], "image_id": r[1], "purpose": r[2], "model": r[3],
             "input_tokens": r[4], "output_tokens": r[5], "cost_usd": float(r[6]),
             "latency_ms": r[7], "status": r[8], "error": r[9], "created_at": r[10]}
            for r in calls
        ],
    }


class PostIn(BaseModel):
    title: str
    body: str


@app.post("/posts", status_code=201)
def add_post(payload: PostIn):
    """Add a blog post. It is tagged and embedded once, then stored."""
    return service.create_post(payload.title, payload.body)


@app.get("/posts/{post_id}/images")
def post_images(post_id: int, refresh: bool = False):
    """Ranked image suggestions for a post, with the guard's decision and reason for each."""
    return service.get_suggestions(post_id, refresh)
