"""Tests for the C engine (engine/): loader, VM, fault handling, and the Zeal (Z80) build.

They need a C compiler (gcc, clang or CC); the Z80 test needs sdcc and the Zeal-8-bit-OS headers."""
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
            make_gif(d / "jane__B8C20.gif", 32, 304, 32, lambda x, y: (x + y) % 32)
            (d / "manifest.json").write_text(
                '{"cgs": {"CG-01": {"gif": "cg01__B8C20.gif"}}, "portraits": {"jane": {"gif": "jane__B8C20.gif"}}}')
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
            for name in ("memo_dat", "memo_vm", "dat_io_zos"):
                src = ctrace.ENGINE / f"{name}.c"
                r = subprocess.run(["sdcc", "-mz80", "--std-c2x", "-c", "-I", str(ctrace.ENGINE), "-I", str(d),
                                    "-I", str(self.ZOS), "--codeseg", "TEXT", "-o", str(d / f"{name}.rel"), str(src)],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f"{name}: {r.stderr}")
                self.assertNotIn("warning", r.stderr, f"{name}: {r.stderr}")


if __name__ == "__main__":
    unittest.main()
