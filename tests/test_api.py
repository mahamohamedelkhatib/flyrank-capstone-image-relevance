import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BAD_REQUESTS = [
    ("POST", "/posts", {"json": {"title": "", "body": "text"}}, 400),
    ("POST", "/posts", {"json": {"title": "hello"}}, 400),
    ("GET", "/posts/999999/images", {}, 404),
    ("GET", "/posts/abc/images", {}, 400),
    ("GET", "/suggestions/999999", {}, 404),
    ("POST", "/suggestions/1/review", {"json": {"verdict": "maybe"}}, 400),
    ("GET", "/costs?limit=0", {}, 400),
    ("GET", "/jobs/999999", {}, 404),
    ("POST", "/posts/999999/images/1/check", {}, 404),
]


@pytest.mark.parametrize("method,url,kwargs,expected", BAD_REQUESTS)
def test_bad_input_gets_a_clean_error(method, url, kwargs, expected):
    response = client.request(method, url, **kwargs)
    assert response.status_code == expected
    assert "error" in response.json()


def test_budget_cap_stops_ai_calls(monkeypatch):
    monkeypatch.setenv("MAX_BUDGET_USD", "0")
    response = client.post("/posts", json={"title": "Fox", "body": "A red fox in a field."})
    assert response.status_code == 402
