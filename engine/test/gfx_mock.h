#ifndef GFX_MOCK_H
#define GFX_MOCK_H

/* A software model of the video board for desktop tests. It implements the platform
 * functions that main.h declares (tile uploads, tilemaps, palette, the off-screen text
 * buffer) so engine modules can be exercised without a Z80 or a Zeal emulator. */

#include <stdint.h>

extern uint8_t  mock_tileset[256][256];
extern uint8_t  mock_fg[40][80];
extern uint8_t  mock_bg[40][80];
extern uint16_t mock_palette[256];

extern unsigned mock_upload_calls;   /* render_text_buffer calls since the last reset */
extern unsigned mock_upload_bytes;
extern unsigned mock_log_count;
extern char     mock_last_log[256];
extern void   (*mock_log_hook)(const char *message);   /* optional, called for every debug_log */

void mock_reset_counters(void);
void mock_reset_video(void);

/* Render the 320x240 screen (layer 1 over layer 0, no scrolling, no sprites) as a P6 PPM. */
int mock_write_ppm(const char *path);

#endif
