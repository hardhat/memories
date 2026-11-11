#!/usr/bin/env python3
"""Export the approved farm pilot, baked into the world palette.

Run: python script\\tools\\export_farm_pilot.py
Inputs: farm-mixed-sample.png and sprites/brad-farm.png (16x192, south,
north, east; two 16x32 frames each). Outputs go to art/exploration/farm-pilot.
Colours are lossless and shared by both images. Indices are BAKED (screen-spec.md
section 3): 0 is transparent, colour n of the shared palette is index 126 + n - 1,
so the pilot's 117 colours occupy 126-242 and the engine copies tiles and palette
without remapping. The GIFs are named __B8CFD (253 palette entries). Tile
slots are not baked: the manifest gives each tile's target hardware slot.
"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "art" / "exploration" / "farm-pilot"
WORLD_FIRST = 126        # first world palette index
WORLD_ENTRIES = 253      # palette entries in the GIF: 0-252 (the C flag, FD)
WORLD_SLOT = 164         # first hardware tile slot for world art


def load_source(path, size):
    with Image.open(path) as source:
        image = source.convert("RGBA")
    if image.size != size:
        raise ValueError(f"{path}: expected {size}, got {image.size}")
    if any(pixel[3] not in (0, 255) for pixel in image.get_flattened_data()):
        raise ValueError(f"{path}: partial alpha is not supported")
    return image


def make_palette(images):
    colours = []
    seen = set()
    for image in images:
        for colour in sorted({p[:3] for p in image.get_flattened_data() if p[3]}):
            if colour not in seen:
                colours.append(colour)
                seen.add(colour)
    if len(colours) > 127:
        raise ValueError(f"Need {len(colours)+1} palette entries; limit is 128")
    return [(0, 0, 0)] + colours


def index_image(image, colours):
    """The image with every colour at its baked index: 0 transparent, colour n at 126 + n - 1."""
    lookup = {colour: WORLD_FIRST + index - 1 for index, colour in enumerate(colours[1:], 1)}
    pixels = bytes(lookup[p[:3]] if p[3] else 0 for p in image.get_flattened_data())
    indexed = Image.frombytes("P", image.size, pixels)
    palette = [0, 0, 0] * WORLD_FIRST + [channel for colour in colours[1:] for channel in colour]
    indexed.putpalette(palette + [0]*(768-len(palette)))
    return indexed


def tile_bytes(image):
    return b"".join(
        image.crop((x, y, x+16, y+16)).tobytes()
        for y in range(0, image.height, 16)
        for x in range(0, image.width, 16))


def export_image(image, colours, stem):
    indexed = index_image(image, colours)
    gif_path = OUTPUT / f"{stem}__B8C{WORLD_ENTRIES:X}.gif"
    indexed.save(gif_path, transparency=0, optimize=False)
    with Image.open(gif_path) as saved:
        if saved.tobytes() != indexed.tobytes() or saved.getpalette() != indexed.getpalette():
            raise ValueError(f"{gif_path}: GIF changed palette or indices")
        for original, decoded in zip(image.get_flattened_data(), saved.convert("RGBA").get_flattened_data()):
            if original[3] != decoded[3] or (original[3] and original != decoded):
                raise ValueError(f"{gif_path}: visible source pixels changed")
        raw = tile_bytes(saved)
    (OUTPUT / f"{stem}.zts").write_bytes(raw)
    return len(raw)//256


def main():
    terrain = load_source(ROOT / "art" / "terrain" / "farm-mixed-sample.png", (64, 160))
    brad = load_source(ROOT / "art" / "sprites" / "brad-farm.png", (16, 192))
    colours = make_palette([terrain, brad])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    terrain_count = export_image(terrain, colours, "farm")
    sprite_count = export_image(brad, colours, "brad-farm")
    if (terrain_count, sprite_count) != (40, 12):
        raise ValueError("Unexpected pilot tile allocation")
    frames = []
    for direction_index, direction in enumerate(("south", "north", "east")):
        for frame in range(2):
            first = 40 + direction_index*4 + frame*2
            frames.append({"direction": direction, "frame": frame,
                           "local_tiles": [first, first+1],
                           "target_hardware_tiles": [WORLD_SLOT+first, WORLD_SLOT+first+1]})
    manifest = {
        "status": "baked into world palette 126-252; map/sprite runtime integration pending (Phase 5)",
        "palette_entries_used_including_transparency": len(colours),
        "palette_rgb": colours, "transparency_index": 0,
        "palette_first_index": WORLD_FIRST, "palette_last_index": WORLD_FIRST + len(colours) - 2,
        "palette_format": "RGB565 (the compiler stores the used slice); GIF palettes carry the 8-bit colours",
        "tile_size": 16, "scenery_tiles": terrain_count,
        "brad_tiles": sprite_count, "resident_tiles": 52, "remaining_world_slots": 40,
        "tile_order": "farm then brad-farm; no deduplication",
        "frames": frames,
        "west": "mirror east horizontally, independently for both vertically stacked tiles",
        "empty_cells": "not exported here; map empty must use hardware tile 0, not relocated world tile",
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(f"Exported 52 resident tiles; {len(colours)-1} colours at {WORLD_FIRST}-{WORLD_FIRST + len(colours) - 2} "
          f"of the 127 world entries; 40 world slots free.")


if __name__ == "__main__":
    main()
