#ifndef LAYOUT_H
#define LAYOUT_H

/* The screen contract (script/screen-spec.md): one 256-slot tileset shared by every
 * layer and sprite, and fixed tile rows for the dialog overlay. Slots and palette
 * indices are baked into the art by the asset tools, never remapped at run time. */

#define SCREEN_COLS        20
#define SCREEN_ROWS        15

/* Hardware tile slots (8bpp tilemap entries are one byte). */
#define SLOT_EMPTY         0
#define SLOT_DIALOG        1      /* 1-60: three rows of text tiles */
#define DIALOG_TILES       60
#define SLOT_MARKER        61     /* continue arrow */
#define SLOT_PORTRAIT_LEFT 64     /* 64-113 */
#define SLOT_PORTRAIT_RIGHT 114   /* 114-163 */
#define SLOT_WORLD         164    /* 164-255: scenery, sprites, effects */

/* Top tile row of the three-row text box. A CG covers tile rows 0-11, so the box
 * moves up over the CG's bottom three rows (see screen-spec.md). */
#define TEXT_ROWS          3
#define ROW_TEXT_MAP       12
#define ROW_TEXT_CG        9

/* Palette indices. 0 is shared: transparent on layer 1 and sprites, black on layer 0. */
#define PAL_TRANSPARENT    0
#define PAL_BOX_BG         1
#define PAL_BOX_FRAME      2
#define PAL_TEXT           3
#define PAL_NAME           4
#define PAL_PHONE          5
#define PAL_CREDITS        6
#define PAL_SELECT_BG      7
#define PAL_MARKER         8
#define PAL_DIALOG_COUNT   9      /* entries defined so far; 0-31 are reserved for dialog */

/* The planned ranges for the remaining art (not loaded yet). */
#define PAL_PORTRAIT_LEFT  32     /* 32-78 */
#define PAL_PORTRAIT_RIGHT 79     /* 79-125 */
#define PAL_WORLD          126    /* 126-252: map, sprites, effects or CG */

#endif
