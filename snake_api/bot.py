"""
Greedy AI bot for Snake race mode.

The bot picks the direction that moves its head closest to its food
(Manhattan distance) while avoiding an immediate collision with its
own body.  It never attempts a 180° reversal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .game import BOARD_H, BOARD_W, Direction, Game, Point, _DELTAS, _OPPOSITES, _wrap


def greedy_direction(game: Game) -> Direction:
    """Return the best next direction for a bot controlling *game*."""
    head = game.head
    food = game.food

    # Compute signed deltas to food, accounting for wrap-around.
    dx = food.x - head.x
    dy = food.y - head.y
    if abs(dx) > BOARD_W // 2:
        dx = -dx
    if abs(dy) > BOARD_H // 2:
        dy = -dy

    # Build a preference list: primary axis first, then secondary.
    h_dirs = [Direction.RIGHT if dx > 0 else Direction.LEFT]
    v_dirs = [Direction.DOWN if dy > 0 else Direction.UP]

    if abs(dx) >= abs(dy):
        preferred = h_dirs + v_dirs
    else:
        preferred = v_dirs + h_dirs

    # Append the remaining two directions as last-resort fallbacks.
    all_dirs = list(Direction)
    for d in all_dirs:
        if d not in preferred:
            preferred.append(d)

    opp = _OPPOSITES[game.direction]
    for d in preferred:
        if d is opp:
            continue
        delta = _DELTAS[d]
        next_pos = _wrap(head.x + delta[0], head.y + delta[1])
        if not game.cell_is_snake(next_pos.x, next_pos.y):
            return d

    # All moves lead into the body; keep current direction (game over soon).
    return game.direction


@dataclass
class BotSession:
    """A server-side snake player with no WebSocket — controlled by the AI."""

    player_id: str
    name: str
    game: Game = field(default_factory=Game)

    def __post_init__(self) -> None:
        self.game.init()

    def tick(self) -> None:
        """Compute and apply the bot's next direction, then step the game."""
        if not self.game.game_over:
            self.game.set_direction(greedy_direction(self.game))
