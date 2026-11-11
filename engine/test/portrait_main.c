/* Desktop tests for the portrait module against the video model in gfx_mock.c and a real
 * memo.dat. Usage: portrait_test <memo.dat> <left id> <right id> <other right id> <no art id> <out dir>
 * The left character has 10 expressions (44 tiles), the right one 8 (36 tiles) and the
 * other right one 4 (20 tiles). Writes portrait-*.ppm for the caller to compare with the art. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "layout.h"
#include "memo_dat.h"
#include "portrait.h"
#include "stream.h"
#include "gfx_mock.h"

#define LEFT_COL  COL_PORTRAIT_LEFT
#define RIGHT_COL COL_PORTRAIT_RIGHT

static const char *out_dir;

static void dump(const char *name)
{
    char path[512];

    snprintf(path, sizeof path, "%s/portrait-%s.ppm", out_dir, name);
    assert(mock_write_ppm(path));
}

static uint8_t cell(uint8_t col, uint8_t r)
{
    return mock_fg[ROW_PORTRAIT + r / 2][col + r % 2];   /* r counts cells in raster order, 0..7 */
}

static bool blank(uint8_t col)
{
    uint8_t i;

    for (i = 0; i < 8; i++) {
        if (cell(col, i) != 0) {
            return false;
        }
    }
    return true;
}

/* All eight cells of a portrait at `slot`, showing expression e whose head starts at
 * `head_slot` (the two top rows of cells are the head). */
static bool shows(uint8_t col, uint8_t slot, uint8_t e)
{
    uint8_t i;

    for (i = 0; i < 8; i++) {
        uint8_t expect = (uint8_t)(slot + i);

        if (e != 0 && i < 4) {
            expect = (uint8_t)(slot + 8 + (e - 1) * 4 + i);
        }
        if (cell(col, i) != expect) {
            return false;
        }
    }
    return true;
}

/* One frame with the upload budget; returns the uploads it made (never more than one). */
static unsigned frame(bool budget)
{
    mock_reset_counters();
    portrait_draw(budget);
    assert(mock_upload_calls <= 1 && mock_upload_bytes <= STREAM_CHUNK_TILES * 256u);
    return mock_upload_calls;
}

/* Draw frames until nothing uploads; returns the frames that uploaded. */
static unsigned settle(void)
{
    unsigned n = 0, guard = 0;

    while (frame(true)) {
        n++;
        assert(++guard < 20);
    }
    return n;
}

static bool palette_set(uint8_t first, uint8_t last)
{
    uint8_t i;

    for (i = first; i <= last; i++) {
        if (mock_palette[i] != 0) {
            return true;
        }
    }
    return false;
}

int main(int argc, char **argv)
{
    uint8_t left, right, other, none, who, expr;
    unsigned chunks, i;

    if (argc != 7) {
        fprintf(stderr, "usage: portrait_test <memo.dat> <left> <right> <other> <none> <outdir>\n");
        return 2;
    }
    left = (uint8_t)atoi(argv[2]);
    right = (uint8_t)atoi(argv[3]);
    other = (uint8_t)atoi(argv[4]);
    none = (uint8_t)atoi(argv[5]);
    out_dir = argv[6];
    if (dat_open(argv[1], 0) != DAT_OK) {
        fprintf(stderr, "cannot open the dat\n");
        return 2;
    }
    mock_reset_video();
    portrait_init();

    /* Nothing is drawn until something is asked for. */
    assert(frame(true) == 0 && blank(LEFT_COL) && blank(RIGHT_COL));

    /* A new left character: palette first, then 44 tiles in 8 tile chunks. The cells stay
     * blank until the 8 base tiles are in, then the base appears while the rest streams. */
    portrait_show(left, 1, 0);
    assert(frame(true) == 0);                       /* the palette step uploads no tiles */
    assert(palette_set(PAL_PORTRAIT_LEFT, PAL_PORTRAIT_RIGHT - 1));
    assert(mock_palette[PAL_PORTRAIT_LEFT - 1] == 0 && mock_palette[PAL_PORTRAIT_RIGHT] == 0);
    assert(blank(LEFT_COL));
    assert(frame(true) == 1);
    assert(shows(LEFT_COL, SLOT_PORTRAIT_LEFT, 0));
    chunks = settle();
    assert(chunks == 5);                            /* 44 tiles: 8 + 8 + 8 + 8 + 8 + 4 */
    assert(shows(LEFT_COL, SLOT_PORTRAIT_LEFT, 0));
    assert(blank(RIGHT_COL));
    dump("brad0");

    /* Everything is resident: an expression change is four tilemap cells and no upload. */
    portrait_show(left, 1, 5);
    assert(frame(true) == 0 && shows(LEFT_COL, SLOT_PORTRAIT_LEFT, 5));
    assert(portrait_visible(PORTRAIT_LEFT, &who, &expr) && who == left && expr == 5);
    dump("brad5");
    portrait_show(left, 1, 9);
    assert(frame(true) == 0 && shows(LEFT_COL, SLOT_PORTRAIT_LEFT, 9));
    dump("brad9");

    /* EXPR_NONE keeps the expression; one the portrait lacks falls back to the base. */
    portrait_show(left, 1, EXPR_NONE);
    assert(frame(true) == 0 && shows(LEFT_COL, SLOT_PORTRAIT_LEFT, 9));
    portrait_show(left, 1, 10);
    assert(frame(true) == 0 && shows(LEFT_COL, SLOT_PORTRAIT_LEFT, 0));

    /* The right side streams while the left stays put. The head for expression 2 needs 16
     * tiles, so nothing shows after the first chunk and the portrait appears with the second. */
    portrait_show(right, 2, 2);
    assert(frame(true) == 0 && blank(RIGHT_COL));
    assert(frame(true) == 1 && blank(RIGHT_COL));
    assert(shows(LEFT_COL, SLOT_PORTRAIT_LEFT, 0));
    assert(frame(true) == 1 && shows(RIGHT_COL, SLOT_PORTRAIT_RIGHT, 2));
    chunks = settle();
    assert(chunks == 3);                            /* 36 tiles: 8 + 8 + [8 + 8 + 4] */
    assert(shows(RIGHT_COL, SLOT_PORTRAIT_RIGHT, 2) && shows(LEFT_COL, SLOT_PORTRAIT_LEFT, 0));
    dump("both");

    /* A character resident on the right comes back as the same: another expression is cells. */
    portrait_show(right, 2, 7);
    assert(frame(true) == 0 && shows(RIGHT_COL, SLOT_PORTRAIT_RIGHT, 7));
    dump("jane7");

    /* A late expression waits for its head: the base stays up until the tiles are in. */
    portrait_show(other, 2, 0);
    for (i = 0; i < 3; i++) {
        frame(true);                                /* palette, then two chunks of Daniel */
    }
    portrait_show(other, 2, 3);                     /* needs all 20 tiles, 16 are in */
    assert(shows(RIGHT_COL, SLOT_PORTRAIT_RIGHT, 0));
    assert(frame(true) == 1 && shows(RIGHT_COL, SLOT_PORTRAIT_RIGHT, 3));
    assert(frame(true) == 0);
    dump("daniel3");

    /* Another character on the right: hidden first, nothing shows while the slots change. */
    portrait_show(right, 2, 0);
    assert(frame(false) == 0 && blank(RIGHT_COL));  /* no budget: no upload, still blank */
    assert(frame(false) == 0 && blank(RIGHT_COL));
    for (i = 0; i < 2; i++) {
        mock_reset_counters();
        portrait_draw(true);
        assert(blank(RIGHT_COL) == (i == 0));       /* palette step, then the base arrives */
    }
    settle();
    assert(shows(RIGHT_COL, SLOT_PORTRAIT_RIGHT, 0) && shows(LEFT_COL, SLOT_PORTRAIT_LEFT, 0));
    dump("jane0");
    portrait_show(other, 2, 3);                     /* swap back: streams again */
    assert(frame(true) == 0 && blank(RIGHT_COL));   /* the palette step */
    settle();
    assert(shows(RIGHT_COL, SLOT_PORTRAIT_RIGHT, 3));
    dump("daniel3b");

    /* Hiding keeps the tiles, so the speaker comes back with no upload at all. */
    portrait_hide();
    assert(frame(true) == 0 && blank(LEFT_COL) && blank(RIGHT_COL));
    assert(!portrait_visible(PORTRAIT_LEFT, NULL, NULL));
    portrait_show(left, 1, 4);
    portrait_show(other, 2, EXPR_NONE);
    assert(frame(true) == 0);
    assert(shows(LEFT_COL, SLOT_PORTRAIT_LEFT, 4) && shows(RIGHT_COL, SLOT_PORTRAIT_RIGHT, 3));

    /* A character without art hides only its own side. */
    portrait_show(none, 2, 0);
    assert(frame(true) == 0 && blank(RIGHT_COL) && shows(LEFT_COL, SLOT_PORTRAIT_LEFT, 4));
    assert(!portrait_visible(PORTRAIT_RIGHT, NULL, NULL));

    /* The narrator (no side) takes both down. */
    portrait_show(0, 0, 0);
    assert(frame(true) == 0 && blank(LEFT_COL) && blank(RIGHT_COL));

    /* The tile slots hold what the file holds: spot check one tile per portrait against dat. */
    {
        uint16_t block, tiles;
        uint8_t h[11], t[256];

        assert(dat_index_get(DAT_TABLE_PORTRAITS, left, &block) && dat_read_block(block, 0, h, 11));
        tiles = (uint16_t)(h[7] | (h[8] << 8));
        assert(dat_read_block(tiles, 4 + 43 * 256, t, 256));
        assert(memcmp(t, mock_tileset[SLOT_PORTRAIT_LEFT + 43], 256) == 0);
    }
    assert(mock_tileset[0][0] == 0 && mock_tileset[SLOT_PORTRAIT_LEFT - 1][0] == 0);
    printf("portrait tests passed\n");
    return 0;
}
