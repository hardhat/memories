"""Tests for the C engine (engine/): loader, VM, fault handling, and the Zeal (Z80) build.

They need a C compiler (gcc, clang or CC); the Z80 test needs sdcc and the Zeal-8-bit-OS headers."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from memo import ctrace  # noqa: E402
from memo.assets import DEFAULT_TOOL, load_assets  # noqa: E402
from memo.compile import compile_project  # noqa: E402
from memo.datread import Dat  # noqa: E402
from memo.pack import build_dat  # noqa: E402
from memo.project import load_project  # noqa: E402
from memo.sidecar import ids_header  # noqa: E402
from memo.spec import SCENE_CODE_BASE  # noqa: E402
from test_assets import make_gif  # noqa: E402
from test_compile import mini, scene  # noqa: E402

def have_tool():
    try:
        return DEFAULT_TOOL.exists()
    except OSError:
        return False


HAVE_CC = ctrace.find_compiler() is not None
ERR = {"PC": 2, "OP": 3, "VAR": 4, "STACK": 5, "EXPLORE": 6, "STRING": 8}


def full_game(manifest=None, convert=False):
    p = load_project()
    codes = compile_project(p)
    assets = load_assets(p, manifest, convert=convert)
    data, _ = build_dat(p, codes, assets)
    return p, data, ids_header(p, data, codes)


@unittest.skipUnless(HAVE_CC, "no C compiler")
class FullGame(unittest.TestCase):
    def test_engine_matches_python(self):
        p, data, header = full_game()
        with tempfile.TemporaryDirectory() as d:
            result = ctrace.compare_c(p, data, header, d, range(25))
        self.assertTrue(result["ok"], result.get("error"))
        self.assertGreater(result["events"], 10000)

    @unittest.skipUnless(have_tool(), "SDK gif2zeal.py not found")
    def test_engine_with_real_art_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            make_gif(d / "cg01__B8C20.gif", 320, 192, 30, lambda x, y: (x // 16 + y // 16) % 30)
            make_gif(d / "jane__B8C7E.gif", 32, 288, 126, lambda x, y: 79 + (x + y) % 47)
            (d / "manifest.json").write_text(
                '{"cgs": {"CG-01": {"gif": "cg01__B8C20.gif"}}, "portraits": {"jane": {"gif": "jane__B8C7E.gif"}}}')
            p, data, header = full_game(d / "manifest.json", convert=True)
            self.assertGreater(len(data), 61440 + 10000)
            result = ctrace.compare_c(p, data, header, d / "work", range(3), ("uniform",))
        self.assertTrue(result["ok"], result.get("error"))


@unittest.skipUnless(HAVE_CC, "no C compiler")
class Faults(unittest.TestCase):
    """Corrupt scene code must stop the VM with a specific error, never run wild."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.tmp.name)
        cls.project = mini([scene({"A": [{"op": "end"}]})])
        data, _ = build_dat(cls.project, compile_project(cls.project))
        cls.exe = ctrace.build_harness(cls.work, ids_header(cls.project, data, compile_project(cls.project)))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_blocks(self, blocks, patch=None, entry="A", extra=()):
        """Compile a mini scene, optionally patch one code byte, run it in the C harness."""
        p = mini([scene(blocks, entry)])
        data, _ = build_dat(p, compile_project(p))
        data = bytearray(data)
        if patch:
            pos, value = patch
            offset = Dat(bytes(data)).entries[SCENE_CODE_BASE][0]
            data[offset + 6 + pos] = value
        path = self.work / "case.dat"
        path.write_bytes(bytes(data))
        dec = self.work / "none.txt"
        dec.write_text("R 0 0\n\n")
        r = ctrace.run_exe(self.exe, path, "--decisions", dec, "--text", *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        runs = [l for l in r.stdout.splitlines() if l.startswith("RUN ")]
        self.assertEqual(len(runs), 1, r.stdout)
        events = [l for l in r.stdout.splitlines() if not l.startswith("RUN ")]
        return ctrace.parse_run_line(runs[0]), events

    def test_clean_run(self):
        res, events = self.run_blocks({"A": [{"op": "set", "var": "aff", "n": 3}, {"op": "end"}]})
        self.assertEqual((res["rc"], events), (0, ["var 0 3", "end"]))

    def test_unknown_opcode(self):
        res, _ = self.run_blocks({"A": [{"op": "end"}]}, patch=(0, 0x7F))
        self.assertEqual((res["rc"], res["pc"]), (ERR["OP"], 0))

    def test_ret_without_call(self):
        res, _ = self.run_blocks({"A": [{"op": "end"}]}, patch=(0, 0x24))
        self.assertEqual(res["rc"], ERR["STACK"])

    def test_xret_outside_explore(self):
        res, _ = self.run_blocks({"A": [{"op": "end"}]}, patch=(0, 0x32))
        self.assertEqual(res["rc"], ERR["EXPLORE"])

    def test_operand_past_end_of_code(self):
        res, _ = self.run_blocks({"A": [{"op": "end"}]}, patch=(0, 0x01))   # SAY needs 5 bytes
        self.assertEqual((res["rc"], res["pc"]), (ERR["PC"], 0))

    def test_variable_out_of_range(self):
        res, _ = self.run_blocks({"A": [{"op": "set", "var": "aff", "n": 1}, {"op": "end"}]}, patch=(1, 0x30))
        self.assertEqual(res["rc"], ERR["VAR"])

    def test_bad_string_id(self):
        blocks = {"A": [{"op": "say", "who": "jane", "expr": "smile", "text": "Hi."}, {"op": "end"}]}
        res, _ = self.run_blocks(blocks, patch=(4, 0x7F))
        self.assertEqual(res["rc"], ERR["STRING"])

    def test_call_depth_limit(self):
        res, _ = self.run_blocks({"A": [{"op": "call", "block": "B"}, {"op": "end"}],
                                  "B": [{"op": "call", "block": "B"}]})
        self.assertEqual(res["rc"], ERR["STACK"])

    def test_tutorial_shown_once_in_the_game(self):
        blocks = {"A": [{"op": "tutorial", "id": "t1", "text": "Hint."}] * 2 + [{"op": "end"}]}
        _, every = self.run_blocks(blocks)
        _, once = self.run_blocks(blocks, extra=("--tutorial-once",))
        self.assertEqual([e for e in every if e.startswith("tutorial")], ["tutorial 0 Hint."] * 2)
        self.assertEqual([e for e in once if e.startswith("tutorial")], ["tutorial 0 Hint."])

    def test_loader_rejects_bad_files(self):
        path = self.work / "bad.dat"
        for label, raw, code in (("empty", b"", 2), ("not a dat", bytes(64), 3)):
            path.write_bytes(raw)
            r = ctrace.run_exe(self.exe, path, "--inspect")
            self.assertIn(f"open error {code}", r.stdout, label)
        r = ctrace.run_exe(self.exe, self.work / "missing.dat", "--inspect")
        self.assertIn("open error 1", r.stdout)


@unittest.skipUnless(shutil.which("sdcc"), "sdcc not installed")
class ZealBuild(unittest.TestCase):
    ZOS = Path(__file__).resolve().parents[3] / "Zeal-8-bit-OS" / "sdk" / "sdcc" / "include"

    def test_engine_compiles_for_z80(self):
        try:
            if not self.ZOS.exists():
                self.skipTest("Zeal-8-bit-OS headers not found")
        except OSError:
            self.skipTest("Zeal-8-bit-OS headers not found")
        p, data, header = full_game()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "memo_ids.h").write_text(header, encoding="utf-8")
            for name in ("memo_dat", "memo_vm", "dat_io_zos", "game", "host", "screen", "portrait", "title"):
                src = ctrace.ENGINE / f"{name}.c"
                r = subprocess.run(["sdcc", "-mz80", "--std-c2x", "-c", "-I", str(ctrace.ENGINE), "-I", str(d),
                                    "-I", str(self.ZOS), "--codeseg", "TEXT", "-o", str(d / f"{name}.rel"), str(src)],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f"{name}: {r.stderr}")
                self.assertNotIn("warning", r.stderr, f"{name}: {r.stderr}")


def build_c(work, sources, exe_name, header):
    """Compile desktop test programs strictly against a generated memo_ids.h."""
    (work / "memo_ids.h").write_text(header, encoding="utf-8")
    exe = work / exe_name
    command = [ctrace.find_compiler(), "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic",
               "-I", str(ctrace.ENGINE), "-I", str(work)]
    command += [str(ctrace.ENGINE / name) for name in sources] + ["-o", str(exe)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return exe


@unittest.skipUnless(HAVE_CC, "no C compiler")
class FrameLoop(unittest.TestCase):
    def test_nonblocking_game_host_vm(self):
        p = mini([scene({"A": [{"op": "end"}]})])
        codes = compile_project(p)
        data, _ = build_dat(p, codes)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            exe = build_c(work, ("memo_vm.c", "game.c", "host.c", "screen.c", "portrait.c", "test/gfx_mock.c",
                                 "test/frame_main.c"), "frame_test.exe", ids_header(p, data, codes))
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(HAVE_CC, "no C compiler")
class ScreenModel(unittest.TestCase):
    """The dialog box against a software model of the video board."""

    def test_dialog_box(self):
        from PIL import Image

        p = mini([scene({"A": [{"op": "end"}]})])
        codes = compile_project(p)
        data, _ = build_dat(p, codes)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            exe = build_c(work, ("screen.c", "test/gfx_mock.c", "test/screen_main.c"), "screen_test.exe",
                          ids_header(p, data, codes))
            result = subprocess.run([str(exe), str(work)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("screen tests passed", result.stdout)
            with Image.open(work / "screen-dialog.ppm") as image:
                shot = image.convert("RGB")
            self.assertEqual(shot.size, (320, 240))
            top = shot.crop((0, 0, 320, 192))
            self.assertEqual(set(top.get_flattened_data()), {(0, 0, 0)})   # art area untouched
            box = shot.crop((0, 192, 320, 240))
            colours = set(box.get_flattened_data())
            self.assertGreaterEqual(len(colours), 3)                       # background, name, text
            self.assertEqual(shot.getpixel((0, 192)), shot.getpixel((319, 239)))


@unittest.skipUnless(HAVE_CC, "no C compiler")
class TitleScreen(unittest.TestCase):
    """The startup title picture against a software model of the video board."""

    def test_title_matches_the_gif(self):
        from PIL import Image

        p, data, header = full_game()
        gif = Path(p.cgs["CG-title"]["file"])
        gif = gif if gif.is_absolute() else Path(__file__).resolve().parents[2] / gif
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            exe = build_c(work, ("title.c", "memo_dat.c", "dat_io_stdio.c", "test/gfx_mock.c",
                                 "test/title_main.c"), "title_test.exe", header)
            (work / "memo.dat").write_bytes(data)
            result = subprocess.run([str(exe), str(work / "title.ppm")], capture_output=True, text=True,
                                    timeout=10, cwd=work)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("layer1 0", result.stdout)
            with Image.open(work / "title.ppm") as image:
                shot = image.convert("RGB")
        with Image.open(gif) as image:
            palette = image.getpalette()
            pixels = image.load()

            def rgb565(i):
                r, g, b = palette[i * 3:i * 3 + 3]
                return ((r >> 3) * 255 // 31, (g >> 2) * 255 // 63, (b >> 3) * 255 // 31)

            for y in range(192):
                for x in range(320):
                    self.assertEqual(shot.getpixel((x, y)), rgb565(pixels[x, y]), (x, y))
            below = {shot.getpixel((x, y)) for y in range(192, 240) for x in range(320)}
        self.assertEqual(len(below), 1)
        self.assertLess(sum(below.pop()), 24)                              # near black


@unittest.skipUnless(HAVE_CC and have_tool(), "no C compiler or SDK gif2zeal.py")
class PortraitDisplay(unittest.TestCase):
    """Streaming and showing portraits against the video model, using the real Brad and Jane."""

    ART = Path(__file__).resolve().parents[1] / "assets" / "portraits"

    @staticmethod
    def rgb565(palette, i):
        if i == 0:
            return (0, 0, 0)
        r, g, b = palette[i * 3:i * 3 + 3]
        return ((r >> 3) * 255 // 31, (g >> 2) * 255 // 63, (b >> 3) * 255 // 31)

    def expected(self, sheets, left, right):
        """The screen the board should show: (sheet name, expression) for each side, or None."""
        from PIL import Image

        shot = Image.new("RGB", (320, 240), (0, 0, 0))
        for x0, spec in ((0, left), (288, right)):
            if spec is None:
                continue
            palette, pixels = sheets[spec[0]]
            e = spec[1]
            for y in range(64):
                for x in range(32):
                    sy = 64 + 32 * (e - 1) + y if e and y < 32 else y
                    shot.putpixel((x0 + x, 128 + y), self.rgb565(palette, pixels[x, sy]))
        return shot

    def test_stream_and_show(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            for name in ("brad__B8C4F.gif", "jane__B8C7E.gif"):
                shutil.copy(self.ART / name, work / name)
            make_gif(work / "daniel__B8C7E.gif", 32, 160, 126,
                     lambda x, y: 0 if (x + y) % 7 == 0 else 79 + (x // 3 + y // 5) % 47)
            (work / "manifest.json").write_text(json.dumps({"portraits": {
                "brad": {"gif": "brad__B8C4F.gif"}, "jane": {"gif": "jane__B8C7E.gif"},
                "daniel": {"gif": "daniel__B8C7E.gif"}}}))
            p, data, header = full_game(work / "manifest.json", convert=True)
            ids = {c["name"]: i for i, c in enumerate(Dat(data).chars)}
            exe = build_c(work, ("memo_dat.c", "dat_io_stdio.c", "portrait.c", "test/gfx_mock.c",
                                 "test/portrait_main.c"), "portrait_test.exe", header)
            (work / "memo.dat").write_bytes(data)
            args = [str(exe), str(work / "memo.dat"), str(ids["Brad"]), str(ids["Jane"]), str(ids["Dad"]),
                    str(ids["Gord"]), str(work)]
            result = subprocess.run(args, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("portrait tests passed", result.stdout)
            sheets = {}
            for key, name in (("brad", "brad__B8C4F.gif"), ("jane", "jane__B8C7E.gif"),
                              ("daniel", "daniel__B8C7E.gif")):
                with Image.open(work / name) as image:
                    sheet = image.copy()
                sheets[key] = (sheet.getpalette(), sheet.load())
            cases = {"brad0": (("brad", 0), None), "brad5": (("brad", 5), None), "brad9": (("brad", 9), None),
                     "both": (("brad", 0), ("jane", 2)), "jane7": (("brad", 0), ("jane", 7)),
                     "daniel3": (("brad", 0), ("daniel", 3)), "jane0": (("brad", 0), ("jane", 0)),
                     "daniel3b": (("brad", 0), ("daniel", 3))}
            for name, (left, right) in cases.items():
                with Image.open(work / f"portrait-{name}.ppm") as image:
                    shot = image.convert("RGB")
                want = self.expected(sheets, left, right)
                self.assertEqual(shot.tobytes(), want.tobytes(), name)


@unittest.skipUnless(HAVE_CC, "no C compiler")
class CharsBlock(unittest.TestCase):
    def test_loader_matches_python_reader(self):
        p, data, header = full_game()
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            exe = build_c(work, ("memo_dat.c", "dat_io_stdio.c", "test/chars_main.c"), "chars_test.exe", header)
            (work / "memo.dat").write_bytes(data)
            result = subprocess.run([str(exe), str(work / "memo.dat")], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        expected = [f"{i} {c['side']} {c['exprs']} {c['name']}".rstrip() for i, c in enumerate(Dat(data).chars)]
        self.assertEqual([line.rstrip() for line in lines[:len(expected)]], expected)
        self.assertEqual(lines[len(expected):], ["past-end 0", "tiny 0", "no-capacity 0"])


if __name__ == "__main__":
    unittest.main()
