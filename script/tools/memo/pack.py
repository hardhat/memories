"""Write memo.dat (compiler-spec.md section 5)."""
import struct
import zlib

from .blocks import Block
from .spec import (ASSET_BASE, BLOCK_CHARS, BLOCK_INDEX, BLOCK_MAGIC, BLOCK_META, BLOCK_VARS, ENTRY,
                   F_MISSING, MAGIC, MAX_SCENES, SCENE_CODE_BASE, SCENE_STR_BASE, SIDE, T_MAGIC,
                   T_SCENE_CODE, T_STRINGS, T_TABLE, T_UNUSED, VERSION)


class PackError(Exception):
    pass


def vars_block(p):
    n = len(p.var_names)
    return bytes([n]) + bytes(p.var_max) + bytes(n)  # count, max[], init[] (all 0)


def chars_block(p):
    pool, entries = bytearray(), []
    for name in p.char_names:
        c = p.chars_raw[name]
        has_portrait = c.get("portrait", True) is not False
        side = SIDE[c.get("side")] if has_portrait else 0
        entries.append((side, len(p.char_exprs[name]) if has_portrait else 0, len(pool)))
        pool += c.get("name", "").encode("ascii") + b"\x00"
    out = bytearray([len(entries)])
    for side, nexpr, off in entries:
        out += struct.pack("<BBH", side, nexpr, off)
    return bytes(out + pool)


def index_block(p, assets):
    """Logical id -> block id tables (0 means no block)."""
    def table(rows, width):
        out = bytearray([len(rows)])
        for r in rows:
            r = r if isinstance(r, tuple) else (r,)
            assert len(r) == width
            for v in r:
                out += struct.pack("<H", v)
        return bytes(out)
    zeros = lambda n, w: [(0,) * w for _ in range(n)]
    return (table(zeros(len(p.map_names), 1), 1)                 # mapdef block per map (M6)
            + table(assets.index["cgs"], 3)                      # tiles, tilemap, palette per CG
            + table(assets.index["portraits"], 1)                # portrait descriptor per character
            + table(zeros(len(p.char_names), 2), 2)              # sprite tiles, palette per character
            + table(assets.index["tilesets"], 2)                 # map tilesets (tiles, palette)
            + table(zeros(len(p.music), 1), 1)
            + table(zeros(len(p.sfx), 1), 1))


def build_blocks(p, scene_codes, assets):
    if len(scene_codes) > MAX_SCENES:
        raise PackError("too many scenes")
    blocks = {
        BLOCK_VARS: Block(BLOCK_VARS, T_TABLE, vars_block(p), "VARS"),
        BLOCK_CHARS: Block(BLOCK_CHARS, T_TABLE, chars_block(p), "CHARS"),
        BLOCK_INDEX: Block(BLOCK_INDEX, T_TABLE, index_block(p, assets), "INDEX"),
    }
    for b in assets.blocks:
        blocks[b.id] = b
    total_strings = 0
    for i, sc in enumerate(scene_codes):
        total_strings += len(sc.strings.items)
        code = sc.block()
        limit = p.config["limits"]["code_buf"]
        if len(sc.code) > limit:
            raise PackError(f"{sc.scene_id}: code is {len(sc.code)} bytes (limit {limit})")
        strings = sc.strings.block()
        if len(strings) > p.config["limits"]["strings_bytes"]:
            raise PackError(f"{sc.scene_id}: strings are {len(strings)} bytes")
        blocks[SCENE_CODE_BASE + i] = Block(SCENE_CODE_BASE + i, T_SCENE_CODE, code, f"CODE {sc.scene_id}")
        blocks[SCENE_STR_BASE + i] = Block(SCENE_STR_BASE + i, T_STRINGS, strings, f"STR  {sc.scene_id}")
    crc = 0
    for bid in sorted(blocks):
        crc = zlib.crc32(blocks[bid].data, crc)
    meta = struct.pack("<BBHI", VERSION, len(scene_codes), total_strings, crc)
    blocks[BLOCK_META] = Block(BLOCK_META, T_TABLE, meta, "META")
    return blocks


def build_dat(p, scene_codes, assets=None):
    """Return (file bytes, list of (id, type, offset, size, flags, name)).

    `assets` is an assets.AssetSet; without one every asset is a missing placeholder."""
    if assets is None:
        from .assets import load_assets
        assets = load_assets(p)
    blocks = build_blocks(p, scene_codes, assets)
    entry_count = ASSET_BASE + len(assets.blocks)
    if entry_count > 255:
        raise PackError(f"{entry_count} blocks; ids are 8 bits wide")
    header_size = entry_count * ENTRY.size
    layout, offset = [], header_size
    entries = [ENTRY.pack(MAGIC, header_size, T_MAGIC, VERSION)]
    body = bytearray()
    for bid in range(1, entry_count):
        b = blocks.get(bid)
        if b is None:
            entries.append(ENTRY.pack(0, 0, T_UNUSED, 0))
            continue
        if len(b.data) > 65535:
            raise PackError(f"block {b.name} is {len(b.data)} bytes (max 65535)")
        if not b.data:
            # empty block (missing art or unused slot): no offset, the flag tells the loader
            entries.append(ENTRY.pack(0, 0, b.type, b.flags))
            layout.append((bid, b.type, 0, 0, b.flags, b.name))
            continue
        entries.append(ENTRY.pack(offset, len(b.data), b.type, b.flags))
        layout.append((bid, b.type, offset, len(b.data), b.flags, b.name))
        body += b.data
        offset += len(b.data)
    return b"".join(entries) + bytes(body), layout
