/* Desktop backend for the loader (test harness only). */
#include <stdio.h>

#include "dat_io.h"

static FILE *fp;

bool dat_io_open(const char *path)
{
    fp = fopen(path, "rb");
    return fp != NULL;
}

void dat_io_close(void)
{
    if (fp) {
        fclose(fp);
        fp = NULL;
    }
}

bool dat_io_seek(uint32_t offset)
{
    return fp != NULL && fseek(fp, (long)offset, SEEK_SET) == 0;
}

bool dat_io_read(void *dst, uint16_t n)
{
    return fp != NULL && fread(dst, 1, n, fp) == n;
}
