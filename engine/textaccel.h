// Accelerated draw functions
#include <stdint.h>

void draw_text_char_aligned(const uint8_t *charpattern, uint8_t *target, uint8_t color);
void draw_text_char_opaque_aligned(const uint8_t *charpattern, uint8_t *target, uint8_t fg, uint8_t bg);
