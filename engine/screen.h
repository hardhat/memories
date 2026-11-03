#ifndef SCREEN_H
#define SCREEN_H

/* Screen compositor (script/screen-spec.md). Requests are recorded in game_update();
 * every VRAM write happens in screen_draw(), once per frame right after vblank starts,
 * and a frame performs at most one tile upload. */

#include <stdbool.h>
#include <stdint.h>

#define SCREEN_NAME_MAX 16

/* Load the dialog palette and the static tiles. Call after gfx_initialize(). */
void screen_init(void);

/* Advance timers (marker blink). elapsed is in milliseconds. */
void screen_update(uint16_t elapsed);

/* Perform the pending VRAM work for this frame. */
void screen_draw(void);

/* Show text in the box. name may be NULL or empty; text is split at '\n' into at most
 * three lines. Both strings are copied. Replaces any text already shown. */
void screen_text_show(const char *name, const char *text, uint8_t style);

/* Remove the box at the next screen_draw(). The art underneath is untouched. */
void screen_text_hide(void);

/* True once every row of the current text is on screen. */
bool screen_text_ready(void);

/* Show or hide the blinking continue arrow (only visible while the text is ready). */
void screen_text_marker(bool on);

#endif
