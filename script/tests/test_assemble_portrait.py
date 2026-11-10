"""Tests for the portrait assembler (script/tools/assemble_portrait.py)."""
import json
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


class Defringe(unittest.TestCase):
    def blended(self):
        """A figure on a keyed background with a blended pixel on its edge."""
        image = ap.key_magenta(figure(10))
        image.putpixel((3, 20), (150, 40, 130, 255))     # halo pixel next to the background
        return image

    def test_edge_halo_is_removed(self):
        out = ap.defringe(self.blended(), 20)
        self.assertEqual(out.getpixel((3, 20))[3], 0)
        self.assertEqual(out.getpixel((4, 20)), (10, 20, 4, 255))   # the figure itself is untouched

    def test_nothing_changes_when_there_is_no_halo(self):
        image = ap.key_magenta(figure(10))
        self.assertEqual(ap.defringe(image, 20).tobytes(), image.tobytes())

    def test_a_tinted_pixel_inside_the_figure_is_refused(self):
        image = ap.key_magenta(figure(10))
        image.putpixel((15, 30), (200, 60, 190, 255))    # a real colour deep inside
        with self.assertRaisesRegex(ap.AssembleError, "inside the figure"):
            ap.defringe(image, 20)

    def test_a_halo_two_pixels_deep_is_followed_through(self):
        image = self.blended()
        image.putpixel((4, 20), (160, 50, 140, 255))
        out = ap.defringe(image, 20)
        self.assertEqual((out.getpixel((3, 20))[3], out.getpixel((4, 20))[3]), (0, 0))

    def test_natural_colours_are_never_tinted(self):
        for colour in ((140, 20, 20), (230, 170, 140), (110, 75, 50), (60, 120, 180), (25, 25, 30), (240, 240, 240)):
            image = Image.new("RGBA", (32, 64), (*colour, 255))
            image.putpixel((0, 0), (0, 0, 0, 0))
            self.assertEqual(ap.defringe(image, 20).tobytes(), image.tobytes(), colour)


class Edits(unittest.TestCase):
    def setUp(self):
        self.base = ap.key_magenta(figure(1))
        self.donors = [self.base, ap.key_magenta(figure(2)), ap.key_magenta(figure(3))]
        self.window = (8, 12, 25, 31)

    def test_pixels_are_set_in_the_named_head_only(self):
        sheet = ap.assemble(self.base, self.donors, self.window, {2: [(10, 20, (9, 8, 7))]})
        self.assertEqual(sheet.getpixel((10, 64 + 32 + 20)), (9, 8, 7, 255))        # position 2: second head
        self.assertNotEqual(sheet.getpixel((10, 64 + 20)), (9, 8, 7, 255))          # the other head is untouched
        self.assertNotEqual(sheet.getpixel((10, 20)), (9, 8, 7, 255))               # so is the base

    def test_position_zero_edits_the_base(self):
        sheet = ap.assemble(self.base, self.donors, self.window, {0: [(10, 20, (9, 8, 7))]})
        self.assertEqual(sheet.getpixel((10, 20)), (9, 8, 7, 255))

    def test_edits_must_land_on_opaque_pixels_inside_the_head(self):
        with self.assertRaisesRegex(ap.AssembleError, "not on an opaque pixel"):
            ap.assemble(self.base, self.donors, self.window, {1: [(0, 0, (1, 1, 1))]})      # background
        with self.assertRaisesRegex(ap.AssembleError, "outside the 32x32 head region"):
            ap.assemble(self.base, self.donors, self.window, {1: [(10, 40, (1, 1, 1))]})
        with self.assertRaisesRegex(ap.AssembleError, "expression position"):
            ap.assemble(self.base, self.donors, self.window, {5: [(10, 20, (1, 1, 1))]})


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


class Portraits(unittest.TestCase):
    """The checked-in sheets must be reproducible from their recorded sources."""

    def test_sheets_match_their_sources(self):
        for name, size in (("jane", (32, 288)), ("brad", (32, 352))):
            with self.subTest(name):
                sheet = ap.build(name)
                with Image.open(ap.PORTRAITS / f"{name}.png") as existing:
                    self.assertEqual(existing.convert("RGBA").tobytes(), sheet.tobytes())
                self.assertEqual(sheet.size, size)

    def test_every_face_fits_inside_the_head_region(self):
        for name in ("jane", "brad"):
            with self.subTest(name):
                sheet = ap.build(name)
                heads = [sheet.crop((0, 0, 32, 32))] + [sheet.crop((0, 64 + 32 * k, 32, 96 + 32 * k))
                                                          for k in range((sheet.height - 64) // 32)]
                for head in heads:
                    self.assertGreater(len(head.getbbox()), 0)
                    # hair reaches the top region and the face never needs the second tile row's pixels
                    self.assertLess(head.getbbox()[1], 8)

    def test_hair_is_identical_across_expressions_outside_the_window(self):
        sheet = ap.build("brad")
        spec = json.loads((ap.PORTRAITS / "brad.json").read_text())
        x0, y0, x1, y1 = spec["window"]
        base = sheet.crop((0, 0, 32, 32))
        for k in range((sheet.height - 64) // 32):
            head = sheet.crop((0, 64 + 32 * k, 32, 96 + 32 * k))
            for y in range(32):
                for x in range(32):
                    if not (x0 <= x < x1 and y0 <= y < y1):
                        self.assertEqual(head.getpixel((x, y)), base.getpixel((x, y)), (k, x, y))

    def test_spec_errors_are_reported(self):
        with self.assertRaisesRegex(ap.AssembleError, "not a character with portrait expressions"):
            ap.build("narrator")


if __name__ == "__main__":
    unittest.main()
