#ifndef MEMO_VM_H
#define MEMO_VM_H

/* Script VM (compiler-spec.md sections 6 and 10). It executes the bytecode that memo_dat.c
 * loaded and calls the host_* functions of memo_host.h. It mirrors interp.VM in
 * script/tools/memo/interp.py; the two are kept equal by the trace comparison (section 9). */

#include <stdbool.h>
#include <stdint.h>

#include "memo_ids.h"

#define MEMO_VAR_MAX        64     /* RAM reserved for variables; the file has 44 today */
#define MEMO_DIALOG_MAX     128    /* DIALOG_MAX_STRING */

/* Run results. 0 is success; anything else is a corrupt or hostile script and carries the
 * scene (memo_fault_scene) and the program counter (memo_fault_pc) of the failing instruction. */
#define MEMO_OK              0
#define MEMO_ERR_DAT         1   /* loader failure */
#define MEMO_ERR_PC          2   /* pc outside the code, or an operand runs past the end */
#define MEMO_ERR_OP          3   /* unknown opcode, or a bad comparison code */
#define MEMO_ERR_VAR         4   /* variable or bit number out of range */
#define MEMO_ERR_STACK       5   /* call depth exceeded, or RET without CALL */
#define MEMO_ERR_EXPLORE     6   /* XRET/XEXIT outside an explore, bad table, nothing to pick */
#define MEMO_ERR_CHOICE      7   /* bad option count or host result */
#define MEMO_ERR_STRING      8   /* string id bad or text does not fit its buffer */
#define MEMO_ERR_TUTORIAL    9   /* tutorial id above 31 */

extern uint8_t  memo_vars[MEMO_VAR_MAX];
extern uint8_t  memo_var_count;
extern uint8_t  memo_tutorial_seen[4];   /* saved with the variables; bit n set = tutorial n shown */
extern bool     memo_tutorial_once;      /* true in the game; the trace harness turns it off */
extern uint16_t memo_fault_pc;
extern uint8_t  memo_fault_scene;
extern char     memo_dialog[MEMO_DIALOG_MAX];

/* Load VARS from the open file and reset all state. */
uint8_t memo_vm_init(void);

/* Run one scene from its entry point until END. */
uint8_t memo_run_scene(uint8_t scene);

/* Run scene 1, then follow the `scene` variable until a scene leaves it unchanged. */
uint8_t memo_run_game(void);

const char *memo_error_text(uint8_t code);

#endif /* MEMO_VM_H */
