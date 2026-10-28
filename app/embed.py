import math
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DIMENSIONS = 768  # shorter vectors: cheaper to store and fast to compare


def embed_text(text: str) -> list[float]:
    """Turn text into a list of numbers that captures its meaning."""
    model = os.environ["GEMINI_EMBED_MODEL"]
    key = os.environ["GEMINI_API_KEY"]
    body = {
        "model": f"models/{model}",
        "content": {"parts": [{"text": text}]},
        "taskType": "SEMANTIC_SIMILARITY",
        "outputDimensionality": DIMENSIONS,
    }
    response = httpx.post(
        f"{BASE_URL}/models/{model}:embedContent",
        headers={"x-goog-api-key": key},
        json=body,
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Gemini embed error {response.status_code}: {response.text[:300]}")
    return response.json()["embedding"]["values"]


def cosine(a: list[float], b: list[float]) -> float:
    """How similar two vectors are: close to 1 means same meaning."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b)


if __name__ == "__main__":
    fox_a = embed_text("A red fox sits in a grassy field.")
    fox_b = embed_text("A fox with orange fur standing in the snow.")
    car = embed_text("A black sports car parked on a city street.")
    print("vector length:", len(fox_a))
    print("fox vs fox:", round(cosine(fox_a, fox_b), 3))
    print("fox vs car:", round(cosine(fox_a, car), 3))
