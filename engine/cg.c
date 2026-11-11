#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "main.h"
#include "layout.h"
#include "memo_dat.h"
#include "screen.h"
#include "stream.h"
#include "cg.h"

#define TILE_BYTES    256u
#define TILES_HEADER  4      /* TILESET block: bpp, comp, tile_count u16 */
#define PAL_HEADER    2      /* PALETTE block: first, last */

enum { CG_NONE, CG_LOADING, CG_SHOWN };

static uint8_t  state;
static uint8_t  current;                /* CG id of the request */
static bool     wanted;                 /* cg_show() without a later cg_hide() */
static uint16_t tiles_block, pal_block;
static uint8_t  top_done;               /* tiles of the top nine rows resident */
static uint8_t  bottom_done;            /* tiles of the bottom three rows resident in slots 1-60 */
static bool     cells_up;               /* the layer 0 cells point at the CG */

void cg_init(void)
{
    state = CG_NONE;
    current = 0;
    wanted = false;
    top_done = 0;
    bottom_done = 0;
    cells_up = false;
}

/* The art must be a 240 tile, 8bpp, uncompressed picture without a tile map, with a palette
 * slice inside the world range. Nothing is written to VRAM here. */
static bool check(uint8_t id, uint16_t *tiles, uint16_t *pal)
{
    uint16_t ids[3];
    uint8_t t[TILES_HEADER], p[PAL_HEADER];
    DatEntry e;

    if (!dat_index_get(DAT_TABLE_CGS, id, ids) || ids[0] == 0 || ids[1] != 0 || ids[2] == 0) {
        return false;
    }
    if (!dat_read_block(ids[0], 0, t, TILES_HEADER) || t[0] != 8 || t[1] != 0
        || t[2] != (CG_TILES & 0xFF) || t[3] != (CG_TILES >> 8)
        || !dat_entry(ids[0], &e) || e.size < TILES_HEADER + CG_TILES * TILE_BYTES) {
        return false;
    }
    if (!dat_read_block(ids[2], 0, p, PAL_HEADER) || p[0] < PAL_WORLD || p[1] > PAL_WORLD_LAST || p[1] < p[0]
        || !dat_entry(ids[2], &e) || e.size != PAL_HEADER + (p[1] - p[0] + 1) * 2) {
        return false;
    }
    *tiles = ids[0];
    *pal = ids[2];
    return true;
}

bool cg_show(uint8_t id)
{
    uint16_t tiles, pal;

    if (wanted && state != CG_NONE && id == current) {
        return true;
    }
    wanted = false;
    if (!check(id, &tiles, &pal)) {
        debug_logf("CG %u cannot be shown (missing, or not baked for palette %u-%u)", id, PAL_WORLD, PAL_WORLD_LAST);
        return false;
    }
    current = id;
    tiles_block = tiles;
    pal_block = pal;
    wanted = true;
    state = CG_LOADING;
    top_done = 0;
    bottom_done = 0;
    return true;
}

void cg_hide(void)
{
    wanted = false;
}

bool cg_active(void)
{
    return wanted;
}

bool cg_ready(void)
{
    return !wanted || state == CG_SHOWN;
}

static void clear_bg(void)
{
    uint8_t zeros[SCREEN_COLS];
    uint8_t row;

    memset(zeros, 0, sizeof zeros);
    for (row = 0; row < SCREEN_ROWS; row++) {
        draw_bg(zeros, 0, row, SCREEN_COLS, 1);
    }
    cells_up = false;
}

static bool fail(void)
{
    debug_logf("CG %u: read failed", current);
    wanted = false;
    return false;
}

/* One chunk of the bottom three rows into the text slots. The text cache goes stale with the
 * first one. */
static bool restore_bottom(void)
{
    uint8_t n = CG_BOTTOM_TILES - bottom_done;

    if (bottom_done == 0) {
        screen_invalidate();
    }
    if (n > STREAM_CHUNK_TILES) {
        n = STREAM_CHUNK_TILES;
    }
    if (!stream_tiles(tiles_block, CG_TOP_TILES + bottom_done, n, SLOT_DIALOG + bottom_done)) {
        return fail();
    }
    bottom_done += n;
    return true;
}

/* Everything is resident: load the palette and point the cells at the picture, all in one frame. */
static void reveal(void)
{
    uint8_t cells[SCREEN_COLS];
    uint8_t row, col;

    if (!stream_palette(pal_block, PAL_WORLD, PAL_WORLD_LAST)) {
        fail();
        return;
    }
    for (row = 0; row < SCREEN_ROWS; row++) {
        for (col = 0; col < SCREEN_COLS; col++) {
            if (row < CG_TOP_ROWS) {
                cells[col] = (uint8_t)(SLOT_CG_TOP + row * SCREEN_COLS + col);
            } else if (row < CG_ROWS) {
                cells[col] = (uint8_t)(SLOT_DIALOG + (row - CG_TOP_ROWS) * SCREEN_COLS + col);
            } else {
                cells[col] = SLOT_EMPTY;
            }
        }
        draw_bg(cells, 0, row, SCREEN_COLS, 1);
    }
    screen_set_layout(true);
    cells_up = true;
    state = CG_SHOWN;
}

bool cg_draw(bool upload_ok)
{
    uint8_t n;

    if (!wanted) {
        if (state != CG_NONE) {
            if (cells_up) {
                clear_bg();
            }
            screen_set_layout(false);
            state = CG_NONE;
        }
        return false;
    }
    if (!screen_text_idle()) {
        bottom_done = 0;       /* the text owns slots 1-60 now */
    }

    if (state == CG_LOADING) {
        if (top_done < CG_TOP_TILES) {
            if (!upload_ok) {
                return false;
            }
            if (cells_up) {
                clear_bg();    /* a CG on screen is replaced: nothing visible may point at slots being rewritten */
            }
            n = CG_TOP_TILES - top_done;
            if (n > STREAM_CHUNK_TILES) {
                n = STREAM_CHUNK_TILES;
            }
            if (!stream_tiles(tiles_block, top_done, n, SLOT_CG_TOP + top_done)) {
                return fail();
            }
            top_done += n;
            return true;
        }
        if (bottom_done < CG_BOTTOM_TILES && screen_text_idle()) {
            return upload_ok && restore_bottom();
        }
        if ((bottom_done == CG_BOTTOM_TILES && screen_text_idle()) || screen_text_ready()) {
            reveal();
        }
        return false;
    }

    /* On screen: when the text goes away, bring the picture's bottom rows back. */
    if (bottom_done < CG_BOTTOM_TILES && screen_text_idle() && upload_ok) {
        return restore_bottom();
    }
    return false;
}
