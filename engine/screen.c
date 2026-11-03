#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "main.h"
#include "layout.h"
#include "memo_vm.h"
#include "screen.h"

#define RGB565(r, g, b) ((uint16_t)((((r) >> 3) << 11) | (((g) >> 2) << 5) | ((b) >> 3)))

/* The box is three tile rows of 16 px: six 8 px text lines. Line 0 is the name plate,
 * lines 1-3 the dialog; lines 4-5 are spare and hold the continue arrow. */
#define BOX_LINES        (TEXT_ROWS * 2)
#define BODY_LINES       3
#define TEXT_X           ((SCREEN_COLS * 16 - DIALOG_COLS * 8) / 2)
#define MARKER_BLINK_MS  400
#define MARKER_COL       (SCREEN_COLS - 1)

static const uint16_t dialog_palette[PAL_DIALOG_COUNT] = {
    RGB565(0, 0, 0),         /* 0 shared transparent / black */
    RGB565(16, 20, 48),      /* 1 box background */
    RGB565(200, 184, 120),   /* 2 frame (reserved) */
    RGB565(240, 240, 224),   /* 3 body text */
    RGB565(232, 200, 96),    /* 4 name plate */
    RGB565(136, 216, 232),   /* 5 phone */
    RGB565(200, 200, 216),   /* 6 credits */
    RGB565(64, 72, 120),     /* 7 selection background */
    RGB565(255, 255, 255)    /* 8 continue arrow */
};

static const uint8_t style_colors[3] = {PAL_TEXT, PAL_PHONE, PAL_CREDITS};

enum { TXT_OFF, TXT_BUILD, TXT_SHOWN };

static uint8_t box_cells[DIALOG_TILES];      /* tile slots 1..60 in screen order */
static uint8_t clear_cells[DIALOG_TILES];    /* all zero: tile 0 is transparent on the FG layer */

static char    name_text[SCREEN_NAME_MAX + 1];
static char    body_text[MEMO_DIALOG_MAX];
static const char *lines[BOX_LINES];
static uint8_t line_color[BOX_LINES];

static uint8_t state;
static bool    visible;      /* box cells are on the FG layer */
static bool    swap;         /* rebuilding text that is already visible */
static bool    hide_pending;
static uint8_t build_row;
static bool    vram_blank[TEXT_ROWS];   /* the row's slots currently hold plain box background */

static bool     marker_want;
static bool     marker_phase;
static bool     marker_dirty;
static uint16_t marker_ms;

static bool line_empty(uint8_t i)
{
    return lines[i] == 0 || lines[i][0] == '\0';
}

static bool row_blank(uint8_t row)
{
    return line_empty(row * 2) && line_empty(row * 2 + 1);
}

/* Compose one tile row (two lines) in the off-screen buffer and upload it. */
static void upload_row(uint8_t row)
{
    uint8_t k, i;

    clear_text_buffer(PAL_BOX_BG);
    for (k = 0; k < 2; k++) {
        i = row * 2 + k;
        if (!line_empty(i)) {
            draw_text(TEXT_X, k * 8, lines[i], line_color[i]);
        }
    }
    render_text_buffer(SLOT_DIALOG + row * SCREEN_COLS, SCREEN_COLS);
    vram_blank[row] = row_blank(row);
}

static uint8_t text_top(void)
{
    return ROW_TEXT_MAP;
}

static void reveal_rows(uint8_t first, uint8_t count)
{
    draw_fg(&box_cells[first * SCREEN_COLS], 0, text_top() + first, SCREEN_COLS, count);
}

static void blank_rows(uint8_t first, uint8_t count)
{
    draw_fg(clear_cells, 0, text_top() + first, SCREEN_COLS, count);
}

void screen_init(void)
{
    uint8_t i, j;
    uint8_t zeros[80];

    load_palette(dialog_palette, 0, PAL_DIALOG_COUNT);

    for (i = 0; i < 80; i++) {
        zeros[i] = 0;
    }
    for (j = 0; j < 40; j++) {
        draw_bg(zeros, 0, j, 80, 1);
        draw_fg(zeros, 0, j, 80, 1);
    }

    /* Slot 0 stays an empty tile; the box background fills the dialog slots. */
    clear_text_buffer(PAL_TRANSPARENT);
    render_text_buffer(SLOT_EMPTY, 1);
    memset(lines, 0, sizeof(lines));
    for (i = 0; i < TEXT_ROWS; i++) {
        upload_row(i);
    }

    /* Continue arrow: a small downward triangle centered in its tile. */
    clear_text_buffer(PAL_BOX_BG);
    for (j = 0; j < 4; j++) {
        for (i = j; i < 8 - j; i++) {
            draw_text_pixel(4 + i, 8 + j, PAL_MARKER);
        }
    }
    render_text_buffer(SLOT_MARKER, 1);

    for (i = 0; i < DIALOG_TILES; i++) {
        box_cells[i] = SLOT_DIALOG + i;
    }
    state = TXT_OFF;
    visible = false;
    swap = false;
    hide_pending = false;
    marker_want = false;
    marker_phase = true;
    marker_dirty = false;
    marker_ms = 0;
}

void screen_text_show(const char *name, const char *text, uint8_t style)
{
    uint8_t n = 0, line = 1, i;
    char *p;
    uint8_t color = style_colors[style < 3 ? style : 0];

    name_text[0] = '\0';
    if (name != 0 && style != 2) {
        while (n < SCREEN_NAME_MAX && name[n] != '\0') {
            name_text[n] = name[n];
            n++;
        }
        name_text[n] = '\0';
    }

    memset(lines, 0, sizeof(lines));
    for (i = 0; i < MEMO_DIALOG_MAX - 1 && text != 0 && text[i] != '\0'; i++) {
        body_text[i] = text[i];
    }
    body_text[i] = '\0';

    lines[0] = name_text;
    line_color[0] = PAL_NAME;
    lines[1] = body_text;
    for (i = 0; body_text[i] != '\0'; i++) {
        if (body_text[i] == '\n') {
            body_text[i] = '\0';
            if (line < BODY_LINES) {
                lines[++line] = &body_text[i + 1];
            }
        }
    }
    for (i = 1; i <= BODY_LINES; i++) {
        line_color[i] = color;
        if (lines[i] != 0) {
            /* Strings are wrapped at build time; clip anyway, because text drawn past the
             * 20-tile buffer would corrupt memory. The scan stops at the first NUL, so it
             * never leaves body_text. */
            p = &body_text[lines[i] - body_text];
            for (n = 0; n < DIALOG_COLS && p[n] != '\0'; n++) {
            }
            p[n] = '\0';
        }
    }

    swap = visible;
    build_row = 0;
    hide_pending = false;
    state = TXT_BUILD;
}

void screen_text_hide(void)
{
    if (state != TXT_OFF) {
        hide_pending = true;
    }
}

bool screen_text_ready(void)
{
    return state == TXT_SHOWN && !hide_pending;
}

void screen_text_marker(bool on)
{
    if (marker_want != on) {
        marker_want = on;
        marker_dirty = true;
        marker_phase = true;
        marker_ms = 0;
    }
}

void screen_update(uint16_t elapsed)
{
    if (!marker_want) {
        return;
    }
    marker_ms += elapsed;
    if (marker_ms >= MARKER_BLINK_MS) {
        marker_ms = 0;
        marker_phase = !marker_phase;
        marker_dirty = true;
    }
}

/* Rows that are blank both now and in VRAM need no upload. */
static void skip_unchanged(void)
{
    while (build_row < TEXT_ROWS && row_blank(build_row) && vram_blank[build_row]) {
        build_row++;
    }
}

/* Upload the next row that changed. At most one upload per frame. */
static void build_step(void)
{
    uint8_t row;

    skip_unchanged();
    if (build_row < TEXT_ROWS) {
        row = build_row++;
        if (swap) {
            blank_rows(row, 1);
        }
        upload_row(row);
        if (swap) {
            reveal_rows(row, 1);
        }
        skip_unchanged();
    }
    if (build_row >= TEXT_ROWS) {
        /* A first showing stays invisible until every row is staged, then appears at once. */
        if (!swap) {
            reveal_rows(0, TEXT_ROWS);
        }
        visible = true;
        swap = false;
        state = TXT_SHOWN;
        marker_dirty = true;
    }
}

void screen_draw(void)
{
    uint8_t cell;

    if (hide_pending) {
        blank_rows(0, TEXT_ROWS);
        hide_pending = false;
        visible = false;
        swap = false;
        state = TXT_OFF;
        return;
    }
    if (state == TXT_BUILD) {
        build_step();
        return;
    }
    if (state == TXT_SHOWN && marker_dirty) {
        cell = (marker_want && marker_phase) ? SLOT_MARKER : box_cells[DIALOG_TILES - 1];
        draw_fg(&cell, MARKER_COL, text_top() + TEXT_ROWS - 1, 1, 1);
        marker_dirty = false;
    }
}
