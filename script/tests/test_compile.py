"""Golden tests for the memo compiler. Run: python -m unittest discover script/tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from memo.check import check_project  # noqa: E402
from memo.compile import compile_scene, compile_project  # noqa: E402
from memo.datread import Dat  # noqa: E402
from memo.pack import build_dat  # noqa: E402
from memo.project import Project  # noqa: E402
from memo.trace import compare  # noqa: E402


def mini(scenes):
    """Tiny project with known ids: chars narrator 0, jane 1 (expressions smile 0, serious 1);
    vars aff 0, stops 1, scene 2, route 3, F_X 4, clues 5; map M01 spawns a,b triggers t1,t2."""
    chars = {"narrator": {"name": "", "portrait": False},
             "jane": {"name": "Jane", "side": "right", "have": ["smile", "serious"], "todo": []}}
    variables = {"counters": {"aff": {"max": 30}, "stops": {"max": 3}, "scene": {"max": 10}, "route": {"max": 4}},
                 "flags": {"F_X": ""}, "bits": {"clues": {"CL1": "", "CL2": ""}}}
    maps = {"M01": {"name": "m", "spawns": ["a", "b"], "triggers": ["t1", "t2"]}}
    audio = {"music": {"m": {}}, "sfx": {"s": {}}}
    return Project(chars, variables, maps, {"CG-01": {}}, scenes, audio=audio)


def scene(blocks, entry="A", sid="s01"):
    return {"id": sid, "title": "t", "entry": entry, "blocks": blocks}


def code_of(blocks, entry="A"):
    p = mini([scene(blocks, entry)])
    return compile_scene(p, p.scenes[0])


def hx(s):
    return bytes.fromhex(s.replace("|", " "))


class Lowering(unittest.TestCase):
    def test_if_else(self):
        sc = code_of({"A": [{"op": "if", "test": {"var": "aff", "cmp": "gte", "n": 6},
                             "then": [{"op": "say", "who": "jane", "expr": "smile", "text": "Yes."}],
                             "else": [{"op": "say", "who": "jane", "expr": "serious", "text": "No."}]}]})
        self.assertEqual(sc.code, hx("21 02 00 06 0E 00 | 01 01 00 00 00 | 20 13 00 | 01 01 01 01 00 | 24"))
        self.assertEqual(sc.strings.items, ["Yes.", "No."])

    def test_if_without_else_and_bit(self):
        sc = code_of({"A": [{"op": "if", "test": {"bit": "CL2"}, "then": [{"op": "add", "var": "aff", "n": 1}]}]})
        self.assertEqual(sc.code, hx("22 01 07 00 | 11 00 01 | 24"))

    def test_choice(self):
        sc = code_of({"A": [{"op": "choice", "id": "c", "prompt": "Pick.", "options": [
            {"text": "Yes", "do": [{"op": "add", "var": "aff", "n": 1}]},
            {"text": "No", "do": []}]}]})
        self.assertEqual(sc.code, hx("30 00 00 02 | 01 00 0C 00 | 02 00 12 00 | 11 00 01 | 20 15 00 | 20 15 00 | 24"))
        self.assertEqual(sc.choices["c"], 0)

    def test_explore_with_clock(self):
        sc = code_of({
            "A": [{"op": "explore", "objective": "t1", "clock": {"var": "stops", "max": 2, "on_max": [{"op": "end"}]},
                   "triggers": [{"at": "t1", "once": True, "do": [{"op": "add", "var": "stops", "n": 1}]},
                                {"at": "t2", "do": [{"op": "goto", "block": "B"}]}]}],
            "B": [{"op": "end"}]})
        self.assertEqual(sc.code, hx("31 00 01 02 02 18 00 19 00 | 00 01 11 00 | 01 00 15 00 | "
                                      "11 01 01 | 32 | 25 19 00 | 00 | 00"))

    def test_clock_body_that_falls_uses_xexit(self):
        sc = code_of({"A": [{"op": "explore", "clock": {"var": "stops", "max": 1, "on_max": []},
                             "triggers": [{"at": "t1", "do": [{"op": "add", "var": "stops", "n": 1}]}]}]})
        self.assertEqual(sc.code, hx("31 ff 01 01 01 11 00 12 00 | 00 00 0D 00 | 11 01 01 | 32 | 33 | 24"))

    def test_call_goto_ret(self):
        sc = code_of({"A": [{"op": "call", "block": "B"}, {"op": "goto", "block": "C"}],
                      "B": [{"op": "say", "who": "narrator", "text": "x"}],
                      "C": [{"op": "end"}]})
        self.assertEqual(sc.code, hx("23 06 00 25 0C 00 | 01 00 1F 00 00 | 24 | 00"))
        self.assertEqual(sc.entry_pc, 0)
        self.assertEqual(sc.labels, {"A": 0, "B": 6, "C": 12})

    def test_simple_ops(self):
        sc = code_of({"A": [
            {"op": "map", "id": "M01", "spawn": "b", "time": "dusk"},
            {"op": "fade", "to": "black", "ms": 600},
            {"op": "fade", "to": "clear"},
            {"op": "music", "id": "m"}, {"op": "sfx", "id": "s"}, {"op": "cg", "id": "CG-01"}, {"op": "cg_off"},
            {"op": "set", "var": "route", "n": 2}, {"op": "sub", "var": "aff", "n": 1},
            {"op": "copy", "from": "aff", "to": "stops"}, {"op": "setbit", "bit": "CL2"},
            {"op": "pick_max", "options": [{"var": "aff", "route": 1}, {"var": "stops", "route": 2}]},
            {"op": "tutorial", "id": "tip", "text": "Hi."},
            {"op": "end"}]})
        self.assertEqual(sc.code, hx("02 00 01 06 | 03 01 3C | 03 00 32 | 04 00 | 05 00 | 06 00 | 07 | "
                                      "10 03 02 | 12 00 01 | 13 01 00 | 14 01 | 15 03 02 00 01 01 02 | 08 00 00 00 | 00"))

    def test_say_style_and_expression_bits(self):
        sc = code_of({"A": [{"op": "say", "who": "jane", "expr": "serious", "style": "phone", "text": "ring"},
                            {"op": "end"}]})
        self.assertEqual(sc.code[:5], hx("01 01 21 00 00"))  # expr 1 | phone(1) << 5

    def test_strings_are_wrapped_and_deduplicated(self):
        text = "The quick brown fox jumps over the lazy dog again and again."
        sc = code_of({"A": [{"op": "say", "who": "narrator", "text": text},
                            {"op": "say", "who": "narrator", "text": text}, {"op": "end"}]})
        self.assertEqual(len(sc.strings.items), 1)
        self.assertEqual(sc.strings.items[0], "The quick brown fox jumps over the\nlazy dog again and again.")


class Container(unittest.TestCase):
    def setUp(self):
        self.p = mini([scene({"A": [{"op": "say", "who": "jane", "expr": "smile", "text": "Hello."},
                                    {"op": "set", "var": "scene", "n": 1}, {"op": "end"}]})])
        self.codes = compile_project(self.p)
        self.data, self.layout = build_dat(self.p, self.codes)

    def test_header_and_tables_round_trip(self):
        dat = Dat(self.data)
        self.assertEqual(dat.scene_count, 1)
        entry, code = dat.scene_code(1)
        self.assertEqual((entry, code), (self.codes[0].entry_pc, self.codes[0].code))
        self.assertEqual(dat.strings(1), ["Hello."])
        self.assertEqual(dat.var_max, [30, 3, 10, 4, 1, 255])
        self.assertEqual([c["name"] for c in dat.chars], ["", "Jane"])
        self.assertEqual(dat.chars[1]["side"], 2)
        self.assertEqual(dat.chars[1]["exprs"], 2)

    def test_build_is_deterministic(self):
        again, _ = build_dat(self.p, compile_project(self.p))
        self.assertEqual(again, self.data)

    def test_corruption_is_detected(self):
        bad = bytearray(self.data)
        bad[-1] ^= 0xFF
        with self.assertRaises(Exception):
            Dat(bytes(bad))


class Checks(unittest.TestCase):
    def errors(self, blocks, entry="A"):
        return [d.msg for d in check_project(mini([scene(blocks, entry)])) if d.level == "error"]

    def test_clean_scene_passes(self):
        self.assertEqual(self.errors({"A": [{"op": "end"}]}), [])

    def test_entry_that_falls_off_is_an_error(self):
        self.assertTrue(any("fall off" in m for m in self.errors({"A": [{"op": "add", "var": "aff", "n": 1}]})))

    def test_goto_inside_called_block(self):
        errs = self.errors({"A": [{"op": "call", "block": "B"}, {"op": "end"}],
                            "B": [{"op": "goto", "block": "C"}], "C": [{"op": "end"}]})
        self.assertTrue(any("goto inside a block that is reached by call" in m for m in errs))

    def test_call_recursion(self):
        errs = self.errors({"A": [{"op": "call", "block": "A"}, {"op": "end"}]})
        self.assertTrue(any("recursion" in m for m in errs))

    def test_explore_without_exit(self):
        errs = self.errors({"A": [{"op": "explore", "triggers": [{"at": "t1", "do": []}]}]})
        self.assertTrue(any("no way out" in m for m in errs))

    def test_nested_explore(self):
        inner = {"op": "explore", "triggers": [{"at": "t1", "do": [{"op": "end"}]}]}
        errs = self.errors({"A": [{"op": "explore", "triggers": [{"at": "t1", "do": [inner, {"op": "end"}]}]}]})
        self.assertTrue(any("not supported" in m for m in errs))

    def test_unknown_things(self):
        errs = self.errors({"A": [{"op": "add", "var": "nope", "n": 1},
                                  {"op": "say", "who": "jane", "expr": "angry", "text": "x"},
                                  {"op": "map", "id": "M01", "spawn": "zzz", "time": "morning"},
                                  {"op": "music", "id": "unlisted"}, {"op": "end"}]})
        joined = " ".join(errs)
        for word in ("unknown variable nope", "no expression angry", "no spawn zzz", "not in audio.json"):
            self.assertIn(word, joined)

    def test_text_rules(self):
        errs = self.errors({"A": [{"op": "say", "who": "narrator", "text": "caf\u00e9"},
                                  {"op": "say", "who": "narrator", "text": "word " * 40}, {"op": "end"}]})
        joined = " ".join(errs)
        self.assertIn("printable ASCII", joined)
        self.assertIn("lines", joined)


class Equivalence(unittest.TestCase):
    """The JSON interpreter and the compiled VM must produce identical traces."""

    def project(self):
        s1 = scene({
            "A": [{"op": "set", "var": "scene", "n": 1},
                  {"op": "map", "id": "M01", "spawn": "a", "time": "morning"},
                  {"op": "say", "who": "jane", "expr": "smile", "text": "Hello there."},
                  {"op": "pick_max", "options": [{"var": "aff", "route": 1}, {"var": "stops", "route": 2}]},
                  {"op": "explore", "objective": "t1",
                   "clock": {"var": "stops", "max": 2, "on_max": [{"op": "goto", "block": "B"}]},
                   "triggers": [{"at": "t1", "once": True, "do": [{"op": "add", "var": "stops", "n": 1}]},
                                {"at": "t2", "do": [{"op": "call", "block": "C"}]}]}],
            "B": [{"op": "choice", "id": "c1", "prompt": "Which?", "options": [
                    {"text": "One", "do": [{"op": "add", "var": "aff", "n": 5}]},
                    {"text": "Two", "do": [{"op": "setbit", "bit": "CL1"}]},
                    {"text": "Three", "do": [{"op": "if", "test": {"bit": "CL2"},
                                              "then": [{"op": "set", "var": "F_X", "n": 1}],
                                              "else": [{"op": "sub", "var": "aff", "n": 3}]}]}]},
                  {"op": "set", "var": "scene", "n": 2}, {"op": "end"}],
            "C": [{"op": "add", "var": "stops", "n": 1}, {"op": "say", "who": "narrator", "text": "Called."}]})
        s2 = scene({"A": [{"op": "set", "var": "scene", "n": 2},
                          {"op": "if", "test": {"var": "aff", "cmp": "gte", "n": 1},
                           "then": [{"op": "say", "who": "jane", "expr": "serious", "text": "Many."}],
                           "else": [{"op": "say", "who": "jane", "expr": "smile", "text": "Few."}]},
                          {"op": "end"}]}, sid="s02")
        return mini([s1, s2])

    def test_traces_agree(self):
        p = self.project()
        self.assertEqual([d.msg for d in check_project(p) if d.level == "error"], [])
        data, _ = build_dat(p, compile_project(p))
        result = compare(p, data, range(60), ("uniform", "first"), invariants=False)
        self.assertTrue(result["ok"], result.get("error"))
        self.assertGreater(result["events"], 100)
        self.assertEqual(result["say_hit"], result["say_total"])


if __name__ == "__main__":
    unittest.main()
