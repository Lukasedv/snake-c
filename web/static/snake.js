/**
 * snake.js — Browser port of the C snake game (game.c / main.c / render.c).
 *
 * Faithfully mirrors:
 *   • 30×18 board with wrap-around walls
 *   • Circular-buffer snake body (MAX_SNAKE = 540)
 *   • Tentative-tail-removal self-collision check
 *   • Speed ramp: 130 ms base → 55 ms floor, −2 ms per growth unit
 *   • Arrow + WASD steering with 180° reversal block (pending_dir pattern)
 *   • R = restart, Space = pause
 */

"use strict";

// ---------------------------------------------------------------------------
// Constants (mirrors game.h)
// ---------------------------------------------------------------------------
const BOARD_W   = 30;
const BOARD_H   = 18;
const MAX_SNAKE = BOARD_W * BOARD_H;  // 540
const CELL      = 24;                 // px per cell  →  720×432 canvas

const DIR_UP    = 0;
const DIR_DOWN  = 1;
const DIR_LEFT  = 2;
const DIR_RIGHT = 3;

// ---------------------------------------------------------------------------
// Game state (mirrors Game struct)
// ---------------------------------------------------------------------------
let bodyX, bodyY;   // circular buffer arrays (length MAX_SNAKE)
let head, tail, length, dir, pendingDir;
let foodX, foodY, score, gameOver;
let paused = false;
let tickHandle = null;

// ---------------------------------------------------------------------------
// Canvas / DOM
// ---------------------------------------------------------------------------
const canvas   = document.getElementById("game-canvas");
const ctx      = canvas.getContext("2d");
const scoreEl  = document.getElementById("score");
const lengthEl = document.getElementById("length");
const statusEl = document.getElementById("status-msg");

const overlay      = document.getElementById("overlay");
const overlayScore = document.getElementById("overlay-score");
const playerName   = document.getElementById("player-name");
const btnSubmit    = document.getElementById("btn-submit");
const btnSkip      = document.getElementById("btn-skip");
const leaderboard  = document.getElementById("leaderboard");

// ---------------------------------------------------------------------------
// Helpers — mirror game.c statics
// ---------------------------------------------------------------------------
function wrap(x, y) {
    if (x < 0)       x = BOARD_W - 1;
    if (x >= BOARD_W) x = 0;
    if (y < 0)       y = BOARD_H - 1;
    if (y >= BOARD_H) y = 0;
    return { x, y };
}

function opposite(a, b) {
    return (a === DIR_UP    && b === DIR_DOWN)  ||
           (a === DIR_DOWN  && b === DIR_UP)    ||
           (a === DIR_LEFT  && b === DIR_RIGHT) ||
           (a === DIR_RIGHT && b === DIR_LEFT);
}

function cellIsSnake(x, y) {
    let i = tail;
    for (let n = 0; n < length; n++) {
        if (bodyX[i] === x && bodyY[i] === y) return true;
        i = (i + 1) % MAX_SNAKE;
    }
    return false;
}

function placeFood() {
    for (;;) {
        const x = Math.floor(Math.random() * BOARD_W);
        const y = Math.floor(Math.random() * BOARD_H);
        if (!cellIsSnake(x, y)) { foodX = x; foodY = y; return; }
    }
}

function gameHead() {
    const idx = (head - 1 + MAX_SNAKE) % MAX_SNAKE;
    return { x: bodyX[idx], y: bodyY[idx] };
}

function tickMs() {
    const base   = 130;
    const fast   = 55;
    const growth = length - 4;
    return Math.max(fast, base - growth * 2);
}

// ---------------------------------------------------------------------------
// game_init
// ---------------------------------------------------------------------------
function gameInit() {
    bodyX = new Int16Array(MAX_SNAKE);
    bodyY = new Int16Array(MAX_SNAKE);
    length = 4;
    tail   = 0;
    head   = length;

    const cy = Math.floor(BOARD_H / 2);
    const cx = Math.floor(BOARD_W / 2) - Math.floor(length / 2);
    for (let i = 0; i < length; i++) {
        bodyX[i] = cx + i;
        bodyY[i] = cy;
    }

    dir        = DIR_RIGHT;
    pendingDir = DIR_RIGHT;
    score      = 0;
    gameOver   = false;
    paused     = false;

    placeFood();
}

// ---------------------------------------------------------------------------
// game_step (mirrors game.c game_step exactly)
// ---------------------------------------------------------------------------
function gameStep() {
    if (gameOver) return;

    dir = pendingDir;
    const h = gameHead();
    let nx = h.x, ny = h.y;

    switch (dir) {
        case DIR_UP:    ny--; break;
        case DIR_DOWN:  ny++; break;
        case DIR_LEFT:  nx--; break;
        case DIR_RIGHT: nx++; break;
    }
    const next = wrap(nx, ny);

    const eating = (next.x === foodX && next.y === foodY);

    // Tentatively remove tail (unless eating) so self-collision allows
    // moving into the square the tail is vacating this tick.
    const oldTail   = tail;
    const oldLength = length;
    if (!eating) {
        tail   = (tail + 1) % MAX_SNAKE;
        length--;
    }

    if (cellIsSnake(next.x, next.y)) {
        tail   = oldTail;
        length = oldLength;
        gameOver = true;
        return;
    }

    bodyX[head] = next.x;
    bodyY[head] = next.y;
    head   = (head + 1) % MAX_SNAKE;
    length++;

    if (eating) {
        score += 10;
        placeFood();
    }
}

// ---------------------------------------------------------------------------
// game_set_direction
// ---------------------------------------------------------------------------
function gameSetDirection(d) {
    if (!opposite(dir, d)) pendingDir = d;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------
const COLOR_BG     = "#1a1a1a";
const COLOR_BORDER = "#4cff91";
const COLOR_SNAKE  = "#4cff91";
const COLOR_HEAD   = "#ffffff";
const COLOR_FOOD   = "#ff5555";
const COLOR_TEXT   = "#ffffff";

function render() {
    ctx.fillStyle = COLOR_BG;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw food
    ctx.fillStyle = COLOR_FOOD;
    ctx.fillRect(foodX * CELL + 2, foodY * CELL + 2, CELL - 4, CELL - 4);

    // Draw snake body
    const hIdx = (head - 1 + MAX_SNAKE) % MAX_SNAKE;
    let i = tail;
    for (let n = 0; n < length; n++) {
        const isHead = (i === hIdx);
        ctx.fillStyle = isHead ? COLOR_HEAD : COLOR_SNAKE;
        ctx.fillRect(bodyX[i] * CELL + 1, bodyY[i] * CELL + 1, CELL - 2, CELL - 2);
        i = (i + 1) % MAX_SNAKE;
    }

    // Game over overlay on canvas
    if (gameOver) {
        ctx.fillStyle = "rgba(0,0,0,0.55)";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#ff5555";
        ctx.font = "bold 36px 'Segoe UI', sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("GAME OVER", canvas.width / 2, canvas.height / 2 - 16);
        ctx.fillStyle = "#fff";
        ctx.font = "20px 'Segoe UI', sans-serif";
        ctx.fillText(`Score: ${score}`, canvas.width / 2, canvas.height / 2 + 20);
        ctx.textAlign = "left";
    } else if (paused) {
        ctx.fillStyle = "rgba(0,0,0,0.45)";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#fff";
        ctx.font = "bold 30px 'Segoe UI', sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("PAUSED", canvas.width / 2, canvas.height / 2);
        ctx.textAlign = "left";
    }

    // HUD
    scoreEl.textContent  = score;
    lengthEl.textContent = length;
    statusEl.textContent = gameOver ? "Game Over" : paused ? "Paused" : "";
}

// ---------------------------------------------------------------------------
// Game loop
// ---------------------------------------------------------------------------
function scheduleNext() {
    if (tickHandle !== null) clearTimeout(tickHandle);
    tickHandle = setTimeout(tick, tickMs());
}

function tick() {
    tickHandle = null;
    if (paused || gameOver) return;
    gameStep();
    render();
    if (gameOver) {
        showOverlay();
    } else {
        scheduleNext();
    }
}

function startGame() {
    if (tickHandle !== null) { clearTimeout(tickHandle); tickHandle = null; }
    gameInit();
    render();
    scheduleNext();
}

// ---------------------------------------------------------------------------
// High-score overlay
// ---------------------------------------------------------------------------
function showOverlay() {
    overlayScore.textContent = score;
    playerName.value = "";
    overlay.classList.remove("hidden");
    playerName.focus();
}

function hideOverlay() {
    overlay.classList.add("hidden");
}

function getPlayerName() {
    return playerName.value.trim() || "Anonymous";
}

async function submitScore(name) {
    try {
        await fetch("/api/scores", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name.trim() || "Anonymous", score }),
        });
        await refreshLeaderboard();
    } catch (err) {
        console.warn("Could not submit score:", err);
    }
}

async function refreshLeaderboard() {
    try {
        const res = await fetch("/api/scores");
        if (!res.ok) return;
        const scores = await res.json();
        leaderboard.innerHTML = scores.map(s =>
            `<li><span class="lb-name">${escHtml(s.name)}</span><span class="lb-score">${s.score}</span></li>`
        ).join("");
    } catch (err) {
        console.warn("Could not load leaderboard:", err);
    }
}

function escHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ---------------------------------------------------------------------------
// Input handling
// ---------------------------------------------------------------------------
document.addEventListener("keydown", (e) => {
    // Prevent arrow keys from scrolling the page
    if (["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"," "].includes(e.key)) {
        e.preventDefault();
    }

    // Don't hijack typing in the name input
    if (document.activeElement === playerName) return;

    switch (e.key) {
        case "ArrowUp":    case "w": case "W": gameSetDirection(DIR_UP);    break;
        case "ArrowDown":  case "s": case "S": gameSetDirection(DIR_DOWN);  break;
        case "ArrowLeft":  case "a": case "A": gameSetDirection(DIR_LEFT);  break;
        case "ArrowRight": case "d": case "D": gameSetDirection(DIR_RIGHT); break;
        case " ":
            if (!gameOver) {
                paused = !paused;
                if (!paused) scheduleNext();
                render();
            }
            break;
        case "r": case "R":
            hideOverlay();
            startGame();
            break;
    }
});

// Overlay buttons
btnSubmit.addEventListener("click", async () => {
    const name = getPlayerName();
    hideOverlay();
    await submitScore(name);
    startGame();
});

btnSkip.addEventListener("click", () => {
    hideOverlay();
    startGame();
});

// Submit on Enter in name field
playerName.addEventListener("keydown", (e) => {
    if (e.key === "Enter") btnSubmit.click();
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
refreshLeaderboard();
startGame();
