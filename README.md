# Matopeli 🐍

A faithful recreation of the classic Nokia **Snake** — available as both a terminal C app and a browser-playable web app.

This is step 1 of the AI Tour Helsinki (BRK442) demo: the "OG" Snake that later steps modernize, port, and extend.

## Controls

- **Arrow keys** (or **WASD**) — steer
- **Q** — quit (terminal version only)
- **R** — restart after game over

## Features

- Arrow-key movement (no 180° reversals)
- Wrap-around walls, classic Nokia style
- Growing snake + randomly placed food
- Score display
- Speed ramps up as you grow
- Game over + restart

## Web App

Open `web/index.html` directly in a browser, **or** use the included Python server
(required when your browser blocks `file://` requests):

```sh
python serve.py        # http://localhost:8000
python serve.py 9000   # custom port
```

## Build (terminal C version)

**With MinGW-w64 (`gcc` + `make`):**

```sh
make
```

**With MSVC (Visual Studio Build Tools):**

```cmd
build.bat
```

Either command produces `snake.exe` in this directory.

## Run (terminal C version)

```sh
./snake.exe
```

or

```sh
make run
```

Best played in **Windows Terminal** (ANSI escape codes are enabled at startup via `SetConsoleMode`).
