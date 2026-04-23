#include "render.h"

#include <stdio.h>
#include <windows.h>

#ifndef ENABLE_VIRTUAL_TERMINAL_PROCESSING
#define ENABLE_VIRTUAL_TERMINAL_PROCESSING 0x0004
#endif

static void enable_vt(void) {
    HANDLE h = GetStdHandle(STD_OUTPUT_HANDLE);
    DWORD mode = 0;
    if (GetConsoleMode(h, &mode)) {
        SetConsoleMode(h, mode | ENABLE_VIRTUAL_TERMINAL_PROCESSING);
    }
}

void render_init(void) {
    enable_vt();
    printf("\x1b[?25l\x1b[2J\x1b[H");
    fflush(stdout);
}

void render_shutdown(void) {
    printf("\x1b[?25h\x1b[%d;1H\n", BOARD_H + 6);
    fflush(stdout);
}

static void draw_border(void) {
    printf("\x1b[1;1H+");
    for (int x = 0; x < BOARD_W * 2; x++) putchar('-');
    printf("+");

    for (int y = 0; y < BOARD_H; y++) {
        printf("\x1b[%d;1H|", y + 2);
        printf("\x1b[%d;%dH|", y + 2, BOARD_W * 2 + 2);
    }

    printf("\x1b[%d;1H+", BOARD_H + 2);
    for (int x = 0; x < BOARD_W * 2; x++) putchar('-');
    printf("+");
}

void render_frame(const Game *g) {
    printf("\x1b[H");
    draw_border();

    for (int y = 0; y < BOARD_H; y++) {
        printf("\x1b[%d;2H", y + 2);
        for (int x = 0; x < BOARD_W; x++) {
            if (game_cell_is_snake(g, x, y)) {
                fputs("##", stdout);
            } else if (g->food.x == x && g->food.y == y) {
                fputs("()", stdout);
            } else {
                fputs("  ", stdout);
            }
        }
    }

    printf("\x1b[%d;1H  MATOPELI   score: %-6d  length: %-4d   [Q] quit\x1b[K",
           BOARD_H + 3, g->score, g->length);
    fflush(stdout);
}

void render_game_over(const Game *g) {
    int row = BOARD_H / 2 + 1;
    int col = (BOARD_W * 2 + 2) / 2 - 10;
    if (col < 2) col = 2;
    printf("\x1b[%d;%dH  *** GAME OVER ***  ", row, col);
    printf("\x1b[%d;%dH  score: %-6d        ", row + 1, col, g->score);
    printf("\x1b[%d;1H  [R] restart   [Q] quit\x1b[K", BOARD_H + 4);
    fflush(stdout);
}
