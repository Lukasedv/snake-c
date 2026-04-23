#ifndef SNAKE_RENDER_H
#define SNAKE_RENDER_H

#include "game.h"

void render_init(void);
void render_shutdown(void);
void render_frame(const Game *g);
void render_game_over(const Game *g);

#endif
