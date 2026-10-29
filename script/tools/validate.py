"""Validate script scene files against the common data files.

Usage: python validate.py [scene.json ...]
With no arguments every file in ../scenes is checked.

Checks: JSON parses, ops are known, speakers and expressions exist, variables
and clue bits are declared, blocks and map/spawn/trigger/CG ids resolve, text
fits the text box (3 lines of 36 characters), choices have 1-3 options and
unique ids. Prints a rough playtime estimate per scene.
"""
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOX_WIDTH = 36
BOX_LINES = 3
SECONDS_PER_BOX = 5
SECONDS_PER_MAP = 10

OPS = {
    "say", "map", "explore", "tutorial", "music", "sfx", "fade", "wait", "cg", "cg_off",
    "choice", "add", "sub", "set", "copy", "setbit", "if", "call", "goto", "end", "show", "hide", "walk", "pick_max",
}
CMPS = {"eq", "ne", "gte", "lt"}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Checker:
    def __init__(self):
        c = ROOT / "common"
        self.chars = load(c / "characters.json")
        self.vars = load(c / "variables.json")
        self.maps = load(c / "maps.json")
        self.cgs = load(c / "cgs.json")
        self.var_names = set(self.vars["counters"]) | set(self.vars["flags"]) | set(self.vars["bits"])
        self.bits = {b for group in self.vars["bits"].values() for b in group}
        self.errors = []
        self.warnings = set()
        self.boxes = 0
        self.maps_loaded = 0
        self.choice_ids = set()
        self.blocks = {}
        self.scene = ""

    def err(self, where, msg):
        self.errors.append(f"{self.scene}:{where}: {msg}")

    def check_text(self, where, text):
        lines = textwrap.wrap(text, BOX_WIDTH)
        if len(lines) > BOX_LINES:
            self.err(where, f"text needs {len(lines)} lines (max {BOX_LINES}): {text[:50]}...")

    def check_var(self, where, name):
        if name not in self.var_names:
            self.err(where, f"unknown variable {name}")

    def check_test(self, where, test):
        if "bit" in test:
            if test["bit"] not in self.bits:
                self.err(where, f"unknown clue bit {test['bit']}")
            return
        self.check_var(where, test.get("var"))
        if test.get("cmp") not in CMPS:
            self.err(where, f"bad cmp {test.get('cmp')}")

    def check_ops(self, where, ops):
        for i, op in enumerate(ops):
            self.check_op(f"{where}[{i}]", op)

    def check_op(self, where, op):
        name = op.get("op")
        if name not in OPS:
            self.err(where, f"unknown op {name}")
            return
        if name == "say":
            who = op.get("who")
            if who not in self.chars or who.startswith("_"):
                self.err(where, f"unknown speaker {who}")
            self.check_text(where, op.get("text", ""))
            self.boxes += 1
            expr = op.get("expr")
            if expr and who in self.chars:
                have = self.chars[who].get("have", [])
                todo = self.chars[who].get("todo", [])
                if expr not in have + todo:
                    self.err(where, f"{who} has no expression {expr}")
                elif expr in todo:
                    self.warnings.add(f"{who}:{expr} (art pending)")
        elif name == "map":
            m = self.maps.get(op.get("id"))
            if not m:
                self.err(where, f"unknown map {op.get('id')}")
            elif op.get("spawn") not in m["spawns"]:
                self.err(where, f"map {op['id']} has no spawn {op.get('spawn')}")
            self.maps_loaded += 1
        elif name == "explore":
            map_id = None
            self.check_explore(where, op)
        elif name == "cg":
            if op.get("id") not in self.cgs:
                self.err(where, f"unknown CG {op.get('id')}")
        elif name == "choice":
            cid = op.get("id")
            if cid in self.choice_ids:
                self.err(where, f"duplicate choice id {cid}")
            self.choice_ids.add(cid)
            opts = op.get("options", [])
            if not 1 <= len(opts) <= 3:
                self.err(where, f"choice has {len(opts)} options (1-3 allowed)")
            for j, opt in enumerate(opts):
                self.check_text(f"{where}.options[{j}]", opt.get("text", ""))
                self.check_ops(f"{where}.options[{j}]", opt.get("do", []))
        elif name in ("add", "sub", "set"):
            self.check_var(where, op.get("var"))
            if not isinstance(op.get("n"), int) or not 0 <= op["n"] <= 255:
                self.err(where, "n must be 0-255")
        elif name == "setbit":
            if op.get("bit") not in self.bits:
                self.err(where, f"unknown clue bit {op.get('bit')}")
        elif name == "copy":
            self.check_var(where, op.get("from"))
            self.check_var(where, op.get("to"))
        elif name == "pick_max":
            opts = op.get("options", [])
            if not opts:
                self.err(where, "pick_max needs options")
            for opt in opts:
                self.check_var(where, opt.get("var"))
                if opt.get("route") not in (1, 2, 3, 4):
                    self.err(where, "pick_max route must be 1-4")
        elif name == "if":
            self.check_test(where, op.get("test", {}))
            self.check_ops(f"{where}.then", op.get("then", []))
            self.check_ops(f"{where}.else", op.get("else", []))
        elif name in ("call", "goto"):
            if op.get("block") not in self.blocks:
                self.err(where, f"unknown block {op.get('block')}")

    def check_explore(self, where, op):
        clock = op.get("clock")
        if clock:
            self.check_var(where, clock.get("var"))
            self.check_ops(f"{where}.clock", clock.get("on_max", []))
        for j, trig in enumerate(op.get("triggers", [])):
            self.check_ops(f"{where}.triggers[{j}]", trig.get("do", []))

    def check_scene(self, path):
        data = load(path)
        self.scene = data.get("id", path.stem)
        self.blocks = data["blocks"]
        self.boxes = 0
        self.maps_loaded = 0
        self.choice_ids = set()
        if data.get("entry") not in self.blocks:
            self.err("entry", f"unknown entry block {data.get('entry')}")
        for name, ops in self.blocks.items():
            self.check_ops(name, ops)
        return data

    def estimate(self):
        seconds = self.boxes * SECONDS_PER_BOX + self.maps_loaded * SECONDS_PER_MAP
        return self.boxes, seconds / 60.0

    def path_seconds(self, entry):
        """Typical single playthrough: choices average their options, optional map
        triggers count half, and a clocked explore plays `max` of its stops."""
        seen = set()

        def block(name):
            if name in seen:
                return 0
            seen.add(name)
            total, _ = ops_time(self.blocks[name])
            seen.discard(name)
            return total

        def ops_time(ops):
            total = 0.0
            for op in ops:
                kind = op["op"]
                if kind == "say":
                    total += SECONDS_PER_BOX
                elif kind == "map":
                    total += SECONDS_PER_MAP
                elif kind == "tutorial":
                    total += SECONDS_PER_BOX
                elif kind == "choice":
                    opts = [ops_time(o.get("do", []))[0] for o in op["options"]]
                    total += SECONDS_PER_BOX + sum(opts) / len(opts)
                elif kind == "if":
                    then_t = ops_time(op.get("then", []))[0]
                    else_t = ops_time(op.get("else", []))[0]
                    total += max(then_t, else_t)
                elif kind == "call":
                    total += block(op["block"])
                elif kind == "goto":
                    return total + block(op["block"]), True
                elif kind == "end":
                    return total, True
                elif kind == "explore":
                    walk = 40
                    trigs = op.get("triggers", [])
                    clock = op.get("clock")
                    if clock:
                        stops = [ops_time(t["do"])[0] for t in trigs if any(o["op"] == "call" for o in t["do"])]
                        avg = sum(stops) / len(stops)
                        on_max, jumped = ops_time(clock["on_max"])
                        return total + walk + avg * clock["max"] + on_max, True
                    for t in trigs:
                        t_time, jumped = ops_time(t["do"])
                        if jumped:
                            return total + walk + t_time, True
                        total += 0.5 * t_time
                    total += walk
            return total, False

        return block(entry)


def main():
    paths = [Path(p) for p in sys.argv[1:]] or sorted((ROOT / "scenes").glob("*.json"))
    checker = Checker()
    for path in paths:
        data = checker.check_scene(path)
        boxes, _ = checker.estimate()
        minutes = checker.path_seconds(data["entry"]) / 60.0
        print(f"{path.name}: {data['title']}: {boxes} text boxes in all branches, ~{minutes:.1f} min on a typical path")
    if checker.warnings:
        print("\nArt pending (allowed):")
        for w in sorted(checker.warnings):
            print(f"  {w}")
    if checker.errors:
        print("\nERRORS:")
        for e in checker.errors:
            print(f"  {e}")
        sys.exit(1)
    print("\nOK")


if __name__ == "__main__":
    main()
