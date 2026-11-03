#ifndef MAIN_H
#define MAIN_H

#include <stdint.h>
#include <stdbool.h>

enum INPUT
{
    INPUT_UP,
    INPUT_DOWN,
    INPUT_LEFT,
    INPUT_RIGHT,
    INPUT_A,
    INPUT_B,
    INPUT_X,
    INPUT_Y,
    INPUT_START,
    INPUT_SELECT,
    INPUT_L,
    INPUT_R,
    MAX_INPUT
};

void debug_log(const char *message);
void debug_logf(const char *format, ...);
// Add a sprite to the offscreen sprite buffer and return its index
uint8_t add_sprite(uint16_t x, uint8_t y, uint8_t sprite);
// Clear the sprite buffer and render empty sprites on the screen
void clear_sprites(void);
// Reset the offscreen sprite buffer without rendering
void reset_sprites(void);
// Render the current offscreen sprite buffer to the screen
void render_sprites(void);
// Draw data to the foreground tilemap
void draw_fg(const uint8_t *data, uint8_t x, uint8_t y, uint8_t width, uint8_t height);
// Draw data to the background tilemap
void draw_bg(const uint8_t *data, uint8_t x, uint8_t y, uint8_t width, uint8_t height);
// Load a palette into the graphics context
void load_palette(const uint16_t *palette, uint8_t offset, uint8_t count);
// Load a tileset into the graphics context
void load_tileset(const uint8_t *tileset, uint16_t offset, uint16_t size, uint8_t palette_base);
// Initialize the host environment for the game
void memo_host_initialize(void);
// Handle input for the game
void game_handle_input(uint8_t input, bool pressed);
// Update the game state
void game_update(uint16_t elapsed);
// Draw the game state to the screen
void game_draw(void);

#endif