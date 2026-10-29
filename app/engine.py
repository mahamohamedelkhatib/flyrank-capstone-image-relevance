import app.guard as guard
from app.db import connect
from app.guard import Verdict, check_basic
from app.judge import judge_subject
from app.matching import rank_vector
from app.post_tags import PostTags, tag_post
from app.vectors import embed_logged

MAX_JUDGE_CALLS = 3


def find_match(post: PostTags, query: list[float], include: tuple = (), exclude: tuple = ()) -> dict:
    """Run the guard for a post that is already tagged and embedded."""
    result = {"match": None, "rejected": []}
    if post.confidence < guard.MIN_POST_CONFIDENCE:
        return {**result, "decision": "no_match",
                "message": "no confident match: the post has no clear visual subject"}

    with connect() as conn:
        captions = dict(conn.execute("SELECT filename, caption FROM images").fetchall())

    judged = 0
    for score, filename, subject, category, status in rank_vector(query, limit=1000):
        if include and not filename.startswith(include):
            continue
        if exclude and filename.startswith(exclude):
            continue
        if score < guard.MIN_SIMILARITY:
            break  # everything after this is even less similar
        image = {"filename": filename, "subject": subject, "category": category, "status": status}
        verdict = check_basic(post, image, score)
        if verdict.ok:
            if judged >= MAX_JUDGE_CALLS:
                break
            judged += 1
            judgement = judge_subject(post.subject, subject, captions[filename])
            if judgement.same_subject:
                return {**result, "decision": "match", "message": "match found",
                        "match": {"filename": filename, "score": round(score, 3),
                                  "subject": subject, "why": judgement.reason}}
            verdict = Verdict(False, "subject_mismatch", judgement.reason)
        result["rejected"].append({"filename": filename, "score": round(score, 3),
                                   "rule": verdict.rule, "reason": verdict.reason})

    return {**result, "decision": "no_match",
            "message": "no confident match: no image passed all the guard rules"}


def match_post(text: str, include: tuple = (), exclude: tuple = ()) -> dict:
    """Tag the post, embed it, and find the best image. Used by the eval script."""
    post = tag_post(text)
    query = [] if post.confidence < guard.MIN_POST_CONFIDENCE else embed_logged(text)
    return {"post": post.model_dump(), **find_match(post, query, include, exclude)}


def show(result: dict) -> None:
    print("POST:", result["post"])
    print("DECISION:", result["decision"], "-", result["message"])
    if result["match"]:
        print("  matched:", result["match"])
    for r in result["rejected"]:
        print(f"  rejected {r['filename']} ({r['score']}) by {r['rule']}: {r['reason']}")
