#!/usr/bin/env python3
"""Export a portrait sheet as a baked, hardware-ready GIF for the memo compiler.

Run: python script/tools/export_portrait.py jane [--check]

Input:  art/portraits/<character>.png, RGBA, 32 px wide: the 64 px base image (expression 0)
        on top, then one 32x32 head per further expression, in characters.json order
        (compiler-spec.md section 5.7). Alpha must be 0 or 255.
Output: script/assets/portraits/<character>__B8C<hex>.gif with every colour at its final
        palette index (index 0 transparent, the character's side range for the rest:
        screen-spec.md section 3), so the engine loads it with a plain copy.

Colours are first rounded to RGB565, which is all the hardware can show. If that still leaves
more than the side's range holds (47), the closest pair is merged repeatedly into the more
frequent colour (no new colours are invented, nothing is blended) and the pixels changed are
reported.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from memo.project import ROOT, load_project  # noqa: E402

REPO = ROOT.parent


class PortraitError(Exception):
    pass


# Merging is for rounding-level differences between near-identical colours. A sheet needing far
# more than this was never palette-reduced and should be quantized with a proper tool first.
MAX_SOURCE_COLORS = 128


def to_565(rgb):
    """The colour the hardware shows for rgb, as 8-bit channels (bits replicated)."""
    r, g, b = rgb
    return ((r >> 3 << 3) | (r >> 5), (g >> 2 << 2) | (g >> 6), (b >> 3 << 3) | (b >> 5))


def distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def reduce_colors(counts, limit):
    """Merge colours until at most `limit` remain. Returns (remap, merges) where remap maps every
    input colour to its survivor. The cheapest merge (Ward cost) goes into the more frequent colour."""
    remap = {c: c for c in counts}
    live = dict(counts)
    merges = 0
    while len(live) > limit:
        best = None
        colors = sorted(live)
        for i, a in enumerate(colors):
            for b in colors[i + 1:]:
                na, nb = live[a], live[b]
                cost = distance(a, b) * na * nb / (na + nb)
                if best is None or cost < best[0]:
                    best = (cost, a, b)
        _, a, b = best
        keep, drop = (a, b) if live[a] >= live[b] else (b, a)
        live[keep] += live.pop(drop)
        for c, target in remap.items():
            if target == drop:
                remap[c] = keep
        merges += 1
    return remap, merges


def expected_height(expressions):
    return 64 + 32 * (expressions - 1)


def bake(image, lo, hi, expressions):
    """Return (indexed image, palette list of RGB tuples for entries 0..hi, report dict)."""
    if image.width != 32 or image.height != expected_height(expressions):
        raise PortraitError(f"sheet is {image.width}x{image.height}; {expressions} expressions need "
                            f"32x{expected_height(expressions)} (64 px base + {expressions - 1} heads of 32 px)")
    pixels = list(image.get_flattened_data())
    if any(p[3] not in (0, 255) for p in pixels):
        raise PortraitError("partial alpha is not supported: every pixel must be fully opaque or transparent")
    counts = Counter(to_565(p[:3]) for p in pixels if p[3])
    if not counts:
        raise PortraitError("the sheet is empty")
    if len(counts) > MAX_SOURCE_COLORS:
        raise PortraitError(f"the sheet has {len(counts)} colours at RGB565 precision; reduce it to at most "
                            f"{MAX_SOURCE_COLORS} (ideally {hi - lo + 1}) before exporting, so the exporter only "
                            f"merges near-identical colours")
    remap, merges = reduce_colors(counts, hi - lo + 1)
    survivors = sorted(set(remap.values()), key=lambda c: (-sum(1 for k, v in remap.items() if v == c), c))
    index = {c: lo + i for i, c in enumerate(survivors)}
    data = bytes(index[remap[to_565(p[:3])]] if p[3] else 0 for p in pixels)
    palette = [(0, 0, 0)] * (hi + 1)
    for c, i in index.items():
        palette[i] = c
    changed = sum(1 for p in pixels if p[3] and remap[to_565(p[:3])] != to_565(p[:3]))
    indexed = Image.frombytes("P", image.size, data)
    flat = [v for c in palette for v in c]
    indexed.putpalette(flat + [0] * (768 - len(flat)))
    return indexed, palette, {"colors_565": len(counts), "colors_used": len(survivors), "merges": merges,
                              "pixels_changed": changed, "opaque_pixels": sum(1 for p in pixels if p[3])}


def gif_name(character, hi):
    return f"{character}__B8C{hi + 1:X}.gif"


def export(character, check_only=False):
    project = load_project()
    if character not in project.chars_raw:
        raise PortraitError(f"unknown character {character!r}")
    side = project.chars_raw[character].get("side")
    ranges = project.config["art"]["portrait"]["palette"]
    if side not in ranges:
        raise PortraitError(f"{character} needs side left or right in characters.json")
    lo, hi = ranges[side]
    expressions = len(project.char_exprs[character])
    source = REPO / "art" / "portraits" / f"{character}.png"
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
    indexed, palette, report = bake(image, lo, hi, expressions)
    out = ROOT / "assets" / "portraits" / gif_name(character, hi)
    if not check_only:
        out.parent.mkdir(parents=True, exist_ok=True)
        indexed.save(out, transparency=0, optimize=False)
        with Image.open(out) as saved:
            if saved.tobytes() != indexed.tobytes():
                raise PortraitError(f"{out.name}: saved indices differ from the baked image")
            if len(saved.getpalette() or []) // 3 < hi + 1:
                raise PortraitError(f"{out.name}: palette was truncated below {hi + 1} entries")
    report.update(side=side, palette=(lo, hi), expressions=expressions, tiles=8 + 4 * (expressions - 1),
                  output=out.relative_to(REPO).as_posix())
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("character")
    parser.add_argument("--check", action="store_true", help="validate and report without writing the GIF")
    args = parser.parse_args(argv)
    try:
        r = export(args.character, args.check)
    except (PortraitError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"{args.character}: {r['expressions']} expressions, {r['tiles']} tiles, {r['side']} palette "
          f"{r['palette'][0]}-{r['palette'][1]}")
    print(f"  {r['colors_565']} colours at RGB565 precision -> {r['colors_used']} used "
          f"({r['merges']} merged, {r['pixels_changed']} of {r['opaque_pixels']} opaque pixels changed)")
    print(f"  {'checked' if args.check else 'wrote'} {r['output']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
