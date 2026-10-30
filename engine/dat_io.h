#ifndef DAT_IO_H
#define DAT_IO_H

/* The only platform-specific part of the loader. memo_dat.c reads the file through these four
 * calls; there is one implementation for Zeal OS (dat_io_zos.c) and one for a desktop test
 * build (dat_io_stdio.c). */

#include <stdbool.h>
#include <stdint.h>

bool dat_io_open(const char *path);
void dat_io_close(void);
bool dat_io_seek(uint32_t offset);
bool dat_io_read(void *dst, uint16_t n);   /* exactly n bytes or false */

#endif /* DAT_IO_H */
