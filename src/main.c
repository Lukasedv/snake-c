#include "game.h"
#include "render.h"

#include <conio.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <windows.h>

static void cleanup(void) {
    render_shutdown();
}

static void on_signal(int sig) {
    (void)sig;
    cleanup();
    exit(0);
}

static void poll_input(Game *g, int *out_quit, int *out_restart) {
    while (_kbhit()) {
        int c = _getch();
        if (c == 0 || c == 0xE0) {
            int code = _getch();
            switch (code) {
                case 0x48: game_set_direction(g, DIR_UP);    break;
                case 0x50: game_set_direction(g, DIR_DOWN);  break;
                case 0x4B: game_set_direction(g, DIR_LEFT);  break;
                case 0x4D: game_set_direction(g, DIR_RIGHT); break;
                default: break;
            }
        } else {
            switch (c) {
                case 'q': case 'Q': *out_quit = 1; return;
                case 'r': case 'R': *out_restart = 1; return;
                // WASD as a bonus — handy on laptops without arrow keys.
                case 'w': case 'W': game_set_direction(g, DIR_UP);    break;
                case 's': case 'S': game_set_direction(g, DIR_DOWN);  break;
                case 'a': case 'A': game_set_direction(g, DIR_LEFT);  break;
                case 'd': case 'D': game_set_direction(g, DIR_RIGHT); break;
                default: break;
            }
        }
    }
}

int main(void) {
    srand((unsigned)time(NULL));
    signal(SIGINT, on_signal);
    atexit(cleanup);
    render_init();

    for (;;) {
        Game g;
        game_init(&g);
        render_frame(&g);

        int quit = 0;
        int restart = 0;

        while (!g.game_over && !quit && !restart) {
            poll_input(&g, &quit, &restart);
            if (quit || restart) break;
            game_step(&g);
            render_frame(&g);
            Sleep(game_tick_ms(&g));
        }

        if (quit) return 0;
        if (restart) continue;

        render_game_over(&g);
        for (;;) {
            int c = _getch();
            if (c == 'q' || c == 'Q') return 0;
            if (c == 'r' || c == 'R') break;
        }
    }
}
