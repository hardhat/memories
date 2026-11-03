#include "main.h"
#include "memo_host.h"
#include "memo_dat.h"
#include "memo_vm.h"
#include "game.h"

static bool held[MAX_INPUT];
static uint8_t result;

void game_initialize(void)
{
    uint8_t i;
    for (i = 0; i < MAX_INPUT; i++) {
        held[i] = false;
    }
    /* main.c's legacy initialization runs before the DAT is open and passes
     * its cookie as the CRC. Re-establish the loader/VM contract here. */
    dat_close();
    result = dat_open("memo.dat", MEMO_CONTENT_CRC);
    if (result != DAT_OK) {
        debug_logf("DAT initialization failed: %u", result);
        result = MEMO_ERR_DAT;
        return;
    }
    result = memo_vm_init();
    if (result == MEMO_OK) {
        result = memo_start_game();
    }
    if (result != MEMO_RUNNING) {
        debug_logf("VM initialization failed: %s", memo_error_text(result));
    }
}

void game_handle_input(uint8_t input, bool pressed)
{
    if (input >= MAX_INPUT) {
        debug_logf("Invalid input: %u", input);
        return;
    }
    if (pressed && !held[input] && result == MEMO_RUNNING) {
        game_host_input(input);
    }
    held[input] = pressed;
}

void game_update(uint16_t elapsed)
{
    if (result != MEMO_RUNNING) {
        return;
    }
    game_host_update(elapsed);
    result = memo_step_game();
    if (result != MEMO_RUNNING && result != MEMO_OK) {
        debug_logf("VM failed in scene %u at PC %u: %s",
                   memo_fault_scene, memo_fault_pc, memo_error_text(result));
    }
}

void game_draw(void)
{
    game_host_draw();
}
