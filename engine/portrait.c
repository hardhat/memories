#include <stdbool.h>
#include <stdint.h>

#include "main.h"
#include "layout.h"
#include "memo_dat.h"
#include "portrait.h"

#define NONE         255
#define HEADER_SIZE  11     /* PORTRAIT block: 7 geometry bytes, tiles block u16, palette block u16 */
#define TILE_BYTES   256u
#define TILES_HEADER 4      /* TILESET block: bpp, comp, tile_count u16 */
#define PAL_MAX      48

typedef struct {
    /* The character whose tiles and palette are in VRAM (or being streamed). */
    uint8_t  who;
    uint16_t tiles_block, pal_block;
    uint8_t  pal_first, pal_count;
    uint8_t  head_x, head_y, head_w, head_h;
    uint8_t  head_tiles, exprs, total;
    uint8_t  loaded;
    bool     pal_done;
    /* What should be on screen, and what the tilemap cells say right now. */
    uint8_t  want_who, want_expr;
    uint8_t  shown_who, shown_expr;
} Side;

static Side sides[2];
static uint8_t chunk[PORTRAIT_CHUNK_TILES * TILE_BYTES];
static uint16_t palette[PAL_MAX];
static const uint8_t blank[PORTRAIT_COLS * PORTRAIT_ROWS];

static uint16_t le16(const uint8_t *p)
{
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static uint8_t slot_base(uint8_t s)
{
    return s == PORTRAIT_LEFT ? SLOT_PORTRAIT_LEFT : SLOT_PORTRAIT_RIGHT;
}

static uint8_t column(uint8_t s)
{
    return s == PORTRAIT_LEFT ? COL_PORTRAIT_LEFT : COL_PORTRAIT_RIGHT;
}

/* Tiles that must be resident to show `expr`: the base, plus heads 1..expr in file order. */
static uint8_t tiles_for(const Side *p, uint8_t expr)
{
    return (uint8_t)(PORTRAIT_COLS * PORTRAIT_ROWS + expr * p->head_tiles);
}

void portrait_init(void)
{
    uint8_t s;

    for (s = 0; s < 2; s++) {
        sides[s].who = NONE;
        sides[s].loaded = 0;
        sides[s].pal_done = false;
        sides[s].want_who = NONE;
        sides[s].want_expr = 0;
        sides[s].shown_who = NONE;
        sides[s].shown_expr = 0;
    }
}

/* Read and check the portrait of character `who` for side `s`. The checks keep a bad file
 * from writing outside the side's slots, palette range or the tilemap. */
static bool load_descriptor(Side *p, uint8_t s, uint8_t who)
{
    DatEntry tiles_entry, pal_entry;
    uint16_t block, total, tile_count;
    uint8_t h[HEADER_SIZE], t[TILES_HEADER], pal[2], lo, hi;

    if (!dat_index_get(DAT_TABLE_PORTRAITS, who, &block) || block == 0
        || !dat_read_block(block, 0, h, HEADER_SIZE)) {
        return false;     /* no art: a missing portrait is an empty block */
    }
    p->head_x = h[2];
    p->head_y = h[3];
    p->head_w = h[4];
    p->head_h = h[5];
    p->exprs = h[6];
    p->tiles_block = le16(h + 7);
    p->pal_block = le16(h + 9);
    p->head_tiles = (uint8_t)(p->head_w * p->head_h);
    if (h[0] != PORTRAIT_COLS || h[1] != PORTRAIT_ROWS || p->head_w != PORTRAIT_COLS
        || p->head_h == 0 || p->head_y + p->head_h > PORTRAIT_ROWS || p->head_x != 0
        || p->exprs == 0) {
        return false;
    }
    total = PORTRAIT_COLS * PORTRAIT_ROWS + (uint16_t)(p->exprs - 1) * p->head_tiles;
    if (total > PORTRAIT_SLOTS) {
        return false;
    }
    p->total = (uint8_t)total;

    if (!dat_read_block(p->tiles_block, 0, t, TILES_HEADER) || t[0] != 8 || t[1] != 0) {
        return false;
    }
    tile_count = le16(t + 2);
    if (tile_count < total || !dat_entry(p->tiles_block, &tiles_entry)
        || tiles_entry.size < TILES_HEADER + total * TILE_BYTES) {
        return false;
    }

    lo = s == PORTRAIT_LEFT ? PAL_PORTRAIT_LEFT : PAL_PORTRAIT_RIGHT;
    hi = s == PORTRAIT_LEFT ? PAL_PORTRAIT_RIGHT - 1 : PAL_WORLD - 1;
    if (!dat_read_block(p->pal_block, 0, pal, 2) || pal[0] < lo || pal[1] > hi || pal[1] < pal[0]
        || pal[1] - pal[0] + 1 > PAL_MAX) {
        return false;
    }
    p->pal_first = pal[0];
    p->pal_count = (uint8_t)(pal[1] - pal[0] + 1);
    return dat_entry(p->pal_block, &pal_entry) && pal_entry.size == 2 + p->pal_count * 2;
}

void portrait_show(uint8_t who, uint8_t side, uint8_t expr)
{
    Side *p;
    uint8_t s;

    if (side != 1 && side != 2) {
        portrait_hide();      /* the narrator, or anyone without a side */
        return;
    }
    s = side - 1;
    p = &sides[s];
    if (p->who != who) {
        p->who = NONE;
        p->loaded = 0;
        p->pal_done = false;
        p->want_expr = 0;
        if (!load_descriptor(p, s, who)) {
            debug_logf("Portrait %u has no usable art", who);
            p->want_who = NONE;
            return;
        }
        p->who = who;
    }
    if (expr != EXPR_NONE) {
        p->want_expr = expr < p->exprs ? expr : 0;
    }
    p->want_who = who;
}

void portrait_hide(void)
{
    sides[0].want_who = NONE;
    sides[1].want_who = NONE;
}

/* The next load step of side s: the palette, then one chunk of tiles. */
static bool step(uint8_t s)
{
    Side *p = &sides[s];
    uint8_t n;

    if (!p->pal_done) {
        if (!dat_read_block(p->pal_block, 2, palette, (uint16_t)p->pal_count * 2)) {
            goto failed;
        }
        load_palette(palette, p->pal_first, p->pal_count);
        p->pal_done = true;
        return true;
    }
    n = p->total - p->loaded;
    if (n > PORTRAIT_CHUNK_TILES) {
        n = PORTRAIT_CHUNK_TILES;
    }
    if (!dat_read_block(p->tiles_block, TILES_HEADER + (uint16_t)p->loaded * TILE_BYTES, chunk,
                        (uint16_t)n * TILE_BYTES)) {
        goto failed;
    }
    load_tileset(chunk, (uint16_t)(slot_base(s) + p->loaded) << 8, (uint16_t)n * TILE_BYTES, 0);
    p->loaded += n;
    return true;

failed:
    debug_logf("Portrait %u: read failed", p->who);
    p->who = NONE;
    p->want_who = NONE;
    return false;
}

static bool pending(const Side *p, uint8_t tiles)
{
    return !p->pal_done || p->loaded < tiles;
}

static void head_cells(const Side *p, uint8_t s, uint8_t expr, uint8_t *out)
{
    uint8_t r, c, slot = slot_base(s);

    for (r = 0; r < p->head_h; r++) {
        for (c = 0; c < p->head_w; c++) {
            out[r * p->head_w + c] = expr == 0
                ? (uint8_t)(slot + (p->head_y + r) * PORTRAIT_COLS + c)
                : (uint8_t)(slot + PORTRAIT_COLS * PORTRAIT_ROWS + (expr - 1) * p->head_tiles
                            + r * p->head_w + c);
        }
    }
}

static void show_cells(Side *p, uint8_t s)
{
    uint8_t cells[PORTRAIT_COLS * PORTRAIT_ROWS], i;

    if (p->shown_who == p->want_who) {
        /* Same character: only the head changes. */
        head_cells(p, s, p->want_expr, cells);
        draw_fg(cells, column(s) + p->head_x, ROW_PORTRAIT + p->head_y, p->head_w, p->head_h);
    } else {
        for (i = 0; i < PORTRAIT_COLS * PORTRAIT_ROWS; i++) {
            cells[i] = slot_base(s) + i;
        }
        if (p->want_expr != 0) {
            uint8_t head[PORTRAIT_COLS * PORTRAIT_ROWS], r, c;

            head_cells(p, s, p->want_expr, head);
            for (r = 0; r < p->head_h; r++) {
                for (c = 0; c < p->head_w; c++) {
                    cells[(p->head_y + r) * PORTRAIT_COLS + p->head_x + c] = head[r * p->head_w + c];
                }
            }
        }
        draw_fg(cells, column(s), ROW_PORTRAIT, PORTRAIT_COLS, PORTRAIT_ROWS);
    }
    p->shown_who = p->want_who;
    p->shown_expr = p->want_expr;
}

bool portrait_draw(bool upload_ok)
{
    Side *p;
    uint8_t s, pick = NONE;
    bool used = false;

    /* Anything on screen that should go (or whose slots are about to change) is blanked
     * before any tile is rewritten. */
    for (s = 0; s < 2; s++) {
        p = &sides[s];
        if (p->shown_who != NONE && p->shown_who != p->want_who) {
            draw_fg(blank, column(s), ROW_PORTRAIT, PORTRAIT_COLS, PORTRAIT_ROWS);
            p->shown_who = NONE;
        }
    }

    if (upload_ok) {
        /* What a visible portrait needs comes first; then finish whatever is resident. */
        for (s = 0; s < 2 && pick == NONE; s++) {
            p = &sides[s];
            if (p->want_who != NONE && p->who == p->want_who && pending(p, tiles_for(p, p->want_expr))) {
                pick = s;
            }
        }
        for (s = 0; s < 2 && pick == NONE; s++) {
            p = &sides[s];
            if (p->who != NONE && pending(p, p->total)) {
                pick = s;
            }
        }
        if (pick != NONE) {
            used = step(pick);
        }
    }

    for (s = 0; s < 2; s++) {
        p = &sides[s];
        if (p->want_who != NONE && p->who == p->want_who && !pending(p, tiles_for(p, p->want_expr))
            && (p->shown_who != p->want_who || p->shown_expr != p->want_expr)) {
            show_cells(p, s);
        }
    }
    return used;
}

bool portrait_visible(uint8_t side, uint8_t *who, uint8_t *expr)
{
    const Side *p = &sides[side & 1];

    if (p->shown_who == NONE) {
        return false;
    }
    if (who != 0) {
        *who = p->shown_who;
    }
    if (expr != 0) {
        *expr = p->shown_expr;
    }
    return true;
}
