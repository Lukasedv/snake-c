"""
FastAPI application — Snake Multiplayer.

Endpoints
---------
GET  /                        → lobby page (static HTML)
GET  /race/{room_id}          → race room page (static HTML)
GET  /api/rooms               → list open rooms (JSON)
POST /api/rooms               → create a new room (JSON)

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
async def get_index() -> HTMLResponse:
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
