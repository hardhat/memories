#ifndef SCREEN_H
#define SCREEN_H

/* Screen compositor (script/screen-spec.md). Requests are recorded in game_update();
 * every VRAM write happens in screen_draw(), once per frame right after vblank starts,
 * and a frame performs at most one tile upload.
 *
 * The box is six 8 px text lines (three tile rows). Each content call lays the lines
 * out, compares them with what is already in VRAM, and uploads only the rows that
 * changed. All strings are copied; lines are cut at the column limit. */

#include <stdbool.h>
#include <stdint.h>

#define SCREEN_NAME_MAX 16
#define SCREEN_LIST_ROWS 5   /* item lines in a list: line 0 is the header */

/* Load the dialog palette and the static tiles. Call after gfx_initialize(). */
void screen_init(void);

/* Advance timers (marker blink). elapsed is in milliseconds. */
void screen_update(uint16_t elapsed);

/* Perform the pending VRAM work for this frame. Returns true if it uploaded tiles, so the
 * caller can keep the frame to one upload (the portraits use what is left). */
bool screen_draw(void);

/* Dialog: name plate on line 0 (NULL or empty for none; ignored for style 2, credits) and
 * the text on lines 1-3, split at '\n'. */
void screen_text_show(const char *name, const char *text, uint8_t style);

/* Choice menu: prompt lines first (may be empty), then each option; option k keeps at
 * least one line even when the total exceeds six. Option 0 starts selected. */
void screen_menu_show(const char *prompt, const char *const *options, uint8_t n);
void screen_menu_select(uint8_t selected);

/* Scrolling list of single-line items under a header line; " k/n" is appended to the
 * header when the list needs scrolling. items must stay valid until the box is hidden. */
void screen_list_show(const char *header, const char *const *items, uint8_t n, uint8_t selected);
void screen_list_select(uint8_t selected);

/* Remove the box at the next screen_draw(). The art underneath is untouched. */
void screen_text_hide(void);

/* True once everything requested is on screen. */
bool screen_text_ready(void);

/* True when the box is hidden and nothing is pending, so the text slots (1-60) hold no
 * content that matters and may be overwritten (by a CG). */
bool screen_text_idle(void);

/* Forget what the text slots hold, after something else wrote to them: the next content
 * re-uploads every row. */
void screen_invalidate(void);

/* Put the box over the bottom three rows of a CG (true) or at the bottom of the screen (false).
 * A box that is on screen moves at once. Draw phase only. */
void screen_set_layout(bool cg);

/* Show or hide the blinking continue arrow (only visible while the text is ready). */
void screen_text_marker(bool on);

#endif
