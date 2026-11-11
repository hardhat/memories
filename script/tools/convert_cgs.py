#!/usr/bin/env python3
"""Convert CG images for the Zeal 8-bit engine.

Downsizes the high-res CG PNGs (1280x768) to 320x192 and quantizes them to 127 colours **baked
into the world palette range**: pixel index = 126 + colour number, so the engine copies the tiles
and palette without remapping (script/screen-spec.md section 3). Index 0 (black, shared with the
dialog) is left for the empty rows below the picture. The GIF is named with gif2zeal flags,
e.g. CG-01__B8CFD.gif (B8 = 8bpp, CFD = 253 palette entries: 0-252); the compiler runs gif2zeal
on it (memo_dat.py build --convert), so no .zts/.ztp is written here.

CG-title is the exception: it is shown at startup, before the dialog and portrait palettes exist,
and uses palette entries 0-127 (CG-title__B8C80.gif, see engine/title.c).

Usage:
  python tools/convert_cgs.py                 # Convert all CG images
  python tools/convert_cgs.py CG-01 CG-04a    # Convert specific CGs
  python tools/convert_cgs.py --force         # Overwrite existing files
"""
import argparse
import sys
from pathlib import Path
from PIL import Image

# Locate directories relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "tools" else SCRIPT_DIR
REPO_ROOT = PROJECT_ROOT.parent if PROJECT_ROOT.name == "script" else PROJECT_ROOT
DEFAULT_INPUT_DIR = REPO_ROOT / "art" / "cg-placeholders"
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR

TARGET_WIDTH = 320
TARGET_HEIGHT = 192
BAKED_FIRST = 126                      # first world palette index (screen-spec.md section 3)
BAKED_COLORS = 127                     # 126-252
BAKED_ENTRIES = BAKED_FIRST + BAKED_COLORS   # 253 = 0xFD palette entries in the GIF
LEGACY = {"CG-title": 128}             # stem -> colours, palette entries 0..colours-1


def rgb_to_rgb565(r, g, b):
    """Convert 8-bit RGB to 16-bit RGB565 little-endian."""
    red = (r >> 3) & 0x1F
    green = (g >> 2) & 0x3F
    blue = (b >> 3) & 0x1F
    val = (red << 11) | (green << 5) | blue
    return val & 0xFF, (val >> 8) & 0xFF


def hardware_colour(r, g, b):
    """The colour the video board shows for (r, g, b): RGB565 with the low bits replicated."""
    return ((r >> 3 << 3) | (r >> 5), (g >> 2 << 2) | (g >> 6), (b >> 3 << 3) | (b >> 5))


def bake(rgb_image):
    """Quantize to 127 colours at palette indices 126-252. Returns an indexed image (253 palette
    entries, 0-125 black) whose palette holds the hardware (RGB565) colours."""
    # kmeans refinement of the median-cut palette is worth 1-1.7 dB on these images
    quantized = rgb_image.quantize(colors=BAKED_COLORS, method=Image.Quantize.MEDIANCUT, kmeans=3)
    source = quantized.getpalette() or []
    colours = [hardware_colour(*source[i * 3:i * 3 + 3]) if i * 3 + 2 < len(source) else (0, 0, 0)
               for i in range(BAKED_COLORS)]
    if max(quantized.tobytes()) >= BAKED_COLORS:
        raise ValueError("quantizer returned an index outside its palette")
    baked = Image.frombytes("P", quantized.size, bytes(i + BAKED_FIRST for i in quantized.tobytes()))
    palette = [0] * (BAKED_FIRST * 3) + [c for colour in colours for c in colour]
    baked.putpalette(palette + [0] * (768 - len(palette)))
    return baked


def convert_image(png_path, out_dir, force=False):
    """Downsize PNG to 320x192 and write the baked (or, for the title, legacy) GIF."""
    stem = png_path.stem  # e.g. "CG-01"
    legacy = LEGACY.get(stem)
    # Filename flags: B8 = 8bpp, C = palette entries in hex (FD = 253, 80 = 128)
    gif_name = f"{stem}__B8C{(legacy or BAKED_ENTRIES):X}.gif"
    gif_path = out_dir / gif_name

    if not force and gif_path.exists() and gif_path.stat().st_mtime >= png_path.stat().st_mtime:
        return False, "up to date"

    with Image.open(png_path) as src_img:
        rgb_img = src_img.convert("RGB")
        resized = rgb_img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)

    if legacy:
        resized.quantize(colors=legacy, method=Image.Quantize.MEDIANCUT).save(gif_path)
    else:
        bake(resized).save(gif_path, optimize=False)   # optimize would renumber the indices

    with Image.open(gif_path) as check:
        used = sorted(set(check.tobytes()))
        if not legacy and (used[0] < BAKED_FIRST or used[-1] >= BAKED_ENTRIES):
            raise ValueError(f"{gif_name}: pixel indices {used[0]}..{used[-1]} are outside {BAKED_FIRST}-{BAKED_ENTRIES - 1}")
    return True, f"-> {gif_name}"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert CG PNGs to 320x192 GIFs baked into palette 126-252")
    parser.add_argument("ids", nargs="*", help="Optional CG IDs to convert (e.g. CG-01 CG-04a)")
    parser.add_argument("-i", "--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Input directory of PNGs")
    parser.add_argument("-o", "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("-f", "--force", action="store_true", help="Force rebuild even if outputs are newer")
    args = parser.parse_args(argv)

    in_dir = args.input_dir.resolve()
    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_dir.exists():
        print(f"Error: input directory not found: {in_dir}", file=sys.stderr)
        return 1

    png_files = sorted(in_dir.glob("*.png"))
    if args.ids:
        png_files = [p for p in png_files if p.stem in args.ids]
        missing = set(args.ids) - {p.stem for p in png_files}
        if missing:
            print(f"Warning: requested IDs not found: {', '.join(sorted(missing))}", file=sys.stderr)

    if not png_files:
        print("No PNG files to convert.")
        return 0

    print(f"Converting {len(png_files)} CG images ({in_dir} -> {out_dir})...")
    converted_count = 0
    for p in png_files:
        converted, msg = convert_image(p, out_dir, force=args.force)
        status = "Converted" if converted else "Skipped"
        print(f"  {status} {p.name} {msg}")
        if converted:
            converted_count += 1

    print(f"\nDone. {converted_count} of {len(png_files)} files converted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

