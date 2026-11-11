#include <stdbool.h>
#include <stdint.h>

#include "main.h"
#include "memo_dat.h"
#include "fade.h"
#include "stream.h"

#define TILE_BYTES    256u
#define TILES_HEADER  4      /* TILESET block: bpp, comp, tile_count u16 */

static union {
    uint8_t  bytes[STREAM_CHUNK_TILES * TILE_BYTES];
    uint16_t words[STREAM_CHUNK_TILES * TILE_BYTES / 2];
} buffer;

bool stream_tiles(uint16_t block, uint16_t first, uint8_t n, uint16_t slot)
{
    if (n == 0 || n > STREAM_CHUNK_TILES) {
        return false;
    }
    if (!dat_read_block(block, TILES_HEADER + first * TILE_BYTES, buffer.bytes, (uint16_t)n * TILE_BYTES)) {
        return false;
    }
    load_tileset(buffer.bytes, slot * TILE_BYTES, (uint16_t)n * TILE_BYTES, 0);
    return true;
}

bool stream_palette(uint16_t block, uint8_t lo, uint8_t hi)
{
    uint8_t head[2];
    uint16_t n;

    if (!dat_read_block(block, 0, head, 2) || head[0] < lo || head[1] > hi || head[1] < head[0]) {
        return false;
    }
    n = head[1] - head[0] + 1;
    if (n > sizeof buffer.words / 2 || !dat_read_block(block, 2, buffer.words, n * 2)) {
        return false;
    }
    fade_palette(head[0], buffer.words, (uint8_t)n);
    return true;
}
