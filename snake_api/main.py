"""
FastAPI application — Snake Multiplayer.

Endpoints
---------
GET  /                        → 1v1 vs Computer (direct play, shared board)
GET  /lobby                   → multiplayer lobby (legacy multi-board mode)
GET  /race/{room_id}          → race room page (static HTML)
GET  /api/rooms               → list open rooms (JSON)
POST /api/rooms               → create a new room (JSON)

WebSocket /ws/play
    ?player_name=<name>       → single human vs bot on a shared arena board

WebSocket /ws/race/{room_id}
    ?player_name=<name>       → join as a player (auto-demoted to spectator
                                if the room is full or already in progress)
WebSocket /ws/race/{room_id}/spectate
                              → join as a spectator (read-only)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .arena import Arena, greedy_arena_direction
from .game import Direction
from .room import RoomManager, RoomState

app = FastAPI(title="Snake Multiplayer", version="1.0.0")

_STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC), name="static")

room_manager = RoomManager()

_DIR_MAP: dict[str, Direction] = {
    "UP": Direction.UP,
    "DOWN": Direction.DOWN,
    "LEFT": Direction.LEFT,
    "RIGHT": Direction.RIGHT,
}

# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def get_play() -> HTMLResponse:
    """Direct 1v1-vs-bot play page."""
    return HTMLResponse((_STATIC / "play.html").read_text())


@app.get("/lobby", response_class=HTMLResponse)
async def get_lobby() -> HTMLResponse:
    """Legacy multiplayer lobby."""
    return HTMLResponse((_STATIC / "index.html").read_text())


@app.get("/race/{room_id}", response_class=HTMLResponse)
async def get_race_room(room_id: str) -> HTMLResponse:  # noqa: ARG001
    return HTMLResponse((_STATIC / "race.html").read_text())


@app.get("/api/rooms")
async def list_rooms() -> dict:
    return {"rooms": room_manager.list_rooms()}


@app.post("/api/rooms")
async def create_room(
    max_players: int = 4,
    target_score: int = 100,
    add_bot: bool = False,
) -> dict:
    room = room_manager.create_room(max_players=max_players, target_score=target_score)
    if add_bot:
        room.add_bot()
    return {"room_id": room.room_id}


# ---------------------------------------------------------------------------
# WebSocket: 1v1 vs bot (shared arena)
# ---------------------------------------------------------------------------


_PLAYER_ID = "player"
_BOT_ID = "bot"


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
                        # Stay connected — wait for restart.
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


# ---------------------------------------------------------------------------
# WebSocket: race player
# ---------------------------------------------------------------------------


@app.websocket("/ws/race/{room_id}")
async def race_websocket(
    websocket: WebSocket,
    room_id: str,
    player_name: str = "Player",
) -> None:
    await websocket.accept()
    room = room_manager.get_or_create_room(room_id)
    player_id = str(uuid.uuid4())[:8]

    # Try to join as a player; fall back to spectator if room is full.
    if not room.add_player(player_id, player_name, websocket):
        await _run_spectator(websocket, room)
        return

    try:
        await room.broadcast_state()

        # Auto-start once the room reaches max capacity.
        if room.player_count >= room.max_players and room.state == RoomState.WAITING:
            asyncio.create_task(room.start_countdown())

        # Listen for direction / start messages.
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
            except asyncio.TimeoutError:
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "dir":
                direction = _DIR_MAP.get(str(msg.get("dir", "")).upper())
                if direction and player_id in room.players:
                    room.players[player_id].game.set_direction(direction)

            elif (
                msg.get("type") == "start"
                and room.state == RoomState.WAITING
                and room.is_ready()
            ):
                asyncio.create_task(room.start_countdown())

    except WebSocketDisconnect:
        pass
    finally:
        room.remove_player(player_id)
        if not room.players and not room.spectators:
            room_manager.rooms.pop(room_id, None)
        else:
            await room.broadcast_state()


# ---------------------------------------------------------------------------
# WebSocket: spectator
# ---------------------------------------------------------------------------


@app.websocket("/ws/race/{room_id}/spectate")
async def spectate_websocket(websocket: WebSocket, room_id: str) -> None:
    await websocket.accept()
    room = room_manager.get_or_create_room(room_id)
    await _run_spectator(websocket, room)


async def _run_spectator(websocket: WebSocket, room) -> None:  # type: ignore[type-arg]
    """Attach *websocket* as a spectator and hold the connection open."""
    room.add_spectator(websocket)
    try:
        await room.broadcast_state()
        # Spectators receive broadcasts from the room's tick loop; we only
        # need to keep the connection alive here.
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        room.remove_spectator(websocket)
        if not room.players and not room.spectators:
            room_manager.rooms.pop(room.room_id, None)
