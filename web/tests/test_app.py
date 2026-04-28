"""Tests for the Snake FastAPI backend.

Run with:  pytest web/tests/
"""

import pytest
from fastapi.testclient import TestClient

from web.app import app, DB_PATH


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    """Redirect the database to a temporary file for each test."""
    import web.app as app_module

    test_db = tmp_path / "test_scores.db"
    monkeypatch.setattr(app_module, "DB_PATH", test_db)
    # Re-initialise the DB at the new path
    app_module._init_db()
    yield
    # tmp_path is cleaned up automatically by pytest


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_scores_empty(client):
    """GET /api/scores returns an empty list when no scores exist."""
    resp = client.get("/api/scores")
    assert resp.status_code == 200
    assert resp.json() == []


def test_post_score_returns_saved_record(client):
    """POST /api/scores persists a score and echoes it back."""
    resp = client.post("/api/scores", json={"name": "Alice", "score": 120})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alice"
    assert data["score"] == 120
    assert "id" in data
    assert "created_at" in data


def test_get_scores_descending_order(client):
    """GET /api/scores returns scores ordered by score DESC."""
    client.post("/api/scores", json={"name": "Low",  "score": 10})
    client.post("/api/scores", json={"name": "High", "score": 200})
    client.post("/api/scores", json={"name": "Mid",  "score": 80})

    resp = client.get("/api/scores")
    assert resp.status_code == 200
    scores = [entry["score"] for entry in resp.json()]
    assert scores == sorted(scores, reverse=True)


def test_get_scores_top_10_only(client):
    """GET /api/scores returns at most 10 entries."""
    for i in range(15):
        client.post("/api/scores", json={"name": f"P{i}", "score": i * 10})

    resp = client.get("/api/scores")
    assert resp.status_code == 200
    assert len(resp.json()) == 10


def test_post_score_invalid_missing_name(client):
    """POST /api/scores with missing name returns 422."""
    resp = client.post("/api/scores", json={"score": 50})
    assert resp.status_code == 422


def test_post_score_invalid_negative_score(client):
    """POST /api/scores with a negative score returns 422."""
    resp = client.post("/api/scores", json={"name": "Bad", "score": -1})
    assert resp.status_code == 422


def test_post_score_invalid_empty_name(client):
    """POST /api/scores with an empty name string returns 422."""
    resp = client.post("/api/scores", json={"name": "", "score": 10})
    assert resp.status_code == 422


def test_root_returns_html(client):
    """GET / serves the HTML front-end."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
