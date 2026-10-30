"""Zeal graphics file helpers: gif2zeal filename flags, RLE/LZ decoders, tile and palette analysis.

Formats come from the SDK tools (gif2zeal.py, tiled2zeal.py); see compiler-spec.md section 5.7.
"""
from pathlib import Path

TILE = 16


class GfxError(Exception):
    pass


def tile_bytes(bpp):
    if bpp not in (1, 2, 4, 8):
        raise GfxError(f"unsupported bpp {bpp}")
    return TILE * TILE * bpp // 8


# ---------------------------------------------------------------------------
# gif2zeal filename flags: name__B8C20R.gif
# ---------------------------------------------------------------------------

def filename_flags(path):
    """Settings gif2zeal derives from the file name. Returns a dict with the output stem and
    the same defaults gif2zeal uses (bpp 8, no compression)."""
    name = Path(path).name
    out = {"stem": Path(name).stem, "bpp": 8, "compress": None, "colors": None,
           "strip": 0, "unique": False, "tilemap": False, "flagged": False}
    if "__" not in name:
        return out
    stem, rest = name.rsplit("__", 1)
    flags = rest.rsplit(".", 1)[0]
    out["stem"], out["flagged"] = stem, True
    i = 0
    while i < len(flags):
        f = flags[i]
        if f == "B":
            out["bpp"] = int(flags[i + 1], 0)
            i += 1
        elif f in "CP":
            out["colors"] = int(flags[i + 1:i + 3], 16)
            i += 2
        elif f in "ZR":
            out["compress"] = "rle"
        elif f == "L":
            out["compress"] = "lz"
        elif f == "S":
            out["strip"] = int(flags[i + 1:i + 3], 16)
            i += 2
        elif f == "U":
            out["unique"] = True
        elif f == "M":
            out["tilemap"] = True
        i += 1
    return out


# ---------------------------------------------------------------------------
# Decoders. gif2zeal compresses each tile separately and concatenates the streams with no length
# field, so decoding must stop at tile boundaries.
# ---------------------------------------------------------------------------

def decode_rle(data, pos, limit):
    """Decode RLE ops from data[pos:] into a list until it holds exactly `limit` bytes.
    Returns (bytes, new pos). Raises GfxError if an op overruns the limit or the data ends."""
    out = bytearray()
    while len(out) < limit:
        if pos >= len(data):
            raise GfxError("RLE stream ends in the middle of a block")
        b = data[pos]
        if b & 0x80:
            n = (b & 0x7F) + 1
            if pos + 1 >= len(data):
                raise GfxError("truncated RLE run")
            out += bytes([data[pos + 1]]) * n
            pos += 2
        else:
            n = b + 1
            if pos + 1 + n > len(data):
                raise GfxError("truncated RLE literal")
            out += data[pos + 1:pos + 1 + n]
            pos += 1 + n
        if len(out) > limit:
            raise GfxError("RLE op crosses a tile boundary")
    return bytes(out), pos


def decode_lz(data, pos, limit):
    out = bytearray()
    while len(out) < limit:
        if pos >= len(data):
            raise GfxError("LZ stream ends in the middle of a block")
        c = data[pos]
        pos += 1
        if c < 0x40:
            out.append(c)
        elif c < 0x80:
            n = (c & 0x3F) + 1
            if pos + n > len(data):
                raise GfxError("truncated LZ literal run")
            out += data[pos:pos + n]
            pos += n
        else:
            if c < 0xC0:
                length, offset = ((c >> 4) & 3) + 3, (c & 0x0F) + 1
            else:
                if pos >= len(data):
                    raise GfxError("truncated LZ match")
                length, offset = (c & 0x3F) + 4, data[pos] + 1
                pos += 1
            if offset > len(out):
                raise GfxError("LZ match reaches before the start of the tile")
            for _ in range(length):
                out.append(out[-offset])
        if len(out) > limit:
            raise GfxError("LZ op crosses a tile boundary")
    return bytes(out), pos


DECODERS = {"rle": decode_rle, "lz": decode_lz}


def decode_tiles(data, comp, bpp):
    """Return the list of raw tile byte strings of a .zts file."""
    size = tile_bytes(bpp)
    if comp is None:
        if len(data) % size:
            raise GfxError(f"tile data is {len(data)} bytes, not a multiple of {size} ({bpp}bpp tiles)")
        return [data[i:i + size] for i in range(0, len(data), size)]
    dec = DECODERS[comp]
    tiles, pos = [], 0
    while pos < len(data):
        tile, pos = dec(data, pos, size)
        tiles.append(tile)
    return tiles


def decode_map(data, comp):
    """A .ztm file: one RLE stream over the whole layer (tiled2zeal compresses the full screen)."""
    if comp is None:
        return bytes(data)
    out, pos = bytearray(), 0
    while pos < len(data):
        b = data[pos]
        if b & 0x80:
            if pos + 1 >= len(data):
                raise GfxError("truncated RLE run in tile map")
            out += bytes([data[pos + 1]]) * ((b & 0x7F) + 1)
            pos += 2
        else:
            n = b + 1
            if pos + 1 + n > len(data):
                raise GfxError("truncated RLE literal in tile map")
            out += data[pos + 1:pos + 1 + n]
            pos += 1 + n
    return bytes(out)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def max_pixel_index(raw, bpp):
    """Highest palette index used by raw tile bytes."""
    if not raw:
        return 0
    if bpp == 8:
        return max(raw)
    if bpp == 4:
        return max(max(raw) >> 4, max(b & 0x0F for b in set(raw)))
    if bpp == 2:
        return max(max((b >> s) & 3 for s in (0, 2, 4, 6)) for b in set(raw))
    return 1 if any(raw) else 0


def palette_colors(ztp):
    if len(ztp) % 2 or not 2 <= len(ztp) <= 512:
        raise GfxError(f"palette is {len(ztp)} bytes; expected 2 to 512, even (RGB565 little endian)")
    return len(ztp) // 2
