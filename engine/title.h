#ifndef TITLE_H
#define TITLE_H

/* Startup title screen: the CG-title image from memo.dat, a 320x192 8bpp picture that fills
 * tile rows 0-11 of layer 0, with the three rows below it filled with its darkest colour.
 *
 * It borrows tile slots 1-241 and palette entries 0-127, so it must be shown before
 * screen_init() (memo_host_initialize), which reloads the dialog palette and tiles and clears
 * both layers. Opens and closes memo.dat itself. */

#include <stdbool.h>

/* Load and draw the title. Returns false, with nothing drawn, if memo.dat or the art is missing. */
bool title_show(void);

#endif /* TITLE_H */
