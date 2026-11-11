/* Desktop tests for the palette fade (fade.c) against the video model in gfx_mock.c.
 * Usage: fade_test */
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "layout.h"
#include "fade.h"
#include "gfx_mock.h"

static uint16_t art[256];       /* the colours the "art" asked for */

static uint16_t scale(uint16_t c, uint16_t level)
{
    uint16_t r = (uint16_t)((c >> 11) * level / 256);
    uint16_t g = (uint16_t)(((c >> 5) & 63) * level / 256);
    uint16_t b = (uint16_t)((c & 31) * level / 256);

    return (uint16_t)(r << 11 | g << 5 | b);
}

/* Every faded entry shows the art at `level`; every other entry is as it was. */
static void expect_shown(uint16_t level)
{
    unsigned i;

    for (i = FADE_FIRST; i <= FADE_LAST; i++) {
        if (art[i] != 0 || level == FADE_FULL) {
            assert(mock_palette[i] == scale(art[i], level));
        }
    }
}

static void expect_dialog_untouched(void)
{
    unsigned i;

    for (i = 0; i < FADE_FIRST; i++) {
        assert(mock_palette[i] == 0x1000 + i);
    }
}

static void frame(uint16_t elapsed)
{
    mock_reset_counters();
    fade_update(elapsed);
    fade_draw();
    assert(mock_palette_colors <= FADE_COUNT);
}

static void load(uint8_t first, uint8_t count, uint16_t seed)
{
    uint16_t colors[256];
    uint8_t i;

    for (i = 0; i < count; i++) {
        uint16_t r = (seed + i * 7) % 32, g = (seed * 3 + i * 5) % 64, b = (seed * 5 + i * 11) % 32;

        colors[i] = (uint16_t)(r << 11 | g << 5 | b);
        art[first + i] = colors[i];
    }
    fade_palette(first, colors, count);
}

int main(void)
{
    unsigned i, frames;
    uint16_t last, mid;
    uint16_t colors[2] = {0xFFFF, 0xFFFF};

    mock_reset_video();
    for (i = 0; i < FADE_FIRST; i++) {
        mock_palette[i] = (uint16_t)(0x1000 + i);        /* a dialog palette to protect */
    }
    fade_init();
    assert(fade_level() == FADE_FULL && !fade_active());

    /* At full brightness a load is a plain copy of just those entries. */
    mock_reset_counters();
    load(PAL_PORTRAIT_RIGHT, 47, 3);
    load(PAL_WORLD, 127, 11);
    assert(mock_palette_calls == 2 && mock_palette_colors == 47 + 127);
    expect_shown(FADE_FULL);
    expect_dialog_untouched();
    frame(16);
    assert(mock_palette_calls == 0);                      /* nothing changed: nothing written */

    /* A fade out: 400 ms in 16 ms frames. Brightness falls steadily, the board always shows the
     * art scaled by it, and the dialog palette is never touched. */
    fade_start(false, 400);
    assert(fade_active() && fade_level() == FADE_FULL);
    last = FADE_FULL;
    frames = 0;
    while (fade_active()) {
        frame(16);
        frames++;
        assert(fade_level() <= last && last - fade_level() <= 12);
        last = fade_level();
        expect_shown(fade_level());
        expect_dialog_untouched();
        assert(mock_palette_calls >= 1 && mock_palette_calls <= 4);   /* 221 colours in chunks of 64 */
        assert(frames < 40);
    }
    assert(frames == 25 && fade_level() == 0);            /* ceil(400 / 16) */
    expect_shown(0);
    for (i = FADE_FIRST; i <= FADE_LAST; i++) {
        assert(mock_palette[i] == 0);
    }
    frame(16);
    assert(mock_palette_calls == 0);                      /* finished: no more writes */

    /* Art loaded while black stays black, and is remembered. */
    load(PAL_PORTRAIT_LEFT, 20, 21);
    for (i = PAL_PORTRAIT_LEFT; i < PAL_PORTRAIT_LEFT + 20; i++) {
        assert(mock_palette[i] == 0);
    }

    /* The fade in brings everything back, the new colours included, ending exactly on the art. */
    fade_start(true, 300);
    frames = 0;
    last = 0;
    while (fade_active()) {
        frame(16);
        frames++;
        assert(fade_level() >= last);
        last = fade_level();
        expect_shown(fade_level());
        assert(frames < 40);
    }
    assert(frames == 19 && fade_level() == FADE_FULL);
    expect_shown(FADE_FULL);
    expect_dialog_untouched();

    /* Fading to where it already is changes nothing. */
    mock_reset_counters();
    fade_start(true, 500);
    assert(!fade_active());
    frame(16);
    assert(mock_palette_calls == 0);

    /* Reversing a fade in the middle continues from the brightness it had reached. */
    fade_start(false, 320);
    for (i = 0; i < 10; i++) {
        frame(16);
    }
    mid = fade_level();
    assert(mid > 100 && mid < 160);
    fade_start(true, 320);
    frame(16);
    assert(fade_level() > mid && fade_level() - mid <= 16);
    expect_shown(fade_level());
    while (fade_active()) {
        frame(16);
    }
    assert(fade_level() == FADE_FULL);
    expect_shown(FADE_FULL);

    /* A zero length fade jumps at the next draw. */
    fade_start(false, 0);
    assert(fade_level() == 0 && !fade_active());
    fade_draw();
    expect_shown(0);
    fade_start(true, 0);
    fade_draw();
    expect_shown(FADE_FULL);

    /* A frame longer than the fade finishes it. */
    fade_start(false, 100);
    frame(500);
    assert(fade_level() == 0 && !fade_active());
    fade_start(true, 100);
    frame(100);
    assert(fade_level() == FADE_FULL);
    expect_shown(FADE_FULL);

    /* Mid-fade loads show at the current brightness and are not left at full. */
    fade_start(false, 320);
    for (i = 0; i < 10; i++) {
        frame(16);
    }
    load(PAL_WORLD + 100, 10, 40);
    for (i = PAL_WORLD + 100; i < PAL_WORLD + 110; i++) {
        assert(mock_palette[i] == scale(art[i], fade_level()));
    }
    fade_start(true, 0);
    fade_draw();
    expect_shown(FADE_FULL);

    /* Entries outside 32-252 are written as they are, at any brightness. */
    fade_start(false, 0);
    fade_draw();
    fade_palette(253, colors, 2);
    assert(mock_palette[253] == 0xFFFF && mock_palette[254] == 0xFFFF);
    fade_palette(30, colors, 2);
    assert(mock_palette[30] == 0xFFFF && mock_palette[31] == 0xFFFF);
    fade_start(true, 0);
    fade_draw();

    /* Scaling is exact at the ends and rounds down: white at half is 15/31 and 31/63. */
    load(PAL_WORLD, 1, 0);
    colors[0] = 0xFFFF;
    fade_palette(PAL_WORLD, colors, 1);
    fade_start(false, 512);
    frame(256);
    assert(fade_level() == 128);
    assert(mock_palette[PAL_WORLD] == (15 << 11 | 31 << 5 | 15));

    printf("fade tests passed\n");
    return 0;
}
