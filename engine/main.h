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

// The off-screen text buffer is a 320x16 pixel  (20x1 tile) area used for off-screen 
//  text rendering before being displayed on the screen
// Clear the off screen text buffer with the specified color, all 20 tiles across
void clear_text_buffer(uint8_t color);
// Draw a single pixel in the text buffer
void draw_text_pixel(uint16_t x, uint8_t y, uint8_t color);
// Draw a single pixel in the text buffer at the specified offset
void draw_text_pixel_offset(uint16_t offset, uint8_t color);
// Draw a character to the text buffer
void draw_text_char(uint16_t x, uint8_t y, uint8_t c, uint8_t color);
// Draw a string of text to the text buffer
void draw_text(uint16_t x, uint8_t y, const char *text, uint8_t color);
// Draw a character to the text buffer with opaque background
void draw_char_opaque(uint16_t x, uint8_t y, uint8_t c, uint8_t fg, uint8_t bg);
// Draw a string of text to the text buffer with opaque background
void draw_text_opaque(uint16_t x, uint8_t y, const char *text, uint8_t fg, uint8_t bg);
// Render the off-screen text buffer to the screen tileset
/// @param first_tile The index of the first tile of the tile set to render to
/// @param num_tiles The number of tiles to render (up to 20)
void render_text_buffer(uint16_t first_tile, uint16_t num_tiles);

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