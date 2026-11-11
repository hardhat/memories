#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "main.h"
#include "layout.h"
#include "memo_dat.h"
#include "title.h"
#include "gfx_mock.h"

static uint16_t original[128];
static unsigned frames;

static uint16_t scale(uint16_t c, unsigned level)
{
    return (uint16_t)(((c >> 11) * level / 256) << 11 | (((c >> 5) & 63) * level / 256) << 5 | (c & 31) * level / 256);
}

/* The fade calls this before each step: the board shows the previous step's brightness. */
static void wait_frame(void)
{
    unsigned level = 256 - ((frames * 171u) >> 4), i;

    for (i = 0; i < 128; i++) {
        assert(mock_palette[i] == scale(original[i], level));
    }
    frames++;
}

int main(int argc, char **argv)
{
    unsigned row, col, layer1 = 0, i;

    if (argc != 2) {
        return 2;
    }
    mock_reset_video();
    if (!title_show()) {
        fprintf(stderr, "title_show failed: %s\n", mock_last_log);
        return 1;
    }
    for (row = 0; row < 40; row++) {
        for (col = 0; col < 80; col++) {
            layer1 += mock_fg[row][col];
        }
    }
    printf("layer1 %u\n", layer1);
    printf("uploads %u\n", mock_upload_calls);
    if (!mock_write_ppm(argv[1])) {
        return 1;
    }

    /* The fade: 24 steps, each at the brightness the formula gives, ending on black. */
    memcpy(original, mock_palette, sizeof original);
    title_fade_out(wait_frame);
    assert(frames == 24);
    for (i = 0; i < 128; i++) {
        assert(mock_palette[i] == 0);
    }
    printf("title fade ok\n");
    return 0;
}