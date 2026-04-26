"""
Entry point — run with:  python -m snake
"""

from __future__ import annotations

import random
import signal
import sys

from . import terminal
from .game import Game


def _cleanup() -> None:
    terminal.shutdown()


def main() -> None:
    random.seed()
    terminal.init()

    def _on_signal(sig: int, frame: object) -> None:
        _cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, _on_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _on_signal)

    try:
        _run_loop()
    finally:
        _cleanup()


def _run_loop() -> None:
    while True:
        g = Game()
        g.init()
        terminal.render_frame(g)

        quit_game = False
        restart = False

        while not g.game_over and not quit_game and not restart:
            quit_game, restart = terminal.poll_input(g)
            if quit_game or restart:
                break
            g.step()
            terminal.render_frame(g)
            terminal.sleep_ms(g.tick_ms())

        if quit_game:
            return

        if restart:
            continue

        # Natural game-over
        terminal.render_game_over(g)
        if not terminal.wait_for_restart_or_quit():
            return


if __name__ == "__main__":
    main()
