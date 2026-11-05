/* Shows the title screen against the video model and writes the result as a PPM.
 * Usage (run in the directory that holds memo.dat): title_test <out.ppm> */
#include <stdio.h>

#include "main.h"
#include "layout.h"
#include "memo_dat.h"
#include "title.h"
#include "gfx_mock.h"

int main(int argc, char **argv)
{
    unsigned row, col, layer1 = 0;

    if (argc != 2) {
        return 2;
    }
    mock_reset_video();
    if (!title_show()) {
        fprintf(stderr, "title_show failed: %s\n", mock_last_log);
        return 1;
    }
    for (row = 0; row < 40; row++) {
        for (col = 0; col < 80; col++) {
            layer1 += mock_fg[row][col];
        }
    }
    printf("layer1 %u\n", layer1);
    printf("uploads %u\n", mock_upload_calls);
    return mock_write_ppm(argv[1]) ? 0 : 1;
}
