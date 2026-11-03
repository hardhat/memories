/* Desktop tests for the screen compositor, run against the video model in gfx_mock.c.
 * Usage: screen_test <output directory>   (writes screen-*.ppm for review) */
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "../layout.h"
#include "../screen.h"
#include "gfx_mock.h"

#define BYTES_PER_ROW (SCREEN_COLS * 256u)

static const char *out_dir;

static void dump(const char *name)
{
    char path[512];

    snprintf(path, sizeof path, "%s/%s", out_dir, name);
    assert(mock_write_ppm(path));
}

static bool box_clear(void)
{
    uint8_t row, col;

    for (row = 0; row < TEXT_ROWS; row++) {
        for (col = 0; col < SCREEN_COLS; col++) {
            if (mock_fg[ROW_TEXT_MAP + row][col] != 0) {
                return false;
            }
        }
    }
    return true;
}

static bool box_complete(void)
{
    uint8_t row, col;

    for (row = 0; row < TEXT_ROWS; row++) {
        for (col = 0; col < SCREEN_COLS; col++) {
            uint8_t cell = mock_fg[ROW_TEXT_MAP + row][col];
            bool arrow_cell = row == TEXT_ROWS - 1 && col == SCREEN_COLS - 1;

            if (arrow_cell ? (cell != DIALOG_TILES && cell != SLOT_MARKER)
                           : cell != SLOT_DIALOG + row * SCREEN_COLS + col) {
                return false;
            }
        }
    }
    return true;
}

/* Run draws until the text is ready; every frame obeys the one-upload budget. */
static unsigned settle(unsigned *uploads)
{
    unsigned frames = 0;

    *uploads = 0;
    while (!screen_text_ready()) {
        mock_reset_counters();
        screen_draw();
        frames++;
        assert(mock_upload_calls <= 1 && mock_upload_bytes <= BYTES_PER_ROW);
        *uploads += mock_upload_calls;
        assert(frames < 10);
    }
    return frames;
}

static bool tile_is(uint8_t slot, uint8_t color)
{
    uint16_t i;

    for (i = 0; i < 256; i++) {
        if (mock_tileset[slot][i] != color) {
            return false;
        }
    }
    return true;
}

static unsigned count_color(uint8_t slot_first, uint8_t slot_count, uint8_t color)
{
    unsigned n = 0, i;

    for (i = 0; i < (unsigned)slot_count * 256; i++) {
        n += mock_tileset[slot_first][i] == color;
    }
    return n;
}

int main(int argc, char **argv)
{
    unsigned frames, uploads, before;
    uint8_t slot, i;
    const char *five = "one\ntwo\nthree\nfour\nfive";
    char long_text[200];

    assert(argc == 2);
    out_dir = argv[1];
    mock_reset_video();
    screen_init();
    mock_bg[13][3] = 7;                       /* untouched art underneath the box */

    /* Static content: palette, empty tile, box background, continue arrow. */
    assert(mock_palette[PAL_BOX_BG] != 0 && mock_palette[PAL_TEXT] != mock_palette[PAL_BOX_BG]);
    assert(tile_is(SLOT_EMPTY, 0));
    for (slot = SLOT_DIALOG; slot < SLOT_DIALOG + DIALOG_TILES; slot++) {
        assert(tile_is(slot, PAL_BOX_BG));
    }
    assert(count_color(SLOT_MARKER, 1, PAL_MARKER) == 20 && mock_tileset[SLOT_MARKER][8 * 16 + 4] == PAL_MARKER);
    assert(box_clear() && mock_bg[13][3] == 7);
    assert(!screen_text_ready());

    /* First showing: staged invisibly, two uploads (the spare row is already blank). */
    screen_text_show("Brad", "Hello there!\nSecond line.\nThird.", 0);
    assert(!screen_text_ready());
    mock_reset_counters();
    screen_draw();
    assert(box_clear() && mock_upload_calls == 1);
    frames = settle(&uploads);
    assert(frames == 1 && uploads == 1 && box_complete());
    assert(count_color(SLOT_DIALOG, 20, PAL_NAME) > 0);              /* name plate and line 1 share row 0 */
    assert(count_color(SLOT_DIALOG + 20, 20, PAL_TEXT) > 0);         /* lines 2 and 3 */
    assert(count_color(SLOT_DIALOG + 40, 20, PAL_NAME) == 0 && tile_is(SLOT_DIALOG + 59, PAL_BOX_BG));
    assert(mock_tileset[SLOT_DIALOG][0] == PAL_BOX_BG);              /* margin left of the text */
    dump("screen-dialog.ppm");

    /* Continue arrow blinks in the corner cell of the third row. */
    screen_text_marker(true);
    screen_draw();
    assert(mock_fg[ROW_TEXT_MAP + 2][SCREEN_COLS - 1] == SLOT_MARKER);
    screen_update(399);
    screen_draw();
    assert(mock_fg[ROW_TEXT_MAP + 2][SCREEN_COLS - 1] == SLOT_MARKER);
    screen_update(1);
    screen_draw();
    assert(mock_fg[ROW_TEXT_MAP + 2][SCREEN_COLS - 1] == DIALOG_TILES);
    screen_update(400);
    screen_draw();
    assert(mock_fg[ROW_TEXT_MAP + 2][SCREEN_COLS - 1] == SLOT_MARKER);
    dump("screen-marker.ppm");
    screen_text_marker(false);
    screen_draw();
    assert(box_complete() && mock_fg[ROW_TEXT_MAP + 2][SCREEN_COLS - 1] == DIALOG_TILES);

    /* Replacing text that is visible keeps the box up and rewrites only changed rows. */
    screen_text_show("", "Narration only.", 0);
    assert(!screen_text_ready());
    mock_reset_counters();
    screen_draw();
    assert(mock_upload_calls == 1 && mock_fg[ROW_TEXT_MAP][0] == SLOT_DIALOG);
    frames = settle(&uploads);
    assert(frames <= 1 && box_complete());
    assert(count_color(SLOT_DIALOG, 20, PAL_NAME) == 0);             /* no name plate */
    assert(tile_is(SLOT_DIALOG + 20, PAL_BOX_BG));                   /* old lines 2-3 are gone */
    dump("screen-narration.ppm");

    /* Hiding clears only the FG cells; later text stages invisibly again. */
    screen_text_hide();
    assert(!screen_text_ready());
    screen_draw();
    assert(box_clear() && mock_bg[13][3] == 7);
    before = mock_upload_calls;
    screen_draw();
    assert(mock_upload_calls == before);
    screen_text_show("Gord", "Back again.", 1);
    assert(box_clear());
    frames = settle(&uploads);
    assert(box_complete());
    assert(count_color(SLOT_DIALOG, 20, PAL_PHONE) > 0);             /* phone style colour */

    /* Credits have no name plate even when one is supplied. */
    screen_text_show("Ignored", "Directed by\nSomeone", 2);
    settle(&uploads);
    assert(count_color(SLOT_DIALOG, 20, PAL_NAME) == 0 && count_color(SLOT_DIALOG, 20, PAL_CREDITS) > 0);

    /* Hiding while a first showing is still being staged leaves nothing on screen. */
    screen_text_hide();
    screen_draw();
    screen_text_show("Brad", "Quick.", 0);
    screen_draw();
    screen_text_hide();
    screen_draw();
    assert(box_clear() && !screen_text_ready());

    /* Extra lines and over-long lines are cut off, never written outside the box. */
    screen_text_show("A very long speaker name", five, 0);
    settle(&uploads);
    assert(count_color(SLOT_DIALOG + 40, 20, PAL_TEXT) == 0);        /* fifth line is dropped */
    memset(long_text, 'W', sizeof long_text - 1);
    long_text[sizeof long_text - 1] = '\0';
    screen_text_show(NULL, long_text, 0);
    settle(&uploads);
    assert(box_complete());
    assert(tile_is(SLOT_DIALOG + SCREEN_COLS - 1, PAL_BOX_BG));      /* clipped at 36 columns */
    assert(count_color(SLOT_DIALOG, 20, PAL_TEXT) > 0);
    for (i = 0; i < SCREEN_COLS; i++) {
        assert(mock_fg[ROW_TEXT_MAP - 1][i] == 0 && mock_fg[ROW_TEXT_MAP + TEXT_ROWS][i] == 0);
    }
    assert(mock_bg[13][3] == 7);
    printf("screen tests passed\n");
    return 0;
}
