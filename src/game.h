#ifndef SNAKE_GAME_H
#define SNAKE_GAME_H

#include <stdbool.h>

#define BOARD_W 30
#define BOARD_H 18
#define MAX_SNAKE (BOARD_W * BOARD_H)

typedef enum {
    DIR_UP,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT
} Direction;

typedef struct {
    int x;
    int y;
} Point;

typedef struct {
    Point body[MAX_SNAKE];
    int head;
    int tail;
    int length;
    Direction dir;
    Direction pending_dir;
    Point food;
    int score;
    bool game_over;
} Game;

void game_init(Game *g);
void game_set_direction(Game *g, Direction d);
void game_step(Game *g);
bool game_cell_is_snake(const Game *g, int x, int y);
Point game_head(const Game *g);
int game_tick_ms(const Game *g);

#endif
