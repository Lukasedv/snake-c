"""
FastAPI application — Snake: You vs Computer.

Endpoints
---------
GET  /              → vs-bot play page (static HTML)

WebSocket /ws/play
    ?player_name=<name>
                    → single human vs bot on a shared arena board
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .arena import Arena, greedy_arena_direction
from .game import Direction

app = FastAPI(title="Snake — You vs Computer", version="2.0.0")

_STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC), name="static")

_DIR_MAP: dict[str, Direction] = {
    "UP": Direction.UP,
    "DOWN": Direction.DOWN,
    "LEFT": Direction.LEFT,
    "RIGHT": Direction.RIGHT,
}

_PLAYER_ID = "player"
_BOT_ID = "bot"


# ---------------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def get_play() -> HTMLResponse:
    return HTMLResponse((_STATIC / "play.html").read_text())


# ---------------------------------------------------------------------------
# WebSocket: 1v1 vs bot (shared arena)
# ---------------------------------------------------------------------------


def _arena_payload(arena: Arena) -> dict:
    return {
        "type": "state",
        "food": [arena.food.x, arena.food.y],
        "snakes": [
            {
                "id": s.snake_id,
                "name": s.name,
                "is_bot": s.snake_id == _BOT_ID,
                "score": s.score,
                "alive": not s.dead,
                "body": [[p.x, p.y] for p in s.body],
                "length": s.length,
            }
            for s in arena.snakes.values()
        ],
        "game_over": arena.game_over,
        "winner_id": arena.winner_id,
    }


@app.websocket("/ws/play")
async def play_websocket(
    websocket: WebSocket,
    player_name: str = "Player",
) -> None:
    await websocket.accept()
    arena = Arena()
    arena.init_two_player(_PLAYER_ID, player_name, _BOT_ID, "Computer")

    async def send_state() -> None:
        try:
            await websocket.send_text(json.dumps(_arena_payload(arena)))
        except Exception:
            pass

    await send_state()

    stop = asyncio.Event()

    async def reader() -> None:
        try:
            while not stop.is_set():
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                mtype = msg.get("type")
                if mtype == "dir":
                    direction = _DIR_MAP.get(str(msg.get("dir", "")).upper())
                    if direction:
                        arena.set_direction(_PLAYER_ID, direction)
                elif mtype == "restart":
                    arena.init_two_player(_PLAYER_ID, player_name, _BOT_ID, "Computer")
                    await send_state()
        except WebSocketDisconnect:
            stop.set()

    async def ticker() -> None:
        try:
            # Brief pause so the player can see the starting position.
            await asyncio.sleep(0.6)
            while not stop.is_set():
                if not arena.game_over:
                    arena.set_direction(_BOT_ID, greedy_arena_direction(arena, _BOT_ID))
                    arena.step()
                    await send_state()
                    if arena.game_over:
                        await asyncio.sleep(0.05)
                        continue
                    await asyncio.sleep(arena.tick_ms() / 1000.0)
                else:
                    await asyncio.sleep(0.1)
        except Exception:
            stop.set()

    reader_task = asyncio.create_task(reader())
    ticker_task = asyncio.create_task(ticker())

    try:
        await asyncio.wait(
            [reader_task, ticker_task], return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        stop.set()
        for t in (reader_task, ticker_task):
            if not t.done():
                t.cancel()
