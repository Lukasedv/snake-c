"""
Multiplayer room and session management for the Snake Race mode.

A *Room* hosts a set of players who each run their own independent Game
instance.  The first player to reach ``target_score`` points wins (race
mode).  Spectators may connect to any room and receive the same state
broadcast as players but cannot send input.

Room lifecycle
--------------
WAITING  → (enough players join or host clicks Start) →
COUNTDOWN (3-2-1) →
PLAYING  → (a win condition is met) →
FINISHED
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from fastapi import WebSocket

from .game import Direction, Game


class RoomState(str, Enum):
    WAITING = "waiting"
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    FINISHED = "finished"


@dataclass
class PlayerSession:
    """Bundles a WebSocket connection with a running Game instance."""

    player_id: str
    name: str
    websocket: WebSocket
    game: Game = field(default_factory=Game)

    def __post_init__(self) -> None:
        self.game.init()


class Room:
    """A single multiplayer room.

    Parameters
    ----------
    room_id:
        Unique identifier for this room.
    max_players:
        Maximum number of active (playing) connections.  Connections beyond
        this limit are automatically demoted to spectators.
    target_score:
        The score a player must reach to win the race.
    """

    MIN_PLAYERS_TO_START = 2

    def __init__(
        self,
        room_id: str,
        max_players: int = 4,
        target_score: int = 100,
    ) -> None:
        self.room_id = room_id
        self.max_players = max(2, min(max_players, 4))
        self.target_score = max(10, target_score)
        self.state = RoomState.WAITING
        self.players: dict[str, PlayerSession] = {}
        self.spectators: list[WebSocket] = []
        self.winner: Optional[str] = None
        self._tick_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def add_player(self, player_id: str, name: str, ws: WebSocket) -> bool:
        """Register *ws* as a player.  Returns False when the room is full."""
        if len(self.players) >= self.max_players or self.state != RoomState.WAITING:
            return False
        self.players[player_id] = PlayerSession(player_id, name, ws)
        return True

    def add_spectator(self, ws: WebSocket) -> None:
        self.spectators.append(ws)

    def remove_player(self, player_id: str) -> None:
        self.players.pop(player_id, None)

    def remove_spectator(self, ws: WebSocket) -> None:
        if ws in self.spectators:
            self.spectators.remove(ws)

    @property
    def player_count(self) -> int:
        return len(self.players)

    @property
    def spectator_count(self) -> int:
        return len(self.spectators)

    def is_ready(self) -> bool:
        """True when enough players have joined to start a race."""
        return self.player_count >= self.MIN_PLAYERS_TO_START

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------

    async def broadcast_state(self, extra: Optional[dict] = None) -> None:
        """Push the current room state to every connected WebSocket."""
        base_payload = self._make_state_payload()
        if extra:
            base_payload.update(extra)

        for player_id, session in list(self.players.items()):
            payload = dict(base_payload)
            payload["my_player_id"] = player_id
            payload["role"] = "player"
            try:
                await session.websocket.send_text(json.dumps(payload))
            except Exception:
                pass

        spectator_payload = dict(base_payload)
        spectator_payload["role"] = "spectator"
        for ws in list(self.spectators):
            try:
                await ws.send_text(json.dumps(spectator_payload))
            except Exception:
                pass

    def _make_state_payload(self) -> dict:
        players_data = [
            {
                "player_id": pid,
                "name": session.name,
                "score": session.game.score,
                "alive": not session.game.game_over,
                "body": [[p.x, p.y] for p in session.game.body],
                "food": [session.game.food.x, session.game.food.y],
                "length": session.game.length,
            }
            for pid, session in self.players.items()
        ]
        return {
            "type": "state",
            "room_id": self.room_id,
            "mode": "race",
            "room_state": self.state.value,
            "players": players_data,
            "winner": self.winner,
            "target_score": self.target_score,
            "max_players": self.max_players,
        }

    # ------------------------------------------------------------------
    # Game lifecycle
    # ------------------------------------------------------------------

    async def start_countdown(self) -> None:
        """Run the 3-2-1 countdown then begin the tick loop."""
        if self.state != RoomState.WAITING:
            return
        self.state = RoomState.COUNTDOWN
        for i in range(3, 0, -1):
            await self.broadcast_state({"countdown": i})
            await asyncio.sleep(1)

        self.state = RoomState.PLAYING
        await self.broadcast_state()
        self._tick_task = asyncio.create_task(self._run_tick_loop())

    async def _run_tick_loop(self) -> None:
        """Advance all player games and check win conditions each tick."""
        while self.state == RoomState.PLAYING:
            alive = [s for s in self.players.values() if not s.game.game_over]
            if not alive:
                break

            tick_ms = min(s.game.tick_ms() for s in alive)
            await asyncio.sleep(tick_ms / 1000.0)

            for session in list(self.players.values()):
                if not session.game.game_over:
                    session.game.step()

            winner_name = self._check_winner()
            if winner_name is not None:
                self.winner = winner_name
                self.state = RoomState.FINISHED
                await self.broadcast_state()
                return

            await self.broadcast_state()

    def _check_winner(self) -> Optional[str]:
        """Return a winner's name when a race end condition is met."""
        # 1. First to reach the target score.
        for session in self.players.values():
            if session.game.score >= self.target_score:
                return session.name

        alive = [s for s in self.players.values() if not s.game.game_over]
        dead = [s for s in self.players.values() if s.game.game_over]

        # 2. Last snake standing when at least one player has died.
        if len(alive) == 1 and dead:
            return alive[0].name

        # 3. Everyone crashed simultaneously — highest score wins.
        if not alive and dead:
            best = max(self.players.values(), key=lambda s: s.game.score)
            return best.name

        return None


# ---------------------------------------------------------------------------
# Room registry
# ---------------------------------------------------------------------------


class RoomManager:
    """Global registry of active rooms."""

    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}

    def create_room(
        self,
        room_id: Optional[str] = None,
        max_players: int = 4,
        target_score: int = 100,
    ) -> Room:
        if room_id is None:
            room_id = str(uuid.uuid4())[:8]
        room = Room(room_id, max_players, target_score)
        self.rooms[room_id] = room
        return room

    def get_room(self, room_id: str) -> Optional[Room]:
        return self.rooms.get(room_id)

    def get_or_create_room(self, room_id: str) -> Room:
        if room_id not in self.rooms:
            self.rooms[room_id] = Room(room_id)
        return self.rooms[room_id]

    def cleanup_empty(self) -> None:
        empty = [
            rid
            for rid, room in self.rooms.items()
            if not room.players and not room.spectators
        ]
        for rid in empty:
            del self.rooms[rid]

    def list_rooms(self) -> list[dict]:
        return [
            {
                "room_id": rid,
                "state": room.state.value,
                "players": room.player_count,
                "max_players": room.max_players,
                "spectators": room.spectator_count,
                "target_score": room.target_score,
            }
            for rid, room in self.rooms.items()
        ]
