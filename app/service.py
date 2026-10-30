import os

import app.guard as guard
from app import repository
from app.embed import cosine
from app.engine import find_match
from app.errors import BadInput, Conflict, NotFound
from app.guard import Verdict, check_basic, subject_mismatch_reason
from app.judge import judge_subject
from app.matching import rank_vector
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


def get_suggestions(post_id: int, refresh: bool = False, top: int = 10) -> dict:
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

    vector = repository.get_post_vector(post_id)
    ranking = [
        {"rank": i, "filename": f, "subject": s, "category": c, "status": st, "score": round(score, 3)}
        for i, (score, f, s, c, st) in enumerate(rank_vector(vector, top), start=1)
    ] if vector else []
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
        "ranking": ranking,
    }


def get_suggestion(suggestion_id: int) -> dict:
    """Why an image was selected or refused, with its tags and any human reviews."""
    suggestion = repository.get_suggestion(suggestion_id)
    if suggestion is None:
        raise NotFound(f"suggestion {suggestion_id} does not exist")
    return suggestion


def review_suggestion(suggestion_id: int, verdict: str, note: str | None) -> dict:
    """Record a human decision on a suggestion."""
    if verdict not in ("approved", "rejected"):
        raise BadInput("verdict must be 'approved' or 'rejected'")
    if note is not None and len(note) > 1000:
        raise BadInput("note is limited to 1000 characters")
    if repository.get_suggestion(suggestion_id) is None:
        raise NotFound(f"suggestion {suggestion_id} does not exist")
    review_id = repository.add_review(suggestion_id, verdict, note)
    return {"review_id": review_id, "suggestion_id": suggestion_id, "verdict": verdict, "note": note}


def check_image(post_id: int, image_id: int) -> dict:
    """Would the guard accept this one image for this post? Nothing is saved."""
    post = repository.get_post(post_id)
    if post is None:
        raise NotFound(f"post {post_id} does not exist")
    image = repository.get_image(image_id)
    if image is None:
        raise NotFound(f"image {image_id} does not exist")

    tags = PostTags(subject=post["subject"], category=post["category"], confidence=post["confidence"])
    post_vector = repository.get_post_vector(post_id)
    image_vector = repository.get_image_vector(image_id)
    similarity = cosine(post_vector, image_vector) if post_vector and image_vector else 0.0

    verdict = check_basic(tags, image, similarity)
    if verdict.ok:
        judgement = judge_subject(tags.subject, image["subject"], image["caption"])
        verdict = (Verdict(True, None, judgement.reason) if judgement.same_subject
                   else Verdict(False, "subject_mismatch",
                           subject_mismatch_reason(tags.subject, image["subject"], judgement.reason)))
    return {"post_id": post_id, "image": image["filename"], "similarity": round(similarity, 3),
            "accepted": verdict.ok, "rule": verdict.rule, "reason": verdict.reason}


def start_job() -> int:
    """Create a job row for the pending images. Only one job may run at a time."""
    if repository.has_running_job():
        raise Conflict("a job is already running")
    return repository.create_job("process", repository.count_pending_images())


def get_job(job_id: int) -> dict:
    job = repository.get_job(job_id)
    if job is None:
        raise NotFound(f"job {job_id} does not exist")
    return job
