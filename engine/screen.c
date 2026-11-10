#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "main.h"
#include "layout.h"
#include "memo_vm.h"
#include "screen.h"

#define RGB565(r, g, b) ((uint16_t)((((r) >> 3) << 11) | (((g) >> 2) << 5) | ((b) >> 3)))

/* The box is three tile rows of 16 px: six text lines of 8 px. */
#define BOX_LINES        (TEXT_ROWS * 2)
#define BODY_LINES       3
#define LINE_CAP         (DIALOG_COLS + 1)
#define TEXT_X           ((SCREEN_COLS * 16 - DIALOG_COLS * 8) / 2)
#define MARK_X           (TEXT_X - 12)
#define MARKER_BLINK_MS  400
#define MARKER_COL       (SCREEN_COLS - 1)
#define MENU_MAX         CHOICE_OPTIONS_MAX

static const uint16_t dialog_palette[PAL_DIALOG_COUNT] = {
    RGB565(0, 0, 0),         /* 0 shared transparent / black */
    RGB565(16, 20, 48),      /* 1 box background */
    RGB565(200, 184, 120),   /* 2 frame (reserved) */
    RGB565(240, 240, 224),   /* 3 body text */
    RGB565(232, 200, 96),    /* 4 name plate */
    RGB565(136, 216, 232),   /* 5 phone */
    RGB565(200, 200, 216),   /* 6 credits */
    RGB565(64, 72, 120),     /* 7 selection background */
    RGB565(255, 255, 255)    /* 8 continue arrow, selection mark */
};

static const uint8_t style_colors[3] = {PAL_TEXT, PAL_PHONE, PAL_CREDITS};

enum { TXT_OFF, TXT_BUILD, TXT_SHOWN };
enum { KIND_TEXT, KIND_MENU, KIND_LIST };

static uint8_t box_cells[DIALOG_TILES];      /* tile slots 1..60 in screen order */
static uint8_t clear_cells[DIALOG_TILES];    /* all zero: tile 0 is transparent on the FG layer */

/* What the six lines say. Rows whose lines differ from VRAM are marked in row_dirty. */
static char    line_buf[BOX_LINES][LINE_CAP];
static uint8_t line_color[BOX_LINES];
static uint8_t line_bg[BOX_LINES];           /* 0 = plain, else a full-width highlight colour */
static bool    line_mark[BOX_LINES];         /* '>' in the left margin */
static uint8_t placed;                       /* lines set by the current layout */
static uint8_t row_dirty;

static uint8_t kind;
static uint8_t menu_n, menu_first[MENU_MAX], menu_lines[MENU_MAX];
static const char *const *list_items;
static uint8_t list_n, list_top;
static char    list_header[LINE_CAP];

static uint8_t state;
static bool    visible;      /* box cells are on the FG layer */
static bool    swap;         /* rebuilding content that is already visible */
static bool    in_place;     /* upload visible rows without blanking them first */
static bool    hide_pending;
static uint8_t build_row;

static bool     marker_want;
static bool     marker_phase;
static bool     marker_dirty;
static uint16_t marker_ms;

/* Set one line. A line identical to the current one costs nothing. */
static void put_line(uint8_t i, const char *src, uint8_t max, uint8_t color, uint8_t bg, bool mark)
{
    char tmp[LINE_CAP];
    uint8_t n = 0;

    if (max > DIALOG_COLS) {
        max = DIALOG_COLS;
    }
    while (n < max && src[n] != '\0' && src[n] != '\n') {
        tmp[n] = src[n];
        n++;
    }
    tmp[n] = '\0';
    if (n == 0 && bg == 0) {
        color = PAL_TEXT;     /* an empty plain line looks the same whatever its colour */
    }
    placed |= (uint8_t)(1u << i);
    if (strcmp(tmp, line_buf[i]) != 0 || color != line_color[i] || bg != line_bg[i] || mark != line_mark[i]) {
        memcpy(line_buf[i], tmp, (size_t)n + 1);
        line_color[i] = color;
        line_bg[i] = bg;
        line_mark[i] = mark;
        row_dirty |= (uint8_t)(1u << (i >> 1));
    }
}

static void set_attr(uint8_t i, uint8_t bg, bool mark)
{
    if (line_bg[i] != bg || line_mark[i] != mark) {
        line_bg[i] = bg;
        line_mark[i] = mark;
        row_dirty |= (uint8_t)(1u << (i >> 1));
    }
}

/* Put text split at '\n' on consecutive lines; returns the lines used (at least one). */
static uint8_t put_text(const char *text, uint8_t first, uint8_t max_lines, uint8_t color)
{
    uint8_t used = 0;

    while (used < max_lines) {
        put_line(first + used, text, DIALOG_COLS, color, 0, false);
        used++;
        while (*text != '\0' && *text != '\n') {
            text++;
        }
        if (*text == '\0') {
            break;
        }
        text++;
    }
    return used;
}

static void begin_layout(void)
{
    placed = 0;
}

static void end_layout(void)
{
    uint8_t i;

    for (i = 0; i < BOX_LINES; i++) {
        if (!(placed & (1u << i))) {
            put_line(i, "", 0, PAL_TEXT, 0, false);
        }
    }
}

static void upload_row(uint8_t row)
{
    uint8_t k, i, n;
    char pad[LINE_CAP];

    clear_text_buffer(PAL_BOX_BG);
    for (k = 0; k < 2; k++) {
        i = row * 2 + k;
        if (line_bg[i]) {
            /* Pad with spaces so the highlight spans the whole text width. */
            n = (uint8_t)strlen(line_buf[i]);
            memcpy(pad, line_buf[i], n);
            memset(pad + n, ' ', DIALOG_COLS - n);
            pad[DIALOG_COLS] = '\0';
            draw_text_opaque(TEXT_X, k * 8, pad, line_color[i], line_bg[i]);
        } else if (line_buf[i][0] != '\0') {
            draw_text(TEXT_X, k * 8, line_buf[i], line_color[i]);
        }
        if (line_mark[i]) {
            draw_text(MARK_X, k * 8, ">", PAL_MARKER);
        }
    }
    render_text_buffer(SLOT_DIALOG + row * SCREEN_COLS, SCREEN_COLS);
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
    memset(line_buf, 0, sizeof(line_buf));
    memset(line_color, PAL_TEXT, sizeof(line_color));
    memset(line_bg, 0, sizeof(line_bg));
    memset(line_mark, 0, sizeof(line_mark));
    for (i = 0; i < TEXT_ROWS; i++) {
        upload_row(i);
    }
    row_dirty = 0;

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
    kind = KIND_TEXT;
    state = TXT_OFF;
    visible = false;
    swap = false;
    in_place = false;
    hide_pending = false;
    marker_want = false;
    marker_phase = true;
    marker_dirty = false;
    marker_ms = 0;
}

/* New content: rebuild whatever differs, hiding nothing that is already right. */
static void request_show(void)
{
    end_layout();
    swap = visible;
    in_place = false;
    build_row = 0;
    hide_pending = false;
    state = TXT_BUILD;
}

/* A small change inside content that is already up (a selection move). */
static void request_update(void)
{
    end_layout();
    if (state == TXT_OFF || row_dirty == 0) {
        return;
    }
    if (state == TXT_SHOWN) {
        swap = true;
        in_place = true;
        state = TXT_BUILD;
    }
    build_row = 0;
}

void screen_text_show(const char *name, const char *text, uint8_t style)
{
    begin_layout();
    put_line(0, name != 0 && style != 2 ? name : "", SCREEN_NAME_MAX, PAL_NAME, 0, false);
    put_text(text != 0 ? text : "", 1, BODY_LINES, style_colors[style < 3 ? style : 0]);
    kind = KIND_TEXT;
    request_show();
}

static void menu_highlight(uint8_t selected)
{
    uint8_t k, l;

    for (k = 0; k < menu_n; k++) {
        for (l = 0; l < menu_lines[k]; l++) {
            set_attr(menu_first[k] + l, k == selected ? PAL_SELECT_BG : 0, k == selected && l == 0);
        }
    }
}

void screen_menu_show(const char *prompt, const char *const *options, uint8_t n)
{
    uint8_t k, used = 0, allowed;

    if (n > MENU_MAX) {
        n = MENU_MAX;
    }
    begin_layout();
    if (prompt != 0 && prompt[0] != '\0') {
        used = put_text(prompt, 0, BOX_LINES - n, PAL_TEXT);
    }
    for (k = 0; k < n; k++) {
        /* Leave one line for every option still to come. */
        allowed = BOX_LINES - used - (n - 1 - k);
        menu_first[k] = used;
        menu_lines[k] = put_text(options[k], used, allowed, PAL_TEXT);
        used += menu_lines[k];
    }
    menu_n = n;
    kind = KIND_MENU;
    menu_highlight(0);
    request_show();
}

void screen_menu_select(uint8_t selected)
{
    if (kind != KIND_MENU || selected >= menu_n) {
        return;
    }
    menu_highlight(selected);
    request_update();
}

static void list_layout(uint8_t selected)
{
    uint8_t j, idx, n = 0;
    char header[LINE_CAP];

    /* Keep the selection inside the window. */
    if (selected < list_top) {
        list_top = selected;
    } else if (selected >= list_top + SCREEN_LIST_ROWS) {
        list_top = selected + 1 - SCREEN_LIST_ROWS;
    }
    begin_layout();
    while (n < DIALOG_COLS && list_header[n] != '\0') {
        header[n] = list_header[n];
        n++;
    }
    if (list_n > SCREEN_LIST_ROWS && n + 7 <= DIALOG_COLS) {
        /* " k/n", each number at most two digits (the explore limit is 16). */
        header[n++] = ' ';
        if (selected + 1 >= 10) {
            header[n++] = '0' + (selected + 1) / 10;
        }
        header[n++] = '0' + (selected + 1) % 10;
        header[n++] = '/';
        if (list_n >= 10) {
            header[n++] = '0' + list_n / 10;
        }
        header[n++] = '0' + list_n % 10;
    }
    header[n] = '\0';
    put_line(0, header, DIALOG_COLS, PAL_NAME, 0, false);
    for (j = 0; j < SCREEN_LIST_ROWS; j++) {
        idx = list_top + j;
        if (idx < list_n) {
            put_line(1 + j, list_items[idx], DIALOG_COLS, PAL_TEXT,
                     idx == selected ? PAL_SELECT_BG : 0, idx == selected);
        }
    }
}

void screen_list_show(const char *header, const char *const *items, uint8_t n, uint8_t selected)
{
    uint8_t i;

    for (i = 0; i < DIALOG_COLS && header != 0 && header[i] != '\0'; i++) {
        list_header[i] = header[i];
    }
    list_header[i] = '\0';
    list_items = items;
    list_n = n;
    list_top = 0;
    kind = KIND_LIST;
    list_layout(selected < n ? selected : 0);
    request_show();
}

void screen_list_select(uint8_t selected)
{
    if (kind != KIND_LIST || selected >= list_n) {
        return;
    }
    list_layout(selected);
    request_update();
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

static void skip_clean(void)
{
    while (build_row < TEXT_ROWS && !(row_dirty & (1u << build_row))) {
        build_row++;
    }
}

/* Upload the next row that changed. At most one upload per frame. */
static bool build_step(void)
{
    uint8_t row;
    bool uploaded = false;

    skip_clean();
    if (build_row < TEXT_ROWS) {
        row = build_row++;
        if (swap && !in_place) {
            blank_rows(row, 1);
        }
        upload_row(row);
        uploaded = true;
        row_dirty &= (uint8_t)~(1u << row);
        if (swap) {
            reveal_rows(row, 1);
        }
        skip_clean();
    }
    if (build_row >= TEXT_ROWS) {
        /* A first showing stays invisible until every row is staged, then appears at once. */
        if (!swap) {
            reveal_rows(0, TEXT_ROWS);
        }
        visible = true;
        swap = false;
        in_place = false;
        state = TXT_SHOWN;
        marker_dirty = true;
    }
    return uploaded;
}

bool screen_draw(void)
{
    uint8_t cell;

    if (hide_pending) {
        blank_rows(0, TEXT_ROWS);
        hide_pending = false;
        visible = false;
        swap = false;
        in_place = false;
        state = TXT_OFF;
        return false;
    }
    if (state == TXT_BUILD) {
        return build_step();
    }
    if (state == TXT_SHOWN && marker_dirty) {
        cell = (marker_want && marker_phase && kind == KIND_TEXT) ? SLOT_MARKER : box_cells[DIALOG_TILES - 1];
        draw_fg(&cell, MARKER_COL, text_top() + TEXT_ROWS - 1, 1, 1);
        marker_dirty = false;
    }
    return false;
}
