"""FastAPI backend for multiplayer Snake web app.

Serves the static front-end, provides high-score API, and handles
WebSocket connections for real-time multiplayer gameplay.
"""

import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from web.websockets import connection_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        # Single-player scores table
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

        # Multiplayer game history
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS multiplayer_games (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id    TEXT    NOT NULL,
                mode       TEXT    NOT NULL,
                winner_id  TEXT,
                created_at TEXT    NOT NULL DEFAULT (datetime('now')),
                finished_at TEXT
            )
            """
        )

        # Multiplayer player results
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS multiplayer_results (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id    INTEGER NOT NULL,
                player_id  TEXT    NOT NULL,
                player_name TEXT   NOT NULL,
                score      INTEGER NOT NULL,
                placement  INTEGER NOT NULL,
                FOREIGN KEY (game_id) REFERENCES multiplayer_games(id)
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
    logger.info("Database initialized")
    yield
    logger.info("Application shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Multiplayer Snake", lifespan=lifespan)


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
# WebSocket endpoint for multiplayer
# ---------------------------------------------------------------------------


@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
    """WebSocket endpoint for multiplayer game communication.

    Args:
        websocket: WebSocket connection
        player_id: Unique player identifier (generated client-side)
    """
    await connection_manager.connect(websocket, player_id)

    try:
        while True:
            # Receive JSON message from client
            data = await websocket.receive_json()

            # Handle the message
            await connection_manager.handle_message(player_id, data)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {player_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {player_id}: {e}")
    finally:
        await connection_manager.disconnect(player_id)


# ---------------------------------------------------------------------------
# API routes for single-player scores
# ---------------------------------------------------------------------------


@app.get("/api/scores", response_model=list[ScoreOut])
def get_scores() -> list[ScoreOut]:
    """Return the top-10 single-player scores ordered by score descending."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, score, created_at FROM scores ORDER BY score DESC LIMIT 10"
        ).fetchall()
    return [ScoreOut(**dict(row)) for row in rows]


@app.post("/api/scores", response_model=ScoreOut, status_code=201)
def post_score(payload: ScoreIn) -> ScoreOut:
    """Persist a new single-player score and return the saved record."""
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
# API routes for multiplayer leaderboard
# ---------------------------------------------------------------------------


@app.get("/api/multiplayer/leaderboard")
def get_multiplayer_leaderboard(limit: int = 10):
    """Get multiplayer leaderboard (top players by wins and scores)."""
    with _get_conn() as conn:
        # Get top players by number of wins
        rows = conn.execute(
            """
            SELECT
                player_name,
                COUNT(CASE WHEN placement = 1 THEN 1 END) as wins,
                COUNT(*) as games_played,
                SUM(score) as total_score,
                AVG(score) as avg_score,
                AVG(placement) as avg_placement
            FROM multiplayer_results
            GROUP BY player_name
            ORDER BY wins DESC, total_score DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

    return [
        {
            "player_name": row["player_name"],
            "wins": row["wins"],
            "games_played": row["games_played"],
            "total_score": row["total_score"],
            "avg_score": round(row["avg_score"], 1) if row["avg_score"] else 0,
            "avg_placement": round(row["avg_placement"], 2) if row["avg_placement"] else 0
        }
        for row in rows
    ]


@app.get("/api/multiplayer/recent_games")
def get_recent_games(limit: int = 10):
    """Get recently finished multiplayer games."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                g.id,
                g.room_id,
                g.mode,
                g.created_at,
                g.finished_at,
                GROUP_CONCAT(r.player_name || ':' || r.score) as player_scores
            FROM multiplayer_games g
            LEFT JOIN multiplayer_results r ON g.id = r.game_id
            WHERE g.finished_at IS NOT NULL
            GROUP BY g.id
            ORDER BY g.finished_at DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

    return [
        {
            "game_id": row["id"],
            "room_id": row["room_id"],
            "mode": row["mode"],
            "created_at": row["created_at"],
            "finished_at": row["finished_at"],
            "players": row["player_scores"]
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Static files + SPA roots
# ---------------------------------------------------------------------------

# Serve everything under /static/…
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    """Serve the single-player game page."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/multiplayer")
def multiplayer() -> FileResponse:
    """Serve the multiplayer game page."""
    return FileResponse(STATIC_DIR / "multiplayer.html")
