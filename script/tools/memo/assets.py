"""Art manifest to asset blocks (compiler-spec.md sections 5.2, 5.5 and 5.7).

Block ids for art are allocated in a fixed order that does not depend on which art exists, so
adding a file never renumbers anything: for each character with expressions three blocks
(portrait descriptor, tiles, palette), for each CG three blocks (tiles, tile map, palette), then
the map tilesets in manifest order (tiles, palette).
"""
import json
import os
import struct
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

from .blocks import Block
from .gfx import (GfxError, decode_map, decode_tiles, filename_flags, max_pixel_index, palette_colors,
                  tile_bytes)
from .project import ROOT
from .spec import ASSET_BASE, F_MISSING, T_PALETTE, T_PORTRAIT, T_TILEMAP, T_TILESET, T_UNUSED

ArtDiag = namedtuple("ArtDiag", "level where msg")
COMP_CODE = {None: 0, "rle": 1, "lz": 2}
DEFAULT_TOOL = ROOT.parents[1] / "Zeal-VideoBoard-SDK" / "tools" / "zeal2gif" / "gif2zeal.py"


class AssetError(Exception):
    pass


class AssetSet:
    def __init__(self):
        self.blocks = []
        self.index = {"cgs": [], "portraits": [], "tilesets": []}
        self.diags = []
        self.missing = []

    def alloc(self, type_, name, flags=0):
        b = Block(ASSET_BASE + len(self.blocks), type_, b"", name, flags)
        self.blocks.append(b)
        return b

    def diag(self, level, where, msg):
        self.diags.append(ArtDiag(level, f"art:{where}", msg))


def mark_missing(*blocks):
    for b in blocks:
        b.flags |= F_MISSING
        b.data = b""


# ---------------------------------------------------------------------------
# Source files
# ---------------------------------------------------------------------------

def tool_path(manifest):
    p = (manifest.get("tools") or {}).get("gif2zeal") or os.environ.get("GIF2ZEAL")
    return Path(p) if p else DEFAULT_TOOL


def resolve_sources(spec, base, convert, tool, name):
    """Find (or make) the converter outputs for one manifest entry.

    Returns a dict: zts, ztp, ztm (path or None), bpp, comp, flags."""
    if "gif" in spec:
        gif = (base / spec["gif"]).resolve()
        flags = filename_flags(gif)
        if not flags["flagged"]:
            raise AssetError(f"{name}: {gif.name} needs gif2zeal flags in its name, e.g. {gif.stem}__B8C20.gif")
        stem = gif.parent / flags["stem"]
        zts, ztp = stem.with_suffix(".zts"), stem.with_suffix(".ztp")
        ztm = stem.with_suffix(".ztm") if flags["tilemap"] else None
        outputs = [zts, ztp] + ([ztm] if ztm else [])
        stale = [o for o in outputs if not o.exists() or (gif.exists() and o.stat().st_mtime < gif.stat().st_mtime)]
        if stale and gif.exists():
            if not convert:
                missing = ", ".join(o.name for o in stale)
                raise AssetError(f"{name}: {missing} missing or older than {gif.name}; run with --convert")
            run_gif2zeal(tool, gif)
        elif stale:
            raise AssetError(f"{name}: neither {gif.name} nor its converter outputs exist")
        if "bpp" in spec and spec["bpp"] != flags["bpp"]:
            raise AssetError(f"{name}: manifest says {spec['bpp']}bpp but the file name flags say {flags['bpp']}bpp")
        return {"zts": zts, "ztp": ztp, "ztm": ztm, "bpp": flags["bpp"], "comp": flags["compress"],
                "unique": flags["unique"]}
    if "zts" in spec and "ztp" in spec:
        ztm = (base / spec["ztm"]) if spec.get("ztm") else None
        return {"zts": base / spec["zts"], "ztp": base / spec["ztp"], "ztm": ztm,
                "bpp": spec.get("bpp", 8), "comp": spec.get("compression"), "unique": bool(ztm)}
    raise AssetError(f"{name}: give either 'gif' or both 'zts' and 'ztp'")


def run_gif2zeal(tool, gif):
    if not tool.exists():
        raise AssetError(f"gif2zeal.py not found at {tool}; set tools.gif2zeal in the manifest or GIF2ZEAL")
    r = subprocess.run([sys.executable, str(tool), "-i", str(gif)], capture_output=True, text=True)
    if r.returncode != 0:
        raise AssetError(f"gif2zeal failed on {gif.name}: {(r.stderr or r.stdout).strip()}")


def read_gfx(src, name):
    """Read and decode converter outputs. Returns a dict with raw tiles and palette facts."""
    for key in ("zts", "ztp"):
        if not src[key].exists():
            raise AssetError(f"{name}: {src[key]} does not exist")
    zts, ztp = src["zts"].read_bytes(), src["ztp"].read_bytes()
    try:
        tiles = decode_tiles(zts, src["comp"], src["bpp"])
        colors = palette_colors(ztp)
    except GfxError as e:
        raise AssetError(f"{name}: {e}")
    raw = b"".join(tiles)
    info = {"bpp": src["bpp"], "comp": src["comp"], "zts": zts, "ztp": ztp, "raw": raw,
            "tile_count": len(tiles), "colors": colors, "ztm": None, "unique": src.get("unique", False)}
    if src["ztm"] is not None:
        if not src["ztm"].exists():
            raise AssetError(f"{name}: {src['ztm']} does not exist")
        info["ztm"] = decode_map(src["ztm"].read_bytes(), None)
    return info


def tiles_block_data(info, keep_compression):
    if keep_compression and info["comp"]:
        return struct.pack("<BBH", info["bpp"], COMP_CODE[info["comp"]], info["tile_count"]) + info["zts"]
    return struct.pack("<BBH", info["bpp"], 0, info["tile_count"]) + info["raw"]


def palette_block_data(info):
    return bytes([0, info["colors"] - 1]) + info["ztp"]


# ---------------------------------------------------------------------------
# Validation per kind
# ---------------------------------------------------------------------------

def check_pixels(a, name, info):
    top = max_pixel_index(info["raw"], info["bpp"])
    if top >= info["colors"]:
        a.diag("error", name, f"pixel index {top} is outside the palette ({info['colors']} colours); "
                              f"export with enough colours (the C flag) or fix the image")
        return False
    return True


def check_portrait(a, p, cname, spec, info):
    art = p.config["art"]["portrait"]
    base = spec.get("base", art["base"])
    head = spec.get("head", art["head"])
    n = len(p.char_exprs[cname])
    ok = check_pixels(a, cname, info)
    if info["bpp"] != 8:
        a.diag("error", cname, f"portraits are 8bpp, found {info['bpp']}bpp")
        ok = False
    if info["colors"] > art["max_colors"]:
        a.diag("error", cname, f"palette has {info['colors']} colours (portrait limit {art['max_colors']}); "
                               f"export with the C flag, e.g. name__B8C20.gif")
        ok = False
    hx, hy, hw, hh = head
    if hx + hw > base[0] or hy + hh > base[1]:
        a.diag("error", cname, f"head region {head} does not fit the {base[0]}x{base[1]} tile base image")
        ok = False
    expected = base[0] * base[1] + (n - 1) * hw * hh
    if info["tile_count"] != expected:
        a.diag("error", cname,
               f"{info['tile_count']} tiles; expected {expected} = {base[0]}x{base[1]} base tiles + "
               f"{n - 1} alternate heads of {hw}x{hh} (a {base[0] * 16} px wide sheet: base image on top, "
               f"each alternate head below it)")
        ok = False
    return ok, base, head


def check_cg(a, p, name, spec, info):
    modes = p.config["art"]["cg_modes"]
    ok = check_pixels(a, name, info)
    mode = modes.get(str(info["bpp"]))
    if mode is None:
        a.diag("error", name, f"CGs must be {', '.join(modes)}bpp, found {info['bpp']}bpp")
        return False, None
    grid = mode[0] * mode[1]
    if info["ztm"] is not None:
        if len(info["ztm"]) != grid:
            a.diag("error", name, f"tile map has {len(info['ztm'])} entries; a {mode[0]}x{mode[1]} tile image needs {grid}")
            ok = False
        elif max(info["ztm"]) >= info["tile_count"]:
            a.diag("error", name, f"tile map refers to tile {max(info['ztm'])} but there are {info['tile_count']} tiles")
            ok = False
    else:
        if info.get("unique"):
            a.diag("error", name, "the unique-tiles flag (U) needs a tile map (M flag)")
            ok = False
        elif info["tile_count"] != grid:
            a.diag("error", name, f"{info['tile_count']} tiles; a {mode[0] * 16}x{mode[1] * 16} image has {grid}")
            ok = False
    return ok, mode


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_manifest(path):
    if path is None or not Path(path).exists():
        return {}, ROOT
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")), path.parent


def load_assets(p, manifest_path=None, convert=False, keep_compression=False):
    manifest, mdir = load_manifest(manifest_path)
    tool = tool_path(manifest)
    a = AssetSet()
    art = p.config["art"]

    for section, known in (("portraits", p.char_names), ("cgs", p.cg_names)):
        for name in manifest.get(section, {}):
            if name not in known:
                a.diag("warn", name, f"manifest {section} entry is not a known {'character' if section == 'portraits' else 'CG'}")

    # Portraits: descriptor, tiles, palette per character with expressions.
    for cname in p.char_names:
        exprs = p.char_exprs[cname]
        if not exprs:
            a.index["portraits"].append(0)
            continue
        desc, tiles, pal = (a.alloc(T_PORTRAIT, f"PORTRAIT {cname}"), a.alloc(T_TILESET, f"TILES {cname}"),
                            a.alloc(T_PALETTE, f"PAL {cname}"))
        a.index["portraits"].append(desc.id)
        pbase, head = list(art["portrait"]["base"]), list(art["portrait"]["head"])
        spec = manifest.get("portraits", {}).get(cname)
        got = None
        if spec is None:
            a.missing.append(cname)
        else:
            try:
                src = resolve_sources(spec, mdir, convert, tool, cname)
                info = read_gfx(src, cname)
                ok, pbase, head = check_portrait(a, p, cname, spec, info)
                got = info if ok else None
            except AssetError as e:
                a.diag("error", cname, str(e).split(": ", 1)[-1])
        if got:
            tiles.data, pal.data = tiles_block_data(got, keep_compression), palette_block_data(got)
            check_size(a, cname, tiles, pal)
        else:
            mark_missing(tiles, pal)
        desc.data = struct.pack("<BBBBBBBHH", pbase[0], pbase[1], head[0], head[1], head[2], head[3],
                                len(exprs), tiles.id, pal.id)

    # CGs: tiles, tile map, palette.
    for cg in p.cg_names:
        tiles, tmap, pal = (a.alloc(T_TILESET, f"TILES {cg}"), a.alloc(T_TILEMAP, f"MAP {cg}"),
                            a.alloc(T_PALETTE, f"PAL {cg}"))
        spec = manifest.get("cgs", {}).get(cg)
        base_dir = mdir
        if spec is None:
            cg_entry = p.cgs.get(cg)
            if cg_entry and cg_entry.get("file"):
                spec = {"gif": cg_entry["file"], "bpp": cg_entry.get("bpp", 8)}
                base_dir = ROOT.parent
        got, mode = None, None
        if spec is None:
            a.missing.append(cg)
        else:
            try:
                src = resolve_sources(spec, base_dir, convert, tool, cg)
                info = read_gfx(src, cg)
                if "bpp" in spec and spec["bpp"] != info["bpp"]:
                    raise AssetError(f"{cg}: manifest says {spec['bpp']}bpp but the art is {info['bpp']}bpp")
                ok, mode = check_cg(a, p, cg, spec, info)
                got = info if ok else None
            except AssetError as e:
                a.diag("error", cg, str(e).split(": ", 1)[-1])
        if got:
            tiles.data, pal.data = tiles_block_data(got, keep_compression), palette_block_data(got)
            if got["ztm"] is not None:
                tmap.data = bytes([0, mode[0], mode[1]]) + got["ztm"]
                a.index["cgs"].append((tiles.id, tmap.id, pal.id))
            else:
                tmap.type, tmap.data = T_UNUSED, b""
                a.index["cgs"].append((tiles.id, 0, pal.id))
            check_size(a, cg, tiles, tmap, pal)
        else:
            mark_missing(tiles, tmap, pal)
            a.index["cgs"].append((tiles.id, tmap.id, pal.id))

    # Map tilesets, in manifest order.
    for name, spec in manifest.get("tilesets", {}).items():
        tiles, pal = a.alloc(T_TILESET, f"TILES {name}"), a.alloc(T_PALETTE, f"PAL {name}")
        a.index["tilesets"].append((tiles.id, pal.id))
        try:
            src = resolve_sources(spec, mdir, convert, tool, name)
            info = read_gfx(src, name)
            ok = check_pixels(a, name, info)
            if info["tile_count"] > 255:
                a.diag("error", name, f"{info['tile_count']} tiles; tile map entries are one byte and 255 means empty, "
                                      f"so a tileset can hold at most 255 tiles")
                ok = False
            if ok:
                tiles.data, pal.data = tiles_block_data(info, keep_compression), palette_block_data(info)
                check_size(a, name, tiles, pal)
                continue
        except AssetError as e:
            a.diag("error", name, str(e).split(": ", 1)[-1])
        mark_missing(tiles, pal)

    if manifest.get("maps"):
        a.diag("warn", "maps", "the manifest has maps; map packing is not implemented yet and they are ignored")
    if a.missing:
        a.diag("missing", "art", f"{len(a.missing)} assets have no art yet: {', '.join(a.missing)}")
    return a


def check_size(a, name, *blocks):
    for b in blocks:
        if len(b.data) > 65535:
            a.diag("error", name, f"{b.name} is {len(b.data)} bytes; a block holds at most 65,535 "
                                  f"(continuation blocks are not implemented)")
            mark_missing(*blocks)
            return
