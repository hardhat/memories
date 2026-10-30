#ifndef MEMO_HOST_H
#define MEMO_HOST_H

/* What the script VM needs from the game. The VM decides nothing about presentation: it calls
 * these functions in script order and the game (or the desktop trace harness) implements them.
 * Strings passed in are valid only for the duration of the call. */

#include <stdint.h>

/* Dialog line. expr is the expression index (EXPR_NONE = no portrait change), style 0 normal,
 * 1 phone, 2 credits. */
void host_say(uint8_t who, uint8_t expr, uint8_t style, const char *text);

void host_map(uint8_t map, uint8_t spawn, uint8_t time_of_day);
void host_fade(uint8_t mode, uint8_t t10ms);   /* mode 0 clear, 1 black; time in 10 ms units */
void host_music(uint8_t id);
void host_sfx(uint8_t id);
void host_cg(uint8_t id);
void host_cg_off(void);
void host_tutorial(uint8_t id, const char *text);
void host_wait(uint8_t ticks);
void host_end(void);

/* Menu: prompt, n options (1..CHOICE_OPTIONS_MAX). Returns the picked index 0..n-1. */
uint8_t host_choose(const char *prompt, const char *const *options, uint8_t n);

/* Map exploration. objective is the trigger id to mark (NO_TRIGGER = none). The player may
 * use any of the n currently enabled triggers: table_idx[k] is its position in the script's
 * explore table, trig_id[k] its global trigger id. Returns k in 0..n-1. */
uint8_t host_pick_trigger(uint8_t objective, const uint8_t *table_idx, const uint8_t *trig_id, uint8_t n);

#ifdef MEMO_TRACE_VARS
/* Called after every variable write (the desktop harness traces them; the game does not). */
void host_var(uint8_t idx, uint8_t value);
#endif

#endif /* MEMO_HOST_H */
