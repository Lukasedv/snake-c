# Snake Web — FastAPI Edition

A browser-based port of the original terminal Snake game.  
The back-end (FastAPI) serves the static front-end and stores high scores in SQLite.  
All game logic runs client-side in vanilla JavaScript, faithfully mirroring the C source.

## Requirements

- Python 3.11+
- Install dependencies:

```sh
pip install -r requirements.txt
```

## Run

From the **`web/`** directory:

```sh
uvicorn app:app --reload
```

Then open <http://127.0.0.1:8000> in your browser.

## Project structure

```
web/
├── app.py              # FastAPI application (API + static-file serving)
├── requirements.txt    # Python dependencies
├── static/
│   ├── index.html      # Game page (canvas + sidebar)
│   ├── style.css       # Dark theme
│   └── snake.js        # Game logic & rendering (port of game.c)
└── tests/
    └── test_app.py     # pytest suite for the API
```

## API

| Method | Path          | Description                    |
|--------|---------------|--------------------------------|
| GET    | `/api/scores` | Top-10 scores (score DESC)     |
| POST   | `/api/scores` | Save a new score `{name, score}` |

## Tests

```sh
# from the repo root
pytest web/tests/
```

## Controls

| Key              | Action          |
|------------------|-----------------|
| Arrow keys / WASD | Steer snake    |
| Space            | Pause / resume  |
| R                | Restart         |
