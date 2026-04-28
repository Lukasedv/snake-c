"""FastAPI backend for the Snake web app.

Serves the static front-end and provides a tiny high-score API backed by
SQLite (stdlib – no extra dependencies).
"""

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "scores.db"

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                score      INTEGER NOT NULL,
                created_at TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_db()
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Snake", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ScoreIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    score: int = Field(ge=0)


class ScoreOut(BaseModel):
    id: int
    name: str
    score: int
    created_at: str


# ---------------------------------------------------------------------------
# API routes (defined BEFORE the static-file catch-all)
# ---------------------------------------------------------------------------


@app.get("/api/scores", response_model=list[ScoreOut])
def get_scores() -> list[ScoreOut]:
    """Return the top-10 scores ordered by score descending."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, score, created_at FROM scores ORDER BY score DESC LIMIT 10"
        ).fetchall()
    return [ScoreOut(**dict(row)) for row in rows]


@app.post("/api/scores", response_model=ScoreOut, status_code=201)
def post_score(payload: ScoreIn) -> ScoreOut:
    """Persist a new score and return the saved record."""
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO scores (name, score) VALUES (?, ?)",
            (payload.name, payload.score),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, name, score, created_at FROM scores WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to save score")
    return ScoreOut(**dict(row))


# ---------------------------------------------------------------------------
# Static files + SPA root
# ---------------------------------------------------------------------------

# Serve everything under /static/…
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
