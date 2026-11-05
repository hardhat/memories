#!/usr/bin/env python3
"""Compose the title screen: art/title/title-bg.png plus the lettering.

The background is a textless 1280x768 image made like the other CGs (gen_cg_placeholders.py
CG-title). The lettering is drawn at the same size, so downscaling it in convert_cgs.py gives
smooth text at 320x192. Writes art/cg-placeholders/CG-title.png; run convert_cgs.py CG-title next.

  python script/tools/make_title.py
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKGROUND = REPO_ROOT / "art" / "title" / "title-bg.png"
OUTPUT = REPO_ROOT / "art" / "cg-placeholders" / "CG-title.png"
FONT = "georgiab.ttf"
FONT_FALLBACK = "timesbd.ttf"

CREAM = (255, 238, 190)
ORANGE = (255, 168, 48)
OUTLINE = (22, 12, 40)

# (text, pixel height at 1280x768, top y, fill). The block is left aligned at X.
X = 48
LINES = [
    ("Memories of", 50, 30, CREAM),
    ("Ravenwood", 96, 78, ORANGE),
    ("College", 96, 178, ORANGE),
    ("by Hardhat", 44, 296, CREAM),
]
OUTLINE_WIDTH = 8


def load_font(size):
    for name in (FONT, FONT_FALLBACK):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    raise SystemExit(f"neither {FONT} nor {FONT_FALLBACK} is installed")


def main():
    with Image.open(BACKGROUND) as src:
        img = src.convert("RGB")
    if img.size != (1280, 768):
        print(f"Error: {BACKGROUND} is {img.size}, expected 1280x768", file=sys.stderr)
        return 1
    draw = ImageDraw.Draw(img)
    for text, size, y, fill in LINES:
        draw.text((X, y), text, font=load_font(size), fill=fill,
                  stroke_width=OUTLINE_WIDTH, stroke_fill=OUTLINE)
    img.save(OUTPUT)
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
