#include <stdint.h>
#include <stdbool.h>

#include "memo_dat.h"
#include "memo_host.h"
#include "memo_vm.h"

#ifdef MEMO_TRACE_VARS
#define ON_VAR(i, v) host_var((i), (v))
#else
#define ON_VAR(i, v) ((void)0)
#endif

/* Prompt and options of one menu share a pool: the menu budget is CHOICE_LINES_MAX lines of
 * DIALOG_COLS characters, plus a newline between lines and a NUL per string. */
#define CHOICE_POOL (CHOICE_LINES_MAX * (DIALOG_COLS + 1) + CHOICE_OPTIONS_MAX + 1)

uint8_t  memo_vars[MEMO_VAR_MAX];
uint8_t  memo_var_count;
uint8_t  memo_tutorial_seen[4];
bool     memo_tutorial_once = true;
uint16_t memo_fault_pc;
uint8_t  memo_fault_scene;
char     memo_dialog[MEMO_DIALOG_MAX];

static uint8_t var_max[MEMO_VAR_MAX];
static char    choice_pool[CHOICE_POOL];

/* Current scene state. All of it is plain data so that a save is just variables + scene. */
static uint16_t call_stack[CALL_DEPTH_MAX];
static uint8_t  call_sp;
static bool     ex_active;
static uint16_t ex_pc;      /* address of the EXPLORE instruction */
static uint16_t ex_once;    /* triggers already used */

#define B(o) (dat_code[pc + (o)])
#define W(o) ((uint16_t)dat_code[pc + (o)] | ((uint16_t)dat_code[pc + (o) + 1] << 8))
#define NEED(len) do { if ((uint16_t)(pc + (len)) > dat_code_size) { err = MEMO_ERR_PC; goto fault; } } while (0)
#define CHECK_VAR(i) do { if ((i) >= memo_var_count) { err = MEMO_ERR_VAR; goto fault; } } while (0)

static void write_var(uint8_t i, uint8_t value)
{
    memo_vars[i] = value;
    ON_VAR(i, value);
}

uint8_t memo_vm_init(void)
{
    uint8_t init[MEMO_VAR_MAX];
    uint8_t i;

    if (!dat_load_vars(var_max, init, MEMO_VAR_MAX, &memo_var_count)) {
        return MEMO_ERR_DAT;
    }
    for (i = 0; i < memo_var_count; i++) {
        memo_vars[i] = init[i];
    }
    for (i = 0; i < 4; i++) {
        memo_tutorial_seen[i] = 0;
    }
    ex_active = false;
    call_sp = 0;
    return MEMO_OK;
}

/* Choose which enabled trigger fires next and set *target to its code address. */
static uint8_t next_trigger(uint16_t *target)
{
    uint8_t table_idx[EXPLORE_TRIGGERS_MAX];
    uint8_t trig_id[EXPLORE_TRIGGERS_MAX];
    uint8_t n = dat_code[ex_pc + 4];
    uint8_t avail = 0, i, k, t;
    uint16_t row;

    for (i = 0; i < n; i++) {
        row = ex_pc + 9 + 4 * (uint16_t)i;
        if (!((dat_code[row + 1] & 1) && ((ex_once >> i) & 1))) {
            table_idx[avail] = i;
            trig_id[avail] = dat_code[row];
            avail++;
        }
    }
    if (avail == 0) {
        return MEMO_ERR_EXPLORE;
    }
    k = host_pick_trigger(dat_code[ex_pc + 1], table_idx, trig_id, avail);
    if (k >= avail) {
        return MEMO_ERR_EXPLORE;
    }
    t = table_idx[k];
    row = ex_pc + 9 + 4 * (uint16_t)t;
    if (dat_code[row + 1] & 1) {
        ex_once |= (uint16_t)1 << t;
    }
    *target = (uint16_t)dat_code[row + 2] | ((uint16_t)dat_code[row + 3] << 8);
    return MEMO_OK;
}

uint8_t memo_run_scene(uint8_t scene)
{
    uint16_t pc;
    uint8_t err = MEMO_OK;
    uint8_t a, b, c, n, k, i, got;
    uint16_t sid;
    char *pool;
    const char *opts[CHOICE_OPTIONS_MAX];
    uint16_t left;

    memo_fault_scene = scene;
    if (dat_load_scene(scene) != DAT_OK) {
        memo_fault_pc = 0;
        return MEMO_ERR_DAT;
    }
    pc = dat_code_entry;
    call_sp = 0;
    ex_active = false;

    for (;;) {
        if (pc >= dat_code_size) {
            err = MEMO_ERR_PC;
            goto fault;
        }
        switch (dat_code[pc]) {
        case OP_END:
            host_end();
            return MEMO_OK;

        case OP_SAY:
            NEED(5);
            if (!dat_load_string(W(3), memo_dialog, MEMO_DIALOG_MAX)) {
                err = MEMO_ERR_STRING;
                goto fault;
            }
            host_say(B(1), B(2) & 0x1F, B(2) >> 5, memo_dialog);
            pc += 5;
            break;

        case OP_MAP:
            NEED(4);
            host_map(B(1), B(2), B(3));
            pc += 4;
            break;

        case OP_FADE:
            NEED(3);
            host_fade(B(1), B(2));
            pc += 3;
            break;

        case OP_MUSIC:
            NEED(2);
            host_music(B(1));
            pc += 2;
            break;

        case OP_SFX:
            NEED(2);
            host_sfx(B(1));
            pc += 2;
            break;

        case OP_CG:
            NEED(2);
            host_cg(B(1));
            pc += 2;
            break;

        case OP_CG_OFF:
            host_cg_off();
            pc += 1;
            break;

        case OP_TUTOR:
            NEED(4);
            a = B(1);
            if (memo_tutorial_once) {
                if (a >= 32) {
                    err = MEMO_ERR_TUTORIAL;
                    goto fault;
                }
                if (memo_tutorial_seen[a >> 3] & (1 << (a & 7))) {
                    pc += 4;
                    break;
                }
                memo_tutorial_seen[a >> 3] |= (uint8_t)(1 << (a & 7));
            }
            if (!dat_load_string(W(2), memo_dialog, MEMO_DIALOG_MAX)) {
                err = MEMO_ERR_STRING;
                goto fault;
            }
            host_tutorial(a, memo_dialog);
            pc += 4;
            break;

        case OP_WAIT:
            NEED(2);
            host_wait(B(1));
            pc += 2;
            break;

        case OP_SET:
            NEED(3);
            a = B(1);
            CHECK_VAR(a);
            write_var(a, B(2));
            pc += 3;
            break;

        case OP_ADD:
            NEED(3);
            a = B(1);
            CHECK_VAR(a);
            left = (uint16_t)memo_vars[a] + B(2);
            write_var(a, left > var_max[a] ? var_max[a] : (uint8_t)left);
            pc += 3;
            break;

        case OP_SUB:
            NEED(3);
            a = B(1);
            CHECK_VAR(a);
            write_var(a, memo_vars[a] > B(2) ? (uint8_t)(memo_vars[a] - B(2)) : 0);
            pc += 3;
            break;

        case OP_COPY:
            NEED(3);
            a = B(1);
            b = B(2);
            CHECK_VAR(a);
            CHECK_VAR(b);
            write_var(a, memo_vars[b]);
            pc += 3;
            break;

        case OP_SETBIT:
            NEED(2);
            a = B(1);
            CHECK_VAR(VAR_CLUES);
            if (a > 7) {
                err = MEMO_ERR_VAR;
                goto fault;
            }
            write_var(VAR_CLUES, memo_vars[VAR_CLUES] | (uint8_t)(1 << a));
            pc += 2;
            break;

        case OP_PICKMAX:
            NEED(3);
            a = B(1);
            n = B(2);
            CHECK_VAR(a);
            if (n == 0) {
                err = MEMO_ERR_OP;
                goto fault;
            }
            NEED(3 + 2 * (uint16_t)n);
            c = 0;
            got = 0;
            for (i = 0; i < n; i++) {
                b = B(3 + 2 * i);
                CHECK_VAR(b);
                if (i == 0 || memo_vars[b] > c) {
                    c = memo_vars[b];
                    got = B(4 + 2 * i);
                }
            }
            write_var(a, got);
            pc += 3 + 2 * (uint16_t)n;
            break;

        case OP_JMP:
            NEED(3);
            pc = W(1);
            break;

        case OP_BRF:
            NEED(6);
            a = B(1);
            b = B(2);
            CHECK_VAR(b);
            c = B(3);
            switch (a) {
            case CMP_EQ:  k = memo_vars[b] == c; break;
            case CMP_NE:  k = memo_vars[b] != c; break;
            case CMP_GTE: k = memo_vars[b] >= c; break;
            case CMP_LT:  k = memo_vars[b] < c; break;
            default:
                err = MEMO_ERR_OP;
                goto fault;
            }
            pc = k ? pc + 6 : W(4);
            break;

        case OP_BRFB:
            NEED(4);
            a = B(1);
            CHECK_VAR(VAR_CLUES);
            if (a > 7) {
                err = MEMO_ERR_VAR;
                goto fault;
            }
            pc = ((memo_vars[VAR_CLUES] >> a) & 1) ? pc + 4 : W(2);
            break;

        case OP_CALL:
            NEED(3);
            if (call_sp >= CALL_DEPTH_MAX) {
                err = MEMO_ERR_STACK;
                goto fault;
            }
            call_stack[call_sp++] = pc + 3;
            pc = W(1);
            break;

        case OP_RET:
            if (call_sp == 0) {
                err = MEMO_ERR_STACK;
                goto fault;
            }
            pc = call_stack[--call_sp];
            break;

        case OP_GOTO:
            NEED(3);
            call_sp = 0;
            ex_active = false;
            pc = W(1);
            break;

        case OP_CHOICE:
            NEED(4);
            n = B(3);
            if (n == 0 || n > CHOICE_OPTIONS_MAX) {
                err = MEMO_ERR_CHOICE;
                goto fault;
            }
            NEED(4 + 4 * (uint16_t)n);
            pool = choice_pool;
            left = CHOICE_POOL;
            got = dat_load_string(W(1), pool, (uint8_t)left);
            if (!got) {
                err = MEMO_ERR_STRING;
                goto fault;
            }
            pool += got;
            left -= got;
            for (i = 0; i < n; i++) {
                sid = W(4 + 4 * i);
                got = dat_load_string(sid, pool, (uint8_t)left);
                if (!got) {
                    err = MEMO_ERR_STRING;
                    goto fault;
                }
                opts[i] = pool;
                pool += got;
                left -= got;
            }
            k = host_choose(choice_pool, opts, n);
            if (k >= n) {
                err = MEMO_ERR_CHOICE;
                goto fault;
            }
            pc = W(4 + 4 * k + 2);
            break;

        case OP_EXPLORE:
            NEED(9);
            n = B(4);
            if (n == 0 || n > EXPLORE_TRIGGERS_MAX) {
                err = MEMO_ERR_EXPLORE;
                goto fault;
            }
            NEED(9 + 4 * (uint16_t)n);
            ex_active = true;
            ex_pc = pc;
            ex_once = 0;
            err = next_trigger(&pc);
            if (err) {
                goto fault;
            }
            break;

        case OP_XRET:
            if (!ex_active) {
                err = MEMO_ERR_EXPLORE;
                goto fault;
            }
            a = dat_code[ex_pc + 2];
            if (a != NO_VAR) {
                CHECK_VAR(a);
            }
            if (a != NO_VAR && memo_vars[a] >= dat_code[ex_pc + 3]) {
                pc = (uint16_t)dat_code[ex_pc + 5] | ((uint16_t)dat_code[ex_pc + 6] << 8);
            } else {
                err = next_trigger(&pc);
                if (err) {
                    goto fault;
                }
            }
            break;

        case OP_XEXIT:
            if (!ex_active) {
                err = MEMO_ERR_EXPLORE;
                goto fault;
            }
            pc = (uint16_t)dat_code[ex_pc + 7] | ((uint16_t)dat_code[ex_pc + 8] << 8);
            ex_active = false;
            break;

        default:
            err = MEMO_ERR_OP;
            goto fault;
        }
    }

fault:
    memo_fault_pc = pc;
    return err;
}

uint8_t memo_run_game(void)
{
    uint8_t n = 1, next, err;

    for (;;) {
        err = memo_run_scene(n);
        if (err) {
            return err;
        }
        if (VAR_SCENE >= memo_var_count) {
            return MEMO_ERR_VAR;
        }
        next = memo_vars[VAR_SCENE];
        if (next <= n || next > dat_scene_count) {
            return MEMO_OK;
        }
        n = next;
    }
}

const char *memo_error_text(uint8_t code)
{
    switch (code) {
    case MEMO_OK:          return "ok";
    case MEMO_ERR_DAT:     return "loader failure";
    case MEMO_ERR_PC:      return "program counter outside the scene code";
    case MEMO_ERR_OP:      return "unknown opcode or comparison";
    case MEMO_ERR_VAR:     return "variable or bit out of range";
    case MEMO_ERR_STACK:   return "call stack overflow or underflow";
    case MEMO_ERR_EXPLORE: return "explore misuse";
    case MEMO_ERR_CHOICE:  return "bad menu";
    case MEMO_ERR_STRING:  return "bad or oversized string";
    case MEMO_ERR_TUTORIAL: return "bad tutorial id";
    default:               return "unknown error";
    }
}
