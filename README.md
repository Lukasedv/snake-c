# Matopeli 🐍

A faithful, terminal-based recreation of the classic Nokia **Snake** — in C, with zero dependencies.

This is step 1 of the AI Tour Helsinki (BRK442) demo: the "OG" Snake that later steps modernize, port, and extend.

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

## Build

**With MinGW-w64 (`gcc` + `make`):**

```sh
make
```

**With MSVC (Visual Studio Build Tools):**

```cmd
build.bat
```

Either command produces `snake.exe` in this directory.

## Run

```sh
./snake.exe
```

or

```sh
make run
```

Best played in **Windows Terminal** (ANSI escape codes are enabled at startup via `SetConsoleMode`).

---

## Web version 🌐

A Python web app that runs the same 30×18 Snake in the browser with a high-score leaderboard.

**Stack:** FastAPI + uvicorn · vanilla JS (game logic) · HTML5 Canvas · SQLite

```sh
cd web
pip install -r requirements.txt
uvicorn app:app --reload
```

Open <http://127.0.0.1:8000>.  See [`web/README.md`](web/README.md) for full details.
