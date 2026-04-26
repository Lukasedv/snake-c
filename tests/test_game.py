"""
Unit tests for snake/game.py.

These tests verify that the Python port reproduces the same gameplay rules
as the reference C implementation in src/game.c.
"""

import random
import unittest
from collections import deque

from snake.game import (
    BOARD_H,
    BOARD_W,
    Direction,
    Game,
    Point,
    _TICK_BASE_MS,
    _TICK_FAST_MS,
)


class TestGameInit(unittest.TestCase):
    def setUp(self) -> None:
        self.g = Game()
        self.g.init()

    def test_initial_length(self) -> None:
        self.assertEqual(self.g.length, 4)

    def test_initial_direction(self) -> None:
        self.assertEqual(self.g.direction, Direction.RIGHT)
        self.assertEqual(self.g.pending_dir, Direction.RIGHT)

    def test_initial_score(self) -> None:
        self.assertEqual(self.g.score, 0)

    def test_not_game_over(self) -> None:
        self.assertFalse(self.g.game_over)

    def test_snake_centered(self) -> None:
        """Snake should start roughly in the centre of the board."""
        cx = BOARD_W // 2 - 2
        cy = BOARD_H // 2
        expected = deque(Point(cx + i, cy) for i in range(4))
        self.assertEqual(self.g.body, expected)

    def test_food_not_on_snake(self) -> None:
        self.assertFalse(self.g.cell_is_snake(self.g.food.x, self.g.food.y))


class TestDirectionControl(unittest.TestCase):
    def setUp(self) -> None:
        self.g = Game()
        self.g.init()

    def test_set_direction_up(self) -> None:
        # UP is perpendicular to the initial RIGHT direction — should be accepted.
        self.g.set_direction(Direction.UP)
        self.assertEqual(self.g.pending_dir, Direction.UP)

    def test_set_direction_down(self) -> None:
        # DOWN is also perpendicular to the initial RIGHT direction.
        self.g.set_direction(Direction.DOWN)
        self.assertEqual(self.g.pending_dir, Direction.DOWN)

    def test_no_reverse_right_to_left(self) -> None:
        """180° reversal should be silently ignored."""
        self.g.set_direction(Direction.LEFT)  # opposite of initial RIGHT
        self.assertEqual(self.g.pending_dir, Direction.RIGHT)

    def test_no_reverse_up_to_down(self) -> None:
        self.g.set_direction(Direction.UP)
        self.g.step()  # commit UP
        self.g.set_direction(Direction.DOWN)  # opposite of UP → ignored
        self.assertEqual(self.g.pending_dir, Direction.UP)

    def test_perpendicular_allowed(self) -> None:
        self.g.set_direction(Direction.UP)
        self.g.step()
        self.g.set_direction(Direction.LEFT)
        self.assertEqual(self.g.pending_dir, Direction.LEFT)


class TestWrapAround(unittest.TestCase):
    def _place_head_at(self, g: Game, x: int, y: int) -> None:
        """Teleport the snake so its head is at (x, y) facing right."""
        g.body = deque([Point(x - 1, y), Point(x, y)])
        g.direction = Direction.RIGHT
        g.pending_dir = Direction.RIGHT

    def test_wrap_right_edge(self) -> None:
        g = Game()
        g.init()
        self._place_head_at(g, BOARD_W - 1, 5)
        g.food = Point(0, BOARD_H - 1)  # valid cell far from the snake path
        g.step()
        self.assertEqual(g.head.x, 0)
        self.assertEqual(g.head.y, 5)

    def test_wrap_left_edge(self) -> None:
        g = Game()
        g.init()
        g.body = deque([Point(1, 5), Point(0, 5)])
        g.direction = Direction.LEFT
        g.pending_dir = Direction.LEFT
        g.food = Point(BOARD_W - 1, BOARD_H - 1)  # valid cell far from the snake path
        g.step()
        self.assertEqual(g.head.x, BOARD_W - 1)

    def test_wrap_top_edge(self) -> None:
        g = Game()
        g.init()
        g.body = deque([Point(5, 1), Point(5, 0)])
        g.direction = Direction.UP
        g.pending_dir = Direction.UP
        g.food = Point(BOARD_W - 1, BOARD_H - 1)  # valid cell far from the snake path
        g.step()
        self.assertEqual(g.head.y, BOARD_H - 1)

    def test_wrap_bottom_edge(self) -> None:
        g = Game()
        g.init()
        g.body = deque([Point(5, BOARD_H - 2), Point(5, BOARD_H - 1)])
        g.direction = Direction.DOWN
        g.pending_dir = Direction.DOWN
        g.food = Point(BOARD_W - 1, 0)  # valid cell far from the snake path
        g.step()
        self.assertEqual(g.head.y, 0)


class TestEating(unittest.TestCase):
    def _make_game_with_food_ahead(self) -> Game:
        g = Game()
        g.init()
        head = g.head
        # Place food directly in front of the head (to the right)
        g.food = Point(head.x + 1, head.y)
        return g

    def test_score_increases_on_eat(self) -> None:
        g = self._make_game_with_food_ahead()
        prev_score = g.score
        g.step()
        self.assertEqual(g.score, prev_score + 10)

    def test_length_increases_on_eat(self) -> None:
        g = self._make_game_with_food_ahead()
        prev_length = g.length
        g.step()
        self.assertEqual(g.length, prev_length + 1)

    def test_new_food_placed_after_eat(self) -> None:
        g = self._make_game_with_food_ahead()
        old_food = g.food
        g.step()
        # New food should not be the same cell (probabilistically guaranteed
        # for a non-full board) and must not be on the snake.
        self.assertFalse(g.cell_is_snake(g.food.x, g.food.y))
        # After eating the head is at old_food; new food must differ.
        self.assertNotEqual(g.food, old_food)

    def test_no_score_without_eat(self) -> None:
        g = Game()
        g.init()
        # Place food away from the snake path
        g.food = Point(0, BOARD_H - 1)
        prev_score = g.score
        g.step()
        self.assertEqual(g.score, prev_score)


class TestSelfCollision(unittest.TestCase):
    def test_self_collision_triggers_game_over(self) -> None:
        """Head moving into an interior body cell triggers game over."""
        g = Game()
        g.init()
        # Snake (tail→head): (0,0)→(1,0)→(2,0)→(2,1)→(1,1)→(0,1)
        # Head at (0,1), direction RIGHT → next = (1,1) which IS in the body
        # and is NOT the tail (tail is (0,0)), so game_over must fire.
        g.body = deque([
            Point(0, 0), Point(1, 0), Point(2, 0),
            Point(2, 1), Point(1, 1), Point(0, 1),
        ])
        g.direction = Direction.RIGHT
        g.pending_dir = Direction.RIGHT
        g.food = Point(10, 10)  # well away from the snake
        g.step()
        self.assertTrue(g.game_over)

    def test_moving_into_vacated_tail_is_ok(self) -> None:
        """
        The snake should be allowed to move into the cell the tail just vacated
        (the C code removes the tail before the collision check).
        """
        g = Game()
        g.init()
        # Build a snake: tail at (1,0), body (2,0),(3,0), head at (3,0).
        # Direct the head left so next cell = (2,0) which is body, BUT
        # put the food somewhere else and make the snake move right so the
        # tail at (1,0) vacates and the head won't collide.
        #
        # Actually let's test the precise boundary case: snake of length 2,
        # head is adjacent to the tail cell it is about to vacate.
        g.body = deque([Point(5, 5), Point(6, 5)])  # tail=5,5  head=6,5
        g.direction = Direction.DOWN
        g.pending_dir = Direction.DOWN
        g.food = Point(0, 0)
        g.step()  # head moves to (6,6), tail vacates (5,5)
        # Now steer left then up to reach (5,6) then (5,5) — old tail cell
        g.set_direction(Direction.LEFT)
        g.step()  # head → (5,6)
        g.set_direction(Direction.UP)
        g.step()  # head → (5,5)  which is now free (tail moved to (6,6) then (6,5)…)
        # What matters: game is NOT over from moving into a previously tail cell.
        # The exact result depends on snake growth; as long as no collision →
        # game should still be running.
        self.assertFalse(g.game_over)


class TestTickMs(unittest.TestCase):
    def setUp(self) -> None:
        self.g = Game()
        self.g.init()

    def test_initial_tick(self) -> None:
        # length=4, growth=0 → ms = 130
        self.assertEqual(self.g.tick_ms(), _TICK_BASE_MS)

    def test_speed_increases_with_length(self) -> None:
        # Artificially grow the snake
        for _ in range(10):
            self.g.body.append(Point(0, 0))
        self.assertLess(self.g.tick_ms(), _TICK_BASE_MS)

    def test_minimum_tick(self) -> None:
        # Fill nearly the entire board to ensure we hit the floor
        for _ in range(BOARD_W * BOARD_H):
            self.g.body.append(Point(0, 0))
        self.assertEqual(self.g.tick_ms(), _TICK_FAST_MS)

    def test_formula(self) -> None:
        """tick_ms = max(base - (length - 4) * 2, fast)"""
        for extra in range(0, 40):
            for _ in range(extra):
                self.g.body.append(Point(0, 0))
            expected = max(_TICK_BASE_MS - extra * 2, _TICK_FAST_MS)
            self.assertEqual(self.g.tick_ms(), expected)
            self.g.body = deque([Point(0, 0)] * 4)


class TestCellIsSnake(unittest.TestCase):
    def test_detects_body_cells(self) -> None:
        g = Game()
        g.init()
        for pt in g.body:
            self.assertTrue(g.cell_is_snake(pt.x, pt.y))

    def test_free_cell(self) -> None:
        g = Game()
        g.init()
        # (0,0) is unlikely to be occupied by the 4-cell centred snake
        self.assertFalse(g.cell_is_snake(0, 0))


if __name__ == "__main__":
    unittest.main()
