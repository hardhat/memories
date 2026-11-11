#include "main.h"
#include "memo_host.h"
#include "memo_dat.h"
#include "memo_vm.h"
#include "game.h"
#include "screen.h"
#include "portrait.h"
#include "cg.h"

enum {
    HOST_IDLE, HOST_DIALOG, HOST_TUTORIAL, HOST_TIMER, HOST_CHOICE, HOST_EXPLORE, HOST_CG_LOAD
};

#define EXPLORE_HEADER_MAX 28   /* leaves room for the " k/n" scroll position */

static const char *const trigger_names[TRIG_COUNT] = MEMO_TRIGGER_NAMES;

static uint8_t state;
static uint16_t ms_left;
static uint8_t selected, count;
static bool confirmed;
static const char *trigger_labels[EXPLORE_TRIGGERS_MAX];
static char explore_header[EXPLORE_HEADER_MAX + 1];

/* Append src to dst after len characters, never past EXPLORE_HEADER_MAX; returns the new length. */
static uint8_t append_text(char *dst, uint8_t len, const char *src)
{
    while (*src != '\0' && len < EXPLORE_HEADER_MAX) {
        dst[len++] = *src++;
    }
    dst[len] = '\0';
    return len;
}

void memo_host_initialize(void)
{
    state = HOST_IDLE;
    ms_left = 0;
    confirmed = false;
    screen_init();
    portrait_init();
    cg_init();
    game_initialize();
}

bool host_busy(void)
{
    return state == HOST_DIALOG || state == HOST_TUTORIAL || state == HOST_TIMER || state == HOST_CG_LOAD;
}

void game_host_update(uint16_t elapsed)
{
    screen_update(elapsed);
    if (state == HOST_CG_LOAD && cg_ready()) {
        state = HOST_IDLE;     /* the script resumes once the picture is on screen */
    }
    if (state == HOST_TIMER) {
        if (elapsed >= ms_left) {
            ms_left = 0;
            state = HOST_IDLE;
        } else {
            ms_left -= elapsed;
        }
    }
}

void game_host_input(uint8_t input)
{
    uint8_t before = selected;

    if (state == HOST_DIALOG || state == HOST_TUTORIAL) {
        /* Input is ignored until every row of the text is on screen. */
        if (screen_text_ready() && (input == INPUT_A || input == INPUT_START)) {
            state = HOST_IDLE;
        }
    } else if (state == HOST_CHOICE || state == HOST_EXPLORE) {
        if (input == INPUT_UP || input == INPUT_LEFT) {
            selected = selected == 0 ? count-1 : selected-1;
        } else if (input == INPUT_DOWN || input == INPUT_RIGHT) {
            selected = (selected+1) % count;
        } else if (input == INPUT_A || input == INPUT_START) {
            if (screen_text_ready()) {
                confirmed = true;
            }
        }
        if (selected != before) {
            if (state == HOST_CHOICE) {
                screen_menu_select(selected);
            } else {
                screen_list_select(selected);
            }
        }
    }
}

void game_host_draw(void)
{
    bool text = state == HOST_DIALOG || state == HOST_TUTORIAL;
    bool up, portraits_up;

    /* The box stays up while anything waits for the player, and across back-to-back
     * lines: the VM replaces the content in the same frame the previous one is dismissed. */
    if (!text && state != HOST_CHOICE && state != HOST_EXPLORE) {
        screen_text_hide();
    }
    screen_text_marker(text && screen_text_ready());

    /* Portraits stay up for a line and for a choice about it; anything else takes them down. */
    if (state != HOST_DIALOG && state != HOST_CHOICE) {
        portrait_hide();
    }
    /* The box has first call on the frame's one upload, then the CG, then the portraits. A CG
     * overwrites the portrait slots, so it waits until the portraits are down. */
    up = screen_draw();
    portraits_up = portrait_visible(PORTRAIT_LEFT, 0, 0) || portrait_visible(PORTRAIT_RIGHT, 0, 0);
    up = cg_draw(!up && !portraits_up) || up;
    portrait_draw(!up);
}

void host_say(uint8_t who, uint8_t expr, uint8_t style, const char *text)
{
    char name[SCREEN_NAME_MAX + 1];
    uint8_t side, exprs;

    if (!dat_load_char(who, &side, &exprs, name, sizeof name)) {
        name[0] = '\0';
        side = 0;
    }
    screen_text_show(name, text, style);
    if (cg_active()) {
        portrait_hide();      /* no portraits over a CG: the name plate says who speaks */
    } else {
        portrait_show(who, side, expr);
    }
    state = HOST_DIALOG;
}

void host_map(uint8_t map, uint8_t spawn, uint8_t time_of_day)
{
    debug_logf("Map %u spawn %u time %u (renderer not bound)", map, spawn, time_of_day);
}

void host_fade(uint8_t mode, uint8_t t10ms)
{
    debug_logf("Fade %u, %u x10ms (renderer not bound)", mode, t10ms);
    ms_left = (uint16_t)t10ms * 10;
    state = ms_left ? HOST_TIMER : HOST_IDLE;
}

void host_music(uint8_t id)
{
    debug_logf("Music %u (audio not bound)", id);
}

void host_sfx(uint8_t id)
{
    debug_logf("SFX %u (audio not bound)", id);
}

void host_cg(uint8_t id)
{
    if (cg_show(id)) {
        portrait_forget();     /* the CG takes over the portrait slots */
        state = HOST_CG_LOAD;  /* the script waits for the picture */
    }
}

void host_cg_off(void)
{
    cg_hide();
}

void host_tutorial(uint8_t id, const char *text)
{
    debug_logf("Tutorial %u", id);
    screen_text_show("Tutorial", text, 0);
    state = HOST_TUTORIAL;
}

void host_wait(uint8_t ticks)
{
    ms_left = (uint16_t)ticks * 16;
    state = ms_left ? HOST_TIMER : HOST_IDLE;
}

void host_end(void)
{
    debug_log("Scene ended");
}

uint8_t host_choose(const char *text, const char *const *choices, uint8_t n)
{
    uint8_t result;

    if (state != HOST_CHOICE) {
        count = n;
        selected = 0;
        confirmed = false;
        screen_menu_show(text, choices, n);
        state = HOST_CHOICE;
    }
    if (!confirmed) {
        return HOST_PENDING;
    }
    result = selected;
    state = HOST_IDLE;
    confirmed = false;
    return result;
}

uint8_t host_pick_trigger(uint8_t objective, const uint8_t *table_idx,
                          const uint8_t *trig_id, uint8_t n)
{
    uint8_t i, result, id, len;

    (void)table_idx;
    if (state != HOST_EXPLORE) {
        count = n;
        selected = 0;
        confirmed = false;
        for (i = 0; i < n; i++) {
            id = trig_id[i];
            trigger_labels[i] = id < TRIG_COUNT ? trigger_names[id] : "?";
        }
        /* A placeholder for walking the map: pick a place from a list. */
        len = append_text(explore_header, 0, "Go where?");
        if (objective < TRIG_COUNT) {
            len = append_text(explore_header, len, " Goal: ");
            append_text(explore_header, len, trigger_names[objective]);
        }
        screen_list_show(explore_header, trigger_labels, n, 0);
        state = HOST_EXPLORE;
    }
    if (!confirmed) {
        return HOST_PENDING;
    }
    result = selected;
    state = HOST_IDLE;
    confirmed = false;
    return result;
}
