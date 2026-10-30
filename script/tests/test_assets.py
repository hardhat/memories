"""Tests for the art pipeline. Run: python -m unittest discover script/tests

End-to-end tests run the real SDK gif2zeal.py and are skipped when it is not next to this repo."""
import importlib.util
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image  # noqa: E402

from memo import gfx  # noqa: E402
from memo.assets import DEFAULT_TOOL, load_assets  # noqa: E402
from memo.compile import compile_project  # noqa: E402
from memo.datread import Dat  # noqa: E402
from memo.pack import build_dat  # noqa: E402
from memo.spec import ASSET_BASE  # noqa: E402
from test_compile import mini, scene  # noqa: E402

try:
    HAVE_TOOL = DEFAULT_TOOL.exists()
except OSError:
    HAVE_TOOL = False


def sdk():
    spec = importlib.util.spec_from_file_location("gif2zeal_sdk", DEFAULT_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def project():
    return mini([scene({"A": [{"op": "end"}]})])


def make_gif(path, w, h, colors, pixel=lambda x, y: 0):
    """Palette GIF whose palette uses every one of `colors` entries, so indices survive saving."""
    img = Image.new("P", (w, h))
    pal = []
    for i in range(256):
        pal += [i, (i * 3) & 255, (255 - i) & 255]
    img.putpalette(pal)
    img.putdata([pixel(x, y) % colors for y in range(h) for x in range(w)])
    img.save(path)


def build(p, manifest, folder, **kw):
    mpath = Path(folder) / "manifest.json"
    mpath.write_text(json.dumps(manifest), encoding="utf-8")
    assets = load_assets(p, mpath, **kw)
    data, layout = build_dat(p, compile_project(p), assets)
    return assets, Dat(data), layout


def errors(assets):
    return [d.msg for d in assets.diags if d.level == "error"]


@unittest.skipUnless(HAVE_TOOL, "SDK gif2zeal.py not found")
class Decoders(unittest.TestCase):
    def test_against_sdk_encoders(self):
        g = sdk()
        rng = random.Random(7)
        for bpp in (4, 8):
            size = gfx.tile_bytes(bpp)
            for kind in ("flat", "noise", "runs", "repeat"):
                if kind == "flat":
                    tile = [5] * size
                elif kind == "noise":
                    tile = [rng.randrange(256) for _ in range(size)]
                elif kind == "runs":
                    tile = [(i // rng.choice((3, 7, 40))) % 4 for i in range(size)]
                else:
                    tile = [(i % 9) for i in range(size)]
                for name, enc in (("rle", g.compress), ("lz", g.compress_lz)):
                    stream = bytes(enc(list(tile)))
                    two = stream + bytes(enc(list(tile)))
                    tiles = gfx.decode_tiles(two, name, bpp)
                    self.assertEqual(tiles, [bytes(tile)] * 2, f"{name} {kind} {bpp}bpp")

    def test_truncated_streams_fail(self):
        with self.assertRaises(gfx.GfxError):
            gfx.decode_tiles(b"\x05\x01\x02", "rle", 8)
        with self.assertRaises(gfx.GfxError):
            gfx.decode_tiles(b"\xff", "lz", 8)


class Flags(unittest.TestCase):
    def test_filename_flags(self):
        f = gfx.filename_flags("x/jane__B8C20R.gif")
        self.assertEqual((f["stem"], f["bpp"], f["colors"], f["compress"]), ("jane", 8, 0x20, "rle"))
        f = gfx.filename_flags("cg__B4UM.gif")
        self.assertEqual((f["bpp"], f["unique"], f["tilemap"], f["compress"]), (4, True, True, None))
        self.assertFalse(gfx.filename_flags("plain.gif")["flagged"])

    def test_pixel_index(self):
        self.assertEqual(gfx.max_pixel_index(bytes([1, 9, 3]), 8), 9)
        self.assertEqual(gfx.max_pixel_index(bytes([0x12, 0x3F]), 4), 15)
        self.assertEqual(gfx.max_pixel_index(bytes([0b00011011]), 2), 3)


class MissingArt(unittest.TestCase):
    def test_placeholders_keep_ids_stable(self):
        p = project()
        with tempfile.TemporaryDirectory() as d:
            assets, dat, layout = build(p, {}, d)
        # jane: descriptor, tiles, palette; one CG: tiles, tilemap, palette
        self.assertEqual(len(assets.blocks), 6)
        self.assertEqual(assets.blocks[0].id, ASSET_BASE)
        self.assertEqual(dat.index["portraits"], [(0,), (ASSET_BASE,)])
        self.assertEqual(dat.index["cgs"], [(ASSET_BASE + 3, ASSET_BASE + 4, ASSET_BASE + 5)])
        self.assertTrue(dat.is_missing(ASSET_BASE + 1))
        self.assertIsNone(dat.tileset(ASSET_BASE + 1))
        self.assertEqual(sorted(assets.missing), ["CG-01", "jane"])
        self.assertTrue(any(d.level == "missing" for d in assets.diags))


@unittest.skipUnless(HAVE_TOOL, "SDK gif2zeal.py not found")
class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def gif(self, name, w, h, colors, pixel=lambda x, y: 0):
        make_gif(self.dir / name, w, h, colors, pixel)
        return name

    def test_cg_8bpp(self):
        px = lambda x, y: (x // 16 + y // 16) % 30
        manifest = {"cgs": {"CG-01": {"gif": self.gif("cg01__B8C20.gif", 320, 192, 30, px)}}}
        assets, dat, _ = build(project(), manifest, self.dir, convert=True)
        self.assertEqual(errors(assets), [])
        tiles, tmap, pal = dat.index["cgs"][0]
        bpp, comp, count, data = dat.tileset(tiles)
        self.assertEqual((bpp, comp, count, len(data)), (8, 0, 240, 240 * 256))
        self.assertEqual(tmap, 0)
        first, last, colors = dat.palette(pal)
        self.assertEqual((first, last), (0, 31))
        self.assertEqual(colors[1], ((1 >> 3) << 11) | ((3 >> 2) << 5) | (254 >> 3))
        self.assertEqual(data[0], 0)
        self.assertEqual(data[256], 1)  # second tile is one 16 px step to the right
        self.assertEqual(sorted(assets.missing), ["jane"])

    def test_cg_4bpp_unique_with_tilemap(self):
        manifest = {"cgs": {"CG-01": {"gif": self.gif("cg01__B4UMC10.gif", 320, 240, 16,
                                                         lambda x, y: (x // 16) % 16)}}}
        assets, dat, _ = build(project(), manifest, self.dir, convert=True)
        self.assertEqual(errors(assets), [])
        tiles, tmap, pal = dat.index["cgs"][0]
        bpp, comp, count, data = dat.tileset(tiles)
        self.assertEqual((bpp, count, len(data)), (4, 16, 16 * 128))
        comp_, w, h, table = dat.tilemap(tmap)
        self.assertEqual((w, h, len(table)), (20, 15, 300))
        self.assertEqual(max(table), 15)

    def test_cg_wrong_size_is_an_error(self):
        manifest = {"cgs": {"CG-01": {"gif": self.gif("cg01__B8.gif", 320, 176, 8)}}}
        assets, _, _ = build(project(), manifest, self.dir, convert=True)
        self.assertTrue(any("220" in e or "tiles" in e for e in errors(assets)), errors(assets))

    def test_portrait(self):
        # 32 wide: 80 px base, then one 32 px alternate head
        manifest = {"portraits": {"jane": {"gif": self.gif("jane__B8C20.gif", 32, 112, 32,
                                                           lambda x, y: (x + y) % 32)}}}
        assets, dat, _ = build(project(), manifest, self.dir, convert=True)
        self.assertEqual(errors(assets), [])
        desc = dat.portrait(dat.index["portraits"][1][0])
        self.assertEqual(desc["base"], (2, 5))
        self.assertEqual(desc["head"], (0, 0, 2, 2))
        self.assertEqual(desc["exprs"], 2)
        bpp, comp, count, data = dat.tileset(desc["tiles"])
        self.assertEqual((bpp, count), (8, 14))
        first, last, colors = dat.palette(desc["palette"])
        self.assertEqual(last, 31)

    def test_portrait_checks(self):
        cases = {
            "tile count": self.gif("a__B8C20.gif", 32, 80, 32),            # no alternate head
            "colours": self.gif("b__B8.gif", 32, 112, 256, lambda x, y: x + y * 32),   # 256 colour palette
            "bpp": self.gif("c__B4C10.gif", 32, 112, 16),
        }
        for label, gif in cases.items():
            with self.subTest(label):
                assets, _, _ = build(project(), {"portraits": {"jane": {"gif": gif}}}, self.dir, convert=True)
                self.assertTrue(errors(assets), label)
                self.assertIn("jane", assets.missing + ["jane"])

    def test_palette_overflow(self):
        gif = self.gif("jane__B8C10.gif", 32, 112, 64, lambda x, y: x + y)
        assets, dat, _ = build(project(), {"portraits": {"jane": {"gif": gif}}}, self.dir, convert=True)
        self.assertTrue(any("outside the palette" in e for e in errors(assets)), errors(assets))
        self.assertTrue(dat.is_missing(dat.index["portraits"][1][0] + 1))

    def test_keep_compression(self):
        manifest = {"cgs": {"CG-01": {"gif": self.gif("cg01__B8C20R.gif", 320, 192, 30,
                                                         lambda x, y: (y // 16) % 30)}}}
        raw = {"cgs": {"CG-01": {"gif": "cg01__B8C20R.gif"}}}
        assets, dat, _ = build(project(), manifest, self.dir, convert=True, keep_compression=True)
        self.assertEqual(errors(assets), [])
        tiles = dat.index["cgs"][0][0]
        bpp, comp, count, packed = dat.tileset(tiles)
        self.assertEqual((comp, count), (1, 240))
        self.assertLess(len(packed), 240 * 256 // 4)
        assets2, dat2, _ = build(project(), raw, self.dir)
        bpp2, comp2, count2, plain = dat2.tileset(dat2.index["cgs"][0][0])
        self.assertEqual((comp2, count2), (0, 240))
        self.assertEqual(b"".join(gfx.decode_tiles(packed, "rle", 8)), plain)

    def test_tileset_limit(self):
        gif = self.gif("town__B8C10.gif", 256, 256, 8, lambda x, y: (x // 16 + y // 16) % 8)
        assets, _, _ = build(project(), {"tilesets": {"town": {"gif": gif}}}, self.dir, convert=True)
        self.assertTrue(any("at most 255" in e for e in errors(assets)), errors(assets))

    def test_tileset_ok(self):
        gif = self.gif("town__B8C10.gif", 256, 128, 8, lambda x, y: (x // 16) % 8)
        assets, dat, _ = build(project(), {"tilesets": {"town": {"gif": gif}}}, self.dir, convert=True)
        self.assertEqual(errors(assets), [])
        tiles, pal = dat.index["tilesets"][0]
        self.assertEqual(dat.tileset(tiles)[2], 128)

    def test_stale_output_needs_convert(self):
        gif = self.gif("jane__B8C20.gif", 32, 112, 32)
        assets, _, _ = build(project(), {"portraits": {"jane": {"gif": gif}}}, self.dir)
        self.assertTrue(any("--convert" in e for e in errors(assets)), errors(assets))

    def test_unflagged_name_rejected(self):
        gif = self.gif("jane.gif", 32, 112, 32)
        assets, _, _ = build(project(), {"portraits": {"jane": {"gif": gif}}}, self.dir, convert=True)
        self.assertTrue(any("flags" in e for e in errors(assets)), errors(assets))


if __name__ == "__main__":
    unittest.main()
