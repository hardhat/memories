#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "main.h"
#include "layout.h"
#include "memo_dat.h"
#include "stream.h"
#include "title.h"

#define TITLE_TILES        240          /* 20 x 12 tiles */
#define TITLE_ROWS         12
#define TITLE_COLORS       128
#define TITLE_FILL_SLOT    (1u + TITLE_TILES)
#define TILE_BYTES         256u
#define TILESET_HEADER     4            /* bpp, comp, u16 tile count (compiler-spec.md 5.7) */
#define PALETTE_HEADER     2            /* first, last */

/* The palette entry closest to black, used for the rows below the picture. */
static uint8_t darkest(const uint16_t *palette)
{
    uint8_t i, best = 0;
    uint8_t level, best_level = 255;

    for (i = 0; i < TITLE_COLORS; i++) {
        uint16_t c = palette[i];
        /* red + green + blue, each reduced to 5 bits */
        level = (uint8_t)(((c >> 11) & 0x1F) + ((c >> 6) & 0x1F) + (c & 0x1F));
        if (level < best_level) {
            best_level = level;
            best = i;
        }
    }
    return best;
}

static bool load_art(uint16_t *palette)
{
    uint16_t ids[3];
    uint8_t head[TILESET_HEADER];
    uint16_t t;

    if (!dat_index_get(DAT_TABLE_CGS, CG_TITLE, ids) || ids[0] == 0 || ids[2] == 0) {
        return false;
    }
    if (!dat_read_block(ids[0], 0, head, TILESET_HEADER) || head[0] != 8 || head[1] != 0
        || head[2] != (TITLE_TILES & 0xFF) || head[3] != (TITLE_TILES >> 8)) {
        return false;
    }
    if (!dat_read_block(ids[2], 0, head, PALETTE_HEADER) || head[0] != 0 || head[1] != TITLE_COLORS - 1
        || !dat_read_block(ids[2], PALETTE_HEADER, palette, TITLE_COLORS * 2)) {
        return false;
    }
    for (t = 0; t < TITLE_TILES; t += STREAM_CHUNK_TILES) {
        if (!stream_tiles(ids[0], t, STREAM_CHUNK_TILES, 1u + t)) {
            return false;
        }
    }
    return true;
}

bool title_show(void)
{
    uint16_t palette[TITLE_COLORS];
    uint8_t fill[TILE_BYTES];
    uint8_t cells[SCREEN_COLS];
    uint8_t row, col;
    bool ok;

    if (dat_open("memo.dat", MEMO_CONTENT_CRC) != DAT_OK) {
        if(dat_open("h:/memo.dat", MEMO_CONTENT_CRC) != DAT_OK) {
            debug_log("Failed to open memo.dat");
            return false;
        }
    }
    ok = load_art(palette);
    dat_close();
    if (!ok) {
        debug_log("Title art missing");
        return false;
    }

    memset(fill, darkest(palette), TILE_BYTES);
    load_tileset(fill, TITLE_FILL_SLOT * TILE_BYTES, TILE_BYTES, 0);
    load_palette(palette, 0, TITLE_COLORS);

    for (row = 0; row < SCREEN_ROWS; row++) {
        memset(cells, 0, sizeof(cells));
        draw_fg(cells, 0, row, SCREEN_COLS, 1);
        for (col = 0; col < SCREEN_COLS; col++) {
            cells[col] = row < TITLE_ROWS ? (uint8_t)(1 + row * SCREEN_COLS + col) : (uint8_t)TITLE_FILL_SLOT;
        }
        draw_bg(cells, 0, row, SCREEN_COLS, 1);
    }
    return true;
}
