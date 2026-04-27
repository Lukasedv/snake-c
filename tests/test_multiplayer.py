"""
Tests for the Snake multiplayer room and session logic.

Coverage
--------
- RoomManager: create, get, list, cleanup
- Room: player joining, spectator joining, capacity limits
- Room state transitions: WAITING → COUNTDOWN → PLAYING → FINISHED
- Win conditions: target score, last alive, all-dead tie-break
- Direction input forwarding
- Broadcast payload shape
- FastAPI REST endpoints (via httpx.AsyncClient)
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from snake_api.game import Direction, Game, Point
from snake_api.main import app
from snake_api.room import Room, RoomManager, RoomState


# ── helpers ─────────────────────────────────────────────────────────────────

def _mock_websocket(player_id: str = "ws") -> MagicMock:
    ws = MagicMock()
    ws.send_text = AsyncMock()
    return ws


def _room_with_two_players(target_score: int = 100) -> tuple[Room, str, str]:
    """Return a room and two player IDs (not yet started)."""
    room = Room("test-room", max_players=2, target_score=target_score)
    ws1, ws2 = _mock_websocket("p1"), _mock_websocket("p2")
    pid1, pid2 = "player-1", "player-2"
    assert room.add_player(pid1, "Alice", ws1)
    assert room.add_player(pid2, "Bob", ws2)
    return room, pid1, pid2


# ── RoomManager ──────────────────────────────────────────────────────────────

class TestRoomManager:
    def test_create_room_generates_id(self) -> None:
        rm = RoomManager()
        room = rm.create_room()
        assert room.room_id in rm.rooms
        assert len(room.room_id) > 0

    def test_create_room_explicit_id(self) -> None:
        rm = RoomManager()
        room = rm.create_room(room_id="myroom")
        assert rm.get_room("myroom") is room

    def test_get_missing_room(self) -> None:
        rm = RoomManager()
        assert rm.get_room("nope") is None

    def test_get_or_create_creates(self) -> None:
        rm = RoomManager()
        room = rm.get_or_create_room("new")
        assert rm.get_room("new") is room

    def test_get_or_create_returns_existing(self) -> None:
        rm = RoomManager()
        r1 = rm.get_or_create_room("x")
        r2 = rm.get_or_create_room("x")
        assert r1 is r2

    def test_list_rooms(self) -> None:
        rm = RoomManager()
        rm.create_room(room_id="a", max_players=2, target_score=50)
        rm.create_room(room_id="b", max_players=4, target_score=200)
        rooms = rm.list_rooms()
        ids = {r["room_id"] for r in rooms}
        assert {"a", "b"} <= ids

    def test_cleanup_empty_rooms(self) -> None:
        rm = RoomManager()
        rm.create_room(room_id="empty")
        rm.create_room(room_id="occupied")
        ws = _mock_websocket()
        rm.rooms["occupied"].add_spectator(ws)
        rm.cleanup_empty()
        assert "empty" not in rm.rooms
        assert "occupied" in rm.rooms


# ── Room — capacity and roles ────────────────────────────────────────────────

class TestRoomCapacity:
    def test_add_player_succeeds(self) -> None:
        room = Room("r", max_players=2)
        ws = _mock_websocket()
        assert room.add_player("p1", "Alice", ws)
        assert room.player_count == 1

    def test_add_player_fails_when_full(self) -> None:
        room, _, _ = _room_with_two_players()
        ws3 = _mock_websocket()
        assert not room.add_player("p3", "Charlie", ws3)
        assert room.player_count == 2

    def test_add_spectator(self) -> None:
        room = Room("r")
        ws = _mock_websocket()
        room.add_spectator(ws)
        assert room.spectator_count == 1

    def test_remove_player(self) -> None:
        room, pid1, _ = _room_with_two_players()
        room.remove_player(pid1)
        assert room.player_count == 1
        assert pid1 not in room.players

    def test_remove_spectator(self) -> None:
        room = Room("r")
        ws = _mock_websocket()
        room.add_spectator(ws)
        room.remove_spectator(ws)
        assert room.spectator_count == 0

    def test_is_ready_requires_two(self) -> None:
        room = Room("r", max_players=4)
        ws1 = _mock_websocket()
        room.add_player("p1", "Alice", ws1)
        assert not room.is_ready()
        ws2 = _mock_websocket()
        room.add_player("p2", "Bob", ws2)
        assert room.is_ready()

    def test_player_cannot_join_after_game_started(self) -> None:
        room, _, _ = _room_with_two_players()
        room.state = RoomState.PLAYING
        ws3 = _mock_websocket()
        assert not room.add_player("p3", "Carol", ws3)

    def test_max_players_clamped(self) -> None:
        room = Room("r", max_players=10)
        assert room.max_players == 4
        room2 = Room("r2", max_players=1)
        assert room2.max_players == 2

    def test_target_score_clamped(self) -> None:
        room = Room("r", target_score=5)
        assert room.target_score == 10


# ── Room — win conditions ────────────────────────────────────────────────────

class TestWinConditions:
    def _set_score(self, room: Room, player_id: str, score: int) -> None:
        room.players[player_id].game.score = score

    def test_target_score_win(self) -> None:
        room, pid1, _ = _room_with_two_players(target_score=50)
        self._set_score(room, pid1, 50)
        winner = room._check_winner()
        assert winner == "Alice"

    def test_no_winner_below_target(self) -> None:
        room, pid1, _ = _room_with_two_players(target_score=50)
        self._set_score(room, pid1, 40)
        assert room._check_winner() is None

    def test_last_alive_wins(self) -> None:
        room, pid1, pid2 = _room_with_two_players()
        room.players[pid1].game.game_over = True
        winner = room._check_winner()
        assert winner == "Bob"

    def test_all_dead_highest_score_wins(self) -> None:
        room, pid1, pid2 = _room_with_two_players()
        room.players[pid1].game.score = 30
        room.players[pid2].game.score = 20
        room.players[pid1].game.game_over = True
        room.players[pid2].game.game_over = True
        winner = room._check_winner()
        assert winner == "Alice"

    def test_no_winner_when_both_alive_below_target(self) -> None:
        room, _, _ = _room_with_two_players(target_score=100)
        assert room._check_winner() is None


# ── Room — direction forwarding ──────────────────────────────────────────────

class TestDirectionForwarding:
    def test_direction_is_forwarded_to_game(self) -> None:
        room, pid1, _ = _room_with_two_players()
        room.players[pid1].game.set_direction(Direction.UP)
        assert room.players[pid1].game.pending_dir == Direction.UP

    def test_reverse_direction_ignored(self) -> None:
        room, pid1, _ = _room_with_two_players()
        # Initial direction is RIGHT; sending LEFT (opposite) should be ignored.
        room.players[pid1].game.set_direction(Direction.LEFT)
        assert room.players[pid1].game.pending_dir == Direction.RIGHT


# ── Room — broadcast payload ─────────────────────────────────────────────────

class TestBroadcastPayload:
    def test_payload_structure(self) -> None:
        room, _, _ = _room_with_two_players(target_score=50)
        payload = room._make_state_payload()
        assert payload["type"] == "state"
        assert payload["mode"] == "race"
        assert payload["room_id"] == "test-room"
        assert payload["target_score"] == 50
        assert len(payload["players"]) == 2

    def test_player_entry_fields(self) -> None:
        room, pid1, _ = _room_with_two_players()
        payload = room._make_state_payload()
        p = next(p for p in payload["players"] if p["name"] == "Alice")
        assert "score" in p
        assert "alive" in p
        assert "body" in p
        assert "food" in p
        assert "length" in p

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_players(self) -> None:
        room, _, _ = _room_with_two_players()
        await room.broadcast_state()
        for session in room.players.values():
            session.websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_spectator(self) -> None:
        room, _, _ = _room_with_two_players()
        spec_ws = _mock_websocket()
        room.add_spectator(spec_ws)
        await room.broadcast_state()
        spec_ws.send_text.assert_called_once()
        raw = spec_ws.send_text.call_args[0][0]
        msg = json.loads(raw)
        assert msg["role"] == "spectator"

    @pytest.mark.asyncio
    async def test_player_broadcast_includes_my_player_id(self) -> None:
        room, pid1, _ = _room_with_two_players()
        await room.broadcast_state()
        ws1 = room.players[pid1].websocket
        raw = ws1.send_text.call_args[0][0]
        msg = json.loads(raw)
        assert msg["my_player_id"] == pid1
        assert msg["role"] == "player"


# ── Room — state transitions ─────────────────────────────────────────────────

class TestStateTransitions:
    @pytest.mark.asyncio
    async def test_countdown_transitions_to_playing(self) -> None:
        room, _, _ = _room_with_two_players()
        # Patch asyncio.sleep so the test doesn't actually wait 3 seconds.
        original_sleep = asyncio.sleep

        async def fast_sleep(delay: float) -> None:
            await original_sleep(0)

        asyncio.sleep = fast_sleep  # type: ignore[assignment]
        try:
            await room.start_countdown()
        finally:
            asyncio.sleep = original_sleep  # type: ignore[assignment]

        assert room.state in (RoomState.PLAYING, RoomState.FINISHED)

    @pytest.mark.asyncio
    async def test_cannot_start_countdown_twice(self) -> None:
        room, _, _ = _room_with_two_players()
        room.state = RoomState.PLAYING
        # start_countdown should be a no-op when not WAITING
        await room.start_countdown()
        assert room.state == RoomState.PLAYING


# ── Game engine smoke tests ──────────────────────────────────────────────────

class TestGameEngine:
    def test_initial_state(self) -> None:
        g = Game()
        g.init()
        assert g.length == 4
        assert g.score == 0
        assert not g.game_over

    def test_step_moves_head(self) -> None:
        g = Game()
        g.init()
        old_head = g.head
        g.food = Point(0, 0)  # keep food away from path
        g.step()
        assert g.head != old_head

    def test_eating_increases_score(self) -> None:
        g = Game()
        g.init()
        # Place food directly in front of the head.
        head = g.head
        g.food = Point(head.x + 1, head.y)
        g.step()
        assert g.score == 10

    def test_collision_ends_game(self) -> None:
        g = Game()
        g.init()
        # Build a snake shaped like a backwards C so the head walks into the
        # middle segment on the next step:
        #   body (tail→head): (5,1) (4,1) (3,1) (2,1) (2,2) (3,2) (4,2)
        # Head is at (4,2) facing RIGHT → next = (5,2), which is not occupied.
        # Then turn UP → next = (4,1), which IS occupied (index 1 in the body).
        from collections import deque
        from snake_api.game import BOARD_H
        g.body = deque([
            Point(5, 1), Point(4, 1), Point(3, 1),
            Point(2, 1), Point(2, 2), Point(3, 2), Point(4, 2),
        ])
        g.direction = Direction.RIGHT
        g.pending_dir = Direction.UP   # UP from (4,2) → (4,1) which is in the body
        g.food = Point(0, BOARD_H - 1)
        g.step()
        assert g.game_over


# ── FastAPI HTTP endpoints ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_rooms_empty() -> None:
    from snake_api.main import room_manager
    room_manager.rooms.clear()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/rooms")
    assert resp.status_code == 200
    assert resp.json() == {"rooms": []}


@pytest.mark.asyncio
async def test_create_room_endpoint() -> None:
    from snake_api.main import room_manager
    room_manager.rooms.clear()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/rooms?max_players=2&target_score=50")
    assert resp.status_code == 200
    data = resp.json()
    assert "room_id" in data
    assert data["room_id"] in room_manager.rooms


@pytest.mark.asyncio
async def test_index_html() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/")
        assert resp.status_code == 200
    # `/` now serves the direct vs-bot play page.
    assert "You vs Computer" in resp.text

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        lobby = await client.get("/lobby")
        assert lobby.status_code == 200
    assert "Snake Multiplayer" in lobby.text


@pytest.mark.asyncio
async def test_race_html() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/race/testroom")
    assert resp.status_code == 200
    assert "Snake Race" in resp.text
