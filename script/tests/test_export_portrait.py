"""Tests for the portrait exporter (script/tools/export_portrait.py)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from PIL import Image  # noqa: E402

import export_portrait as ep  # noqa: E402


def sheet(expressions, paint):
    """An RGBA sheet of the right size; paint(x, y) returns an RGB colour or None (transparent)."""
    image = Image.new("RGBA", (32, ep.expected_height(expressions)))
    for y in range(image.height):
        for x in range(32):
            c = paint(x, y)
            if c is not None:
                image.putpixel((x, y), (*c, 255))
    return image


class Colours(unittest.TestCase):
    def test_565_matches_what_the_hardware_shows(self):
        self.assertEqual(ep.to_565((0, 0, 0)), (0, 0, 0))
        self.assertEqual(ep.to_565((255, 255, 255)), (255, 255, 255))
        self.assertEqual(ep.to_565((200, 100, 50)), ep.to_565(ep.to_565((200, 100, 50))))   # idempotent
        self.assertEqual(ep.to_565((9, 9, 9)), ep.to_565((8, 8, 8)))                       # rounds to the same step

    def test_reduce_keeps_only_existing_colours_and_merges_into_the_frequent_one(self):
        counts = {(10, 10, 10): 100, (12, 12, 12): 3, (200, 0, 0): 50, (0, 200, 0): 40}
        remap, merges = ep.reduce_colors(counts, 3)
        self.assertEqual(merges, 1)
        self.assertEqual(remap[(12, 12, 12)], (10, 10, 10))
        self.assertEqual(set(remap.values()), {(10, 10, 10), (200, 0, 0), (0, 200, 0)})

    def test_reduce_is_deterministic_and_respects_the_limit(self):
        counts = {(i * 5, i * 3, 255 - i * 4): 1 + i % 7 for i in range(60)}
        first = ep.reduce_colors(counts, 47)
        self.assertEqual(first, ep.reduce_colors(dict(counts), 47))
        self.assertLessEqual(len(set(first[0].values())), 47)
        self.assertEqual(first[1], 60 - 47)
        self.assertTrue(set(first[0].values()) <= set(counts))


class Bake(unittest.TestCase):
    def test_indices_are_baked_into_the_side_range(self):
        image = sheet(2, lambda x, y: (x * 8, 40, 90) if y % 2 == 0 and x < 4 else None)
        indexed, palette, report = ep.bake(image, 79, 125, 2)
        data = indexed.tobytes()
        self.assertEqual(min(v for v in data if v), 79)
        self.assertEqual(max(data), 79 + report["colors_used"] - 1)
        self.assertEqual(report["pixels_changed"], 0)             # four colours fit: nothing is merged
        self.assertEqual(data[5 * 32 + 20], 0)                    # transparent stays index 0
        self.assertEqual(len(palette), 126)
        for i, v in enumerate(image.get_flattened_data()):
            if v[3]:
                self.assertEqual(palette[data[i]], ep.to_565(v[:3]))

    def test_too_many_colours_are_merged_to_fit(self):
        # 8 x 12 = 96 distinct colours, merged down to the 47 of a left-side portrait
        image = sheet(2, lambda x, y: ((x % 8) * 30, (y % 12) * 20, 80))
        indexed, palette, report = ep.bake(image, 32, 78, 2)
        self.assertEqual(report["colors_used"], 47)
        self.assertGreater(report["merges"], 0)
        self.assertGreater(report["pixels_changed"], 0)
        self.assertTrue(set(indexed.tobytes()) <= set(range(32, 79)))

    def test_a_sheet_far_over_budget_is_rejected_not_squeezed(self):
        image = sheet(2, lambda x, y: ((x * 8) % 256, (y * 3) % 256, 80))
        with self.assertRaisesRegex(ep.PortraitError, "reduce it to at most 128"):
            ep.bake(image, 79, 125, 2)

    def test_wrong_size_is_rejected_with_the_expected_one(self):
        with self.assertRaisesRegex(ep.PortraitError, r"8 expressions need 32x288"):
            ep.bake(Image.new("RGBA", (32, 80)), 79, 125, 8)
        with self.assertRaisesRegex(ep.PortraitError, "32x64"):
            ep.bake(Image.new("RGBA", (16, 64)), 79, 125, 1)

    def test_partial_alpha_and_empty_sheets_are_rejected(self):
        image = Image.new("RGBA", (32, 64), (1, 2, 3, 128))
        with self.assertRaisesRegex(ep.PortraitError, "partial alpha"):
            ep.bake(image, 79, 125, 1)
        with self.assertRaisesRegex(ep.PortraitError, "empty"):
            ep.bake(Image.new("RGBA", (32, 64)), 79, 125, 1)

    def test_opaque_black_is_not_transparent(self):
        indexed, _, _ = ep.bake(sheet(1, lambda x, y: (0, 0, 0)), 79, 125, 1)
        self.assertEqual(set(indexed.tobytes()), {79})


class Jane(unittest.TestCase):
    """The real asset: it must fit its side's range and keep its pixels through the export."""

    def test_checked_export(self):
        report = ep.export("jane", check_only=True)
        self.assertEqual((report["expressions"], report["tiles"], report["side"]), (8, 36, "right"))
        self.assertEqual(report["palette"], (79, 125))
        self.assertLessEqual(report["colors_used"], 47)
        self.assertLess(report["pixels_changed"] / report["opaque_pixels"], 0.05)   # the colour merge stays small

    def test_unknown_character_is_rejected(self):
        with self.assertRaisesRegex(ep.PortraitError, "unknown character"):
            ep.export("nobody", check_only=True)
        with self.assertRaisesRegex(ep.PortraitError, "side"):
            ep.export("narrator", check_only=True)


if __name__ == "__main__":
    unittest.main()
