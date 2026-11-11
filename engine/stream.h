#ifndef STREAM_H
#define STREAM_H

/* Shared art streaming: one 2 KB buffer for everything that copies tiles or palettes out of
 * memo.dat into VRAM (title, portraits, CGs). Whole 16x16 8bpp tiles, STREAM_CHUNK_TILES at a
 * time, so a caller spreads a larger transfer over frames. The buffer is only used inside
 * a call, so modules can share it. */

#include <stdbool.h>
#include <stdint.h>

#define STREAM_CHUNK_TILES 8

/* Copy tiles [first, first + n) of the 8bpp uncompressed TILESET block `block` (after its 4 byte
 * header) into tile slots starting at `slot`. n is at most STREAM_CHUNK_TILES. */
bool stream_tiles(uint16_t block, uint16_t first, uint8_t n, uint16_t slot);

/* Load the entries stored in PALETTE block `block` (first, last, then RGB565 words) at their own
 * indices, through the fade (fade.h), so they show at the current brightness. Refuses, writing nothing, unless first and last lie inside lo..hi. */
bool stream_palette(uint16_t block, uint8_t lo, uint8_t hi);

#endif
