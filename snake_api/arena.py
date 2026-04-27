"""
Shared-board snake arena: multiple snakes share one playfield and one food.

Snakes can collide with their own body, the other snake's body, or each
other head-on.  The first to land on the food eats it (head-on collisions
on the food cell kill both snakes, food persists).
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .game import (
    BOARD_H,
    BOARD_W,
    Direction,
    Point,
    _DELTAS,
    _OPPOSITES,
    _wrap,
)

_TICK_BASE_MS = 130
_TICK_FAST_MS = 55


@dataclass
class Snake:
    snake_id: str
    name: str
    body: deque[Point] = field(default_factory=deque)
    direction: Direction = Direction.RIGHT
    pending_dir: Direction = Direction.RIGHT
    score: int = 0
    dead: bool = False

    @property
    def head(self) -> Point:
        return self.body[-1]

    @property
    def length(self) -> int:
        return len(self.body)


@dataclass
class Arena:
    """Shared playfield holding multiple snakes and a single food cell."""

    snakes: dict[str, Snake] = field(default_factory=dict)
    food: Point = field(default_factory=lambda: Point(0, 0))
    game_over: bool = False
    winner_id: Optional[str] = None

    def add_snake(
        self,
        snake_id: str,
        name: str,
        start_x: int,
        start_y: int,
        direction: Direction = Direction.RIGHT,
        length: int = 4,
    ) -> None:
        body: deque[Point] = deque()
        for i in range(length):
            body.append(Point(start_x + i, start_y))
        self.snakes[snake_id] = Snake(
            snake_id=snake_id,
            name=name,
            body=body,
            direction=direction,
            pending_dir=direction,
        )

    def init_two_player(self, p1_id: str, p1_name: str, p2_id: str, p2_name: str) -> None:
        """Set up a fresh 1v1 arena: p1 left-mid, p2 right-mid."""
        self.snakes.clear()
        self.game_over = False
        self.winner_id = None

        cy = BOARD_H // 2
        # Player 1 on the left, heading right
        self.add_snake(p1_id, p1_name, start_x=4, start_y=cy, direction=Direction.RIGHT)
        # Player 2 on the right, heading left
        p2 = Snake(
            snake_id=p2_id,
            name=p2_name,
            body=deque(Point(BOARD_W - 5 - i, cy) for i in range(4)),
            direction=Direction.LEFT,
            pending_dir=Direction.LEFT,
        )
        self.snakes[p2_id] = p2

        self.food = self._place_food()

    def set_direction(self, snake_id: str, d: Direction) -> None:
        s = self.snakes.get(snake_id)
        if s is None or s.dead:
            return
        if d is not _OPPOSITES[s.direction]:
            s.pending_dir = d

    def occupied_cells(self) -> set[Point]:
        cells: set[Point] = set()
        for s in self.snakes.values():
            if s.dead:
                continue
            cells.update(s.body)
        return cells

    def step(self) -> None:
        if self.game_over:
            return

        alive = [s for s in self.snakes.values() if not s.dead]
        if not alive:
            self.game_over = True
            return

        for s in alive:
            s.direction = s.pending_dir

        # Compute each alive snake's next head position.
        next_heads: dict[str, Point] = {}
        for s in alive:
            dx, dy = _DELTAS[s.direction]
            next_heads[s.snake_id] = _wrap(s.head.x + dx, s.head.y + dy)

        eating = {sid: nh == self.food for sid, nh in next_heads.items()}

        # Build "future bodies" — the cells each snake will occupy AFTER the
        # tail vacates (unless eating).  This lets a snake follow its own tail.
        future_bodies: dict[str, set[Point]] = {}
        for s in alive:
            body = list(s.body)
            if not eating[s.snake_id]:
                body = body[1:]  # tail vacates this tick
            future_bodies[s.snake_id] = set(body)

        deaths: set[str] = set()

        # Head-to-head: two heads landing on the same cell — both die.
        head_cells: dict[Point, list[str]] = {}
        for sid, nh in next_heads.items():
            head_cells.setdefault(nh, []).append(sid)
        for cell, sids in head_cells.items():
            if len(sids) > 1:
                deaths.update(sids)

        # Head crashing into any snake's future body (own or other's).
        for sid, nh in next_heads.items():
            for other_sid, body in future_bodies.items():
                if nh in body:
                    deaths.add(sid)
                    break

        for sid in deaths:
            self.snakes[sid].dead = True

        # Apply moves for survivors.
        any_ate = False
        for s in alive:
            if s.snake_id in deaths:
                continue
            if not eating[s.snake_id]:
                s.body.popleft()
            s.body.append(next_heads[s.snake_id])
            if eating[s.snake_id]:
                s.score += 10
                any_ate = True

        if any_ate:
            self.food = self._place_food()

        # End conditions
        still_alive = [s for s in self.snakes.values() if not s.dead]
        if not still_alive:
            self.game_over = True
            self.winner_id = self._highest_score_id()
        elif len(still_alive) == 1 and len(self.snakes) > 1:
            self.game_over = True
            self.winner_id = still_alive[0].snake_id

    def _highest_score_id(self) -> Optional[str]:
        if not self.snakes:
            return None
        best = max(self.snakes.values(), key=lambda s: s.score)
        # Tie → no winner declared
        top = [s for s in self.snakes.values() if s.score == best.score]
        if len(top) > 1:
            return None
        return best.snake_id

    def tick_ms(self) -> int:
        alive = [s for s in self.snakes.values() if not s.dead]
        longest = max((s.length for s in alive), default=4)
        ms = _TICK_BASE_MS - (longest - 4) * 2
        return max(ms, _TICK_FAST_MS)

    def _place_food(self) -> Point:
        occupied = self.occupied_cells()
        # In the unlikely case the board is nearly full, fall back to scan.
        if len(occupied) >= BOARD_W * BOARD_H - 1:
            for y in range(BOARD_H):
                for x in range(BOARD_W):
                    if Point(x, y) not in occupied:
                        return Point(x, y)
        while True:
            p = Point(random.randrange(BOARD_W), random.randrange(BOARD_H))
            if p not in occupied:
                return p


def greedy_arena_direction(arena: Arena, snake_id: str) -> Direction:
    """Greedy bot move: head toward food, avoid all snake bodies."""
    s = arena.snakes.get(snake_id)
    if s is None or s.dead:
        return Direction.RIGHT

    head = s.head
    food = arena.food

    dx = food.x - head.x
    dy = food.y - head.y
    if abs(dx) > BOARD_W // 2:
        dx = -dx
    if abs(dy) > BOARD_H // 2:
        dy = -dy

    h_dir = Direction.RIGHT if dx > 0 else Direction.LEFT
    v_dir = Direction.DOWN if dy > 0 else Direction.UP

    if abs(dx) >= abs(dy):
        preferred = [h_dir, v_dir]
    else:
        preferred = [v_dir, h_dir]
    for d in Direction:
        if d not in preferred:
            preferred.append(d)

    blocked = arena.occupied_cells()
    opp = _OPPOSITES[s.direction]

    for d in preferred:
        if d is opp:
            continue
        delta = _DELTAS[d]
        nxt = _wrap(head.x + delta[0], head.y + delta[1])
        if nxt not in blocked:
            return d

    return s.direction
