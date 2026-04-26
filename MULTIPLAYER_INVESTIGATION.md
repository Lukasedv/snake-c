# Multiplayer Support Investigation for FastAPI Snake

## Executive Summary

This document investigates viable directions for extending the FastAPI Snake rewrite (currently in PR #1) to support multiplayer, race mode, and spectator functionality. The investigation explores technical approaches, architectural considerations, and implementation strategies compatible with the existing FastAPI session architecture.

## Current Architecture Analysis

### Existing FastAPI Implementation (PR #1)

The current modernization effort transforms the C terminal Snake into a web-based application:

**Backend (`web/app.py`):**
- FastAPI application serving static files and REST API
- SQLite-backed high-score persistence
- Simple GET/POST `/api/scores` endpoints
- No session management or real-time communication

**Frontend (`web/static/snake.js`):**
- Client-side game loop running entirely in the browser
- 30×18 board, circular buffer snake implementation
- Canvas rendering with 24px cells
- Local keyboard input (Arrow keys, WASD)
- Pause/restart functionality

**Key Characteristics:**
- **Stateless backend**: No game state stored server-side
- **Client-authoritative**: All game logic runs in browser
- **No real-time communication**: Only HTTP REST calls for scores
- **Single-player only**: Each client runs independent game instance

## Multiplayer Architecture Options

### Option 1: WebSocket-Based Real-Time Multiplayer (RECOMMENDED)

**Overview:**
Transform the architecture to support server-authoritative multiplayer using WebSockets for real-time bidirectional communication.

**Architecture:**
```
┌─────────────┐         WebSocket          ┌─────────────┐
│  Client A   │ ◄───────────────────────► │             │
│  (Browser)  │                            │   FastAPI   │
└─────────────┘                            │   Server    │
                                           │             │
┌─────────────┐         WebSocket          │  + Game     │
│  Client B   │ ◄───────────────────────► │   Rooms     │
│  (Browser)  │                            │             │
└─────────────┘                            │  + State    │
                                           │   Manager   │
┌─────────────┐         WebSocket          │             │
│ Spectator   │ ◄───────────────────────► │             │
│  (Browser)  │                            └─────────────┘
└─────────────┘
```

**Technical Components:**

1. **WebSocket Server** (`web/websockets.py`):
   - Use `websockets` or FastAPI's native WebSocket support
   - Handle connection lifecycle (connect, disconnect, error)
   - Route messages to appropriate game rooms
   - Broadcast state updates to connected clients

2. **Game Room Manager** (`web/rooms.py`):
   - Create/join/leave room logic
   - Room states: WAITING, PLAYING, FINISHED
   - Player capacity limits (2-4 players per room)
   - Room lifecycle management

3. **Server-Side Game Engine** (`web/game_engine.py`):
   - Port snake.js game logic to Python
   - Server-authoritative tick loop (55-130ms)
   - Collision detection and scoring
   - Multi-snake board state management
   - Handle simultaneous inputs from multiple players

4. **Client Updates** (`web/static/multiplayer.js`):
   - WebSocket client connection
   - Send input commands (direction changes)
   - Receive and render state updates
   - Display other players' snakes
   - Show room lobby and player list

**Message Protocol:**
```json
// Client → Server
{
  "type": "create_room",
  "mode": "competitive|cooperative|race",
  "max_players": 4
}

{
  "type": "join_room",
  "room_id": "abc123"
}

{
  "type": "input",
  "direction": "UP|DOWN|LEFT|RIGHT"
}

// Server → Client
{
  "type": "room_created",
  "room_id": "abc123",
  "player_id": "p1"
}

{
  "type": "game_state",
  "tick": 1234,
  "snakes": [
    {
      "player_id": "p1",
      "name": "Alice",
      "body": [[10,5], [9,5], [8,5], [7,5]],
      "score": 30,
      "alive": true
    }
  ],
  "foods": [[15,10], [20,12]]
}

{
  "type": "game_over",
  "winner": "p1",
  "scores": [
    {"player_id": "p1", "name": "Alice", "score": 150},
    {"player_id": "p2", "name": "Bob", "score": 80}
  ]
}
```

**Game Modes:**

1. **Competitive Mode**:
   - 2-4 players on shared board
   - Each player has different colored snake
   - Collision with other snakes = death
   - Last snake alive wins
   - Shared food spawns

2. **Race Mode**:
   - Fixed time limit (e.g., 2 minutes)
   - Highest score wins
   - Collision with other snakes doesn't kill, just bounces back
   - Multiple food items on board
   - Speed boosters and obstacles

3. **Cooperative Mode**:
   - Team shares score
   - Goal: reach target score together
   - Special food items give team bonuses
   - Collision with teammate = game over for both

**Spectator Support:**
- Spectators connect with `spectator: true` flag
- Receive same `game_state` updates
- Cannot send input commands
- Can switch between different active rooms
- Real-time leaderboard view

**Implementation Pros:**
- ✅ True real-time multiplayer experience
- ✅ Server authority prevents cheating
- ✅ Supports multiple game modes
- ✅ Spectator mode naturally integrated
- ✅ Scalable to many concurrent games
- ✅ Compatible with existing FastAPI architecture

**Implementation Cons:**
- ❌ Requires significant backend development
- ❌ Server needs to run game loop (CPU usage)
- ❌ WebSocket infrastructure more complex than HTTP
- ❌ Requires careful synchronization and lag handling

**Estimated Effort:** Medium-High (3-5 development days)

---

### Option 2: Turn-Based Multiplayer via REST API

**Overview:**
Implement asynchronous turn-based multiplayer where players take turns moving their snakes.

**Architecture:**
- REST endpoints for creating games, submitting moves
- Polling or Server-Sent Events (SSE) for updates
- Server stores game state in database
- Each player moves once per turn

**Technical Components:**

1. **Game API** (`/api/multiplayer/*`):
   - `POST /api/games` - Create new multiplayer game
   - `GET /api/games/{game_id}` - Get current game state
   - `POST /api/games/{game_id}/moves` - Submit move
   - `GET /api/games/{game_id}/status` - Poll for updates

2. **Turn-Based Game Engine**:
   - Process all player moves simultaneously each turn
   - Calculate collisions and new positions
   - Store state in SQLite/PostgreSQL
   - Return updated board state

**Implementation Pros:**
- ✅ Simpler than WebSockets
- ✅ Uses familiar HTTP/REST patterns
- ✅ Easier to test and debug
- ✅ No persistent connections needed

**Implementation Cons:**
- ❌ Not real-time (feels slower)
- ❌ Requires polling or SSE
- ❌ Less engaging gameplay
- ❌ Doesn't match original Snake feel

**Estimated Effort:** Low-Medium (1-2 development days)

---

### Option 3: Peer-to-Peer with Server Coordination

**Overview:**
Use WebRTC for peer-to-peer game state synchronization with server acting as signaling server and arbiter.

**Architecture:**
- Server handles room matching and initial WebRTC signaling
- Clients exchange game state via WebRTC data channels
- Server validates final scores and prevents cheating
- Optimistic client-side prediction with server reconciliation

**Implementation Pros:**
- ✅ Reduced server load (P2P data transfer)
- ✅ Lower latency between players
- ✅ Scalable to more concurrent games

**Implementation Cons:**
- ❌ Complex WebRTC setup and NAT traversal
- ❌ Harder to prevent cheating
- ❌ Requires STUN/TURN servers
- ❌ More difficult to implement spectator mode
- ❌ Not all browsers support WebRTC equally

**Estimated Effort:** High (5-7 development days)

---

## Recommended Implementation Path

### Phase 1: WebSocket Infrastructure (MVP)

**Scope:**
- Add WebSocket support to FastAPI
- Implement basic room management
- Port game logic to server-side Python
- Create simple 2-player competitive mode
- Update frontend for multiplayer rendering

**Files to Create/Modify:**

```
web/
├── app.py                    # Add WebSocket endpoint
├── websockets.py            # NEW: WebSocket handler
├── rooms.py                 # NEW: Room management
├── game_engine.py           # NEW: Server-side game logic
├── static/
│   ├── multiplayer.js       # NEW: Multiplayer client
│   ├── lobby.html           # NEW: Room lobby UI
│   └── snake.js             # Keep for single-player
└── tests/
    └── test_multiplayer.py  # NEW: Multiplayer tests
```

**Dependencies to Add:**
```python
# requirements.txt additions
websockets==12.0
python-socketio==5.10.0  # Alternative: use native FastAPI WebSockets
```

### Phase 2: Race Mode

**Scope:**
- Add time-based game mode
- Multiple food items on board
- Score-based winning condition
- Power-ups and obstacles

### Phase 3: Spectator Mode

**Scope:**
- Spectator WebSocket connections
- Room browsing UI
- Live game list
- Spectator-specific message filtering

### Phase 4: Advanced Features

**Scope:**
- Replay system (record game states)
- Tournament brackets
- ELO rating system
- Custom room settings (speed, board size)

---

## Compatibility with Existing Architecture

### Session Management

**Current State:**
- No session concept (stateless HTTP)
- High scores use anonymous submissions

**Multiplayer Requirements:**
- Player identity tracking
- Session persistence across WebSocket reconnects
- Optional authentication/registration

**Proposed Solution:**
```python
# Simple session tokens (no auth required for MVP)
from secrets import token_urlsafe

class SessionManager:
    def __init__(self):
        self.sessions = {}  # session_id -> player_info

    def create_session(self, player_name: str) -> str:
        session_id = token_urlsafe(16)
        self.sessions[session_id] = {
            "name": player_name,
            "created_at": datetime.now(),
            "current_room": None
        }
        return session_id

    def get_session(self, session_id: str) -> dict:
        return self.sessions.get(session_id)
```

### Database Schema Extensions

**New Tables:**

```sql
-- Game rooms
CREATE TABLE rooms (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,  -- 'competitive', 'race', 'cooperative'
    max_players INTEGER NOT NULL,
    status TEXT NOT NULL,  -- 'waiting', 'playing', 'finished'
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

-- Room participants
CREATE TABLE room_players (
    room_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    score INTEGER DEFAULT 0,
    placement INTEGER,  -- Final ranking (1st, 2nd, etc.)
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    PRIMARY KEY (room_id, player_id)
);

-- Game history (for replays and statistics)
CREATE TABLE game_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    state_snapshot TEXT NOT NULL,  -- JSON blob of full game state
    created_at TEXT NOT NULL,
    FOREIGN KEY (room_id) REFERENCES rooms(id)
);
```

### Backwards Compatibility

**Strategy:**
- Keep single-player mode completely separate (`/` and `/static/snake.js`)
- Add multiplayer at new routes (`/multiplayer`, `/static/multiplayer.js`)
- Existing `/api/scores` endpoints remain unchanged
- Single-player scores and multiplayer scores in separate tables

---

## Testing Strategy

### Unit Tests

```python
# test_game_engine.py
def test_multi_snake_collision():
    """Test collision between two snakes."""
    engine = GameEngine(board_size=(30, 18))
    engine.add_snake("p1", start_pos=(5, 5))
    engine.add_snake("p2", start_pos=(10, 10))

    # Move p1 into p2's body
    engine.set_direction("p1", Direction.RIGHT)
    # ... simulate until collision

    assert engine.is_snake_alive("p1") == False
    assert engine.get_winner() == "p2"

def test_simultaneous_food_eating():
    """Test when two snakes reach same food at same tick."""
    # Implementation...

def test_race_mode_time_limit():
    """Test race mode ends after time limit."""
    # Implementation...
```

### Integration Tests

```python
# test_websocket_multiplayer.py
import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

@pytest.mark.asyncio
async def test_two_players_can_join_room():
    """Test basic room joining flow."""
    # Create WebSocket clients
    # Send join messages
    # Assert both receive player_joined events

@pytest.mark.asyncio
async def test_game_state_broadcast():
    """Test state updates broadcast to all players."""
    # Join room with 2 clients
    # Start game
    # Send input from client 1
    # Assert both clients receive updated state

@pytest.mark.asyncio
async def test_spectator_receives_updates():
    """Test spectator can watch game."""
    # Create game with 2 players
    # Join as spectator
    # Assert spectator receives state but cannot send input
```

### Manual Testing Checklist

- [ ] Create room and wait for players
- [ ] Join existing room from second browser/tab
- [ ] Play full 2-player competitive game
- [ ] Test race mode with timer
- [ ] Join as spectator during active game
- [ ] Test disconnect/reconnect scenarios
- [ ] Test simultaneous input handling
- [ ] Verify score persistence to database
- [ ] Check leaderboard with multiplayer scores
- [ ] Test with 3-4 players simultaneously

---

## Performance Considerations

### Server Load

**Estimated Resources per Active Game:**
- Memory: ~5-10 KB per game state
- CPU: ~1-2% per game (60 ticks/second)
- WebSocket connections: 2-4 per game

**Scalability Target:**
- Support 100 concurrent games on modest server
- ~400 active WebSocket connections
- ~500 MB RAM, 20% CPU usage

**Optimization Strategies:**
- Use connection pooling
- Implement room timeout/cleanup
- Add rate limiting on inputs
- Consider Redis for state management if scaling beyond single server

### Network Latency

**Challenges:**
- Client-server round trip affects responsiveness
- Players in different regions experience different delays

**Mitigation:**
- Client-side prediction for local player
- Interpolation for remote players
- Buffer small amount of inputs (1-2 ticks)
- Display latency indicator to players

---

## Security Considerations

### Input Validation

```python
def validate_direction(direction: str) -> bool:
    """Validate direction input."""
    return direction in {"UP", "DOWN", "LEFT", "RIGHT"}

def validate_room_id(room_id: str) -> bool:
    """Validate room ID format."""
    return len(room_id) == 22 and room_id.isalnum()

def rate_limit_player(player_id: str) -> bool:
    """Prevent input spam."""
    # Max 20 direction changes per second
    # Implementation...
```

### Anti-Cheat

**Server Authority:**
- All game logic runs server-side
- Client cannot manipulate snake position
- Server validates all movements
- Score calculated server-side only

**Rate Limiting:**
- Limit room creation (max 5 per minute per IP)
- Limit message rate (max 50 messages per second per connection)
- Timeout idle connections (5 minutes no activity)

### Data Sanitization

```python
def sanitize_player_name(name: str) -> str:
    """Sanitize player name to prevent XSS."""
    # Strip HTML tags
    # Limit length to 30 characters
    # Remove special characters
    return html.escape(name[:30])
```

---

## Implementation Code Samples

### WebSocket Endpoint (web/app.py)

```python
from fastapi import WebSocket, WebSocketDisconnect
from web.websockets import ConnectionManager

manager = ConnectionManager()

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for multiplayer game."""
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_message(session_id, data)
    except WebSocketDisconnect:
        await manager.disconnect(session_id)
```

### Game Engine (web/game_engine.py)

```python
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Tuple
import asyncio

class Direction(Enum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3

@dataclass
class Snake:
    player_id: str
    name: str
    body: List[Tuple[int, int]]  # [(x, y), ...]
    direction: Direction
    pending_direction: Direction
    score: int = 0
    alive: bool = True
    color: str = "#4cff91"

class GameEngine:
    """Server-side game engine for multiplayer Snake."""

    def __init__(self, board_w: int = 30, board_h: int = 18):
        self.board_w = board_w
        self.board_h = board_h
        self.snakes: Dict[str, Snake] = {}
        self.foods: List[Tuple[int, int]] = []
        self.tick_count = 0
        self.tick_interval = 0.130  # 130ms

    def add_snake(self, player_id: str, name: str, color: str) -> None:
        """Add a new snake to the game."""
        # Find empty starting position
        start_x = (self.board_w // 4) * (len(self.snakes) + 1)
        start_y = self.board_h // 2

        body = [(start_x + i, start_y) for i in range(4)]

        self.snakes[player_id] = Snake(
            player_id=player_id,
            name=name,
            body=body,
            direction=Direction.RIGHT,
            pending_direction=Direction.RIGHT,
            color=color
        )

    def set_direction(self, player_id: str, direction: Direction) -> None:
        """Set pending direction for a snake (validates no 180° turn)."""
        snake = self.snakes.get(player_id)
        if not snake or not snake.alive:
            return

        # Check for 180° reversal
        if self._is_opposite(snake.direction, direction):
            return

        snake.pending_direction = direction

    def _is_opposite(self, d1: Direction, d2: Direction) -> bool:
        """Check if two directions are opposite."""
        opposites = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT
        }
        return opposites[d1] == d2

    def tick(self) -> Dict:
        """Execute one game tick and return updated state."""
        self.tick_count += 1

        # Move all alive snakes
        for snake in self.snakes.values():
            if not snake.alive:
                continue

            snake.direction = snake.pending_direction
            head_x, head_y = snake.body[0]

            # Calculate new head position
            if snake.direction == Direction.UP:
                new_head = (head_x, head_y - 1)
            elif snake.direction == Direction.DOWN:
                new_head = (head_x, head_y + 1)
            elif snake.direction == Direction.LEFT:
                new_head = (head_x - 1, head_y)
            else:  # RIGHT
                new_head = (head_x + 1, head_y)

            # Wrap around walls
            new_head = (new_head[0] % self.board_w, new_head[1] % self.board_h)

            # Check if eating food
            eating = new_head in self.foods

            # Move snake
            snake.body.insert(0, new_head)
            if not eating:
                snake.body.pop()  # Remove tail
            else:
                snake.score += 10
                self.foods.remove(new_head)
                self._spawn_food()

        # Check collisions AFTER all moves
        self._check_collisions()

        # Calculate speed (gets faster as snakes grow)
        max_length = max((len(s.body) for s in self.snakes.values()), default=4)
        self.tick_interval = max(0.055, 0.130 - (max_length - 4) * 0.002)

        return self.get_state()

    def _check_collisions(self) -> None:
        """Check for snake collisions (self and others)."""
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
                if head in other.body:
                    snake.alive = False
                    break

    def _spawn_food(self) -> None:
        """Spawn food at random empty location."""
        while True:
            x = random.randint(0, self.board_w - 1)
            y = random.randint(0, self.board_h - 1)

            # Check not on any snake
            occupied = False
            for snake in self.snakes.values():
                if (x, y) in snake.body:
                    occupied = True
                    break

            if not occupied and (x, y) not in self.foods:
                self.foods.append((x, y))
                return

    def get_state(self) -> Dict:
        """Get current game state as dict."""
        return {
            "type": "game_state",
            "tick": self.tick_count,
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
            "foods": self.foods
        }

    def is_game_over(self) -> bool:
        """Check if game is over (0 or 1 snake alive)."""
        alive = sum(1 for s in self.snakes.values() if s.alive)
        return alive <= 1

    def get_winner(self) -> str | None:
        """Get winner player_id."""
        alive_snakes = [s for s in self.snakes.values() if s.alive]
        if len(alive_snakes) == 1:
            return alive_snakes[0].player_id
        # Tie or all dead - highest score wins
        if self.snakes:
            winner = max(self.snakes.values(), key=lambda s: s.score)
            return winner.player_id
        return None
```

### Room Manager (web/rooms.py)

```python
from typing import Dict, Set
from dataclasses import dataclass
from secrets import token_urlsafe
import asyncio

@dataclass
class Room:
    room_id: str
    mode: str  # 'competitive', 'race', 'cooperative'
    max_players: int
    players: Set[str]  # player_ids
    spectators: Set[str]  # player_ids
    status: str  # 'waiting', 'playing', 'finished'
    game_engine: GameEngine | None = None

class RoomManager:
    """Manage multiplayer game rooms."""

    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def create_room(self, mode: str = "competitive", max_players: int = 4) -> str:
        """Create a new room and return room_id."""
        room_id = token_urlsafe(8)
        self.rooms[room_id] = Room(
            room_id=room_id,
            mode=mode,
            max_players=max_players,
            players=set(),
            spectators=set(),
            status="waiting"
        )
        return room_id

    def join_room(self, room_id: str, player_id: str, spectator: bool = False) -> bool:
        """Join a room. Returns True if successful."""
        room = self.rooms.get(room_id)
        if not room:
            return False

        if spectator:
            room.spectators.add(player_id)
            return True

        if len(room.players) >= room.max_players:
            return False  # Room full

        if room.status != "waiting":
            return False  # Game already started

        room.players.add(player_id)
        return True

    def leave_room(self, room_id: str, player_id: str) -> None:
        """Leave a room."""
        room = self.rooms.get(room_id)
        if not room:
            return

        room.players.discard(player_id)
        room.spectators.discard(player_id)

        # Cleanup empty rooms
        if not room.players and not room.spectators:
            del self.rooms[room_id]

    def start_game(self, room_id: str) -> bool:
        """Start the game in a room."""
        room = self.rooms.get(room_id)
        if not room or room.status != "waiting":
            return False

        if len(room.players) < 2:
            return False  # Need at least 2 players

        room.status = "playing"
        room.game_engine = GameEngine()

        # Add all players to game engine
        colors = ["#4cff91", "#ff5555", "#5555ff", "#ffff55"]
        for i, player_id in enumerate(room.players):
            room.game_engine.add_snake(
                player_id,
                f"Player{i+1}",
                colors[i % len(colors)]
            )

        # Spawn initial food
        for _ in range(3):
            room.game_engine._spawn_food()

        return True

    def get_room(self, room_id: str) -> Room | None:
        """Get room by ID."""
        return self.rooms.get(room_id)

    def list_rooms(self, status: str | None = None) -> List[Dict]:
        """List all rooms, optionally filtered by status."""
        rooms = self.rooms.values()
        if status:
            rooms = [r for r in rooms if r.status == status]

        return [
            {
                "room_id": r.room_id,
                "mode": r.mode,
                "players": len(r.players),
                "max_players": r.max_players,
                "spectators": len(r.spectators),
                "status": r.status
            }
            for r in rooms
        ]
```

---

## Frontend Multiplayer Client Sample

```javascript
// web/static/multiplayer.js
class MultiplayerClient {
    constructor() {
        this.ws = null;
        this.sessionId = null;
        this.playerId = null;
        this.roomId = null;
        this.gameState = null;
    }

    connect(sessionId) {
        this.sessionId = sessionId;
        const wsUrl = `ws://${window.location.host}/ws/${sessionId}`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log("Connected to server");
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.ws.onerror = (error) => {
            console.error("WebSocket error:", error);
        };

        this.ws.onclose = () => {
            console.log("Disconnected from server");
            // Attempt reconnect
            setTimeout(() => this.connect(sessionId), 3000);
        };
    }

    handleMessage(data) {
        switch (data.type) {
            case "room_created":
                this.roomId = data.room_id;
                this.playerId = data.player_id;
                this.showRoomCode(data.room_id);
                break;

            case "player_joined":
                this.updatePlayerList(data.players);
                break;

            case "game_started":
                this.startGameView();
                break;

            case "game_state":
                this.gameState = data;
                this.render(data);
                break;

            case "game_over":
                this.showGameOver(data.winner, data.scores);
                break;

            default:
                console.warn("Unknown message type:", data.type);
        }
    }

    createRoom(mode = "competitive", maxPlayers = 4) {
        this.send({
            type: "create_room",
            mode: mode,
            max_players: maxPlayers
        });
    }

    joinRoom(roomId) {
        this.send({
            type: "join_room",
            room_id: roomId
        });
    }

    sendDirection(direction) {
        this.send({
            type: "input",
            direction: direction
        });
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    render(state) {
        // Clear canvas
        ctx.fillStyle = COLOR_BG;
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw all snakes
        state.snakes.forEach(snake => {
            snake.body.forEach((pos, i) => {
                const isHead = (i === 0);
                ctx.fillStyle = isHead ? "#ffffff" : snake.color;
                ctx.fillRect(pos[0] * CELL + 1, pos[1] * CELL + 1, CELL - 2, CELL - 2);
            });

            // Draw player name above snake
            if (snake.alive) {
                const head = snake.body[0];
                ctx.fillStyle = "#fff";
                ctx.font = "12px sans-serif";
                ctx.fillText(snake.name, head[0] * CELL, head[1] * CELL - 5);
            }
        });

        // Draw foods
        state.foods.forEach(food => {
            ctx.fillStyle = COLOR_FOOD;
            ctx.fillRect(food[0] * CELL + 2, food[1] * CELL + 2, CELL - 4, CELL - 4);
        });

        // Update scoreboard
        this.updateScoreboard(state.snakes);
    }
}
```

---

## Conclusion

This investigation recommends **Option 1: WebSocket-Based Real-Time Multiplayer** as the best path forward for the FastAPI Snake rewrite. This approach:

1. ✅ Provides true real-time multiplayer experience
2. ✅ Supports competitive, race, and cooperative modes
3. ✅ Naturally integrates spectator functionality
4. ✅ Compatible with existing FastAPI architecture
5. ✅ Server-authoritative design prevents cheating
6. ✅ Scalable and performant
7. ✅ Clear separation from single-player MVP

The phased implementation approach allows for incremental delivery:
- Phase 1 delivers core 2-player multiplayer (MVP)
- Phase 2 adds race mode variety
- Phase 3 enables spectator experience
- Phase 4 provides advanced features

All proposed changes are additive and maintain backwards compatibility with the existing single-player implementation.
