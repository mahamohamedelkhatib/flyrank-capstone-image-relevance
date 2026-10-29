from dataclasses import dataclass

from app.post_tags import PostTags

MIN_POST_CONFIDENCE = 0.5
MIN_SIMILARITY = 0.80  # placeholder: tuned on the labeled posts in Block 9


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
                       f"post is about {post.category} ({post.subject}), "
                       f"image shows {image['category']} ({image['subject']})")
    # Rule 3: similar enough?
    if similarity < MIN_SIMILARITY:
        return Verdict(False, "low_similarity",
                       f"similarity {similarity:.2f} is below {MIN_SIMILARITY}")
    return Verdict(True)
