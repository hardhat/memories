#ifndef GAME_H
#define GAME_H

#include <stdbool.h>
#include <stdint.h>

void game_initialize(void);
void game_host_update(uint16_t elapsed);
void game_host_draw(void);
void game_host_input(uint8_t input);

#endif
