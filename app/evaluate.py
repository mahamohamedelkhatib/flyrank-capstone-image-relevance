import csv
import json
import sys

import app.guard as guard
from app.engine import match_post


def is_correct(expected: str, result: dict) -> bool:
    if expected == "none":
        return result["decision"] == "no_match"
    return (result["decision"] == "match"
            and result["match"]["filename"].startswith(expected + "-"))


def run(threshold: float | None = None) -> float:
    if threshold is not None:
        guard.MIN_SIMILARITY = threshold
    rows = list(csv.DictReader(open("eval/posts.csv")))
    details = []
    correct = 0
    for row in rows:
        try:
            result = match_post(row["text"])
        except Exception as e:
            result = {"decision": "error", "match": None, "message": f"{type(e).__name__}: {e}"[:200]}
        ok = is_correct(row["expected"], result)
        correct += ok
        got = result["match"]["filename"] if result["match"] else result["decision"]
        print(f"{'OK ' if ok else 'BAD'} post {row['id']:>2}: expected {row['expected']:9} got {got}")
        details.append({"id": row["id"], "expected": row["expected"], "correct": ok, "result": result})

    precision = correct / len(rows)
    print(f"\nthreshold {guard.MIN_SIMILARITY}: {correct}/{len(rows)} correct, top-1 precision {precision:.2f}")
    with open("eval/results.json", "w") as f:
        json.dump({"threshold": guard.MIN_SIMILARITY, "precision": precision, "posts": details}, f, indent=2)
    return precision


if __name__ == "__main__":
    run(float(sys.argv[1]) if len(sys.argv) > 1 else None)
