"""Tests for the room manager.

Run with: pytest web/tests/test_rooms.py -v
"""

import pytest
from web.rooms import RoomManager, Room
from web.game_engine import Direction


class TestRoomManager:
    """Tests for the RoomManager class."""

    def setup_method(self):
        """Setup for each test - create fresh room manager."""
        self.manager = RoomManager()

    def test_create_room(self):
        """Test creating a new room."""
        room_id = self.manager.create_room()

        assert room_id is not None
        assert len(room_id) > 0
        assert room_id in self.manager.rooms

        room = self.manager.rooms[room_id]
        assert room.mode == "competitive"
        assert room.max_players == 4
        assert room.status == "waiting"
        assert len(room.players) == 0

    def test_create_room_with_params(self):
        """Test creating room with custom parameters."""
        room_id = self.manager.create_room(mode="race", max_players=2)

        room = self.manager.rooms[room_id]
        assert room.mode == "race"
        assert room.max_players == 2

    def test_create_room_validates_max_players(self):
        """Test that max_players is validated."""
        # Too high
        room_id = self.manager.create_room(max_players=10)
        assert self.manager.rooms[room_id].max_players == 4

        # Too low
        room_id2 = self.manager.create_room(max_players=1)
        assert self.manager.rooms[room_id2].max_players == 4

    def test_create_room_validates_mode(self):
        """Test that mode is validated."""
        room_id = self.manager.create_room(mode="invalid")
        assert self.manager.rooms[room_id].mode == "competitive"

    def test_join_room_as_player(self):
        """Test joining a room as a player."""
        room_id = self.manager.create_room()

        success = self.manager.join_room(room_id, "p1", "Alice")

        assert success is True
        assert "p1" in self.manager.rooms[room_id].players
        assert self.manager.rooms[room_id].players["p1"] == "Alice"

    def test_join_room_as_spectator(self):
        """Test joining a room as a spectator."""
        room_id = self.manager.create_room()

        success = self.manager.join_room(room_id, "s1", "Spectator", spectator=True)

        assert success is True
        assert "s1" in self.manager.rooms[room_id].spectators
        assert "s1" not in self.manager.rooms[room_id].players

    def test_join_nonexistent_room(self):
        """Test joining a room that doesn't exist."""
        success = self.manager.join_room("invalid", "p1", "Alice")
        assert success is False

    def test_join_full_room(self):
        """Test that joining a full room fails."""
        room_id = self.manager.create_room(max_players=2)

        # Fill room
        self.manager.join_room(room_id, "p1", "Alice")
        self.manager.join_room(room_id, "p2", "Bob")

        # Try to join full room
        success = self.manager.join_room(room_id, "p3", "Charlie")

        assert success is False
        assert "p3" not in self.manager.rooms[room_id].players

    def test_spectators_can_join_full_room(self):
        """Test that spectators can join even if room is full."""
        room_id = self.manager.create_room(max_players=2)

        # Fill room
        self.manager.join_room(room_id, "p1", "Alice")
        self.manager.join_room(room_id, "p2", "Bob")

        # Spectator should still be able to join
        success = self.manager.join_room(room_id, "s1", "Spectator", spectator=True)

        assert success is True

    def test_cannot_join_started_game(self):
        """Test that players cannot join after game starts."""
        room_id = self.manager.create_room()
        self.manager.join_room(room_id, "p1", "Alice")
        self.manager.join_room(room_id, "p2", "Bob")

        # Start game
        self.manager.start_game(room_id)

        # Try to join after start
        success = self.manager.join_room(room_id, "p3", "Charlie")

        assert success is False

    def test_spectators_can_join_started_game(self):
        """Test that spectators can join after game starts."""
        room_id = self.manager.create_room()
        self.manager.join_room(room_id, "p1", "Alice")
        self.manager.join_room(room_id, "p2", "Bob")

        # Start game
        self.manager.start_game(room_id)

        # Spectator should be able to join
        success = self.manager.join_room(room_id, "s1", "Spectator", spectator=True)

        assert success is True

    def test_leave_room(self):
        """Test leaving a room."""
        room_id = self.manager.create_room()
        self.manager.join_room(room_id, "p1", "Alice")
        self.manager.join_room(room_id, "p2", "Bob")  # Add second player so room isn't deleted

        assert "p1" in self.manager.rooms[room_id].players

        self.manager.leave_room(room_id, "p1")

        # Room should still exist (p2 still in it)
        assert room_id in self.manager.rooms
        assert "p1" not in self.manager.rooms[room_id].players
        assert "p2" in self.manager.rooms[room_id].players

    def test_leave_room_cleanup(self):
        """Test that empty rooms are cleaned up."""
        room_id = self.manager.create_room()
        self.manager.join_room(room_id, "p1", "Alice")

        assert room_id in self.manager.rooms

        # Leave room
        self.manager.leave_room(room_id, "p1")

        # Room should be deleted
        assert room_id not in self.manager.rooms

    def test_start_game(self):
        """Test starting a game."""
        room_id = self.manager.create_room()
        self.manager.join_room(room_id, "p1", "Alice")
        self.manager.join_room(room_id, "p2", "Bob")

        success = self.manager.start_game(room_id)

        assert success is True

        room = self.manager.rooms[room_id]
        assert room.status == "playing"
        assert room.game_engine is not None
        assert len(room.game_engine.snakes) == 2

    def test_start_game_requires_two_players(self):
        """Test that game requires at least 2 players."""
        room_id = self.manager.create_room()
        self.manager.join_room(room_id, "p1", "Alice")

        success = self.manager.start_game(room_id)

        assert success is False
        assert self.manager.rooms[room_id].status == "waiting"

    def test_start_game_spawns_food(self):
        """Test that starting game spawns food."""
        room_id = self.manager.create_room()
        self.manager.join_room(room_id, "p1", "Alice")
        self.manager.join_room(room_id, "p2", "Bob")

        self.manager.start_game(room_id)

        room = self.manager.rooms[room_id]
        assert len(room.game_engine.foods) == 3  # Should spawn 3 initial food

    def test_start_nonexistent_game(self):
        """Test starting a nonexistent game."""
        success = self.manager.start_game("invalid")
        assert success is False

    def test_set_player_direction(self):
        """Test setting player direction."""
        room_id = self.manager.create_room()
        self.manager.join_room(room_id, "p1", "Alice")
        self.manager.join_room(room_id, "p2", "Bob")
        self.manager.start_game(room_id)

        success = self.manager.set_player_direction(room_id, "p1", "UP")

        assert success is True

        room = self.manager.rooms[room_id]
        assert room.game_engine.snakes["p1"].pending_direction == Direction.UP

    def test_set_player_direction_invalid(self):
        """Test setting invalid direction."""
        room_id = self.manager.create_room()
        self.manager.join_room(room_id, "p1", "Alice")
        self.manager.join_room(room_id, "p2", "Bob")
        self.manager.start_game(room_id)

        success = self.manager.set_player_direction(room_id, "p1", "INVALID")

        assert success is False

    def test_get_room(self):
        """Test getting a room."""
        room_id = self.manager.create_room()

        room = self.manager.get_room(room_id)

        assert room is not None
        assert room.room_id == room_id

    def test_get_nonexistent_room(self):
        """Test getting a nonexistent room."""
        room = self.manager.get_room("invalid")
        assert room is None

    def test_list_rooms(self):
        """Test listing all rooms."""
        room_id1 = self.manager.create_room()
        room_id2 = self.manager.create_room(mode="race")

        rooms = self.manager.list_rooms()

        assert len(rooms) == 2
        assert any(r["room_id"] == room_id1 for r in rooms)
        assert any(r["room_id"] == room_id2 for r in rooms)

    def test_list_rooms_filtered(self):
        """Test listing rooms filtered by status."""
        room_id1 = self.manager.create_room()
        room_id2 = self.manager.create_room()

        self.manager.join_room(room_id2, "p1", "Alice")
        self.manager.join_room(room_id2, "p2", "Bob")
        self.manager.start_game(room_id2)

        # Filter for waiting rooms
        waiting_rooms = self.manager.list_rooms(status="waiting")
        assert len(waiting_rooms) == 1
        assert waiting_rooms[0]["room_id"] == room_id1

        # Filter for playing rooms
        playing_rooms = self.manager.list_rooms(status="playing")
        assert len(playing_rooms) == 1
        assert playing_rooms[0]["room_id"] == room_id2

    def test_get_room_info(self):
        """Test getting detailed room info."""
        room_id = self.manager.create_room(mode="race", max_players=3)
        self.manager.join_room(room_id, "p1", "Alice")
        self.manager.join_room(room_id, "s1", "Spectator", spectator=True)

        info = self.manager.get_room_info(room_id)

        assert info is not None
        assert info["room_id"] == room_id
        assert info["mode"] == "race"
        assert info["max_players"] == 3
        assert info["status"] == "waiting"
        assert len(info["players"]) == 1
        assert info["players"][0]["player_id"] == "p1"
        assert info["players"][0]["name"] == "Alice"
        assert info["spectator_count"] == 1

    def test_end_game(self):
        """Test ending a game."""
        room_id = self.manager.create_room()
        self.manager.join_room(room_id, "p1", "Alice")
        self.manager.join_room(room_id, "p2", "Bob")
        self.manager.start_game(room_id)

        # Set some scores
        room = self.manager.rooms[room_id]
        room.game_engine.snakes["p1"].score = 100
        room.game_engine.snakes["p2"].score = 50

        results = self.manager.end_game(room_id)

        assert results is not None
        assert len(results) == 2
        assert results[0]["player_id"] == "p1"  # Higher score first
        assert results[0]["score"] == 100
        assert results[0]["placement"] == 1

        assert room.status == "finished"

    def test_player_colors_assigned(self):
        """Test that players get different colors."""
        room_id = self.manager.create_room()
        self.manager.join_room(room_id, "p1", "Alice")
        self.manager.join_room(room_id, "p2", "Bob")
        self.manager.join_room(room_id, "p3", "Charlie")
        self.manager.join_room(room_id, "p4", "David")
        self.manager.start_game(room_id)

        room = self.manager.rooms[room_id]
        colors = [s.color for s in room.game_engine.snakes.values()]

        # Should have 4 different colors
        assert len(set(colors)) == 4

    def test_cleanup_old_rooms(self):
        """Test cleanup of old rooms."""
        from datetime import datetime, timedelta

        room_id = self.manager.create_room()

        # Make room old
        self.manager.rooms[room_id].created_at = datetime.now() - timedelta(hours=2)

        # Cleanup rooms older than 1 hour
        cleaned = self.manager.cleanup_old_rooms(max_age_seconds=3600)

        assert cleaned == 1
        assert room_id not in self.manager.rooms

    def test_cleanup_keeps_recent_rooms(self):
        """Test that cleanup keeps recent rooms."""
        room_id = self.manager.create_room()

        # Cleanup rooms older than 1 hour (this one is new)
        cleaned = self.manager.cleanup_old_rooms(max_age_seconds=3600)

        assert cleaned == 0
        assert room_id in self.manager.rooms
