#!/usr/bin/env python3
"""Convert CG placeholder images for the Zeal 8-bit engine.

Downsizes high-res CG placeholder PNGs (1280x768) to 320x192, converts them
to 128-color palette GIFs (named with gif2zeal flags, e.g. CG-01__B8C80.gif),
and converts them directly to uncompressed Zeal formats:
  - .ztp: 128-color palette (RGB565 little-endian, 256 bytes)
  - .zts: 240 tiles (16x16 pixels, 8bpp, raster order, 61,440 bytes)

Usage:
  python tools/convert_cgs.py                 # Convert all CG placeholders
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
TILE_SIZE = 16
TILES_X = TARGET_WIDTH // TILE_SIZE    # 20
TILES_Y = TARGET_HEIGHT // TILE_SIZE   # 12
TOTAL_TILES = TILES_X * TILES_Y        # 240
COLOR_COUNT = 128                      # 128 colors = 0x80 in hex
EXPECTED_ZTS_SIZE = TOTAL_TILES * TILE_SIZE * TILE_SIZE  # 61,440 bytes (8bpp)
EXPECTED_ZTP_SIZE = COLOR_COUNT * 2                      # 256 bytes (RGB565)


def rgb_to_rgb565(r, g, b):
    """Convert 8-bit RGB to 16-bit RGB565 little-endian."""
    red = (r >> 3) & 0x1F
    green = (g >> 2) & 0x3F
    blue = (b >> 3) & 0x1F
    val = (red << 11) | (green << 5) | blue
    return val & 0xFF, (val >> 8) & 0xFF


def convert_image(png_path, out_dir, force=False):
    """Downsize PNG to 320x192, quantize to 128-color GIF, and export .ztp and .zts."""
    stem = png_path.stem  # e.g. "CG-01"
    # Filename flag: B8 = 8bpp, C80 = 128 colors (0x80 in hex)
    gif_name = f"{stem}__B8C80.gif"
    gif_path = out_dir / gif_name
    ztp_path = out_dir / f"{stem}.ztp"
    zts_path = out_dir / f"{stem}.zts"

    if not force and gif_path.exists() and ztp_path.exists() and zts_path.exists():
        if (gif_path.stat().st_mtime >= png_path.stat().st_mtime and
            ztp_path.stat().st_mtime >= png_path.stat().st_mtime and
            zts_path.stat().st_mtime >= png_path.stat().st_mtime):
            return False, "up to date"

    # 1. Downsize to 320x192
    with Image.open(png_path) as src_img:
        rgb_img = src_img.convert("RGB")
        resized = rgb_img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)

    # 2. Quantize to 128 colors
    quantized = resized.quantize(colors=COLOR_COUNT, method=Image.Quantize.MEDIANCUT)

    # Save GIF
    quantized.save(gif_path)

    # 3. Read back saved GIF to ensure palette and indices match what was written
    with Image.open(gif_path) as gif_img:
        pal = gif_img.getpalette() or []
        pixels = gif_img.load()

        # Build .ztp (RGB565 little-endian, COLOR_COUNT entries = 256 bytes)
        ztp = bytearray()
        for i in range(COLOR_COUNT):
            idx = i * 3
            if idx + 2 < len(pal):
                r, g, b = pal[idx], pal[idx + 1], pal[idx + 2]
            else:
                r, g, b = 0, 0, 0
            lo, hi = rgb_to_rgb565(r, g, b)
            ztp.append(lo)
            ztp.append(hi)

        # Build .zts (8bpp tiles in 16x16 raster order = 61,440 bytes)
        zts = bytearray()
        for ty in range(TILES_Y):
            for tx in range(TILES_X):
                for py in range(TILE_SIZE):
                    for px in range(TILE_SIZE):
                        x = tx * TILE_SIZE + px
                        y = ty * TILE_SIZE + py
                        p = pixels[x, y]
                        if p >= COLOR_COUNT:
                            raise ValueError(f"Pixel index {p} >= {COLOR_COUNT} in {png_path.name}")
                        zts.append(p)

    assert len(ztp) == EXPECTED_ZTP_SIZE, f"Unexpected .ztp size: {len(ztp)}"
    assert len(zts) == EXPECTED_ZTS_SIZE, f"Unexpected .zts size: {len(zts)}"

    ztp_path.write_bytes(ztp)
    zts_path.write_bytes(zts)

    return True, f"-> {gif_name}, {ztp_path.name} ({len(ztp)} B), {zts_path.name} ({len(zts)} B)"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert CG placeholders to 320x192 128-color GIFs and Zeal .ztp/.zts")
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

