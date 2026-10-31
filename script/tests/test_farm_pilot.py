import importlib.util
from pathlib import Path
import struct
import sys
import unittest

from PIL import Image

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("export_farm_pilot", TOOLS / "export_farm_pilot.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class FarmPilotTests(unittest.TestCase):
    def test_exact_palette_and_transparency(self):
        image = Image.new("RGBA", (16, 16))
        image.putpixel((0, 0), (0, 0, 0, 255))
        image.putpixel((1, 0), (20, 40, 60, 255))
        colours = exporter.make_palette([image])
        indexed = exporter.index_image(image, colours)
        self.assertEqual(indexed.getpixel((0, 0)), 1)
        self.assertEqual(indexed.getpixel((1, 0)), 2)
        self.assertEqual(indexed.getpixel((2, 0)), 0)

    def test_palette_overflow_rejected(self):
        image = Image.new("RGBA", (16, 16))
        for index in range(128):
            image.putpixel((index % 16, index // 16), (index, 0, 0, 255))
        with self.assertRaisesRegex(ValueError, "limit is 128"):
            exporter.make_palette([image])

    def test_partial_alpha_rejected(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            path = Path(directory) / "partial.png"
            Image.new("RGBA", (16, 16), (1, 2, 3, 128)).save(path)
            with self.assertRaisesRegex(ValueError, "partial alpha"):
                exporter.load_source(path, (16, 16))

    def test_saved_exports(self):
        import json

        manifest = json.loads((exporter.OUTPUT / "manifest.json").read_text())
        self.assertLessEqual(manifest["palette_entries_used_including_transparency"], 128)
        expected_palette = b"".join(struct.pack(
            "<H", (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3))
            for r, g, b in manifest["palette_rgb"])
        self.assertEqual((exporter.OUTPUT / "farm-shared.ztp").read_bytes(),
                         expected_palette.ljust(256, b"\0"))
        for stem, count in (("farm", 40), ("brad-farm", 12)):
            raw = (exporter.OUTPUT / f"{stem}.zts").read_bytes()
            self.assertEqual(len(raw), count*256)
            with Image.open(exporter.OUTPUT / f"{stem}__B8C80.gif") as image:
                rebuilt = Image.new("P", image.size)
                for index in range(count):
                    tile = Image.frombytes("P", (16, 16), raw[index*256:(index+1)*256])
                    columns = image.width//16
                    rebuilt.paste(tile, (index % columns*16, index//columns*16))
                self.assertEqual(rebuilt.tobytes(), image.tobytes())
                self.assertEqual(image.info["transparency"], 0)
                self.assertLess(max(raw), 128)
        self.assertEqual([frame["local_tiles"] for frame in manifest["frames"]],
                         [[40, 41], [42, 43], [44, 45], [46, 47], [48, 49], [50, 51]])


if __name__ == "__main__":
    unittest.main()
