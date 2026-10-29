import app.guard as guard
from app.db import connect
from app.guard import Verdict, check_basic
from app.judge import judge_subject
from app.matching import rank
from app.post_tags import tag_post

MAX_JUDGE_CALLS = 3


def match_post(text: str, include: tuple = (), exclude: tuple = ()) -> dict:
    """Find the best image for a post, or say there is no confident match."""
    post = tag_post(text)
    base = {"post": post.model_dump(), "match": None, "rejected": []}

    if post.confidence < guard.MIN_POST_CONFIDENCE:
        return {**base, "decision": "no_match",
                "message": "no confident match: the post has no clear visual subject"}

    with connect() as conn:
        captions = dict(conn.execute("SELECT filename, caption FROM images").fetchall())

    judged = 0
    for score, filename, subject, category, status in rank(text, limit=1000):
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
                return {**base, "decision": "match", "message": "match found",
                        "match": {"filename": filename, "score": round(score, 3),
                                  "subject": subject, "why": judgement.reason}}
            verdict = Verdict(False, "subject_mismatch", judgement.reason)
        base["rejected"].append({"filename": filename, "score": round(score, 3),
                                 "rule": verdict.rule, "reason": verdict.reason})

    return {**base, "decision": "no_match",
            "message": "no confident match: no image passed all the guard rules"}


def show(result: dict) -> None:
    print("POST:", result["post"])
    print("DECISION:", result["decision"], "-", result["message"])
    if result["match"]:
        print("  matched:", result["match"])
    for r in result["rejected"]:
        print(f"  rejected {r['filename']} ({r['score']}) by {r['rule']}: {r['reason']}")
