#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "main.h"
#include "layout.h"
#include "fade.h"

#define CHUNK 64     /* palette entries scaled and written at a time */

static uint16_t shadow[FADE_COUNT];   /* the colours the art asked for, entries FADE_FIRST.. */
static uint16_t level;                /* brightness now */
static uint16_t from_level, to_level; /* a running fade goes from one to the other */
static uint16_t total_ms, done_ms;
static bool     running;
static bool     dirty;                /* the board is not showing `level` yet */

/* Scale tables for one brightness: 5 bit red and blue, 6 bit green. Built by repeated addition
 * (v * level), because a multiply is slow on the Z80. */
static uint8_t  lut5[32];
static uint8_t  lut6[64];
static uint16_t lut_level;
static bool     lut_valid;

static void build_tables(uint16_t scale)
{
    uint16_t acc = 0;
    uint8_t v;

    if (lut_valid && lut_level == scale) {
        return;
    }
    for (v = 0; v < 64; v++) {
        if (v < 32) {
            lut5[v] = (uint8_t)(acc >> 8);
        }
        lut6[v] = (uint8_t)(acc >> 8);
        acc += scale;
    }
    lut_level = scale;
    lut_valid = true;
}

void fade_scale(uint16_t *dst, const uint16_t *src, uint8_t count, uint16_t scale)
{
    uint8_t i;
    uint16_t c;

    build_tables(scale);
    for (i = 0; i < count; i++) {
        c = src[i];
        dst[i] = (uint16_t)(((uint16_t)lut5[c >> 11] << 11) | ((uint16_t)lut6[(c >> 5) & 63] << 5)
                            | lut5[c & 31]);
    }
}

/* Show entries first..first+count-1 (all inside FADE_FIRST..FADE_LAST) at the current brightness. */
static void show(uint8_t first, uint8_t count)
{
    uint16_t out[CHUNK];
    uint8_t n;

    if (level >= FADE_FULL) {
        load_palette(&shadow[first - FADE_FIRST], first, count);
        return;
    }
    while (count) {
        n = count < CHUNK ? count : CHUNK;
        fade_scale(out, &shadow[first - FADE_FIRST], n, level);
        load_palette(out, first, n);
        first += n;
        count -= n;
    }
}
void fade_init(void)
{
    memset(shadow, 0, sizeof shadow);
    level = FADE_FULL;
    running = false;
    dirty = false;
    lut_valid = false;
}

void fade_start(bool clear, uint16_t ms)
{
    uint16_t target = clear ? FADE_FULL : 0;

    if (target == level) {
        running = false;
        return;
    }
    if (ms == 0) {
        level = target;
        running = false;
        dirty = true;
        return;
    }
    from_level = level;
    to_level = target;
    total_ms = ms;
    done_ms = 0;
    running = true;
}

void fade_update(uint16_t elapsed)
{
    uint16_t step;

    if (!running) {
        return;
    }
    if (elapsed >= total_ms - done_ms) {
        level = to_level;
        running = false;
    } else {
        done_ms += elapsed;
        if (to_level > from_level) {
            step = (uint16_t)((uint32_t)(to_level - from_level) * done_ms / total_ms);
            level = from_level + step;
        } else {
            step = (uint16_t)((uint32_t)(from_level - to_level) * done_ms / total_ms);
            level = from_level - step;
        }
    }
    dirty = true;
}

void fade_draw(void)
{
    if (dirty) {
        show(FADE_FIRST, (uint8_t)FADE_COUNT);
        dirty = false;
    }
}

void fade_palette(uint8_t first, const uint16_t *colors, uint8_t count)
{
    if (count == 0) {
        return;
    }
    if (first < FADE_FIRST || (uint16_t)first + count - 1 > FADE_LAST) {
        load_palette(colors, first, count);
        return;
    }
    memcpy(&shadow[first - FADE_FIRST], colors, (size_t)count * 2);
    show(first, count);
}

uint16_t fade_level(void)
{
    return level;
}

bool fade_active(void)
{
    return running;
}
