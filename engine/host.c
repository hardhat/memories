#include "main.h"
#include "memo_host.h"
#include "memo_vm.h"
#include "game.h"

enum {
    HOST_IDLE, HOST_DIALOG, HOST_TUTORIAL, HOST_TIMER, HOST_CHOICE, HOST_EXPLORE
};

static uint8_t state;
static uint16_t ms_left;
static uint8_t selected, count;
static bool confirmed, dirty;
static const char *prompt;
static const char *options[CHOICE_OPTIONS_MAX];
static uint8_t triggers[EXPLORE_TRIGGERS_MAX];

void memo_host_initialize(void)
{
    state = HOST_IDLE;
    ms_left = 0;
    confirmed = dirty = false;
    game_initialize();
}

bool host_busy(void)
{
    return state == HOST_DIALOG || state == HOST_TUTORIAL || state == HOST_TIMER;
}

void game_host_update(uint16_t elapsed)
{
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
    if (state == HOST_DIALOG || state == HOST_TUTORIAL) {
        if (input == INPUT_A || input == INPUT_START) {
            state = HOST_IDLE;
        }
    } else if (state == HOST_CHOICE || state == HOST_EXPLORE) {
        if (input == INPUT_UP || input == INPUT_LEFT) {
            selected = selected == 0 ? count-1 : selected-1;
            dirty = true;
        } else if (input == INPUT_DOWN || input == INPUT_RIGHT) {
            selected = (selected+1) % count;
            dirty = true;
        } else if (input == INPUT_A || input == INPUT_START) {
            confirmed = true;
        }
    }
}

void game_host_draw(void)
{
    uint8_t i;
    if (!dirty) {
        return;
    }
    dirty = false;
    /* Serial-only presentation until the tile/font/map renderers are bound. */
    if (state == HOST_DIALOG || state == HOST_TUTORIAL) {
        debug_log(prompt);
        debug_log("A/Start: continue");
    } else if (state == HOST_CHOICE) {
        debug_log(prompt);
        for (i = 0; i < count; i++) {
            debug_logf("%c %u: %s", i == selected ? '>' : ' ', i, options[i]);
        }
    } else if (state == HOST_EXPLORE) {
        for (i = 0; i < count; i++) {
            debug_logf("%c trigger %u", i == selected ? '>' : ' ', triggers[i]);
        }
    }
}

void host_say(uint8_t who, uint8_t expr, uint8_t style, const char *text)
{
    debug_logf("Dialog: character %u, expression %u, style %u", who, expr, style);
    prompt = text;
    state = HOST_DIALOG;
    dirty = true;
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
    debug_logf("CG %u (renderer not bound)", id);
}

void host_cg_off(void)
{
    debug_log("CG off (renderer not bound)");
}

void host_tutorial(uint8_t id, const char *text)
{
    debug_logf("Tutorial %u", id);
    prompt = text;
    state = HOST_TUTORIAL;
    dirty = true;
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
    uint8_t i, result;
    if (state != HOST_CHOICE) {
        prompt = text;
        count = n;
        selected = 0;
        confirmed = false;
        for (i = 0; i < n; i++) {
            options[i] = choices[i];
        }
        state = HOST_CHOICE;
        dirty = true;
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
    uint8_t i, result;
    (void)table_idx;
    if (state != HOST_EXPLORE) {
        debug_logf("Explore objective %u (serial trigger selection)", objective);
        count = n;
        selected = 0;
        confirmed = false;
        for (i = 0; i < n; i++) {
            triggers[i] = trig_id[i];
        }
        state = HOST_EXPLORE;
        dirty = true;
    }
    if (!confirmed) {
        return HOST_PENDING;
    }
    result = selected;
    state = HOST_IDLE;
    confirmed = false;
    return result;
}
