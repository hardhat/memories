#include <stdint.h>
#include <stdbool.h>

#include "dat_io.h"
#include "memo_dat.h"

uint8_t  dat_code[CODE_BUF_SIZE];
uint16_t dat_code_size;
uint16_t dat_code_entry;
uint8_t  dat_scene_count;
uint32_t dat_crc;

static uint16_t entry_count;

/* Strings block of the loaded scene: where it is and how many strings it holds. */
static uint32_t str_offset;
static uint16_t str_size;
static uint16_t str_count;

static const uint8_t index_widths[DAT_TABLE_COUNT] = {1, 3, 1, 2, 2, 1, 1};

static uint16_t le16(const uint8_t *p)
{
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static uint32_t le32(const uint8_t *p)
{
    return (uint32_t)le16(p) | ((uint32_t)le16(p + 2) << 16);
}

static bool read_entry(uint16_t id, DatEntry *out)
{
    uint8_t raw[8];

    if (!dat_io_seek((uint32_t)id * 8u) || !dat_io_read(raw, 8)) {
        return false;
    }
    out->offset = le32(raw);
    out->size = le16(raw + 4);
    out->type = raw[6];
    out->flags = raw[7];
    return true;
}

uint8_t dat_open(const char *path, uint32_t expected_crc)
{
    DatEntry e;
    uint8_t meta[8];

    if (!dat_io_open(path)) {
        return DAT_ERR_OPEN;
    }
    if (!read_entry(0, &e)) {
        dat_close();
        return DAT_ERR_IO;
    }
    if (e.offset != MEMO_MAGIC || e.type != DAT_TYPE_MAGIC || e.size < 16 || (e.size & 7)) {
        dat_close();
        return DAT_ERR_MAGIC;
    }
    if (e.flags != MEMO_FORMAT_VERSION) {
        dat_close();
        return DAT_ERR_VERSION;
    }
    entry_count = e.size >> 3;

    /* META: u8 version, u8 scene_count, u16 string_total, u32 content_crc32 */
    if (!dat_read_block(BLOCK_META, 0, meta, 8)) {
        dat_close();
        return DAT_ERR_BLOCK;
    }
    dat_scene_count = meta[1];
    dat_crc = le32(meta + 4);
    if (expected_crc != 0 && dat_crc != expected_crc) {
        dat_close();
        return DAT_ERR_CRC;
    }
    return DAT_OK;
}

void dat_close(void)
{
    dat_io_close();
    entry_count = 0;
}

uint16_t dat_entry_count(void)
{
    return entry_count;
}

bool dat_entry(uint16_t id, DatEntry *out)
{
    return id < entry_count && read_entry(id, out);
}

bool dat_read_block(uint16_t id, uint16_t offset, void *dst, uint16_t n)
{
    DatEntry e;

    if (id == 0 || !dat_entry(id, &e) || e.type == DAT_TYPE_UNUSED) {
        return false;
    }
    if ((uint32_t)offset + n > e.size) {
        return false;
    }
    return dat_io_seek(e.offset + offset) && dat_io_read(dst, n);
}

bool dat_load_vars(uint8_t *vmax, uint8_t *vinit, uint8_t cap, uint8_t *count)
{
    uint8_t n;

    /* VARS: u8 count, u8 max[count], u8 init[count] */
    if (!dat_read_block(BLOCK_VARS, 0, &n, 1) || n > cap) {
        return false;
    }
    *count = n;
    return dat_read_block(BLOCK_VARS, 1, vmax, n) && dat_read_block(BLOCK_VARS, 1 + n, vinit, n);
}

uint8_t dat_load_scene(uint8_t scene)
{
    DatEntry e;
    uint8_t head[6];
    uint8_t cnt[2];

    if (scene < 1 || scene > dat_scene_count || scene > MEMO_MAX_SCENES) {
        return DAT_ERR_RANGE;
    }

    /* SCENE_CODE: u16 size, u16 entry_pc, u16 reserved, then the code */
    if (!dat_entry(SCENE_CODE_BASE + scene - 1, &e) || e.type != DAT_TYPE_SCENE_CODE) {
        return DAT_ERR_BLOCK;
    }
    if (!dat_read_block(SCENE_CODE_BASE + scene - 1, 0, head, 6)) {
        return DAT_ERR_IO;
    }
    dat_code_size = le16(head);
    dat_code_entry = le16(head + 2);
    if (dat_code_size > CODE_BUF_SIZE) {
        return DAT_ERR_RANGE;
    }
    if ((uint32_t)6 + dat_code_size > e.size || dat_code_entry >= dat_code_size) {
        return DAT_ERR_BLOCK;
    }
    if (!dat_read_block(SCENE_CODE_BASE + scene - 1, 6, dat_code, dat_code_size)) {
        return DAT_ERR_IO;
    }

    /* STRINGS: u16 count, u16 offset[count], then NUL terminated text */
    if (!dat_entry(SCENE_STR_BASE + scene - 1, &e) || e.type != DAT_TYPE_STRINGS) {
        return DAT_ERR_BLOCK;
    }
    if (!dat_read_block(SCENE_STR_BASE + scene - 1, 0, cnt, 2)) {
        return DAT_ERR_IO;
    }
    str_offset = e.offset;
    str_size = e.size;
    str_count = le16(cnt);
    if ((uint32_t)2 + 2u * str_count > str_size) {
        return DAT_ERR_BLOCK;
    }
    return DAT_OK;
}

uint8_t dat_load_string(uint16_t id, char *dst, uint8_t cap)
{
    uint8_t raw[2];
    uint16_t start, pos, n, i;

    if (id >= str_count || cap == 0) {
        return 0;
    }
    if (!dat_io_seek(str_offset + 2u + 2u * id) || !dat_io_read(raw, 2)) {
        return 0;
    }
    start = 2u + 2u * str_count;
    pos = start + le16(raw);
    if (pos >= str_size) {
        return 0;
    }
    n = str_size - pos;
    if (n > cap) {
        n = cap;
    }
    if (!dat_io_seek(str_offset + pos) || !dat_io_read(dst, n)) {
        return 0;
    }
    for (i = 0; i < n; i++) {
        if (dst[i] == '\0') {
            return (uint8_t)(i + 1);
        }
    }
    return 0;   /* no terminator within cap: the string does not fit */
}

uint8_t dat_index_width(uint8_t table)
{
    return table < DAT_TABLE_COUNT ? index_widths[table] : 0;
}

static bool index_find(uint8_t table, uint16_t *first, uint8_t *count)
{
    uint16_t pos = 0;
    uint8_t t, c;

    if (table >= DAT_TABLE_COUNT) {
        return false;
    }
    for (t = 0;; t++) {
        if (!dat_read_block(BLOCK_INDEX, pos, &c, 1)) {
            return false;
        }
        if (t == table) {
            *first = pos + 1;
            *count = c;
            return true;
        }
        pos += 1 + (uint16_t)c * 2u * index_widths[t];
    }
}

uint8_t dat_index_count(uint8_t table)
{
    uint16_t first;
    uint8_t count;

    return index_find(table, &first, &count) ? count : 0;
}

bool dat_index_get(uint8_t table, uint8_t i, uint16_t *out)
{
    uint16_t first;
    uint8_t count, w, k, raw[6];

    if (!index_find(table, &first, &count) || i >= count) {
        return false;
    }
    w = index_widths[table];
    if (!dat_read_block(BLOCK_INDEX, first + (uint16_t)i * 2u * w, raw, 2u * w)) {
        return false;
    }
    for (k = 0; k < w; k++) {
        out[k] = le16(raw + 2 * k);
    }
    return true;
}

bool dat_stream_block(uint16_t id, uint8_t *buf, uint16_t chunk, dat_sink_fn sink, void *ctx)
{
    DatEntry e;
    uint16_t left, n;

    if (!dat_entry(id, &e) || e.type == DAT_TYPE_UNUSED || chunk == 0) {
        return false;
    }
    if (e.size == 0) {
        return true;   /* missing art: nothing to load */
    }
    if (!dat_io_seek(e.offset)) {
        return false;
    }
    for (left = e.size; left; left -= n) {
        n = left < chunk ? left : chunk;
        if (!dat_io_read(buf, n) || !sink(buf, n, ctx)) {
            return false;
        }
    }
    return true;
}
