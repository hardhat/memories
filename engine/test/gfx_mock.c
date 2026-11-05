#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../Nicety.h"
#include "../main.h"
#include "gfx_mock.h"

uint8_t  mock_tileset[256][256];
uint8_t  mock_fg[40][80];
uint8_t  mock_bg[40][80];
uint16_t mock_palette[256];

unsigned mock_upload_calls;
unsigned mock_upload_bytes;
unsigned mock_log_count;
char     mock_last_log[256];
void   (*mock_log_hook)(const char *message);

uint8_t text_tiles[256 * 20];

static void fail(const char *what)
{
    fprintf(stderr, "gfx_mock: %s\n", what);
    exit(70);
}

void mock_reset_counters(void)
{
    mock_upload_calls = 0;
    mock_upload_bytes = 0;
}

void mock_reset_video(void)
{
    memset(mock_tileset, 0, sizeof mock_tileset);
    memset(mock_fg, 0, sizeof mock_fg);
    memset(mock_bg, 0, sizeof mock_bg);
    memset(mock_palette, 0, sizeof mock_palette);
    memset(text_tiles, 0, sizeof text_tiles);
    mock_reset_counters();
    mock_log_count = 0;
    mock_last_log[0] = '\0';
}

void debug_log(const char *message)
{
    mock_log_count++;
    strncpy(mock_last_log, message, sizeof mock_last_log - 1);
    mock_last_log[sizeof mock_last_log - 1] = '\0';
    if (mock_log_hook != NULL) {
        mock_log_hook(message);
    }
}

void debug_logf(const char *format, ...)
{
    char buffer[256];
    va_list args;

    va_start(args, format);
    vsnprintf(buffer, sizeof buffer, format, args);
    va_end(args);
    debug_log(buffer);
}

void clear_text_buffer(uint8_t color)
{
    memset(text_tiles, color, sizeof text_tiles);
}

void draw_text_pixel(uint16_t x, uint8_t y, uint8_t color)
{
    uint16_t offset = ((x >> 4) << 8) + (y << 4) + (x & 0x0F);

    if (offset >= sizeof text_tiles) {
        return;
    }
    text_tiles[offset] = color;
}

static void draw_char(uint16_t x, uint8_t y, uint8_t c, uint8_t color)
{
    const uint8_t *glyph;
    uint8_t i, j;

    if (c < 32 || c > 127) {
        c = 32;
    }
    glyph = FONT_NICETY_BITMAP + ((c - 32) << 3);
    for (j = 0; j < 8; j++) {
        for (i = 0; i < 8; i++) {
            if (glyph[j] & (1 << (7 - i))) {
                draw_text_pixel(x + i, y + j, color);
            }
        }
    }
}

void draw_text(uint16_t x, uint8_t y, const char *text, uint8_t color)
{
    size_t i;

    for (i = 0; i < strlen(text); i++) {
        draw_char(x + i * 8, y, (uint8_t)text[i], color);
    }
}

void draw_text_opaque(uint16_t x, uint8_t y, const char *text, uint8_t fg, uint8_t bg)
{
    size_t i;
    uint8_t row, col, c;

    for (i = 0; i < strlen(text); i++) {
        c = (uint8_t)text[i];
        if (c < 32 || c > 127) {
            c = 32;
        }
        for (row = 0; row < 8; row++) {
            for (col = 0; col < 8; col++) {
                draw_text_pixel(x + i * 8 + col, y + row,
                                (FONT_NICETY_BITMAP[((c - 32) << 3) + row] & (1 << (7 - col))) ? fg : bg);
            }
        }
    }
}

void render_text_buffer(uint16_t first_tile, uint16_t num_tiles)
{
    if (num_tiles > 20 || first_tile + num_tiles > 256) {
        fail("render_text_buffer outside the tileset");
    }
    memcpy(mock_tileset[first_tile], text_tiles, (size_t)num_tiles * 256);
    mock_upload_calls++;
    mock_upload_bytes += (unsigned)num_tiles * 256;
}

static void draw_layer(uint8_t layer[40][80], const uint8_t *data, uint8_t x, uint8_t y,
                       uint8_t width, uint8_t height)
{
    uint8_t j;

    if (x + width > 80 || y + height > 40) {
        fail("tilemap write outside the 80x40 map");
    }
    for (j = 0; j < height; j++) {
        memcpy(&layer[y + j][x], &data[j * width], width);
    }
}

void draw_fg(const uint8_t *data, uint8_t x, uint8_t y, uint8_t width, uint8_t height)
{
    draw_layer(mock_fg, data, x, y, width, height);
}

void draw_bg(const uint8_t *data, uint8_t x, uint8_t y, uint8_t width, uint8_t height)
{
    draw_layer(mock_bg, data, x, y, width, height);
}

void load_palette(const uint16_t *palette, uint8_t offset, uint8_t count)
{
    if ((unsigned)offset + count > 256) {
        fail("palette write outside 256 colours");
    }
    memcpy(&mock_palette[offset], palette, (size_t)count * 2);
}

void load_tileset(const uint8_t *tileset, uint16_t offset, uint16_t size, uint8_t palette_base)
{
    (void)palette_base;
    if ((offset & 0xFF) != 0 || (size & 0xFF) != 0 || (offset >> 8) + (size >> 8) > 256) {
        fail("load_tileset outside the tileset");
    }
    memcpy(mock_tileset[offset >> 8], tileset, size);
    mock_upload_calls++;
    mock_upload_bytes += size;
}

int mock_write_ppm(const char *path)
{
    FILE *f = fopen(path, "wb");
    int x, y;

    if (f == NULL) {
        return 0;
    }
    fprintf(f, "P6\n320 240\n255\n");
    for (y = 0; y < 240; y++) {
        for (x = 0; x < 320; x++) {
            int tx = x / 16, ty = y / 16, pixel = (y % 16) * 16 + x % 16;
            uint8_t index = mock_tileset[mock_fg[ty][tx]][pixel];
            uint16_t color;
            uint8_t rgb[3];

            if (index == 0) {
                index = mock_tileset[mock_bg[ty][tx]][pixel];
            }
            color = mock_palette[index];
            rgb[0] = (uint8_t)(((color >> 11) & 0x1F) * 255 / 31);
            rgb[1] = (uint8_t)(((color >> 5) & 0x3F) * 255 / 63);
            rgb[2] = (uint8_t)((color & 0x1F) * 255 / 31);
            fwrite(rgb, 1, 3, f);
        }
    }
    fclose(f);
    return 1;
}
