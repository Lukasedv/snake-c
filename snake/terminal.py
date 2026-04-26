"""
Terminal UI — ANSI rendering and cross-platform keyboard input.

Windows:  uses msvcrt for non-blocking key polling.
POSIX:    uses termios/tty + select for non-blocking key polling.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Optional

from .game import BOARD_H, BOARD_W, Direction, Game

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

_IS_WIN = sys.platform == "win32"

if _IS_WIN:
    import msvcrt

    def _kbhit() -> bool:
        return msvcrt.kbhit()  # type: ignore[attr-defined]

    def _getch() -> bytes:
        return msvcrt.getch()  # type: ignore[attr-defined]

else:
    import select
    import termios
    import tty

    _old_term: Optional[list] = None  # type: ignore[type-arg]

    def _set_raw() -> None:
        global _old_term
        fd = sys.stdin.fileno()
        _old_term = termios.tcgetattr(fd)
        tty.setraw(fd)

    def _restore_term() -> None:
        if _old_term is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _old_term)

    def _kbhit() -> bool:
        return bool(select.select([sys.stdin], [], [], 0)[0])

    def _getch() -> bytes:
        return os.read(sys.stdin.fileno(), 1)


# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

_ESC = "\x1b"
_HIDE_CURSOR = f"{_ESC}[?25l"
_SHOW_CURSOR = f"{_ESC}[?25h"
_CLEAR_SCREEN = f"{_ESC}[2J"
_HOME = f"{_ESC}[H"


def _move(row: int, col: int) -> str:
    """Return ANSI cursor-position sequence (1-based row/col)."""
    return f"{_ESC}[{row};{col}H"


def _write(s: str) -> None:
    sys.stdout.write(s)


def _flush() -> None:
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Windows: enable virtual terminal processing so ANSI codes work in cmd.exe
# ---------------------------------------------------------------------------

def _enable_windows_ansi() -> None:
    if not _IS_WIN:
        return
    try:
        import ctypes
        import ctypes.wintypes

        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        STD_OUTPUT_HANDLE = -11
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.wintypes.DWORD()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:
        pass  # best-effort; modern Windows Terminal works without this


# ---------------------------------------------------------------------------
# Public lifecycle
# ---------------------------------------------------------------------------

def init() -> None:
    """Prepare the terminal for rendering."""
    _enable_windows_ansi()
    if not _IS_WIN:
        _set_raw()
    _write(_HIDE_CURSOR + _CLEAR_SCREEN)
    _flush()


def shutdown() -> None:
    """Restore the terminal to its previous state."""
    if not _IS_WIN:
        _restore_term()
    _write(_SHOW_CURSOR)
    _flush()


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _draw_border() -> None:
    # Top edge
    _write(_move(1, 1))
    _write("+" + "-" * (BOARD_W * 2) + "+")
    # Sides
    for y in range(BOARD_H):
        _write(_move(y + 2, 1) + "|")
        _write(_move(y + 2, BOARD_W * 2 + 2) + "|")
    # Bottom edge
    _write(_move(BOARD_H + 2, 1))
    _write("+" + "-" * (BOARD_W * 2) + "+")


def render_frame(g: Game) -> None:
    """Redraw the full game board."""
    _write(_HOME)
    _draw_border()

    for y in range(BOARD_H):
        _write(_move(y + 2, 2))
        row = ""
        for x in range(BOARD_W):
            if g.cell_is_snake(x, y):
                row += "##"
            elif g.food.x == x and g.food.y == y:
                row += "()"
            else:
                row += "  "
        _write(row)

    status_row = BOARD_H + 3
    _write(_move(status_row, 1))
    _write(f"Score: {g.score}   Length: {g.length}   Speed: {g.tick_ms()} ms   ")
    _flush()


def render_game_over(g: Game) -> None:
    """Overlay the game-over message (press R to restart, Q to quit)."""
    mid_row = BOARD_H // 2 + 1
    mid_col = BOARD_W - 8

    _write(_move(mid_row, mid_col))
    _write("*** GAME OVER ***")
    _write(_move(mid_row + 1, mid_col))
    _write(f"  Score: {g.score:<6}  ")
    _write(_move(mid_row + 2, mid_col))
    _write(" R = restart  ")
    _write(_move(mid_row + 3, mid_col))
    _write(" Q = quit     ")
    _flush()


# ---------------------------------------------------------------------------
# Keyboard input
# ---------------------------------------------------------------------------

# Windows arrow-key sequences via msvcrt:
#   First byte 0x00 or 0xE0, second byte is the actual code.
_WIN_ARROW: dict[int, Direction] = {
    0x48: Direction.UP,
    0x50: Direction.DOWN,
    0x4B: Direction.LEFT,
    0x4D: Direction.RIGHT,
}

# POSIX escape sequences for arrow keys: ESC [ A/B/C/D
_POSIX_ARROW: dict[bytes, Direction] = {
    b"A": Direction.UP,
    b"B": Direction.DOWN,
    b"D": Direction.LEFT,
    b"C": Direction.RIGHT,
}

_WASD: dict[bytes, Direction] = {
    b"w": Direction.UP,
    b"W": Direction.UP,
    b"s": Direction.DOWN,
    b"S": Direction.DOWN,
    b"a": Direction.LEFT,
    b"A": Direction.LEFT,
    b"d": Direction.RIGHT,
    b"D": Direction.RIGHT,
}


def poll_input(g: Game) -> tuple[bool, bool]:
    """
    Drain all pending keystrokes and apply direction changes.

    Returns ``(quit, restart)`` tuple — both are False if neither key was pressed.
    """
    quit_pressed = False
    restart_pressed = False

    while _kbhit():
        ch = _getch()

        if _IS_WIN:
            # Prefix byte for special keys on Windows
            if ch in (b"\x00", b"\xe0"):
                if _kbhit():
                    code = _getch()[0]
                    d = _WIN_ARROW.get(code)
                    if d is not None:
                        g.set_direction(d)
                continue

            if ch in (b"q", b"Q"):
                quit_pressed = True
                return quit_pressed, restart_pressed
            if ch in (b"r", b"R"):
                restart_pressed = True
                return quit_pressed, restart_pressed
            d = _WASD.get(ch)
            if d is not None:
                g.set_direction(d)

        else:
            # POSIX: ESC [ X sequences for arrow keys
            if ch == b"\x1b":
                # Try to read the rest of the escape sequence without blocking
                if _kbhit():
                    bracket = _getch()
                    if bracket == b"[" and _kbhit():
                        arrow = _getch()
                        d = _POSIX_ARROW.get(arrow)
                        if d is not None:
                            g.set_direction(d)
                continue

            if ch in (b"q", b"Q"):
                quit_pressed = True
                return quit_pressed, restart_pressed
            if ch in (b"r", b"R"):
                restart_pressed = True
                return quit_pressed, restart_pressed
            d = _WASD.get(ch)
            if d is not None:
                g.set_direction(d)

    return quit_pressed, restart_pressed


def wait_for_restart_or_quit() -> bool:
    """
    Block until R (restart → True) or Q (quit → False) is pressed.
    Returns True if the player wants to restart, False to quit.
    """
    while True:
        ch = _getch()

        if _IS_WIN:
            if ch in (b"\x00", b"\xe0") and _kbhit():
                _getch()  # discard arrow-key second byte
                continue
        else:
            if ch == b"\x1b":
                if _kbhit():
                    _getch()
                    if _kbhit():
                        _getch()
                continue

        if ch in (b"r", b"R"):
            return True
        if ch in (b"q", b"Q"):
            return False


def sleep_ms(ms: int) -> None:
    time.sleep(ms / 1000.0)
