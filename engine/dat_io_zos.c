/* Zeal OS backend for the loader. */
#include <stdint.h>
#include <stdbool.h>

#include <zos_vfs.h>

#include "dat_io.h"

static zos_dev_t fd = -1;

bool dat_io_open(const char *path)
{
    fd = open(path, O_RDONLY);
    return fd >= 0;
}

void dat_io_close(void)
{
    if (fd >= 0) {
        close(fd);
        fd = -1;
    }
}

bool dat_io_seek(uint32_t offset)
{
    int32_t off = (int32_t)offset;
    return fd >= 0 && seek(fd, &off, SEEK_SET) == 0;
}

/* A ZOS read() must not cross a 16 KB virtual page boundary in the destination buffer (the
 * same rule Wyvern Sorrow's dat_read follows), so a read is split at every page edge. */
bool dat_io_read(void *dst, uint16_t size)
{
    uint8_t *p = (uint8_t *)dst;

    if (fd < 0) {
        return false;
    }
    while (size) {
        uint16_t room = (uint16_t)(0x4000u - ((uint16_t)(uintptr_t)p & 0x3FFFu));
        uint16_t n = size < room ? size : room;
        uint16_t want = n;

        if (read(fd, p, &n) != 0 || n != want) {
            return false;
        }
        p += want;
        size -= want;
    }
    return true;
}
