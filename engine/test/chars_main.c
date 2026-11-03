/* Prints every CHARS entry through dat_load_char: "<id> <side> <expr_count> <name>".
 * Usage: chars_test <memo.dat> */
#include <stdio.h>

#include "memo_dat.h"

int main(int argc, char **argv)
{
    uint8_t id, side, exprs;
    char name[32];

    if (argc != 2 || dat_open(argv[1], 0) != DAT_OK) {
        fprintf(stderr, "cannot open the dat\n");
        return 2;
    }
    for (id = 0; id < 255; id++) {
        if (!dat_load_char(id, &side, &exprs, name, sizeof name)) {
            break;
        }
        printf("%u %u %u %s\n", id, side, exprs, name);
    }
    /* The id past the end, a name that cannot fit, and optional outputs. */
    printf("past-end %d\n", dat_load_char(id, &side, &exprs, name, sizeof name));
    printf("tiny %d\n", dat_load_char(1, NULL, NULL, name, 2));
    printf("no-capacity %d\n", dat_load_char(0, &side, &exprs, name, 0));
    return 0;
}
