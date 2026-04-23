#include "game.h"

#include <stdlib.h>

static Point wrap(int x, int y) {
    if (x < 0) x = BOARD_W - 1;
    if (x >= BOARD_W) x = 0;
    if (y < 0) y = BOARD_H - 1;
    if (y >= BOARD_H) y = 0;
    Point p = {x, y};
    return p;
}

static bool opposite(Direction a, Direction b) {
    return (a == DIR_UP && b == DIR_DOWN) ||
           (a == DIR_DOWN && b == DIR_UP) ||
           (a == DIR_LEFT && b == DIR_RIGHT) ||
           (a == DIR_RIGHT && b == DIR_LEFT);
}

static void place_food(Game *g) {
    for (;;) {
        int x = rand() % BOARD_W;
        int y = rand() % BOARD_H;
        if (!game_cell_is_snake(g, x, y)) {
            g->food.x = x;
            g->food.y = y;
            return;
        }
    }
}

bool game_cell_is_snake(const Game *g, int x, int y) {
    int i = g->tail;
    for (int n = 0; n < g->length; n++) {
        if (g->body[i].x == x && g->body[i].y == y) return true;
        i = (i + 1) % MAX_SNAKE;
    }
    return false;
}

Point game_head(const Game *g) {
    int idx = (g->head - 1 + MAX_SNAKE) % MAX_SNAKE;
    return g->body[idx];
}

void game_init(Game *g) {
    g->length = 4;
    g->tail = 0;
    g->head = g->length;
    int cy = BOARD_H / 2;
    int cx = BOARD_W / 2 - g->length / 2;
    for (int i = 0; i < g->length; i++) {
        g->body[i].x = cx + i;
        g->body[i].y = cy;
    }
    g->dir = DIR_RIGHT;
    g->pending_dir = DIR_RIGHT;
    g->score = 0;
    g->game_over = false;
    place_food(g);
}

void game_set_direction(Game *g, Direction d) {
    if (!opposite(g->dir, d)) {
        g->pending_dir = d;
    }
}

void game_step(Game *g) {
    if (g->game_over) return;

    g->dir = g->pending_dir;
    Point h = game_head(g);
    int nx = h.x, ny = h.y;
    switch (g->dir) {
        case DIR_UP:    ny--; break;
        case DIR_DOWN:  ny++; break;
        case DIR_LEFT:  nx--; break;
        case DIR_RIGHT: nx++; break;
    }
    Point next = wrap(nx, ny);

    bool eating = (next.x == g->food.x && next.y == g->food.y);

    // Tentatively remove the tail unless eating — so self-collision check
    // allows moving into the square the tail is vacating this tick.
    int old_tail = g->tail;
    int old_length = g->length;
    if (!eating) {
        g->tail = (g->tail + 1) % MAX_SNAKE;
        g->length--;
    }

    if (game_cell_is_snake(g, next.x, next.y)) {
        g->tail = old_tail;
        g->length = old_length;
        g->game_over = true;
        return;
    }

    g->body[g->head] = next;
    g->head = (g->head + 1) % MAX_SNAKE;
    g->length++;

    if (eating) {
        g->score += 10;
        place_food(g);
    }
}

int game_tick_ms(const Game *g) {
    int base = 130;
    int fast = 55;
    int growth = g->length - 4;
    int ms = base - growth * 2;
    if (ms < fast) ms = fast;
    return ms;
}
