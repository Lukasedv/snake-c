# Copilot Coding Instructions

These guidelines apply to all code in this repository.  
Copilot code review **must flag any pull request that violates them**.

---

## 1 — No inline suppression comments

Do **not** use `# noqa`, `# type: ignore`, `# pylint: disable`, or any
equivalent inline comment to silence linter or type-checker warnings.  
Fix the root cause instead.

```python
# ✗ Bad
async def get_race_room(room_id: str) -> HTMLResponse:  # noqa: ARG001
    return HTMLResponse(race_html)

# ✓ Good — remove the unused parameter or use it
async def get_race_room(_room_id: str) -> HTMLResponse:
    return HTMLResponse(race_html)
```

---

## 2 — Full type annotations on every public function

Every public function and method must have complete parameter **and** return
type annotations.  Generic types must include their type arguments.

```python
# ✗ Bad
async def _run_spectator(websocket: WebSocket, room) -> None:  # type: ignore[type-arg]
    ...

# ✓ Good
async def _run_spectator(websocket: WebSocket, room: Room) -> None:
    ...
```

---

## 3 — Use `TypedDict` or `dataclass` instead of bare `dict` in signatures

Public functions must not return or accept `dict` / `list[dict]` without a
concrete type.  Define a `TypedDict` or `dataclass` to make the contract
explicit and statically checkable.

```python
# ✗ Bad
def list_rooms(self) -> list[dict]:
    ...

# ✓ Good
from typing import TypedDict

class RoomInfo(TypedDict):
    room_id: str
    state: str
    players: int
    max_players: int
    spectators: int
    target_score: int

def list_rooms(self) -> list[RoomInfo]:
    ...
```

---

## 4 — Validate all user-supplied input at the API boundary

Every value that arrives from an HTTP request, query parameter, or WebSocket
message must be validated **before** it is used.  Check type, length, and
character set.  Reject invalid input with a clear error response — do not
silently truncate or accept it.

```python
# ✗ Bad
async def race_websocket(
    websocket: WebSocket,
    room_id: str,
    player_name: str = "Player",
) -> None:
    ...  # player_name is used as-is

# ✓ Good
_NAME_RE = re.compile(r"^[\x20-\x7E]{1,32}$")

async def race_websocket(
    websocket: WebSocket,
    room_id: str,
    player_name: str = "Player",
) -> None:
    if not _NAME_RE.fullmatch(player_name):
        await websocket.close(code=1008, reason="Invalid player name")
        return
    ...
```

---

## 5 — Public resource IDs must be at least 16 random characters

IDs exposed in URLs or WebSocket messages must be generated with a
cryptographically random source and be at least 16 characters long.  8-character
hex prefixes are not acceptable.

```python
# ✗ Bad
room_id = str(uuid.uuid4())[:8]   # only 8 hex chars — guessable

# ✓ Good
import secrets
room_id = secrets.token_urlsafe(16)   # 128 bits of randomness
```

---

## 6 — Protect shared mutable state with `asyncio.Lock`

Any attribute that is read **and** written from multiple coroutines must be
guarded by an `asyncio.Lock`.  Iterating a dict while another coroutine may
add or remove keys causes silent data races.

```python
# ✗ Bad
class Room:
    def __init__(self) -> None:
        self.players: dict[str, PlayerSession] = {}
        # No lock — broadcast and tick loop both iterate self.players

# ✓ Good
class Room:
    def __init__(self) -> None:
        self.players: dict[str, PlayerSession] = {}
        self._lock = asyncio.Lock()

    async def broadcast_state(self) -> None:
        async with self._lock:
            snapshot = list(self.players.values())
        for session in snapshot:
            await session.websocket.send_text(...)
```

---

## 7 — Functions must not accept parameters they do not use

A function that accepts a parameter it never reads is a design smell.  
Rename it with a leading underscore to signal intentional discard, or
refactor the interface so the parameter is actually needed.

```python
# ✗ Bad — room_id is declared but never read; silenced with noqa
@app.get("/race/{room_id}", response_class=HTMLResponse)
async def get_race_room(room_id: str) -> HTMLResponse:  # noqa: ARG001
    return HTMLResponse(race_html)

# ✓ Option A — prefix with underscore (discard)
async def get_race_room(_room_id: str) -> HTMLResponse:
    return HTMLResponse(race_html)

# ✓ Option B — actually use it (serve room-specific data)
async def get_race_room(room_id: str) -> HTMLResponse:
    room = room_manager.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return HTMLResponse(race_html)
```

---

## 8 — Never silently swallow exceptions

Catch only the exceptions you can meaningfully handle.  Always log unexpected
errors.  WebSocket handlers must send a structured error message before
closing, rather than letting the connection drop silently.

```python
# ✗ Bad
try:
    await _run_player(websocket, room, player_id)
except Exception:
    pass  # silent swallow

# ✓ Good
import logging
_log = logging.getLogger(__name__)

try:
    await _run_player(websocket, room, player_id)
except WebSocketDisconnect:
    pass  # expected — client left normally
except Exception:
    _log.exception("Unexpected error in player WebSocket handler")
    await websocket.close(code=1011, reason="Internal server error")
    raise
```
