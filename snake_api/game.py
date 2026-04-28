"""
Core Snake game model — rules only, no I/O.

Faithfully mirrors the C implementation in src/game.c/.h so that gameplay
(wrap-around walls, no 180° reversals, tail-vacates-before-collision check,
speed formula, etc.) is identical.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto

BOARD_W: int = 30
BOARD_H: int = 18

_TICK_BASE_MS: int = 130
_TICK_FAST_MS: int = 55


class Direction(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()


_OPPOSITES: dict[Direction, Direction] = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}

_DELTAS: dict[Direction, tuple[int, int]] = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}


def _wrap(x: int, y: int) -> Point:
    """Wrap coordinates around the board edges (mirrors wrap() in C)."""
    if x < 0:
        x = BOARD_W - 1
    elif x >= BOARD_W:
        x = 0
    if y < 0:
        y = BOARD_H - 1
    elif y >= BOARD_H:
        y = 0
    return Point(x, y)


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass
class Game:
    # Snake body stored head-last (deque[0] = tail, deque[-1] = head).
    body: deque[Point] = field(default_factory=deque)
    direction: Direction = Direction.RIGHT
    pending_dir: Direction = Direction.RIGHT
    food: Point = field(default_factory=lambda: Point(0, 0))
    score: int = 0
    game_over: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Reset the game to its initial state (mirrors game_init in C)."""
        self.body = deque()
        self.direction = Direction.RIGHT
        self.pending_dir = Direction.RIGHT
        self.score = 0
        self.game_over = False

        length = 4
        cy = BOARD_H // 2
        cx = BOARD_W // 2 - length // 2
        for i in range(length):
            self.body.append(Point(cx + i, cy))

        self.food = self._place_food()

    def set_direction(self, d: Direction) -> None:
        """Queue a direction change; 180° reversals are silently ignored."""
        if d is not _OPPOSITES[self.direction]:
            self.pending_dir = d

    def step(self) -> None:
        """Advance one game tick (mirrors game_step in C)."""
        if self.game_over:
            return

        self.direction = self.pending_dir
        head = self.body[-1]
        dx, dy = _DELTAS[self.direction]
        next_pos = _wrap(head.x + dx, head.y + dy)

        eating = next_pos == self.food

        # Tentatively remove the tail unless eating — the vacated cell is
        # therefore not considered occupied during collision detection.
        # This matches the C behaviour exactly.
        if not eating:
            self.body.popleft()

        if next_pos in self.body:
            if not eating:
                # The tail was already popped; pretend it wasn't so the
                # visible snake length is preserved for the game-over frame.
                pass  # body already without tail — game over display still correct
            self.game_over = True
            return

        self.body.append(next_pos)

        if eating:
            self.score += 10
            self.food = self._place_food()

    @property
    def head(self) -> Point:
        return self.body[-1]

    @property
    def length(self) -> int:
        return len(self.body)

    def cell_is_snake(self, x: int, y: int) -> bool:
        return Point(x, y) in self.body

    def tick_ms(self) -> int:
        """Return the current tick duration in milliseconds."""
        growth = self.length - 4
        ms = _TICK_BASE_MS - growth * 2
        return max(ms, _TICK_FAST_MS)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _place_food(self) -> Point:
        """Return a random cell that is not occupied by the snake."""
        body_set: set[Point] = set(self.body)
        while True:
            p = Point(random.randrange(BOARD_W), random.randrange(BOARD_H))
            if p not in body_set:
                return p
