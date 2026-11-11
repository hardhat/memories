#ifndef CG_H
#define CG_H

/* CG mode (script/screen-spec.md section 4b): a 320x192 8bpp picture on layer 0, tile rows 0-11.
 * Its top nine rows (180 tiles) stream into slots 64-243. Its bottom three rows (60 tiles) share
 * the text slots 1-60: they are streamed in while no text is up, and the text box, which then
 * sits over them (rows 9-11), replaces them when it is shown.
 *
 * cg_show() and cg_hide() only record a request; every VRAM write happens in cg_draw(), which
 * gets one chunk of the frame's upload budget. A CG stays invisible until its tiles are in
 * (one chunk per frame, so a CG takes about half a second), then appears at once. Art must be
 * baked to the world palette range 126-252 (screen-spec.md section 3); anything else is refused. */

#include <stdbool.h>
#include <stdint.h>

/* Forget everything. Call after screen_init(). */
void cg_init(void);

/* Ask for CG `id`. Returns false, and shows no CG, if the art is missing, is not a baked
 * 320x192 8bpp uncompressed picture, or its palette is outside 126-252. Reads memo.dat, so call
 * it from game_update(), not game_draw(). Asking for the CG already shown does nothing. */
bool cg_show(uint8_t id);

/* Take the CG down at the next cg_draw(). */
void cg_hide(void);

/* True from cg_show() until cg_hide(): the CG is up or on its way, so the box belongs over its
 * bottom rows and there are no portraits. */
bool cg_active(void);

/* True once nothing is left to load for a requested CG (it is on screen), or no CG is wanted. */
bool cg_ready(void);

/* Do this frame's VRAM work. upload_ok says whether the frame's one tile upload is still free.
 * Returns true if it uploaded. */
bool cg_draw(bool upload_ok);

#endif
