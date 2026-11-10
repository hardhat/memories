#!/usr/bin/env python3
"""Assemble a portrait sheet from chosen PixelLab candidates.

Run: python script/tools/assemble_portrait.py jane [--check]

Reads art/portraits/<name>.json and the raw 32x64 candidates it names, and writes
art/portraits/<name>.png (the sheet export_portrait.py bakes). Steps, in order:

  1. Key out the flat magenta background (the generator fills the canvas, edge to edge, when asked
     for a magenta background; a transparent request leaves the figure low in the canvas).
  2. Shift the figure up by `shift` rows and repeat the bottom row to refill, so the whole face lies
     inside the 32-row head region.
  3. The base image is the `base` candidate. Every other expression's 32x32 head is the base head
     with the face window `window` (x0, y0, x1, y1; exclusive) pasted from that expression's donor
     candidate. Outside the window the hair and body stay identical in every expression.

Spec (art/portraits/<name>.json):
  {"candidates": "source/jane", "base": 4, "shift": 4, "window": [8, 12, 25, 31],
   "expressions": {"smile": 4, "wink": 7, ...}}      # candidate file c<NN>.png per expression
The expression names must be exactly the character's list in characters.json (have, then todo).
The base expression (the first) must name the base candidate.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from memo.project import ROOT, load_project  # noqa: E402

REPO = ROOT.parent
PORTRAITS = REPO / "art" / "portraits"
SIZE = (32, 64)


class AssembleError(Exception):
    pass


def is_key(pixel):
    r, g, b = pixel[:3]
    return r > 170 and b > 150 and g < 90 and abs(r - b) < 60


def key_magenta(image):
    out = image.convert("RGBA")
    pixels = out.load()
    for y in range(out.height):
        for x in range(out.width):
            if is_key(pixels[x, y]):
                pixels[x, y] = (0, 0, 0, 0)
    return out


def shift_up(image, rows):
    """Move the figure up, dropping the top rows and repeating the last row at the bottom."""
    out = Image.new("RGBA", image.size)
    out.paste(image.crop((0, rows, image.width, image.height)), (0, 0))
    last = image.crop((0, image.height - 1, image.width, image.height))
    for k in range(rows):
        out.paste(last, (0, image.height - rows + k))
    return out


def prepare(path, shift):
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
    if image.size != SIZE:
        raise AssembleError(f"{path.name} is {image.width}x{image.height}; candidates must be 32x64")
    return shift_up(key_magenta(image), shift)


def assemble(base, donors, window):
    """base: prepared 32x64 base candidate; donors: prepared candidates in expression order,
    starting with the base itself. Returns the 32 x (64 + 32 * (n - 1)) sheet."""
    x0, y0, x1, y1 = window
    if not (0 <= x0 < x1 <= 32 and 0 <= y0 < y1 <= 32):
        raise AssembleError(f"face window {list(window)} must lie inside the 32x32 head region")
    sheet = Image.new("RGBA", (32, 64 + 32 * (len(donors) - 1)))
    sheet.paste(base, (0, 0))
    for k, donor in enumerate(donors[1:]):
        head = base.crop((0, 0, 32, 32))
        head.paste(donor.crop(window), (x0, y0))
        sheet.paste(head, (0, 64 + 32 * k))
    return sheet


def build(name):
    project = load_project()
    if name not in project.char_exprs or not project.char_exprs[name]:
        raise AssembleError(f"{name!r} is not a character with portrait expressions")
    spec = json.loads((PORTRAITS / f"{name}.json").read_text(encoding="utf-8"))
    wanted = list(project.char_exprs[name])
    given = list(spec["expressions"])
    if given != wanted:
        raise AssembleError(f"expressions must be exactly {wanted} in that order; the spec has {given}")
    if spec["expressions"][wanted[0]] != spec["base"]:
        raise AssembleError(f"the first expression ({wanted[0]}) must use the base candidate {spec['base']}")
    folder = PORTRAITS / spec["candidates"]

    def load(index):
        return prepare(folder / f"c{index:02}.png", spec["shift"])

    base = load(spec["base"])
    donors = [base if index == spec["base"] else load(index) for index in spec["expressions"].values()]
    return assemble(base, donors, tuple(spec["window"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("name")
    parser.add_argument("--check", action="store_true",
                        help="assemble and compare with the existing art/portraits/<name>.png without writing")
    args = parser.parse_args(argv)
    try:
        sheet = build(args.name)
    except (AssembleError, OSError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    target = PORTRAITS / f"{args.name}.png"
    if args.check:
        same = target.exists() and Image.open(target).convert("RGBA").tobytes() == sheet.tobytes()
        print(f"{target.name}: {'matches' if same else 'DIFFERS from'} the assembled sheet")
        return 0 if same else 1
    sheet.save(target)
    print(f"wrote {target.relative_to(REPO).as_posix()} ({sheet.width}x{sheet.height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
