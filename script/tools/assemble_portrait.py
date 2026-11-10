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
   "defringe": 20,                                    # optional, see below
   "expressions": {"smile": 4, "wink": 7, ...}}      # candidate file c<NN>.png per expression
`defringe` removes the partly blended magenta pixels along the silhouette (red and blue both more
than that much above green); it refuses if any such pixel lies inside the figure.
`edits` (optional) sets hand-placed pixels in one expression's head, as {"embarrassed": [[x, y, [r, g, b]], ...]}
with x, y in the 32x32 head; each must land on an opaque pixel. Used for details the generator cannot
draw at this size, such as a blush.
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


def defringe(image, tint):
    """Remove the partly blended magenta left along the silhouette: pixels whose red and blue both
    exceed green by more than `tint`. Natural colours (hair, skin, eyes, black) never do. Every removed
    pixel must connect to the background through other removed pixels; one inside the figure is a
    real colour, so this refuses rather than punching a hole."""
    out = image.copy()
    pixels = out.load()
    w, h = out.size
    tinted = {(x, y) for y in range(h) for x in range(w)
              if pixels[x, y][3] and pixels[x, y][0] - pixels[x, y][1] > tint and pixels[x, y][2] - pixels[x, y][1] > tint}
    reached, frontier = set(), [(x, y) for y in range(h) for x in range(w) if not pixels[x, y][3]]
    seen = set(frontier)
    while frontier:
        x, y = frontier.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if n in tinted and n not in seen:
                    seen.add(n)
                    reached.add(n)
                    frontier.append(n)
    inner = tinted - reached
    if inner:
        raise AssembleError(f"{len(inner)} tinted pixel(s) lie inside the figure (first at {min(inner)}); they are "
                            f"real colours, so raise the defringe threshold above {tint}")
    for x, y in tinted:
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


def prepare(path, shift, tint=None):
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
    if image.size != SIZE:
        raise AssembleError(f"{path.name} is {image.width}x{image.height}; candidates must be 32x64")
    image = key_magenta(image)
    if tint is not None:
        image = defringe(image, tint)
    return shift_up(image, shift)


def assemble(base, donors, window, edits=None):
    """base: prepared 32x64 base candidate; donors: prepared candidates in expression order,
    starting with the base itself. edits maps an expression position (0 is the base) to a list of
    (x, y, (r, g, b)) pixels set inside that expression's 32x32 head region, each on an opaque pixel.
    Returns the 32 x (64 + 32 * (n - 1)) sheet."""
    x0, y0, x1, y1 = window
    if not (0 <= x0 < x1 <= 32 and 0 <= y0 < y1 <= 32):
        raise AssembleError(f"face window {list(window)} must lie inside the 32x32 head region")
    sheet = Image.new("RGBA", (32, 64 + 32 * (len(donors) - 1)))
    sheet.paste(base, (0, 0))
    for k, donor in enumerate(donors[1:]):
        head = base.crop((0, 0, 32, 32))
        head.paste(donor.crop(window), (x0, y0))
        sheet.paste(head, (0, 64 + 32 * k))
    for position, pixels in (edits or {}).items():
        if not 0 <= position < len(donors):
            raise AssembleError(f"edit for expression position {position}, but there are {len(donors)}")
        top = 0 if position == 0 else 64 + 32 * (position - 1)
        for x, y, color in pixels:
            if not (0 <= x < 32 and 0 <= y < 32):
                raise AssembleError(f"edit pixel ({x}, {y}) is outside the 32x32 head region")
            if sheet.getpixel((x, top + y))[3] != 255:
                raise AssembleError(f"edit pixel ({x}, {y}) is not on an opaque pixel")
            sheet.putpixel((x, top + y), (*color, 255))
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
        return prepare(folder / f"c{index:02}.png", spec["shift"], spec.get("defringe"))

    base = load(spec["base"])
    donors = [base if index == spec["base"] else load(index) for index in spec["expressions"].values()]
    edits = {}
    for expression, pixels in spec.get("edits", {}).items():
        if expression not in wanted:
            raise AssembleError(f"edits name {expression!r}, which is not one of {wanted}")
        edits[wanted.index(expression)] = [(x, y, tuple(color)) for x, y, color in pixels]
    return assemble(base, donors, tuple(spec["window"]), edits)


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
