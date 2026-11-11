#ifndef FADE_H
#define FADE_H

/* Palette fade (script/screen-spec.md section 4c). The portrait, map, sprite and CG palettes
 * (entries 32-252) are loaded through this module, which keeps the colours the art asked for in a
 * shadow copy and writes them to the video board scaled by the current brightness. The dialog
 * palette (0-31) is never touched, so the text box stays readable. Brightness is 0 (black) to 256
 * (the art's own colours, written without scaling).
 *
 * The host starts a fade (fade_start) and counts the time (fade_update) in game_update();
 * every palette write happens in fade_draw() or fade_palette(), in the draw phase. Art loaded
 * while the screen is black stays black until the fade brings it up. */

#include <stdbool.h>
#include <stdint.h>

#define FADE_FULL 256

/* Brightness full, shadow empty. Call after screen_init(). */
void fade_init(void);

/* Fade to full brightness (clear) or to black over ms milliseconds, from the current brightness.
 * ms == 0 jumps. Fading to where it already is does nothing. */
void fade_start(bool clear, uint16_t ms);

/* Advance a running fade by elapsed milliseconds. */
void fade_update(uint16_t elapsed);

/* Write the palette if the brightness changed since the last call. Call first in the draw phase. */
void fade_draw(void);

/* Load `count` RGB565 colours at palette index `first` through the fade: they are remembered and
 * shown at the current brightness. A range outside 32-252 is written as it is. */
void fade_palette(uint8_t first, const uint16_t *colors, uint8_t count);

/* Scale count RGB565 colours by brightness 0-256 (each channel alue * scale >> 8, rounding down).
 * A building block for anything that fades a palette of its own (the title screen). */
void fade_scale(uint16_t *dst, const uint16_t *src, uint8_t count, uint16_t scale);

/* The brightness, 0-256. */
uint16_t fade_level(void);

/* True while a fade is still running. */
bool fade_active(void);

#endif
