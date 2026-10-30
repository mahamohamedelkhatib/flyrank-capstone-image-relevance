from app.guard import MIN_SIMILARITY, check_basic, subject_mismatch_reason
from app.post_tags import PostTags

FOX_POST = PostTags(subject="red fox", category="animal", confidence=1.0)
TAX_POST = PostTags(subject="tax forms", category="other", confidence=0.3)


def image(filename="fox-01.jpg", status="done", category="animal", subject="red fox"):
    return {"filename": filename, "status": status, "category": category, "subject": subject}


def test_good_match_passes():
    assert check_basic(FOX_POST, image(), 0.9).ok


def test_flagged_image_is_not_trusted():
    verdict = check_basic(FOX_POST, image(status="flagged"), 0.9)
    assert not verdict.ok and verdict.rule == "untrusted_image"


def test_post_without_a_clear_subject_is_rejected():
    verdict = check_basic(TAX_POST, image(), 0.9)
    assert not verdict.ok and verdict.rule == "unclear_post"


def test_other_category_is_rejected_with_an_explanation():
    verdict = check_basic(FOX_POST, image("car-01.jpg", category="vehicle", subject="black cab"), 0.9)
    assert verdict.rule == "category_mismatch"
    assert "category mismatch" in verdict.reason and "black cab" in verdict.reason


def test_low_similarity_is_rejected():
    verdict = check_basic(FOX_POST, image(), MIN_SIMILARITY - 0.01)
    assert not verdict.ok and verdict.rule == "low_similarity"


def test_threshold_boundary_is_accepted():
    assert check_basic(FOX_POST, image(), MIN_SIMILARITY).ok


def test_rules_run_in_order():
    flagged_car = image("blurry-01.jpg", status="flagged", category="vehicle")
    assert check_basic(FOX_POST, flagged_car, 0.1).rule == "untrusted_image"


def test_subject_mismatch_reason_names_both_subjects():
    text = subject_mismatch_reason("red fox", "gray wolf", "They are distinct species.")
    assert text.startswith("category mismatch") and "red fox" in text and "gray wolf" in text
