from dataclasses import dataclass

from app.post_tags import PostTags

MIN_POST_CONFIDENCE = 0.5
MIN_SIMILARITY = 0.78  # tuned on eval/posts.csv: sits in the gap between right matches (>= 0.798) and no-match posts (<= 0.761)


@dataclass
class Verdict:
    ok: bool
    rule: str | None = None
    reason: str = ""


def check_basic(post: PostTags, image: dict, similarity: float) -> Verdict:
    """Rules 1 to 3. The first rule that fails rejects the match, with a reason."""
    # Rule 1: can we trust the data?
    if image["status"] != "done":
        return Verdict(False, "untrusted_image",
                       f"{image['filename']} is {image['status']}, so its tags are not trusted")
    if post.confidence < MIN_POST_CONFIDENCE:
        return Verdict(False, "unclear_post",
                       f"the post has no clear visual subject (confidence {post.confidence})")
    # Rule 2: same category?
    if post.category != image["category"]:
        return Verdict(False, "category_mismatch",
                       f"category mismatch: post is about {post.category} ({post.subject}), "
                       f"image shows {image['category']} ({image['subject']})")
    # Rule 3: similar enough?
    if similarity < MIN_SIMILARITY:
        return Verdict(False, "low_similarity",
                       f"similarity {similarity:.2f} is below {MIN_SIMILARITY}")
    return Verdict(True)


def subject_mismatch_reason(post_subject: str, image_subject: str, judge_reason: str) -> str:
    """Explanation for rule 4: the post and the image are about different kinds of things."""
    return (f"category mismatch: the post is about '{post_subject}' but the image shows "
            f"'{image_subject}'. {judge_reason}")
