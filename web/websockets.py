"""WebSocket connection manager for multiplayer Snake.

This module handles WebSocket connections, message routing, and game loop coordination.
"""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

from web.rooms import room_manager

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and message routing."""

    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}  # player_id -> websocket
        self.player_rooms: Dict[str, str] = {}  # player_id -> room_id
        self.player_names: Dict[str, str] = {}  # player_id -> name

    async def connect(self, websocket: WebSocket, player_id: str) -> None:
        """Accept a WebSocket connection.

        Args:
            websocket: WebSocket connection
            player_id: Unique player identifier
        """
        await websocket.accept()
        self.active_connections[player_id] = websocket
        logger.info(f"Player {player_id} connected")

    async def disconnect(self, player_id: str) -> None:
        """Handle player disconnection.

        Args:
            player_id: Player identifier
        """
        # Remove from active room if any
        room_id = self.player_rooms.get(player_id)
        if room_id:
            room_manager.leave_room(room_id, player_id)

            # Notify other players in room
            room = room_manager.get_room(room_id)
            if room:
                await self.broadcast_to_room(
                    room_id,
                    {
                        "type": "player_left",
                        "player_id": player_id,
                        "name": self.player_names.get(player_id, "Unknown")
                    },
                    exclude=player_id
                )

        # Cleanup
        self.active_connections.pop(player_id, None)
        self.player_rooms.pop(player_id, None)
        self.player_names.pop(player_id, None)

        logger.info(f"Player {player_id} disconnected")

    async def send_personal(self, player_id: str, message: Dict) -> None:
        """Send a message to a specific player.

        Args:
            player_id: Player to send to
            message: Message dictionary
        """
        websocket = self.active_connections.get(player_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to {player_id}: {e}")

    async def broadcast_to_room(
        self,
        room_id: str,
        message: Dict,
        exclude: str = None
    ) -> None:
        """Broadcast a message to all players in a room.

        Args:
            room_id: Room identifier
            message: Message dictionary
            exclude: Optional player_id to exclude from broadcast
        """
        room = room_manager.get_room(room_id)
        if not room:
            return

        # Get all recipients (players + spectators)
        recipients = set(room.players.keys()) | room.spectators

        # Send to all except excluded
        for player_id in recipients:
            if player_id != exclude:
                await self.send_personal(player_id, message)

    async def handle_message(self, player_id: str, data: Dict) -> None:
        """Handle incoming WebSocket message.

        Args:
            player_id: Player who sent the message
            data: Message data dictionary
        """
        message_type = data.get("type")

        if message_type == "set_name":
            await self._handle_set_name(player_id, data)

        elif message_type == "create_room":
            await self._handle_create_room(player_id, data)

        elif message_type == "join_room":
            await self._handle_join_room(player_id, data)

        elif message_type == "leave_room":
            await self._handle_leave_room(player_id, data)

        elif message_type == "list_rooms":
            await self._handle_list_rooms(player_id, data)

        elif message_type == "start_game":
            await self._handle_start_game(player_id, data)

        elif message_type == "input":
            await self._handle_input(player_id, data)

        else:
            logger.warning(f"Unknown message type: {message_type}")
            await self.send_personal(
                player_id,
                {"type": "error", "message": f"Unknown message type: {message_type}"}
            )

    async def _handle_set_name(self, player_id: str, data: Dict) -> None:
        """Handle player name setting."""
        name = data.get("name", "Anonymous")
        # Sanitize name
        name = name[:30].strip()
        if not name:
            name = "Anonymous"

        self.player_names[player_id] = name

        await self.send_personal(
            player_id,
            {"type": "name_set", "name": name}
        )

    async def _handle_create_room(self, player_id: str, data: Dict) -> None:
        """Handle room creation."""
        mode = data.get("mode", "competitive")
        max_players = data.get("max_players", 4)

        room_id = room_manager.create_room(mode, max_players)

        # Auto-join creator
        player_name = self.player_names.get(player_id, "Anonymous")
        success = room_manager.join_room(room_id, player_id, player_name)

        if success:
            self.player_rooms[player_id] = room_id

            await self.send_personal(
                player_id,
                {
                    "type": "room_created",
                    "room_id": room_id,
                    "room_info": room_manager.get_room_info(room_id)
                }
            )
        else:
            await self.send_personal(
                player_id,
                {"type": "error", "message": "Failed to create room"}
            )

    async def _handle_join_room(self, player_id: str, data: Dict) -> None:
        """Handle player joining a room."""
        room_id = data.get("room_id")
        spectator = data.get("spectator", False)

        if not room_id:
            await self.send_personal(
                player_id,
                {"type": "error", "message": "Missing room_id"}
            )
            return

        player_name = self.player_names.get(player_id, "Anonymous")
        success = room_manager.join_room(room_id, player_id, player_name, spectator)

        if success:
            self.player_rooms[player_id] = room_id

            # Notify player
            await self.send_personal(
                player_id,
                {
                    "type": "room_joined",
                    "room_id": room_id,
                    "spectator": spectator,
                    "room_info": room_manager.get_room_info(room_id)
                }
            )

            # Notify others in room
            if not spectator:
                await self.broadcast_to_room(
                    room_id,
                    {
                        "type": "player_joined",
                        "player_id": player_id,
                        "name": player_name,
                        "room_info": room_manager.get_room_info(room_id)
                    },
                    exclude=player_id
                )
        else:
            await self.send_personal(
                player_id,
                {"type": "error", "message": "Failed to join room (full or in progress)"}
            )

    async def _handle_leave_room(self, player_id: str, data: Dict) -> None:
        """Handle player leaving a room."""
        room_id = self.player_rooms.get(player_id)
        if not room_id:
            return

        room_manager.leave_room(room_id, player_id)
        del self.player_rooms[player_id]

        await self.send_personal(
            player_id,
            {"type": "room_left", "room_id": room_id}
        )

        # Notify others
        await self.broadcast_to_room(
            room_id,
            {
                "type": "player_left",
                "player_id": player_id,
                "name": self.player_names.get(player_id, "Unknown")
            }
        )

    async def _handle_list_rooms(self, player_id: str, data: Dict) -> None:
        """Handle room list request."""
        status = data.get("status")
        rooms = room_manager.list_rooms(status)

        await self.send_personal(
            player_id,
            {"type": "room_list", "rooms": rooms}
        )

    async def _handle_start_game(self, player_id: str, data: Dict) -> None:
        """Handle game start request."""
        room_id = self.player_rooms.get(player_id)
        if not room_id:
            await self.send_personal(
                player_id,
                {"type": "error", "message": "Not in a room"}
            )
            return

        room = room_manager.get_room(room_id)
        if not room:
            return

        # Check if player is in the room (not spectator)
        if player_id not in room.players:
            await self.send_personal(
                player_id,
                {"type": "error", "message": "Spectators cannot start game"}
            )
            return

        success = room_manager.start_game(room_id)

        if success:
            # Notify all players
            await self.broadcast_to_room(
                room_id,
                {"type": "game_started", "room_id": room_id}
            )

            # Start game loop
            asyncio.create_task(self._game_loop(room_id))
        else:
            await self.send_personal(
                player_id,
                {"type": "error", "message": "Failed to start game (need at least 2 players)"}
            )

    async def _handle_input(self, player_id: str, data: Dict) -> None:
        """Handle player input (direction change)."""
        room_id = self.player_rooms.get(player_id)
        if not room_id:
            return

        direction = data.get("direction")
        if direction:
            room_manager.set_player_direction(room_id, player_id, direction)

    async def _game_loop(self, room_id: str) -> None:
        """Run the game loop for a room.

        Args:
            room_id: Room identifier
        """
        logger.info(f"Starting game loop for room {room_id}")

        room = room_manager.get_room(room_id)
        if not room or not room.game_engine:
            return

        try:
            while room.status == "playing":
                # Tick game engine
                state = room.game_engine.tick()

                # Broadcast state to all players
                await self.broadcast_to_room(room_id, state)

                # Check if game over
                if room.game_engine.is_game_over():
                    results = room_manager.end_game(room_id)

                    await self.broadcast_to_room(
                        room_id,
                        {
                            "type": "game_over",
                            "winner": room.game_engine.get_winner(),
                            "results": results
                        }
                    )
                    break

                # Sleep for tick interval
                await asyncio.sleep(room.game_engine.tick_interval)

        except asyncio.CancelledError:
            logger.info(f"Game loop cancelled for room {room_id}")
        except Exception as e:
            logger.error(f"Error in game loop for room {room_id}: {e}")
        finally:
            logger.info(f"Game loop ended for room {room_id}")


# Global connection manager instance
connection_manager = ConnectionManager()
