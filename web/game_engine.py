"""Server-side game engine for multiplayer Snake.

This module implements the core game logic for multiplayer snake games,
including snake movement, collision detection, and state management.
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Optional


class Direction(Enum):
    """Snake movement directions."""
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3


@dataclass
class Snake:
    """Represents a single snake in the game."""
    player_id: str
    name: str
    body: List[Tuple[int, int]]  # [(x, y), ...] head is at index 0
    direction: Direction
    pending_direction: Direction
    score: int = 0
    alive: bool = True
    color: str = "#4cff91"


class GameEngine:
    """Server-side game engine for multiplayer Snake.

    Manages game state, snake movement, collision detection, and food spawning
    for multiplayer snake games.
    """

    def __init__(self, board_w: int = 30, board_h: int = 18, mode: str = "competitive"):
        """Initialize the game engine.

        Args:
            board_w: Board width in cells
            board_h: Board height in cells
            mode: Game mode ('competitive', 'race', 'cooperative')
        """
        self.board_w = board_w
        self.board_h = board_h
        self.mode = mode
        self.snakes: Dict[str, Snake] = {}
        self.foods: List[Tuple[int, int]] = []
        self.tick_count = 0
        self.tick_interval = 0.130  # 130ms base speed

    def add_snake(self, player_id: str, name: str, color: str) -> None:
        """Add a new snake to the game.

        Args:
            player_id: Unique player identifier
            name: Player display name
            color: Snake color (hex string)
        """
        # Calculate starting position based on player count
        snake_count = len(self.snakes)

        # Distribute snakes evenly across the board
        if snake_count == 0:
            start_x = self.board_w // 4
            start_y = self.board_h // 2
        elif snake_count == 1:
            start_x = (self.board_w * 3) // 4
            start_y = self.board_h // 2
        elif snake_count == 2:
            start_x = self.board_w // 2
            start_y = self.board_h // 4
        else:
            start_x = self.board_w // 2
            start_y = (self.board_h * 3) // 4

        # Create initial snake body (4 segments, facing right)
        body = [(start_x - i, start_y) for i in range(4)]

        self.snakes[player_id] = Snake(
            player_id=player_id,
            name=name,
            body=body,
            direction=Direction.RIGHT,
            pending_direction=Direction.RIGHT,
            color=color
        )

    def remove_snake(self, player_id: str) -> None:
        """Remove a snake from the game.

        Args:
            player_id: Player identifier to remove
        """
        if player_id in self.snakes:
            del self.snakes[player_id]

    def set_direction(self, player_id: str, direction: Direction) -> None:
        """Set pending direction for a snake.

        Validates that the direction is not a 180° reversal.

        Args:
            player_id: Player identifier
            direction: New direction to set
        """
        snake = self.snakes.get(player_id)
        if not snake or not snake.alive:
            return

        # Prevent 180° reversals
        if self._is_opposite(snake.direction, direction):
            return

        snake.pending_direction = direction

    def _is_opposite(self, d1: Direction, d2: Direction) -> bool:
        """Check if two directions are opposite.

        Args:
            d1: First direction
            d2: Second direction

        Returns:
            True if directions are opposite (180° turn)
        """
        opposites = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT
        }
        return opposites.get(d1) == d2

    def tick(self) -> Dict:
        """Execute one game tick and return updated state.

        Moves all snakes, checks collisions, spawns food, and updates game state.

        Returns:
            Dictionary containing current game state
        """
        self.tick_count += 1

        # Process movement for all alive snakes
        for snake in self.snakes.values():
            if not snake.alive:
                continue

            # Apply pending direction
            snake.direction = snake.pending_direction
            head_x, head_y = snake.body[0]

            # Calculate new head position based on direction
            if snake.direction == Direction.UP:
                new_head = (head_x, head_y - 1)
            elif snake.direction == Direction.DOWN:
                new_head = (head_x, head_y + 1)
            elif snake.direction == Direction.LEFT:
                new_head = (head_x - 1, head_y)
            else:  # RIGHT
                new_head = (head_x + 1, head_y)

            # Wrap around walls (Nokia-style)
            new_head = (new_head[0] % self.board_w, new_head[1] % self.board_h)

            # Check if eating food
            eating = new_head in self.foods

            # Move snake (add new head)
            snake.body.insert(0, new_head)

            # Remove tail unless eating (snake grows when eating)
            if not eating:
                snake.body.pop()
            else:
                snake.score += 10
                self.foods.remove(new_head)
                self._spawn_food()

        # Check collisions AFTER all snakes have moved
        self._check_collisions()

        # Update tick interval based on game mode and snake lengths
        if self.mode == "race":
            # Faster pace for race mode
            self.tick_interval = 0.080
        else:
            # Dynamic speed based on longest snake
            max_length = max((len(s.body) for s in self.snakes.values()), default=4)
            self.tick_interval = max(0.055, 0.130 - (max_length - 4) * 0.002)

        return self.get_state()

    def _check_collisions(self) -> None:
        """Check for snake collisions (self-collision and inter-snake collision)."""
        for snake in self.snakes.values():
            if not snake.alive:
                continue

            head = snake.body[0]

            # Check self-collision (head hits own body)
            if head in snake.body[1:]:
                snake.alive = False
                continue

            # Check collision with other snakes
            for other in self.snakes.values():
                if other.player_id == snake.player_id:
                    continue

                # In race mode, collisions just bounce back instead of killing
                if self.mode == "race":
                    if head in other.body:
                        # Revert move
                        snake.body.pop(0)
                        if len(snake.body) > 4:
                            snake.body.append(snake.body[-1])
                        break
                else:
                    # In competitive mode, collision kills the snake
                    if head in other.body:
                        snake.alive = False
                        break

    def _spawn_food(self) -> None:
        """Spawn food at a random empty location."""
        max_attempts = 100
        for _ in range(max_attempts):
            x = random.randint(0, self.board_w - 1)
            y = random.randint(0, self.board_h - 1)

            # Check if position is empty
            occupied = False
            for snake in self.snakes.values():
                if (x, y) in snake.body:
                    occupied = True
                    break

            if not occupied and (x, y) not in self.foods:
                self.foods.append((x, y))
                return

    def get_state(self) -> Dict:
        """Get current game state as a dictionary.

        Returns:
            Dictionary with game state including snakes and foods
        """
        return {
            "type": "game_state",
            "tick": self.tick_count,
            "mode": self.mode,
            "snakes": [
                {
                    "player_id": s.player_id,
                    "name": s.name,
                    "body": s.body,
                    "score": s.score,
                    "alive": s.alive,
                    "color": s.color
                }
                for s in self.snakes.values()
            ],
            "foods": self.foods,
            "tick_interval": self.tick_interval
        }

    def is_game_over(self) -> bool:
        """Check if game is over.

        Game ends when 0 or 1 snake remains alive in competitive mode.

        Returns:
            True if game is over
        """
        if self.mode == "race":
            # Race mode doesn't end on death, only on time limit
            return False

        alive_count = sum(1 for s in self.snakes.values() if s.alive)
        return alive_count <= 1

    def get_winner(self) -> Optional[str]:
        """Get the winner's player_id.

        Returns:
            Player ID of winner, or None if no clear winner
        """
        alive_snakes = [s for s in self.snakes.values() if s.alive]

        # In competitive mode, last snake alive wins
        if len(alive_snakes) == 1:
            return alive_snakes[0].player_id

        # If all dead or race mode, highest score wins
        if self.snakes:
            winner = max(self.snakes.values(), key=lambda s: s.score)
            return winner.player_id

        return None

    def get_results(self) -> List[Dict]:
        """Get final game results sorted by score.

        Returns:
            List of player results sorted by score (highest first)
        """
        results = [
            {
                "player_id": s.player_id,
                "name": s.name,
                "score": s.score,
                "alive": s.alive
            }
            for s in self.snakes.values()
        ]

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)

        # Add placements
        for i, result in enumerate(results):
            result["placement"] = i + 1

        return results
