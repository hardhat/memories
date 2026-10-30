"""Checks and lints for the script (compiler-spec.md section 7).

check_project() returns a list of Diag(level, where, msg) with level 'error',
'warn' or 'info'. Errors stop a build; warnings stop it only with --strict.
"""
from collections import namedtuple

from .flow import collect, falls, has_op, walk_ops
from .project import wrap
from .spec import CMP, FADE_MODE

Diag = namedtuple("Diag", "level where msg")

KNOWN_OPS = {
    "say", "map", "explore", "tutorial", "music", "sfx", "fade", "wait", "cg", "cg_off",
    "choice", "add", "sub", "set", "copy", "setbit", "if", "call", "goto", "end", "pick_max",
}
RESERVED_OPS = {"show", "hide", "walk"}


def printable(text):
    return all(0x20 <= ord(c) <= 0x7E for c in text)


class Checker:
    def __init__(self, project):
        self.p = project
        self.cfg = project.config
        self.diags = []
        self.art_pending = set()
        self.used_exprs = set()
        self.used_cgs = set()
        self.used_music = set()
        self.used_sfx = set()
        self.var_reads = {}
        self.var_writes = {}
        self.scene = ""
        self.blocks = {}
        self.choice_ids = set()

    # ---- reporting -------------------------------------------------------
    def add(self, level, where, msg):
        self.diags.append(Diag(level, f"{self.scene}:{where}" if self.scene else where, msg))

    def error(self, where, msg):
        self.add("error", where, msg)

    def warn(self, where, msg):
        self.add("warn", where, msg)

    def info(self, where, msg):
        self.add("info", where, msg)

    # ---- helpers ---------------------------------------------------------
    def read(self, name):
        self.var_reads[name] = self.var_reads.get(name, 0) + 1

    def write(self, name):
        self.var_writes[name] = self.var_writes.get(name, 0) + 1

    def check_var(self, where, name):
        if name not in self.p.var_index:
            self.error(where, f"unknown variable {name}")
            return False
        return True

    def check_text(self, where, text, max_lines, what="text"):
        if not isinstance(text, str):
            self.error(where, f"{what} must be a string")
            return 0
        if not printable(text):
            bad = sorted({c for c in text if not 0x20 <= ord(c) <= 0x7E})
            self.error(where, f"{what} has characters outside printable ASCII: {bad!r}")
        cols = self.cfg["text"]["cols"]
        wrapped = wrap(text, cols)
        lines = wrapped.count("\n") + 1 if wrapped else 0
        if lines > max_lines:
            self.error(where, f"{what} needs {lines} lines (max {max_lines}): {text[:50]}...")
        if len(wrapped) > self.cfg["text"]["max_len"]:
            self.error(where, f"{what} is {len(wrapped)} characters (max {self.cfg['text']['max_len']})")
        return lines

    def check_test(self, where, test):
        if "bit" in test:
            if test["bit"] not in self.p.bit_index:
                self.error(where, f"unknown clue bit {test['bit']}")
            else:
                self.read(self.p.clue_var)
            return
        if self.check_var(where, test.get("var")):
            self.read(test["var"])
        if test.get("cmp") not in CMP:
            self.error(where, f"bad cmp {test.get('cmp')}")
        if not isinstance(test.get("n"), int) or not 0 <= test["n"] <= 255:
            self.error(where, "test n must be 0-255")

    # ---- per op ----------------------------------------------------------
    def check_op(self, op, where):
        p, cfg = self.p, self.cfg
        k = op.get("op")
        if k in RESERVED_OPS:
            self.error(where, f"op {k} is reserved and not implemented")
            return
        if k not in KNOWN_OPS:
            self.error(where, f"unknown op {k}")
            return
        if k == "say":
            who = op.get("who")
            if who not in p.char_index:
                self.error(where, f"unknown speaker {who}")
            self.check_text(where, op.get("text", ""), cfg["text"]["lines"])
            expr = op.get("expr")
            if expr and who in p.char_index:
                exprs = p.char_exprs[who]
                if expr not in exprs:
                    self.error(where, f"{who} has no expression {expr}")
                else:
                    self.used_exprs.add((who, expr))
                    if expr in p.chars_raw[who].get("todo", []):
                        self.art_pending.add(f"{who}:{expr}")
            if op.get("style") not in (None, "phone", "credits"):
                self.error(where, f"unknown style {op.get('style')}")
        elif k == "tutorial":
            self.check_text(where, op.get("text", ""), cfg["text"]["lines"], "tutorial text")
            if not op.get("id"):
                self.error(where, "tutorial needs an id")
        elif k == "map":
            m = p.maps.get(op.get("id"))
            if not m:
                self.error(where, f"unknown map {op.get('id')}")
            elif op.get("spawn") not in m.get("spawns", []):
                self.error(where, f"map {op['id']} has no spawn {op.get('spawn')}")
            if op.get("time") not in p.time_index:
                self.error(where, f"unknown time of day {op.get('time')}")
        elif k == "fade":
            if op.get("to") not in FADE_MODE:
                self.error(where, f"fade 'to' must be one of {sorted(FADE_MODE)}")
            ms = op.get("ms", 500)
            if not isinstance(ms, int) or ms < 0 or ms > 2550:
                self.error(where, "fade ms must be 0-2550")
            elif ms % 10:
                self.warn(where, f"fade ms {ms} is not a multiple of 10; it will be rounded")
        elif k in ("music", "sfx"):
            registry = p.music_index if k == "music" else p.sfx_index
            (self.used_music if k == "music" else self.used_sfx).add(op.get("id"))
            if op.get("id") not in registry:
                self.error(where, f"{k} {op.get('id')} is not in audio.json")
        elif k == "cg":
            self.used_cgs.add(op.get("id"))
            if op.get("id") not in p.cg_index:
                self.error(where, f"unknown CG {op.get('id')}")
        elif k == "wait":
            if not isinstance(op.get("ticks", 1), int) or not 0 <= op.get("ticks", 1) <= 255:
                self.error(where, "wait ticks must be 0-255")
        elif k == "choice":
            self.check_choice(op, where)
        elif k in ("add", "sub", "set"):
            if self.check_var(where, op.get("var")):
                self.write(op["var"])
            if not isinstance(op.get("n"), int) or not 0 <= op["n"] <= 255:
                self.error(where, "n must be 0-255")
        elif k == "setbit":
            if op.get("bit") not in p.bit_index:
                self.error(where, f"unknown clue bit {op.get('bit')}")
            elif p.clue_var:
                self.write(p.clue_var)
        elif k == "copy":
            if self.check_var(where, op.get("from")):
                self.read(op["from"])
            if self.check_var(where, op.get("to")):
                self.write(op["to"])
        elif k == "pick_max":
            opts = op.get("options", [])
            if not opts:
                self.error(where, "pick_max needs options")
            for opt in opts:
                if self.check_var(where, opt.get("var")):
                    self.read(opt["var"])
                if not isinstance(opt.get("route"), int) or not 0 <= opt["route"] <= 255:
                    self.error(where, "pick_max route must be 0-255")
            if "route" in p.var_index:
                self.write("route")
            else:
                self.error(where, "pick_max writes the 'route' variable, which is not declared")
        elif k == "if":
            self.check_test(where, op.get("test", {}))
        elif k in ("call", "goto"):
            if op.get("block") not in self.blocks:
                self.error(where, f"unknown block {op.get('block')}")
        elif k == "explore":
            self.check_explore(op, where)

    def check_choice(self, op, where):
        cfg = self.cfg
        cid = op.get("id")
        if not cid:
            self.error(where, "choice needs an id")
        elif cid in self.choice_ids:
            self.error(where, f"duplicate choice id {cid}")
        self.choice_ids.add(cid)
        opts = op.get("options", [])
        if not 1 <= len(opts) <= cfg["choice"]["options_max"]:
            self.error(where, f"choice has {len(opts)} options (1-{cfg['choice']['options_max']} allowed)")
        total = self.check_text(where, op.get("prompt", ""), cfg["choice"]["lines_max"], "choice prompt")
        for j, o in enumerate(opts):
            total += self.check_text(f"{where}.options[{j}]", o.get("text", ""),
                                     cfg["choice"]["lines_max"], "option text")
        if total > cfg["choice"]["lines_max"]:
            self.warn(where, f"choice uses {total} lines (menu budget {cfg['choice']['lines_max']})")

    def check_explore(self, op, where):
        p, cfg = self.p, self.cfg
        trig = op.get("triggers", [])
        if not trig:
            self.error(where, "explore needs triggers")
        if len(trig) > cfg["limits"]["explore_triggers"]:
            self.error(where, f"explore has {len(trig)} triggers (max {cfg['limits']['explore_triggers']})")
        for j, t in enumerate(trig):
            if t.get("at") not in p.trigger_index:
                self.error(f"{where}.triggers[{j}]", f"trigger {t.get('at')} is not on any map in maps.json")
        clock = op.get("clock")
        if clock:
            if self.check_var(where, clock.get("var")):
                self.read(clock["var"])
            if not isinstance(clock.get("max"), int) or not 1 <= clock["max"] <= 255:
                self.error(where, "clock max must be 1-255")

    # ---- per scene -------------------------------------------------------
    def check_scene(self, index, scene):
        p = self.p
        self.scene = scene.get("id", f"s{index + 1:02d}")
        self.blocks = scene.get("blocks", {})
        self.choice_ids = set()
        if scene.get("entry") not in self.blocks:
            self.error("entry", f"unknown entry block {scene.get('entry')}")
            return
        expected = f"s{index + 1:02d}"
        if self.scene != expected:
            self.info("id", f"scene id {self.scene} differs from its position ({expected})")
        for name, ops in self.blocks.items():
            walk_ops(ops, lambda op, w, name=name: self.check_op(op, f"{name}{w}"))
        self.check_flow(scene)

    def check_flow(self, scene):
        blocks = self.blocks
        limits = self.cfg["limits"]
        entry = scene["entry"]
        calls = {n: set(collect(ops, "call")) & set(blocks) for n, ops in blocks.items()}
        gotos = {n: set(collect(ops, "goto")) & set(blocks) for n, ops in blocks.items()}

        # Blocks that are entered by goto (or as the entry) must not fall off the end.
        entered = {entry}
        for g in gotos.values():
            entered |= g
        for name in sorted(entered):
            if falls(blocks[name]):
                self.error(name, "block is entered by goto (or is the entry) but can fall off its end")

        # Call graph: recursion, depth, goto inside called blocks.
        depth_cache, visiting = {}, []

        def depth(n):
            if n in depth_cache:
                return depth_cache[n]
            if n in visiting:
                self.error(n, "call recursion: " + " -> ".join(visiting[visiting.index(n):] + [n]))
                return 0
            visiting.append(n)
            d = max([1 + depth(c) for c in calls[n]] + [0])
            visiting.pop()
            depth_cache[n] = d
            return d

        worst = max((depth(n) for n in blocks), default=0)
        if worst > limits["call_depth"]:
            self.error("calls", f"call depth {worst} exceeds {limits['call_depth']}")
        called = set()
        stack = [c for cs in calls.values() for c in cs]
        while stack:
            n = stack.pop()
            if n in called:
                continue
            called.add(n)
            stack.extend(calls[n])
        for n in sorted(called):
            if gotos[n]:
                self.error(n, "goto inside a block that is reached by call")

        # Reachability.
        seen, stack = set(), [entry]
        while stack:
            n = stack.pop()
            if n in seen or n not in blocks:
                continue
            seen.add(n)
            stack.extend(calls[n] | gotos[n])
        for n in sorted(set(blocks) - seen):
            self.warn(n, "block is unreachable")

        # Explore rules.
        for name, ops in blocks.items():
            walk_ops(ops, lambda op, w, name=name: self.check_explore_flow(op, f"{name}{w}", blocks, calls))

    def reaches_explore(self, ops, blocks, seen=None):
        seen = seen or set()
        if has_op(ops, "explore"):
            return True
        for c in collect(ops, "call"):
            if c in blocks and c not in seen:
                seen.add(c)
                if self.reaches_explore(blocks[c], blocks, seen):
                    return True
        return False

    def writes_var(self, ops, var, blocks, seen=None):
        seen = seen or set()
        found = []
        walk_ops(ops, lambda op, w: found.append(op) if op["op"] in ("add", "set") and op.get("var") == var else None)
        if found:
            return True
        for c in collect(ops, "call"):
            if c in blocks and c not in seen:
                seen.add(c)
                if self.writes_var(blocks[c], var, blocks, seen):
                    return True
        return False

    def check_explore_flow(self, op, where, blocks, calls):
        if op["op"] != "explore":
            return
        bodies = [t.get("do", []) for t in op.get("triggers", [])]
        clock = op.get("clock")
        if clock:
            bodies_all = bodies + [clock.get("on_max", [])]
        else:
            bodies_all = bodies
        # No nested explore, directly or through calls.
        for b in bodies_all:
            if self.reaches_explore(b, blocks):
                self.error(where, "explore inside trigger code (directly or through call) is not supported")
                break
        if not clock:
            if not any(has_op(b, "goto") or has_op(b, "end") for b in bodies):
                self.error(where, "explore has no clock and no trigger that reaches goto or end (no way out)")
        else:
            if not any(self.writes_var(b, clock.get("var"), blocks) for b in bodies):
                self.warn(where, f"no trigger changes clock variable {clock.get('var')}; the clock never fires")

    # ---- whole project ---------------------------------------------------
    def check_project(self):
        p = self.p
        self.scene = ""
        if len(p.scenes) > 16:
            self.error("scenes", "more than 16 scenes")
        for name, exprs in p.char_exprs.items():
            if len(exprs) > 31:
                self.error(f"characters:{name}", "more than 31 expressions")
        for name, c in p.chars_raw.items():
            if len(c.get("name", "")) > self.cfg["name_max"]:
                self.error(f"characters:{name}", f"name longer than {self.cfg['name_max']} characters")
            if not printable(c.get("name", "")):
                self.error(f"characters:{name}", "name is not printable ASCII")
        if len(p.var_names) > 64:
            self.error("variables", "more than 64 variables")
        if len(p.trigger_names) > 255:
            self.error("maps", "more than 255 trigger names")
        for i, scene in enumerate(p.scenes):
            self.check_scene(i, scene)
        self.scene = ""

        # Cross-scene hygiene.
        flags = set(p.flag_names)
        silent = sorted(f for f in flags if self.var_writes.get(f) and not self.var_reads.get(f))
        if silent:
            self.info("variables", f"{len(silent)} flags are written but never read: {', '.join(silent)}")
        unset = sorted(f for f in flags if self.var_reads.get(f) and not self.var_writes.get(f))
        for f in unset:
            self.warn("variables", f"flag {f} is read but never written")
        counters = [c for c in p.counter_names if not self.var_reads.get(c) and not self.var_writes.get(c)]
        if counters:
            self.info("variables", f"unused counters: {', '.join(counters)}")
        if self.art_pending:
            self.info("art", f"{len(self.art_pending)} expressions still pending art: "
                             + ", ".join(sorted(self.art_pending)))
        unused_cg = [c for c in p.cg_names if c not in self.used_cgs]
        if unused_cg:
            self.info("art", f"CGs not shown by any script: {', '.join(unused_cg)}")
        unused_music = [m for m in p.music if m not in self.used_music]
        unused_sfx = [s for s in p.sfx if s not in self.used_sfx]
        if unused_music or unused_sfx:
            self.info("audio", f"unused registry entries: {', '.join(unused_music + unused_sfx)}")
        return self.diags


def check_project(project):
    return Checker(project).check_project()
