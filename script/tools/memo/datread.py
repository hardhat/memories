"""Independent reader for memo.dat. Uses only struct and the constants in spec.py."""
import struct
import zlib

from .spec import (BLOCK_CHARS, BLOCK_INDEX, BLOCK_META, BLOCK_VARS, ENTRY, F_MISSING, MAGIC, SCENE_CODE_BASE,
                   SCENE_STR_BASE, T_UNUSED, VERSION)


class DatError(Exception):
    pass


class Dat:
    def __init__(self, data):
        self.data = data
        if len(data) < ENTRY.size:
            raise DatError("file too short")
        off, size, typ, flags = ENTRY.unpack_from(data, 0)
        if off != MAGIC or typ != 0:
            raise DatError("bad magic cookie")
        if flags != VERSION:
            raise DatError(f"unsupported format version {flags}")
        self.header_size = size
        self.entry_count = size // ENTRY.size
        if size % ENTRY.size or size > len(data):
            raise DatError("bad header size")
        self.entries = [ENTRY.unpack_from(data, i * ENTRY.size) for i in range(self.entry_count)]
        self._tables()

    # ---- raw -------------------------------------------------------------
    def entry(self, bid):
        if not 0 <= bid < self.entry_count:
            raise DatError(f"no block {bid}")
        off, size, typ, flags = self.entries[bid]
        return off, size, typ, flags

    def block(self, bid):
        off, size, typ, flags = self.entry(bid)
        if typ == T_UNUSED:
            raise DatError(f"block {bid} is unused")
        if off + size > len(self.data):
            raise DatError(f"block {bid} runs past the end of the file")
        return self.data[off:off + size]

    # ---- tables ----------------------------------------------------------
    def _tables(self):
        meta = self.block(BLOCK_META)
        self.version, self.scene_count, self.string_total, self.crc = struct.unpack("<BBHI", meta)
        crc = 0
        for bid in range(1, self.entry_count):
            if bid == BLOCK_META or self.entries[bid][2] == T_UNUSED:
                continue
            crc = zlib.crc32(self.block(bid), crc)
        if crc != self.crc:
            raise DatError(f"content CRC mismatch (file {self.crc:08x}, computed {crc:08x})")

        v = self.block(BLOCK_VARS)
        n = v[0]
        self.var_count, self.var_max, self.var_init = n, list(v[1:1 + n]), list(v[1 + n:1 + 2 * n])

        c = self.block(BLOCK_CHARS)
        n = c[0]
        pool = 1 + 4 * n
        self.chars = []
        for i in range(n):
            side, nexpr, noff = struct.unpack_from("<BBH", c, 1 + 4 * i)
            end = c.index(b"\x00", pool + noff)
            self.chars.append({"side": side, "exprs": nexpr, "name": c[pool + noff:end].decode("ascii")})

        idx = self.block(BLOCK_INDEX)
        pos, self.index = 0, {}
        for name, width in (("maps", 1), ("cgs", 3), ("portraits", 1), ("sprites", 2),
                            ("tilesets", 2), ("music", 1), ("sfx", 1)):
            count = idx[pos]
            pos += 1
            self.index[name] = [struct.unpack_from("<" + "H" * width, idx, pos + 2 * width * i)
                                for i in range(count)]
            pos += 2 * width * count

    # ---- art -------------------------------------------------------------
    def is_missing(self, bid):
        return bool(self.entry(bid)[3] & F_MISSING)

    def portrait(self, bid):
        b = self.block(bid)
        if not b:
            return None
        base_w, base_h, hx, hy, hw, hh, exprs, tiles, pal = struct.unpack("<BBBBBBBHH", b)
        return {"base": (base_w, base_h), "head": (hx, hy, hw, hh), "exprs": exprs,
                "tiles": tiles, "palette": pal}

    def tileset(self, bid):
        """(bpp, comp, tile_count, data) or None when the art is missing."""
        b = self.block(bid)
        if not b:
            return None
        bpp, comp, count = struct.unpack_from("<BBH", b, 0)
        return bpp, comp, count, b[4:]

    def palette(self, bid):
        """(first, last, [rgb565 words]) or None."""
        b = self.block(bid)
        if not b:
            return None
        first, last = b[0], b[1]
        n = last - first + 1
        return first, last, list(struct.unpack_from("<" + "H" * n, b, 2))

    def tilemap(self, bid):
        """(comp, w, h, data) or None."""
        b = self.block(bid)
        if not b:
            return None
        return b[0], b[1], b[2], b[3:]

    # ---- scenes ----------------------------------------------------------
    def scene_code(self, n):
        """(entry_pc, code bytes) of scene n (1-based)."""
        b = self.block(SCENE_CODE_BASE + n - 1)
        size, entry, _ = struct.unpack_from("<HHH", b, 0)
        code = b[6:6 + size]
        if len(code) != size:
            raise DatError(f"scene {n}: truncated code")
        return entry, code

    def strings(self, n):
        b = self.block(SCENE_STR_BASE + n - 1)
        count = struct.unpack_from("<H", b, 0)[0]
        offsets = struct.unpack_from("<" + "H" * count, b, 2)
        base = 2 + 2 * count
        out = []
        for o in offsets:
            end = b.index(b"\x00", base + o)
            out.append(b[base + o:end].decode("ascii"))
        return out
