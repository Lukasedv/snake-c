/**
 * Matopeli — browser Snake
 *
 * Game rules ported faithfully from src/game.c (C reference implementation).
 * Board layout, speed curve, wrap-around, collision, and scoring are identical.
 */

"use strict";

// ── Constants (mirror game.h) ────────────────────────────────────────────────
const BOARD_W   = 30;
const BOARD_H   = 18;
const MAX_SNAKE = BOARD_W * BOARD_H;
const CELL      = 20; // canvas pixels per board cell

const DIR_UP    = 0;
const DIR_DOWN  = 1;
const DIR_LEFT  = 2;
const DIR_RIGHT = 3;

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Wrap a coordinate onto the board (mirrors static wrap() in game.c). */
function wrap(x, y) {
    if (x < 0)       x = BOARD_W - 1;
    if (x >= BOARD_W) x = 0;
    if (y < 0)       y = BOARD_H - 1;
    if (y >= BOARD_H) y = 0;
    return { x, y };
}

/** Return true when directions a and b are exact opposites. */
function opposite(a, b) {
    return (a === DIR_UP    && b === DIR_DOWN)  ||
           (a === DIR_DOWN  && b === DIR_UP)    ||
           (a === DIR_LEFT  && b === DIR_RIGHT) ||
           (a === DIR_RIGHT && b === DIR_LEFT);
}

// ── Game state ───────────────────────────────────────────────────────────────

/**
 * All mutable game state in one plain object.
 * Shape mirrors the Game struct in game.h.
 *
 * @typedef {{ x: number, y: number }} Point
 * @typedef {{
 *   body:        Point[],
 *   head:        number,
 *   tail:        number,
 *   length:      number,
 *   dir:         number,
 *   pendingDir:  number,
 *   food:        Point,
 *   score:       number,
 *   gameOver:    boolean,
 * }} GameState
 */

/** @returns {GameState} */
function makeState() {
    /** @type {Point[]} */
    const body = new Array(MAX_SNAKE).fill(null).map(() => ({ x: 0, y: 0 }));
    return { body, head: 0, tail: 0, length: 0, dir: DIR_RIGHT, pendingDir: DIR_RIGHT, food: { x: 0, y: 0 }, score: 0, gameOver: false };
}

// ── game_cell_is_snake ───────────────────────────────────────────────────────

/** @param {GameState} g @param {number} x @param {number} y @returns {boolean} */
function gameIsCellSnake(g, x, y) {
    let i = g.tail;
    for (let n = 0; n < g.length; n++) {
        if (g.body[i].x === x && g.body[i].y === y) return true;
        i = (i + 1) % MAX_SNAKE;
    }
    return false;
}

// ── place_food ───────────────────────────────────────────────────────────────

/** @param {GameState} g */
function placeFood(g) {
    for (;;) {
        const x = Math.floor(Math.random() * BOARD_W);
        const y = Math.floor(Math.random() * BOARD_H);
        if (!gameIsCellSnake(g, x, y)) {
            g.food.x = x;
            g.food.y = y;
            return;
        }
    }
}

// ── game_head ────────────────────────────────────────────────────────────────

/** @param {GameState} g @returns {Point} */
function gameHead(g) {
    const idx = (g.head - 1 + MAX_SNAKE) % MAX_SNAKE;
    return g.body[idx];
}

// ── game_init ────────────────────────────────────────────────────────────────

/** @param {GameState} g */
function gameInit(g) {
    g.length     = 4;
    g.tail       = 0;
    g.head       = g.length;
    g.dir        = DIR_RIGHT;
    g.pendingDir = DIR_RIGHT;
    g.score      = 0;
    g.gameOver   = false;

    const cy = Math.floor(BOARD_H / 2);
    const cx = Math.floor(BOARD_W / 2) - Math.floor(g.length / 2);
    for (let i = 0; i < g.length; i++) {
        g.body[i].x = cx + i;
        g.body[i].y = cy;
    }
    placeFood(g);
}

// ── game_set_direction ───────────────────────────────────────────────────────

/** @param {GameState} g @param {number} d */
function gameSetDirection(g, d) {
    if (!opposite(g.dir, d)) {
        g.pendingDir = d;
    }
}

// ── game_step ────────────────────────────────────────────────────────────────

/** Advance the game by one tick. @param {GameState} g */
function gameStep(g) {
    if (g.gameOver) return;

    g.dir = g.pendingDir;
    const h = gameHead(g);
    let nx = h.x;
    let ny = h.y;

    switch (g.dir) {
        case DIR_UP:    ny--; break;
        case DIR_DOWN:  ny++; break;
        case DIR_LEFT:  nx--; break;
        case DIR_RIGHT: nx++; break;
    }

    const next    = wrap(nx, ny);
    const eating  = (next.x === g.food.x && next.y === g.food.y);

    // Tentatively remove tail unless eating — lets the snake move into the
    // square the tail is vacating this tick (mirrors game.c behaviour).
    const oldTail   = g.tail;
    const oldLength = g.length;
    if (!eating) {
        g.tail   = (g.tail + 1) % MAX_SNAKE;
        g.length--;
    }

    if (gameIsCellSnake(g, next.x, next.y)) {
        g.tail   = oldTail;
        g.length = oldLength;
        g.gameOver = true;
        return;
    }

    g.body[g.head] = { x: next.x, y: next.y };
    g.head         = (g.head + 1) % MAX_SNAKE;
    g.length++;

    if (eating) {
        g.score += 10;
        placeFood(g);
    }
}

// ── game_tick_ms ─────────────────────────────────────────────────────────────

/** @param {GameState} g @returns {number} milliseconds */
function gameTickMs(g) {
    const base   = 130;
    const fast   = 55;
    const growth = g.length - 4;
    return Math.max(fast, base - growth * 2);
}

// ── Rendering ────────────────────────────────────────────────────────────────

const canvas  = /** @type {HTMLCanvasElement} */ (document.getElementById("canvas"));
const ctx     = /** @type {CanvasRenderingContext2D} */ (canvas.getContext("2d"));
const elScore  = document.getElementById("score");
const elLength = document.getElementById("length");

canvas.width  = BOARD_W * CELL;
canvas.height = BOARD_H * CELL;

const COLOR_BG     = "#111111";
const COLOR_SNAKE  = "#6abf40";
const COLOR_HEAD   = "#c8f56a";
const COLOR_FOOD   = "#f5a623";
const COLOR_OVERLAY = "rgba(0,0,0,0.72)";
const COLOR_TEXT    = "#c8f56a";

/** @param {GameState} g */
function renderFrame(g) {
    // Background
    ctx.fillStyle = COLOR_BG;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Food
    ctx.fillStyle = COLOR_FOOD;
    ctx.beginPath();
    const fx = g.food.x * CELL + CELL / 2;
    const fy = g.food.y * CELL + CELL / 2;
    ctx.arc(fx, fy, CELL / 2 - 2, 0, 2 * Math.PI);
    ctx.fill();

    // Snake body
    const headPt = gameHead(g);
    let i = g.tail;
    for (let n = 0; n < g.length; n++) {
        const seg = g.body[i];
        ctx.fillStyle = (seg.x === headPt.x && seg.y === headPt.y) ? COLOR_HEAD : COLOR_SNAKE;
        ctx.fillRect(seg.x * CELL + 1, seg.y * CELL + 1, CELL - 2, CELL - 2);
        i = (i + 1) % MAX_SNAKE;
    }

    // HUD
    if (elScore)  elScore.textContent  = String(g.score);
    if (elLength) elLength.textContent = String(g.length);
}

/** @param {GameState} g */
function renderGameOver(g) {
    renderFrame(g);

    ctx.fillStyle = COLOR_OVERLAY;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = COLOR_TEXT;
    ctx.font      = "bold 28px 'Courier New', monospace";
    ctx.textAlign = "center";
    ctx.fillText("GAME OVER", canvas.width / 2, canvas.height / 2 - 24);

    ctx.font = "18px 'Courier New', monospace";
    ctx.fillText(`Score: ${g.score}`, canvas.width / 2, canvas.height / 2 + 8);

    ctx.font      = "14px 'Courier New', monospace";
    ctx.fillStyle = "#aaaaaa";
    ctx.fillText("Press R to restart", canvas.width / 2, canvas.height / 2 + 36);
}

// ── Input handling ───────────────────────────────────────────────────────────

/**
 * Keys that must not scroll the page while playing.
 * @type {Set<string>}
 */
const GAME_KEYS = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]);

document.addEventListener("keydown", (e) => {
    if (GAME_KEYS.has(e.key)) e.preventDefault();

    switch (e.key) {
        case "ArrowUp":    case "w": case "W": gameSetDirection(state, DIR_UP);    break;
        case "ArrowDown":  case "s": case "S": gameSetDirection(state, DIR_DOWN);  break;
        case "ArrowLeft":  case "a": case "A": gameSetDirection(state, DIR_LEFT);  break;
        case "ArrowRight": case "d": case "D": gameSetDirection(state, DIR_RIGHT); break;
        case "r": case "R":
            if (state.gameOver || !running) restart();
            break;
    }
});

// ── Game loop ────────────────────────────────────────────────────────────────

/** @type {GameState} */
const state = makeState();

let running     = false;
let timeoutId   = 0;

function tick() {
    gameStep(state);
    if (state.gameOver) {
        running = false;
        renderGameOver(state);
        return;
    }
    renderFrame(state);
    timeoutId = setTimeout(tick, gameTickMs(state));
}

function start() {
    gameInit(state);
    renderFrame(state);
    running   = true;
    timeoutId = setTimeout(tick, gameTickMs(state));
}

function restart() {
    clearTimeout(timeoutId);
    start();
}

// Kick off on page load.
start();
