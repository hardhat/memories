#ifndef PORTRAIT_H
#define PORTRAIT_H

/* Dialog portraits (script/screen-spec.md section 4a). Brad shows on the left, everyone
 * else on the right, as a 2x4 tile bust on layer 1 above the box. Requests are recorded
 * in portrait_show() / portrait_hide(); every VRAM write happens in portrait_draw().
 *
 * A side keeps its character's tiles and palette resident after the portrait is hidden,
 * so a returning speaker costs only tilemap writes. A different character on the same
 * side is hidden, then streamed in (PORTRAIT_CHUNK_TILES per frame), then revealed. An
 * expression change rewrites the head cells and uploads nothing, as long as the head is
 * resident; the old expression stays up until it is. */

#include <stdbool.h>
#include <stdint.h>

#define PORTRAIT_LEFT  0
#define PORTRAIT_RIGHT 1

/* Forget everything (VRAM contents included). Call after screen_init(). */
void portrait_init(void);

/* Show character `who` on `side` (1 left, 2 right, as in CHARS) with expression `expr`.
 * EXPR_NONE or an expression the portrait lacks keeps the current one for that character,
 * or the base image for a new one. A character without art hides that side. The other
 * side is unchanged. Reads memo.dat, so call it from game_update(), not game_draw(). */
void portrait_show(uint8_t who, uint8_t side, uint8_t expr);

/* Hide both sides at the next portrait_draw(). The tiles stay resident. */
void portrait_hide(void);

/* Do this frame's VRAM work: hide, stream one chunk if upload_ok, reveal what is ready.
 * Returns true if it uploaded. */
bool portrait_draw(bool upload_ok);

/* True if `side` (PORTRAIT_LEFT or PORTRAIT_RIGHT) is on screen showing `who`/`expr`. */
bool portrait_visible(uint8_t side, uint8_t *who, uint8_t *expr);

#endif
