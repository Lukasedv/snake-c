# Matopeli 🐍

A faithful, terminal-based recreation of the classic Nokia **Snake** — originally in C (zero dependencies), now also available as a Python port that preserves every gameplay detail while modernising the architecture.

This is part of the AI Tour Helsinki (BRK442) demo series.

## Controls

- **Arrow keys** (or **WASD**) — steer
- **Q** — quit
- **R** — restart after game over

## Features

- Arrow-key movement (no 180° reversals)
- Wrap-around walls, classic Nokia style
- Growing snake + randomly placed food
- Score display
- Speed ramps up as you grow
- Game over + restart

---

## Python version (`snake/`)

### Requirements

Python 3.8 or newer — no third-party packages needed.

### Run

```sh
python -m snake
```

Works on **Windows** (uses `msvcrt`) and **Linux / macOS** (uses `termios` + `select`).

Best experienced in a terminal that supports ANSI escape codes (Windows Terminal, iTerm2, most modern Linux terminals).

### Run tests

```sh
python -m unittest tests/test_game.py -v
```

---

## C version (`src/`)

### Build

**With MinGW-w64 (`gcc` + `make`):**

```sh
make
```

**With MSVC (Visual Studio Build Tools):**

```cmd
build.bat
```

Either command produces `snake.exe` in this directory.

### Run

```sh
./snake.exe
```

or

```sh
make run
```

Best played in **Windows Terminal** (ANSI escape codes are enabled at startup via `SetConsoleMode`).
