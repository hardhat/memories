"""Tests for the portrait assembler (script/tools/assemble_portrait.py)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from PIL import Image  # noqa: E402

import assemble_portrait as ap  # noqa: E402

MAGENTA = (239, 11, 233, 255)


def figure(fill, rows=64):
    """A 32x64 candidate: magenta background with an opaque block, row by row distinguishable."""
    image = Image.new("RGBA", ap.SIZE, MAGENTA)
    for y in range(rows):
        for x in range(4, 28):
            image.putpixel((x, y), (fill, y, x, 255))
    return image


class Keying(unittest.TestCase):
    def test_magenta_becomes_transparent_and_other_colours_stay(self):
        out = ap.key_magenta(figure(10))
        self.assertEqual(out.getpixel((0, 0))[3], 0)
        self.assertEqual(out.getpixel((10, 5)), (10, 5, 10, 255))

    def test_slightly_off_magenta_is_keyed_too(self):
        image = Image.new("RGBA", (32, 64), (224, 16, 200, 255))
        self.assertEqual(set(ap.key_magenta(image).getchannel("A").get_flattened_data()), {0})

    def test_a_dark_red_or_skin_colour_is_not_mistaken_for_the_key(self):
        for colour in ((140, 20, 20), (230, 170, 140), (40, 40, 200), (255, 120, 200)):
            image = Image.new("RGBA", (32, 64), (*colour, 255))
            self.assertEqual(ap.key_magenta(image).getpixel((3, 3))[3], 255, colour)


class Shift(unittest.TestCase):
    def test_figure_moves_up_and_the_last_row_is_repeated(self):
        image = figure(7)
        out = ap.shift_up(image, 4)
        self.assertEqual(out.size, ap.SIZE)
        self.assertEqual(out.getpixel((10, 0)), image.getpixel((10, 4)))
        self.assertEqual(out.getpixel((10, 59)), image.getpixel((10, 63)))
        for y in range(60, 64):
            self.assertEqual(out.getpixel((10, y)), image.getpixel((10, 63)))

    def test_zero_shift_changes_nothing(self):
        image = figure(7)
        self.assertEqual(ap.shift_up(image, 0).tobytes(), image.tobytes())


class Assemble(unittest.TestCase):
    def setUp(self):
        self.base = ap.shift_up(ap.key_magenta(figure(1)), 0)
        self.donors = [self.base, ap.key_magenta(figure(2)), ap.key_magenta(figure(3))]

    def test_sheet_size_and_base(self):
        sheet = ap.assemble(self.base, self.donors, (8, 12, 25, 31))
        self.assertEqual(sheet.size, (32, 64 + 32 * 2))
        self.assertEqual(sheet.crop((0, 0, 32, 64)).tobytes(), self.base.tobytes())

    def test_only_the_face_window_comes_from_the_donor(self):
        window = (8, 12, 25, 31)
        sheet = ap.assemble(self.base, self.donors, window)
        head = sheet.crop((0, 64, 32, 96))
        for y in range(32):
            for x in range(32):
                inside = window[0] <= x < window[2] and window[1] <= y < window[3]
                source = self.donors[1] if inside else self.base
                self.assertEqual(head.getpixel((x, y)), source.getpixel((x, y)), (x, y))

    def test_window_must_stay_inside_the_head_region(self):
        for window in ((8, 12, 25, 40), (0, 0, 33, 10), (10, 10, 10, 20)):
            with self.assertRaisesRegex(ap.AssembleError, "inside the 32x32 head region"):
                ap.assemble(self.base, self.donors, window)


class Jane(unittest.TestCase):
    """The checked-in sheet must be reproducible from its recorded sources."""

    def test_sheet_matches_its_sources(self):
        sheet = ap.build("jane")
        with Image.open(ap.PORTRAITS / "jane.png") as existing:
            self.assertEqual(existing.convert("RGBA").tobytes(), sheet.tobytes())
        self.assertEqual(sheet.size, (32, 288))

    def test_spec_errors_are_reported(self):
        with self.assertRaisesRegex(ap.AssembleError, "not a character with portrait expressions"):
            ap.build("narrator")


if __name__ == "__main__":
    unittest.main()
