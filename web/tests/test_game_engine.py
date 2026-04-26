"""Tests for the multiplayer Snake game engine.

Run with: pytest web/tests/test_game_engine.py -v
"""

import pytest
from web.game_engine import GameEngine, Direction, Snake


class TestGameEngine:
    """Tests for the GameEngine class."""

    def test_init(self):
        """Test game engine initialization."""
        engine = GameEngine()
        assert engine.board_w == 30
        assert engine.board_h == 18
        assert engine.mode == "competitive"
        assert len(engine.snakes) == 0
        assert len(engine.foods) == 0
        assert engine.tick_count == 0

    def test_add_snake(self):
        """Test adding snakes to the game."""
        engine = GameEngine()

        engine.add_snake("p1", "Alice", "#4cff91")
        assert len(engine.snakes) == 1
        assert "p1" in engine.snakes

        snake = engine.snakes["p1"]
        assert snake.player_id == "p1"
        assert snake.name == "Alice"
        assert snake.color == "#4cff91"
        assert len(snake.body) == 4
        assert snake.alive is True
        assert snake.score == 0

    def test_add_multiple_snakes(self):
        """Test adding multiple snakes with different starting positions."""
        engine = GameEngine()

        engine.add_snake("p1", "Alice", "#4cff91")
        engine.add_snake("p2", "Bob", "#ff5555")

        assert len(engine.snakes) == 2

        # Snakes should have different starting positions
        p1_start = engine.snakes["p1"].body[0]
        p2_start = engine.snakes["p2"].body[0]
        assert p1_start != p2_start

    def test_set_direction(self):
        """Test setting snake direction."""
        engine = GameEngine()
        engine.add_snake("p1", "Alice", "#4cff91")

        # Should accept valid direction
        engine.set_direction("p1", Direction.UP)
        assert engine.snakes["p1"].pending_direction == Direction.UP

    def test_no_180_reversal(self):
        """Test that 180° reversals are prevented."""
        engine = GameEngine()
        engine.add_snake("p1", "Alice", "#4cff91")

        # Snake starts facing RIGHT
        assert engine.snakes["p1"].direction == Direction.RIGHT

        # Try to go LEFT (180° reversal)
        engine.set_direction("p1", Direction.LEFT)

        # Should still be facing RIGHT
        assert engine.snakes["p1"].pending_direction == Direction.RIGHT

    def test_snake_movement(self):
        """Test basic snake movement."""
        engine = GameEngine()
        engine.add_snake("p1", "Alice", "#4cff91")

        initial_head = engine.snakes["p1"].body[0]

        # Tick the game
        engine.tick()

        new_head = engine.snakes["p1"].body[0]

        # Head should have moved right (default direction)
        assert new_head[0] == (initial_head[0] + 1) % engine.board_w
        assert new_head[1] == initial_head[1]

    def test_food_eating(self):
        """Test snake eating food and growing."""
        engine = GameEngine()
        engine.add_snake("p1", "Alice", "#4cff91")

        initial_length = len(engine.snakes["p1"].body)
        initial_score = engine.snakes["p1"].score

        # Place food directly in front of snake
        head = engine.snakes["p1"].body[0]
        food_pos = ((head[0] + 1) % engine.board_w, head[1])
        engine.foods = [food_pos]

        # Tick - snake should eat food
        engine.tick()

        # Snake should grow and score should increase
        assert len(engine.snakes["p1"].body) == initial_length + 1
        assert engine.snakes["p1"].score == initial_score + 10
        assert food_pos not in engine.foods  # Food should be eaten

    def test_wall_wrapping(self):
        """Test that snakes wrap around walls."""
        engine = GameEngine()
        engine.add_snake("p1", "Alice", "#4cff91")

        # Move snake to right edge
        engine.snakes["p1"].body = [(engine.board_w - 1, 5) for _ in range(4)]
        engine.snakes["p1"].direction = Direction.RIGHT
        engine.snakes["p1"].pending_direction = Direction.RIGHT

        # Tick - should wrap to left side
        engine.tick()

        new_head = engine.snakes["p1"].body[0]
        assert new_head[0] == 0  # Wrapped to left edge
        assert new_head[1] == 5

    def test_self_collision(self):
        """Test snake dying from self-collision."""
        engine = GameEngine()
        engine.add_snake("p1", "Alice", "#4cff91")

        # Create a scenario where snake will hit itself
        # Snake body forming a U shape
        engine.snakes["p1"].body = [
            (10, 10),  # head
            (10, 11),
            (10, 12),
            (11, 12),
            (12, 12),
            (12, 11),
            (12, 10),
            (11, 10)  # tail curves back
        ]
        engine.snakes["p1"].direction = Direction.DOWN
        engine.snakes["p1"].pending_direction = Direction.DOWN

        assert engine.snakes["p1"].alive is True

        # Tick - head will move to (10, 11) which is part of body
        engine.tick()

        # Snake should be dead
        assert engine.snakes["p1"].alive is False

    def test_inter_snake_collision_competitive(self):
        """Test snake collision with another snake in competitive mode."""
        engine = GameEngine(mode="competitive")
        engine.add_snake("p1", "Alice", "#4cff91")
        engine.add_snake("p2", "Bob", "#ff5555")

        # Position snakes so p1 will hit p2's stationary body
        # p1 moving right toward p2
        engine.snakes["p1"].body = [(5, 10), (4, 10), (3, 10), (2, 10)]
        engine.snakes["p1"].direction = Direction.RIGHT
        engine.snakes["p1"].pending_direction = Direction.RIGHT

        # p2 stationary obstacle ahead of p1
        engine.snakes["p2"].body = [(8, 10), (8, 11), (8, 12), (8, 13)]
        engine.snakes["p2"].direction = Direction.LEFT
        engine.snakes["p2"].pending_direction = Direction.LEFT

        # Tick 3 times to get p1 close
        engine.tick()  # p1 at (6, 10)
        engine.tick()  # p1 at (7, 10)
        engine.tick()  # p1 at (8, 10) - collision with p2's head

        # At least p1 should be dead from collision
        assert engine.snakes["p1"].alive is False

    def test_race_mode_collision(self):
        """Test that race mode bounces on collision instead of killing."""
        engine = GameEngine(mode="race")
        engine.add_snake("p1", "Alice", "#4cff91")
        engine.add_snake("p2", "Bob", "#ff5555")

        # Position snakes to collide
        engine.snakes["p1"].body = [(10, 10), (9, 10), (8, 10), (7, 10)]
        engine.snakes["p1"].direction = Direction.UP
        engine.snakes["p1"].pending_direction = Direction.UP

        engine.snakes["p2"].body = [(10, 9), (10, 8), (10, 7), (10, 6)]

        # Tick - p1 will collide but should stay alive in race mode
        engine.tick()

        # Both should still be alive
        assert engine.snakes["p1"].alive is True
        assert engine.snakes["p2"].alive is True

    def test_is_game_over_competitive(self):
        """Test game over detection in competitive mode."""
        engine = GameEngine(mode="competitive")
        engine.add_snake("p1", "Alice", "#4cff91")
        engine.add_snake("p2", "Bob", "#ff5555")

        # Both alive - game not over
        assert engine.is_game_over() is False

        # One dies - game over
        engine.snakes["p1"].alive = False
        assert engine.is_game_over() is True

    def test_is_game_over_race_mode(self):
        """Test that race mode doesn't end on death."""
        engine = GameEngine(mode="race")
        engine.add_snake("p1", "Alice", "#4cff91")
        engine.add_snake("p2", "Bob", "#ff5555")

        # Even if one dies, race mode continues
        engine.snakes["p1"].alive = False
        assert engine.is_game_over() is False

    def test_get_winner(self):
        """Test winner determination."""
        engine = GameEngine(mode="competitive")
        engine.add_snake("p1", "Alice", "#4cff91")
        engine.add_snake("p2", "Bob", "#ff5555")

        engine.snakes["p1"].score = 100
        engine.snakes["p2"].score = 50
        engine.snakes["p1"].alive = False

        # p2 should win (last alive)
        assert engine.get_winner() == "p2"

    def test_get_winner_by_score(self):
        """Test winner by score when all dead."""
        engine = GameEngine(mode="competitive")
        engine.add_snake("p1", "Alice", "#4cff91")
        engine.add_snake("p2", "Bob", "#ff5555")

        engine.snakes["p1"].score = 100
        engine.snakes["p2"].score = 150
        engine.snakes["p1"].alive = False
        engine.snakes["p2"].alive = False

        # p2 should win (higher score)
        assert engine.get_winner() == "p2"

    def test_get_results(self):
        """Test getting final game results."""
        engine = GameEngine()
        engine.add_snake("p1", "Alice", "#4cff91")
        engine.add_snake("p2", "Bob", "#ff5555")

        engine.snakes["p1"].score = 100
        engine.snakes["p2"].score = 150

        results = engine.get_results()

        assert len(results) == 2
        # Should be sorted by score
        assert results[0]["player_id"] == "p2"
        assert results[0]["score"] == 150
        assert results[0]["placement"] == 1

        assert results[1]["player_id"] == "p1"
        assert results[1]["score"] == 100
        assert results[1]["placement"] == 2

    def test_get_state(self):
        """Test getting game state."""
        engine = GameEngine()
        engine.add_snake("p1", "Alice", "#4cff91")
        engine.foods = [(15, 10)]

        state = engine.get_state()

        assert state["type"] == "game_state"
        assert state["tick"] == 0
        assert state["mode"] == "competitive"
        assert len(state["snakes"]) == 1
        assert len(state["foods"]) == 1

        snake_data = state["snakes"][0]
        assert snake_data["player_id"] == "p1"
        assert snake_data["name"] == "Alice"
        assert snake_data["alive"] is True
        assert snake_data["score"] == 0

    def test_tick_interval_speeds_up(self):
        """Test that game speeds up as snake grows."""
        engine = GameEngine()
        engine.add_snake("p1", "Alice", "#4cff91")

        initial_interval = engine.tick_interval

        # Make snake longer
        engine.snakes["p1"].body = [(i, 10) for i in range(20)]

        engine.tick()

        # Should be faster
        assert engine.tick_interval < initial_interval

    def test_tick_interval_minimum(self):
        """Test that tick interval has a minimum floor."""
        engine = GameEngine()
        engine.add_snake("p1", "Alice", "#4cff91")

        # Make snake very long
        engine.snakes["p1"].body = [(i, 10) for i in range(200)]

        engine.tick()

        # Should not go below 55ms
        assert engine.tick_interval >= 0.055

    def test_spawn_food_not_on_snake(self):
        """Test that food never spawns on snake body."""
        engine = GameEngine()
        engine.add_snake("p1", "Alice", "#4cff91")

        # Spawn many food items
        for _ in range(10):
            engine._spawn_food()

        # Check none overlap with snake
        snake_positions = set(engine.snakes["p1"].body)
        for food in engine.foods:
            assert food not in snake_positions

    def test_remove_snake(self):
        """Test removing a snake from the game."""
        engine = GameEngine()
        engine.add_snake("p1", "Alice", "#4cff91")
        engine.add_snake("p2", "Bob", "#ff5555")

        assert len(engine.snakes) == 2

        engine.remove_snake("p1")

        assert len(engine.snakes) == 1
        assert "p1" not in engine.snakes
        assert "p2" in engine.snakes
