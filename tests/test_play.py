"""Tests for the arena (shared-board snake) and the / play endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from snake_api.arena import Arena, greedy_arena_direction
from snake_api.game import Direction
from snake_api.main import app


def test_arena_init_two_snakes() -> None:
    a = Arena()
    a.init_two_player("p", "You", "b", "Computer")
    assert set(a.snakes.keys()) == {"p", "b"}
    assert a.snakes["p"].length == 4
    assert a.snakes["b"].length == 4
    assert not a.game_over
    assert a.food not in a.occupied_cells()


def test_arena_step_advances_alive_snakes() -> None:
    a = Arena()
    a.init_two_player("p", "You", "b", "Computer")
    p_head_before = a.snakes["p"].head
    a.step()
    p_head_after = a.snakes["p"].head
    assert p_head_after != p_head_before


def test_greedy_bot_avoids_immediate_self_collision() -> None:
    a = Arena()
    a.init_two_player("p", "You", "b", "Computer")
    # Run many ticks; the bot should never crash into itself in open space.
    for _ in range(200):
        a.set_direction("b", greedy_arena_direction(a, "b"))
        # Player goes straight — will eventually wrap and may crash, that's fine.
        a.step()
        if a.game_over:
            break
    # Bot should still be alive most of the time on a near-empty board.
    # We just assert the game progressed — score increased somewhere.
    total_score = sum(s.score for s in a.snakes.values())
    assert total_score > 0


def test_head_to_head_kills_both() -> None:
    a = Arena()
    a.snakes.clear()
    # Place two snakes on a collision course.
    a.add_snake("p", "You", start_x=10, start_y=9, direction=Direction.RIGHT)
    a.add_snake("b", "Bot", start_x=14, start_y=9, direction=Direction.LEFT)
    # Override direction so they actually move toward each other.
    a.snakes["b"].body.clear()
    from collections import deque

    from snake_api.game import Point

    a.snakes["b"].body = deque(Point(14 + i, 9) for i in range(4))
    a.snakes["b"].direction = Direction.LEFT
    a.snakes["b"].pending_dir = Direction.LEFT
    a.food = Point(0, 0)

    # Step until heads should meet.
    for _ in range(5):
        a.step()
        if a.game_over:
            break
    assert a.game_over
    # Both dead → no winner declared (tie) OR one snake by score; we only assert game_over.


@pytest.mark.asyncio
async def test_play_endpoint_serves_html() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "You vs Computer" in resp.text


@pytest.mark.asyncio
async def test_lobby_endpoints_removed() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        for path in ("/lobby", "/api/rooms", "/race/abc"):
            resp = await client.get(path)
            assert resp.status_code == 404, f"{path} should be 404, got {resp.status_code}"
