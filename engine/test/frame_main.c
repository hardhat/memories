/* Frame-level integration checks: the real game, host, screen and VM against a mock DAT and
 * the video model in gfx_mock.c. */
#include <assert.h>
#include <string.h>
#include "main.h"
#include "game.h"
#include "layout.h"
#include "memo_vm.h"
#include "memo_dat.h"
#include "gfx_mock.h"

uint8_t dat_code[CODE_BUF_SIZE];
uint16_t dat_code_size, dat_code_entry;
uint8_t dat_scene_count = 2;
uint32_t dat_crc;
static const uint8_t *scene_code;
static uint16_t scene_size;
static unsigned ends, loads;

static void on_log(const char *text)
{
    if (strcmp(text, "Scene ended") == 0) {
        ends++;
    }
}
uint8_t dat_open(const char *path, uint32_t crc)
{
    (void)path;
    assert(crc == MEMO_CONTENT_CRC);
    return DAT_OK;
}
void dat_close(void) {}
bool dat_load_vars(uint8_t *max, uint8_t *init, uint8_t cap, uint8_t *count)
{
    (void)cap;
    *count = 6;
    memset(max, 255, 6);
    memset(init, 0, 6);
    return true;
}
bool dat_load_char(uint8_t id, uint8_t *side, uint8_t *expr_count, char *name, uint8_t cap)
{
    (void)cap;
    if (id > 1) {
        return false;
    }
    strcpy(name, id == 1 ? "Jane" : "");
    *side = id == 1 ? 2 : 0;
    *expr_count = id == 1 ? 8 : 0;
    return true;
}
/* Jane's portrait (character 1): three expressions, so 16 tiles. Tile t is filled with t+1. */
#define JANE_PORTRAIT 40
#define JANE_TILES    41
#define JANE_PALETTE  42
#define JANE_TILE_COUNT 16
static const uint8_t jane_head[11] = {2, 4, 0, 0, 2, 2, 3, JANE_TILES, 0, JANE_PALETTE, 0};

static uint16_t jane_size(uint16_t id)
{
    return id == JANE_PORTRAIT ? sizeof jane_head : id == JANE_TILES ? 4 + JANE_TILE_COUNT * 256 : 2 + 4 * 2;
}

bool dat_entry(uint16_t id, DatEntry *out)
{
    if (id < JANE_PORTRAIT || id > JANE_PALETTE) {
        return false;
    }
    out->offset = 0;
    out->size = jane_size(id);
    out->type = DAT_TYPE_PORTRAIT;
    out->flags = 0;
    return true;
}
bool dat_index_get(uint8_t table, uint8_t i, uint16_t *out)
{
    if (table != DAT_TABLE_PORTRAITS || i != 1) {
        return false;
    }
    *out = JANE_PORTRAIT;
    return true;
}
bool dat_read_block(uint16_t id, uint16_t offset, void *dst, uint16_t n)
{
    uint8_t *d = dst;
    uint16_t k, pos;

    if (id < JANE_PORTRAIT || id > JANE_PALETTE || (uint32_t)offset + n > jane_size(id)) {
        return false;
    }
    for (k = 0; k < n; k++) {
        pos = offset + k;
        if (id == JANE_PORTRAIT) {
            d[k] = jane_head[pos];
        } else if (id == JANE_TILES) {
            d[k] = pos < 4 ? (uint8_t[]){8, 0, JANE_TILE_COUNT, 0}[pos] : (uint8_t)((pos - 4) / 256 + 1);
        } else {
            d[k] = pos == 0 ? PAL_PORTRAIT_RIGHT : pos == 1 ? PAL_PORTRAIT_RIGHT + 3 : 0x1F;
        }
    }
    return true;
}
uint8_t dat_load_scene(uint8_t scene)
{
    static const uint8_t final[] = {OP_END};
    loads++;
    dat_code_entry = 0;
    if (scene == 2) {
        memcpy(dat_code, final, sizeof final);
        dat_code_size = sizeof final;
    } else {
        memcpy(dat_code, scene_code, scene_size);
        dat_code_size = scene_size;
    }
    return DAT_OK;
}
/* String 0 fills one tile row; string 1 needs two. */
uint8_t dat_load_string(uint16_t id, char *dst, uint8_t cap)
{
    const char *text = id == 0 ? "line" : "a\nb\nc";
    uint8_t n = (uint8_t)strlen(text) + 1;

    assert(id < 2 && cap >= n);
    memcpy(dst, text, n);
    return n;
}

static void begin(const uint8_t *code, uint16_t size)
{
    scene_code = code;
    scene_size = size;
    ends = loads = 0;
    mock_reset_video();
    mock_log_hook = on_log;
    memo_host_initialize();
}

static void press(uint8_t input)
{
    game_handle_input(input, true);
    game_handle_input(input, false);
}

static void frame(void)
{
    game_update(16);
    game_draw();
}

static bool box_up(void)
{
    return mock_fg[ROW_TEXT_MAP][0] == SLOT_DIALOG && mock_fg[ROW_TEXT_MAP + 2][0] == SLOT_DIALOG + 40;
}

static bool box_down(void)
{
    uint8_t row, col;

    for (row = 0; row < TEXT_ROWS; row++) {
        for (col = 0; col < SCREEN_COLS; col++) {
            if (mock_fg[ROW_TEXT_MAP + row][col] != 0) {
                return false;
            }
        }
    }
    return true;
}

static unsigned color_in_row0(uint8_t color)
{
    unsigned i, n = 0;

    for (i = 0; i < 20u * 256; i++) {
        n += mock_tileset[SLOT_DIALOG][i] == color;
    }
    return n;
}

/* Selection-highlight pixels in one tile row of the box. */
static unsigned selected_rows(uint8_t row)
{
    unsigned i, n = 0;

    for (i = 0; i < 20u * 256; i++) {
        n += mock_tileset[SLOT_DIALOG + row * 20][i] == PAL_SELECT_BG;
    }
    return n;
}

/* A frame that also checks the screen as a whole keeps to one tile upload. */
static void checked_frame(void)
{
    game_update(16);
    mock_reset_counters();
    game_draw();
    assert(mock_upload_calls <= 1);
}

/* Jane (character 1, right side) is on screen showing expression `expr`. */
static bool jane_up(uint8_t expr)
{
    uint8_t i, want;

    for (i = 0; i < 8; i++) {
        want = SLOT_PORTRAIT_RIGHT + i;
        if (expr != 0 && i < 4) {
            want = SLOT_PORTRAIT_RIGHT + 8 + (expr - 1) * 4 + i;
        }
        if (mock_fg[ROW_PORTRAIT + i / 2][COL_PORTRAIT_RIGHT + i % 2] != want) {
            return false;
        }
    }
    return true;
}

static bool jane_down(void)
{
    uint8_t i;

    for (i = 0; i < 8; i++) {
        if (mock_fg[ROW_PORTRAIT + i / 2][COL_PORTRAIT_RIGHT + i % 2] != 0) {
            return false;
        }
    }
    return true;
}

int main(void)
{
    static const uint8_t dialog[] = {
        OP_CALL, 7, 0, OP_SET, 0, 9, OP_END,
        OP_SAY, 0, 0, 0, 0, OP_RET
    };
    static const uint8_t slow_dialog[] = {OP_SAY, 0, 0, 1, 0, OP_SET, 0, 6, OP_END};
    static const uint8_t named[] = {OP_SAY, 1, 0, 0, 0, OP_END};
    static const uint8_t twice[] = {OP_SAY, 0, 0, 0, 0, OP_SAY, 0, 0, 0, 0, OP_WAIT, 5, OP_END};
    static const uint8_t wait[] = {OP_WAIT, 3, OP_SET, 0, 7, OP_END};
    static const uint8_t fade[] = {OP_FADE, 1, 3, OP_SET, 0, 4, OP_END};
    static const uint8_t tutorial[] = {
        OP_TUTOR, 0, 0, 0, OP_TUTOR, 0, 0, 0, OP_SET, 0, 5, OP_END
    };
    static const uint8_t menu[] = {
        OP_CHOICE, 0, 0, 2, 0, 0, 12, 0, 0, 0, 16, 0,
        OP_SET, 0, 1, OP_END, OP_SET, 0, 2, OP_END
    };
    static const uint8_t explore[] = {
        OP_EXPLORE, 0, NO_VAR, 0, 2, 0, 0, 29, 0,
        0, 1, 17, 0, 1, 0, 21, 0,
        OP_ADD, 0, 1, OP_XRET,
        OP_ADD, 0, 2, OP_XEXIT,
        OP_END, OP_END, OP_END, OP_END, OP_END
    };
    static const uint8_t transition[] = {OP_SET, VAR_SCENE, 2, OP_END};
    static const uint8_t jane_say[] = {OP_SAY, 1, 2, 0, 0, OP_END};
    static const uint8_t jane_twice[] = {OP_SAY, 1, 0, 0, 0, OP_SAY, 1, 2, 0, 0, OP_END};
    static const uint8_t jane_menu[] = {
        OP_SAY, 1, 0, 0, 0,
        OP_CHOICE, 0, 0, 2, 0, 0, 17, 0, 0, 0, 21, 0,
        OP_SET, 0, 1, OP_END, OP_SET, 0, 2, OP_END
    };
    static const uint8_t loop[] = {OP_JMP, 0, 0};
    static const uint8_t bad[] = {0x7f};
    uint8_t i;

    /* A dialog waits for the player; the box stays up and the script does not advance. */
    begin(dialog, sizeof dialog);
    assert(box_down());
    frame();
    assert(memo_vars[0] == 0 && box_up());
    for (i = 0; i < 10; i++) {
        frame();
    }
    assert(loads == 1 && memo_vars[0] == 0 && box_up());
    press(INPUT_A);
    game_update(16);
    assert(memo_vars[0] == 9 && ends == 1);
    game_draw();
    assert(box_down());
    frame();
    assert(ends == 1);

    /* Input is ignored until every row of the text is on screen. */
    begin(slow_dialog, sizeof slow_dialog);
    game_update(16);
    game_draw();
    assert(!box_up() && box_down());
    press(INPUT_A);
    game_update(16);
    assert(memo_vars[0] == 0);
    game_draw();
    assert(box_up());
    press(INPUT_A);
    game_update(16);
    assert(memo_vars[0] == 6 && ends == 1);

    /* The speaker's name comes from the CHARS block. */
    begin(named, sizeof named);
    frame();
    assert(box_up() && color_in_row0(PAL_NAME) > 0);

    /* Consecutive lines keep the box up; a wait afterwards takes it down. */
    begin(twice, sizeof twice);
    frame();
    assert(box_up());
    press(INPUT_A);
    frame();
    assert(box_up());
    press(INPUT_A);
    frame();
    assert(box_down());

    begin(wait, sizeof wait);
    game_update(16);
    for (i = 0; i < 2; i++) {
        game_update(16);
        assert(memo_vars[0] == 0);
    }
    game_update(16);
    assert(memo_vars[0] == 7 && ends == 1);

    begin(wait, sizeof wait);
    game_update(16);
    game_update(0);
    game_update(20);
    game_update(27);
    assert(memo_vars[0] == 0);
    game_update(1);
    assert(memo_vars[0] == 7);

    begin(fade, sizeof fade);
    game_update(16);
    game_update(16);
    assert(memo_vars[0] == 0);
    game_update(16);
    assert(memo_vars[0] == 4);

    /* A tutorial uses the same box with a fixed name plate and is shown once. */
    begin(tutorial, sizeof tutorial);
    frame();
    assert(memo_vars[0] == 0 && box_up() && color_in_row0(PAL_NAME) > 0);
    press(INPUT_START);
    game_update(16);
    assert(memo_vars[0] == 5 && ends == 1);

    begin(menu, sizeof menu);
    game_update(16);
    game_draw();
    assert(!box_up() && memo_vars[0] == 0);   /* two rows to draw; the first is staged */
    press(INPUT_A);                           /* too early: nothing is confirmed */
    game_update(16);
    assert(memo_vars[0] == 0 && ends == 0);
    game_draw();
    assert(box_up() && selected_rows(0) > 0);
    game_handle_input(INPUT_DOWN, true);
    game_handle_input(INPUT_DOWN, true); /* key repeat is not another selection */
    game_handle_input(INPUT_DOWN, false);
    frame();
    frame();
    assert(box_up());
    press(INPUT_A);
    game_update(16);
    assert(memo_vars[0] == 2 && ends == 1);
    game_draw();
    assert(box_down());

    /* The trigger picker lists the available places and names the goal. */
    begin(explore, sizeof explore);
    frame();
    frame();
    assert(box_up() && color_in_row0(PAL_NAME) > 0 && selected_rows(0) > 0);
    press(INPUT_A);
    game_update(16);
    assert(memo_vars[0] == 1 && ends == 0);
    frame();
    frame();
    assert(box_up());
    game_update(16); /* pending XRET must retain the once-trigger mask */
    press(INPUT_A);
    game_update(16);
    assert(memo_vars[0] == 3 && ends == 1);

    /* A speaker with a portrait: the box has the first upload of each frame, then the palette
     * and tiles stream in, and the portrait goes away with the box. */
    begin(jane_say, sizeof jane_say);
    for (i = 0; i < 10; i++) {
        checked_frame();
    }
    assert(box_up() && jane_up(2));
    press(INPUT_A);
    game_update(16);
    assert(ends == 1);
    game_draw();
    assert(box_down() && jane_down());

    /* The next line by the same speaker changes the head cells and uploads nothing. */
    begin(jane_twice, sizeof jane_twice);
    for (i = 0; i < 10; i++) {
        checked_frame();
    }
    assert(jane_up(0));
    press(INPUT_A);
    mock_reset_counters();
    game_update(16);
    game_draw();
    assert(box_up() && jane_up(2));
    assert(mock_upload_calls == 0);                   /* the same text is already in VRAM */

    /* A choice about the line keeps the portrait; the end of the scene removes it. */
    begin(jane_menu, sizeof jane_menu);
    for (i = 0; i < 10; i++) {
        checked_frame();
    }
    press(INPUT_A);
    for (i = 0; i < 6; i++) {
        checked_frame();
    }
    assert(box_up() && jane_up(0));
    press(INPUT_A);
    game_update(16);
    assert(memo_vars[0] == 1 && ends == 1);
    game_draw();
    assert(box_down() && jane_down());

    begin(transition, sizeof transition);
    game_update(16);
    assert(loads == 2 && ends == 1);
    game_update(16);
    assert(ends == 2);
    game_update(16);
    assert(ends == 2);

    begin(loop, sizeof loop);
    assert(memo_step_game() == MEMO_RUNNING); /* bounded even with no host op */
    assert(memo_step_game() == MEMO_RUNNING);

    begin(bad, sizeof bad);
    assert(memo_step_game() == MEMO_ERR_OP);
    assert(memo_step_game() == MEMO_ERR_OP);
    assert(memo_fault_pc == 0 && memo_fault_scene == 1);
    return 0;
}
