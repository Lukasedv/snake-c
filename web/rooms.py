"""Room management for multiplayer Snake games.

This module handles game room creation, player joining/leaving, and room lifecycle.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from secrets import token_urlsafe
from typing import Dict, List, Optional, Set

from web.game_engine import GameEngine, Direction


@dataclass
class Room:
    """Represents a multiplayer game room."""
    room_id: str
    mode: str  # 'competitive', 'race', 'cooperative'
    max_players: int
    players: Dict[str, str] = field(default_factory=dict)  # player_id -> name
    spectators: Set[str] = field(default_factory=set)
    status: str = "waiting"  # 'waiting', 'playing', 'finished'
    created_at: datetime = field(default_factory=datetime.now)
    game_engine: Optional[GameEngine] = None
    game_task: Optional[asyncio.Task] = None


class RoomManager:
    """Manages multiplayer game rooms."""

    # Player colors for up to 4 players
    PLAYER_COLORS = ["#4cff91", "#ff5555", "#5555ff", "#ffaa00"]

    def __init__(self):
        """Initialize the room manager."""
        self.rooms: Dict[str, Room] = {}

    def create_room(self, mode: str = "competitive", max_players: int = 4) -> str:
        """Create a new game room.

        Args:
            mode: Game mode ('competitive', 'race', 'cooperative')
            max_players: Maximum number of players (2-4)

        Returns:
            The room ID
        """
        # Validate parameters
        if max_players < 2 or max_players > 4:
            max_players = 4

        if mode not in ["competitive", "race", "cooperative"]:
            mode = "competitive"

        # Generate unique room ID
        room_id = token_urlsafe(8)

        # Create room
        self.rooms[room_id] = Room(
            room_id=room_id,
            mode=mode,
            max_players=max_players
        )

        return room_id

    def join_room(
        self,
        room_id: str,
        player_id: str,
        player_name: str,
        spectator: bool = False
    ) -> bool:
        """Join a room as player or spectator.

        Args:
            room_id: Room to join
            player_id: Unique player identifier
            player_name: Player display name
            spectator: Whether joining as spectator

        Returns:
            True if successfully joined
        """
        room = self.rooms.get(room_id)
        if not room:
            return False

        if spectator:
            # Spectators can join anytime
            room.spectators.add(player_id)
            return True

        # Check if room is full
        if len(room.players) >= room.max_players:
            return False

        # Can only join as player if game hasn't started
        if room.status != "waiting":
            return False

        # Add player to room
        room.players[player_id] = player_name
        return True

    def leave_room(self, room_id: str, player_id: str) -> None:
        """Leave a room.

        Args:
            room_id: Room to leave
            player_id: Player identifier
        """
        room = self.rooms.get(room_id)
        if not room:
            return

        # Remove from players or spectators
        room.players.pop(player_id, None)
        room.spectators.discard(player_id)

        # If a player left during waiting, that's OK
        # If a player left during playing, mark their snake as dead
        if room.game_engine and player_id in room.game_engine.snakes:
            room.game_engine.snakes[player_id].alive = False

        # Cleanup empty rooms
        if not room.players and not room.spectators:
            # Cancel game task if running
            if room.game_task and not room.game_task.done():
                room.game_task.cancel()
            del self.rooms[room_id]

    def start_game(self, room_id: str) -> bool:
        """Start the game in a room.

        Args:
            room_id: Room to start

        Returns:
            True if game started successfully
        """
        room = self.rooms.get(room_id)
        if not room or room.status != "waiting":
            return False

        # Need at least 2 players
        if len(room.players) < 2:
            return False

        # Initialize game engine
        room.game_engine = GameEngine(mode=room.mode)

        # Add all players to game engine
        for i, (player_id, player_name) in enumerate(room.players.items()):
            color = self.PLAYER_COLORS[i % len(self.PLAYER_COLORS)]
            room.game_engine.add_snake(player_id, player_name, color)

        # Spawn initial food (3 items for multiplayer)
        for _ in range(3):
            room.game_engine._spawn_food()

        # Update room status
        room.status = "playing"

        return True

    def set_player_direction(
        self,
        room_id: str,
        player_id: str,
        direction: str
    ) -> bool:
        """Set a player's snake direction.

        Args:
            room_id: Room ID
            player_id: Player ID
            direction: Direction string ('UP', 'DOWN', 'LEFT', 'RIGHT')

        Returns:
            True if direction was set
        """
        room = self.rooms.get(room_id)
        if not room or not room.game_engine:
            return False

        # Convert string to Direction enum
        try:
            dir_enum = Direction[direction.upper()]
        except (KeyError, AttributeError):
            return False

        room.game_engine.set_direction(player_id, dir_enum)
        return True

    def get_room(self, room_id: str) -> Optional[Room]:
        """Get room by ID.

        Args:
            room_id: Room identifier

        Returns:
            Room object or None if not found
        """
        return self.rooms.get(room_id)

    def list_rooms(self, status: Optional[str] = None) -> List[Dict]:
        """List all rooms, optionally filtered by status.

        Args:
            status: Optional status filter ('waiting', 'playing', 'finished')

        Returns:
            List of room information dictionaries
        """
        rooms = self.rooms.values()

        # Filter by status if provided
        if status:
            rooms = [r for r in rooms if r.status == status]

        return [
            {
                "room_id": r.room_id,
                "mode": r.mode,
                "players": len(r.players),
                "max_players": r.max_players,
                "spectators": len(r.spectators),
                "status": r.status,
                "created_at": r.created_at.isoformat()
            }
            for r in rooms
        ]

    def get_room_info(self, room_id: str) -> Optional[Dict]:
        """Get detailed room information.

        Args:
            room_id: Room identifier

        Returns:
            Room information dictionary or None
        """
        room = self.rooms.get(room_id)
        if not room:
            return None

        return {
            "room_id": room.room_id,
            "mode": room.mode,
            "max_players": room.max_players,
            "status": room.status,
            "players": [
                {"player_id": pid, "name": name}
                for pid, name in room.players.items()
            ],
            "spectator_count": len(room.spectators),
            "created_at": room.created_at.isoformat()
        }

    def end_game(self, room_id: str) -> Optional[List[Dict]]:
        """End the game and get final results.

        Args:
            room_id: Room identifier

        Returns:
            List of player results or None if game not found
        """
        room = self.rooms.get(room_id)
        if not room or not room.game_engine:
            return None

        # Get final results
        results = room.game_engine.get_results()

        # Update room status
        room.status = "finished"

        # Cancel game task if running
        if room.game_task and not room.game_task.done():
            room.game_task.cancel()

        return results

    def cleanup_old_rooms(self, max_age_seconds: int = 3600) -> int:
        """Cleanup rooms older than max_age_seconds.

        Args:
            max_age_seconds: Maximum room age in seconds

        Returns:
            Number of rooms cleaned up
        """
        now = datetime.now()
        to_remove = []

        for room_id, room in self.rooms.items():
            age = (now - room.created_at).total_seconds()
            if age > max_age_seconds:
                # Cancel game task if running
                if room.game_task and not room.game_task.done():
                    room.game_task.cancel()
                to_remove.append(room_id)

        for room_id in to_remove:
            del self.rooms[room_id]

        return len(to_remove)


# Global room manager instance
room_manager = RoomManager()
