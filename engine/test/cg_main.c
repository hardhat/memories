/* Desktop tests for CG mode (cg.c with the screen and stream modules) against the video model in
 * gfx_mock.c and a real memo.dat.
 * Usage: cg_test <memo.dat> <baked CG a> <baked CG b> <unbaked CG> <out dir>
 * Writes cg-*.ppm for the caller to compare with the art. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "layout.h"
#include "memo_dat.h"
#include "screen.h"
#include "stream.h"
#include "fade.h"
#include "cg.h"
#include "gfx_mock.h"

static const char *out_dir;

static void dump(const char *name)
{
    char path[512];

    snprintf(path, sizeof path, "%s/cg-%s.ppm", out_dir, name);
    assert(mock_write_ppm(path));
}

/* One frame in the order the host uses: the box first, then the CG. */
static bool frame(void)
{
    bool up;

    mock_reset_counters();
    up = screen_draw();
    up = cg_draw(!up) || up;
    assert(mock_upload_calls <= 1 && mock_upload_bytes <= SCREEN_COLS * 256u);
    assert(up == (mock_upload_calls == 1));
    return up;
}

/* Frames until two in a row upload nothing; returns the frames that uploaded. */
static unsigned settle(void)
{
    unsigned n = 0, quiet = 0, guard = 0;

    while (quiet < 2) {
        if (frame()) {
            n++;
            quiet = 0;
        } else {
            quiet++;
        }
        assert(++guard < 80);
    }
    return n;
}

static void run_until_text_ready(void)
{
    unsigned guard = 0;

    while (!screen_text_ready()) {
        frame();
        assert(++guard < 20);
    }
}

static bool bg_blank(void)
{
    uint8_t r, c;

    for (r = 0; r < SCREEN_ROWS; r++) {
        for (c = 0; c < SCREEN_COLS; c++) {
            if (mock_bg[r][c] != 0) {
                return false;
            }
        }
    }
    return true;
}

/* The layer 0 cells of a revealed CG: slots 64-243 for rows 0-8, 1-60 for rows 9-11, empty below. */
static bool bg_is_cg(void)
{
    uint8_t r, c;

    for (r = 0; r < SCREEN_ROWS; r++) {
        for (c = 0; c < SCREEN_COLS; c++) {
            unsigned want = r < CG_TOP_ROWS ? SLOT_CG_TOP + r * SCREEN_COLS + c
                          : r < CG_ROWS ? SLOT_DIALOG + (r - CG_TOP_ROWS) * SCREEN_COLS + c : 0;

            if (mock_bg[r][c] != want) {
                return false;
            }
        }
    }
    return true;
}

static bool fg_box_at(uint8_t top)
{
    uint8_t r, c;

    for (r = 0; r < SCREEN_ROWS; r++) {
        for (c = 0; c < SCREEN_COLS; c++) {
            bool inside = r >= top && r < top + TEXT_ROWS;
            bool arrow = r == top + TEXT_ROWS - 1 && c == SCREEN_COLS - 1;
            uint8_t cell = mock_fg[r][c];

            if (!inside) {
                if (cell != 0) {
                    return false;
                }
            } else if (arrow ? (cell != DIALOG_TILES && cell != SLOT_MARKER)
                             : cell != SLOT_DIALOG + (r - top) * SCREEN_COLS + c) {
                return false;
            }
        }
    }
    return true;
}

static bool fg_blank(void)
{
    uint8_t r, c;

    for (r = 0; r < SCREEN_ROWS; r++) {
        for (c = 0; c < SCREEN_COLS; c++) {
            if (mock_fg[r][c] != 0) {
                return false;
            }
        }
    }
    return true;
}

int main(int argc, char **argv)
{
    uint8_t a, b, unbaked;
    uint16_t dialog_palette[PAL_WORLD];
    unsigned frames, uploads;
    static const char *text = "Hello there.\nA second line.";

    if (argc != 6) {
        fprintf(stderr, "usage: cg_test <memo.dat> <a> <b> <unbaked> <outdir>\n");
        return 2;
    }
    a = (uint8_t)atoi(argv[2]);
    b = (uint8_t)atoi(argv[3]);
    unbaked = (uint8_t)atoi(argv[4]);
    out_dir = argv[5];
    if (dat_open(argv[1], 0) != DAT_OK) {
        fprintf(stderr, "cannot open the dat\n");
        return 2;
    }
    mock_reset_video();
    screen_init();
    cg_init();
    fade_init();
    memcpy(dialog_palette, mock_palette, sizeof dialog_palette);

    assert(!cg_active() && cg_ready());
    assert(!frame() && bg_blank());

    /* The CG streams in invisibly: 180 + 60 tiles in 8 tile chunks, then appears in one frame. */
    assert(cg_show(a) && cg_active() && !cg_ready());
    frames = uploads = 0;
    while (!cg_ready()) {
        uploads += frame();
        frames++;
        assert(frames < 60);
        assert(cg_ready() || bg_blank());                 /* nothing visible points at changing slots */
    }
    assert(uploads == 31 && frames == 32);                /* 23 top chunks + 8 bottom chunks + the reveal */
    assert(bg_is_cg() && fg_blank());
    assert(memcmp(mock_palette, dialog_palette, sizeof dialog_palette) == 0);   /* dialog and portraits untouched */
    assert(mock_palette[PAL_WORLD] != 0 || mock_palette[PAL_WORLD + 1] != 0);
    assert(settle() == 0);
    dump("a");

    /* A fade scales the picture's palette and leaves the dialog palette alone: at brightness 128 every
     * colour channel is halved, the box (shown now) keeps its own colours, and black is black. */
    fade_start(false, 512);
    fade_update(256);
    fade_draw();
    assert(fade_level() == 128);
    assert(memcmp(mock_palette, dialog_palette, sizeof dialog_palette) == 0);
    dump("fade128");
    screen_text_show("Brad", text, 0);
    run_until_text_ready();
    dump("fade128-box");
    screen_text_hide();
    settle();
    fade_update(256);
    fade_draw();
    assert(fade_level() == 0 && memcmp(mock_palette, dialog_palette, sizeof dialog_palette) == 0);
    dump("fade0");
    fade_start(true, 0);
    fade_draw();
    assert(settle() == 0);
    dump("fade-back");
    /* The box goes over the bottom three rows and replaces them. */
    screen_text_show("Brad", text, 0);
    run_until_text_ready();
    assert(fg_box_at(ROW_TEXT_CG) && bg_is_cg());
    assert(settle() == 0);
    dump("box");

    /* Hiding the text brings the CG's bottom rows back: 60 tiles, 8 chunks. */
    screen_text_hide();
    assert(settle() == 8);
    assert(fg_blank() && bg_is_cg());
    dump("restored");

    /* The same text again must be uploaded again: the restore made the cache stale. */
    screen_text_show("Brad", text, 0);
    run_until_text_ready();
    assert(fg_box_at(ROW_TEXT_CG));
    dump("box2");

    /* Text that comes back while the bottom rows are being restored wins. */
    screen_text_hide();
    frame();
    frame();
    frame();
    screen_text_show("Brad", text, 0);
    run_until_text_ready();
    assert(fg_box_at(ROW_TEXT_CG));
    dump("box3");
    screen_text_hide();
    assert(settle() == 8);                                /* the restore starts over */
    dump("restored2");

    /* Another CG replaces it: the cells go blank before its tiles overwrite the old ones. */
    assert(cg_show(b) && !cg_ready());
    assert(cg_show(b));                                   /* asking again changes nothing */
    frame();
    assert(bg_blank());
    frames = 1;
    while (!cg_ready()) {
        frame();
        frames++;
        assert(frames < 60);
        assert(cg_ready() || bg_blank());
    }
    assert(bg_is_cg() && frames == 32);
    dump("b");

    /* Taking it down clears the layer and moves the box back to the bottom. */
    screen_text_show("Brad", text, 0);
    run_until_text_ready();
    assert(fg_box_at(ROW_TEXT_CG));
    cg_hide();
    assert(!cg_active() && cg_ready());
    frame();
    assert(bg_blank() && fg_box_at(ROW_TEXT_MAP));
    screen_text_hide();
    settle();
    assert(fg_blank());

    /* A CG asked for while the box is up (at the bottom) waits for the box to go: the box moves
     * over the CG when the CG appears. */
    screen_text_show("Brad", text, 0);
    run_until_text_ready();
    assert(fg_box_at(ROW_TEXT_MAP));
    assert(cg_show(a));
    frames = 0;
    while (!cg_ready()) {
        frame();
        assert(++frames < 60);
        assert(cg_ready() || (bg_blank() && fg_box_at(ROW_TEXT_MAP)));
    }
    assert(fg_box_at(ROW_TEXT_CG) && bg_is_cg());
    dump("box4");
    screen_text_hide();
    settle();

    /* Art that is not baked, or does not exist, is refused and changes nothing. */
    mock_log_count = 0;
    assert(!cg_show(unbaked));
    assert(mock_log_count == 1);
    assert(!cg_show(250));
    assert(!cg_active() && cg_ready());
    frame();
    assert(bg_blank() && fg_blank());

    assert(mock_tileset[0][0] == 0 && mock_tileset[SLOT_MARKER + 1][0] == 0);       /* slots 62-63 untouched */
    printf("cg tests passed\n");
    return 0;
}
