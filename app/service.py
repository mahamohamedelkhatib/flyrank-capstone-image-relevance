import os

import app.guard as guard
from app import repository
from app.engine import find_match
from app.errors import BadInput, NotFound
from app.post_tags import PostTags, tag_post
from app.vectors import embed_logged

MAX_TITLE = 200
MAX_BODY = 5000


def create_post(title: str, body: str) -> dict:
    """Check the input, tag and embed the post once, and store it."""
    title, body = title.strip(), body.strip()
    if not title or not body:
        raise BadInput("title and body must not be empty")
    if len(title) > MAX_TITLE or len(body) > MAX_BODY:
        raise BadInput(f"title is limited to {MAX_TITLE} characters and body to {MAX_BODY}")
    text = f"{title}. {body}"
    tags = tag_post(text)
    post_id = repository.insert_post(title, body, tags)
    if tags.confidence >= guard.MIN_POST_CONFIDENCE:
        repository.insert_post_vector(post_id, os.environ["GEMINI_EMBED_MODEL"], embed_logged(text))
    return {"id": post_id, "title": title, "tags": tags.model_dump()}


def get_suggestions(post_id: int, refresh: bool = False) -> dict:
    """The system's decisions for a post: computed once, then read from the database."""
    post = repository.get_post(post_id)
    if post is None:
        raise NotFound(f"post {post_id} does not exist")

    stored = [] if refresh else repository.list_suggestions(post_id)
    if not stored:
        tags = PostTags(subject=post["subject"], category=post["category"],
                        confidence=post["confidence"])
        result = find_match(tags, repository.get_post_vector(post_id) or [])
        items = [{"filename": r["filename"], "score": r["score"], "decision": "rejected",
                  "rule": r["rule"], "reason": r["reason"]} for r in result["rejected"]]
        if result["match"]:
            m = result["match"]
            items.append({"filename": m["filename"], "score": m["score"],
                          "decision": "accepted", "rule": None, "reason": m["why"]})
        items.sort(key=lambda item: item["score"], reverse=True)
        repository.save_suggestions(post_id, items)
        stored = repository.list_suggestions(post_id)

    accepted = any(s["decision"] == "accepted" for s in stored)
    if accepted:
        message = "match found"
    elif post["confidence"] < guard.MIN_POST_CONFIDENCE:
        message = "no confident match: the post has no clear visual subject"
    else:
        message = "no confident match: no image passed all the guard rules"
    return {
        "post": {k: post[k] for k in ("id", "title", "subject", "category", "confidence")},
        "decision": "match" if accepted else "no_match",
        "message": message,
        "suggestions": stored,
    }
