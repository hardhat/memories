"""Two interpreters that must agree: the JSON reference interpreter (sim) and the bytecode VM.

Both consume the same Env (seeded random choices) and emit the same event trace, so any
difference between them is a compiler or VM bug (compiler-spec.md section 9.2)."""
import random

from .disasm import decode
from .flow import falls
from .project import wrap
from .spec import (CALL_DEPTH_MAX, CMP, DEFAULT_FADE_MS, EXPR_NONE, FADE_MODE, NO_TRIGGER, NO_VAR, STYLE)


class RunError(Exception):
    pass


EXPLORE_ROUNDS_MAX = 500  # trigger activations per explore before we call it a stuck play


class Env:
    """Seeded decisions: menu choices and which explore trigger the 'player' uses.

    Policies: 'uniform' (seeded random) and 'first' (always the first option or trigger).
    There is deliberately no 'last': a player who only ever picks the last trigger of an
    explore can loop forever in real play too (for example Scene 1's walk-on exit)."""

    def __init__(self, seed=0, policy="uniform"):
        self.rnd = random.Random(seed)
        self.policy = policy

    def choose(self, n):
        if self.policy == "first":
            return 0
        return self.rnd.randrange(n)

    def pick(self, n):
        if self.policy == "first":
            return 0
        return self.rnd.randrange(n)


class State:
    """Variable array with the clamping rules of the engine (ADD clamps to max, SUB floors at 0)."""

    def __init__(self, p_or_dat):
        if hasattr(p_or_dat, "var_max"):
            self.max = list(p_or_dat.var_max)
            self.v = list(getattr(p_or_dat, "var_init", [0] * len(self.max)))
        self.trace = []

    def write(self, idx, value):
        self.v[idx] = value
        self.trace.append(("var", idx, value))

    def add(self, idx, n):
        self.write(idx, min(self.max[idx], self.v[idx] + n))

    def sub(self, idx, n):
        self.write(idx, max(0, self.v[idx] - n))


def run_game(run_scene, state, scene_var, scene_count):
    """Scene loop shared by both interpreters: scripts set the `scene` variable before they end."""
    n = 1
    while True:
        run_scene(n)
        nxt = state.v[scene_var]
        if nxt <= n or nxt > scene_count:
            return
        n = nxt


# ---------------------------------------------------------------------------
# JSON reference interpreter
# ---------------------------------------------------------------------------

class _Goto(Exception):
    def __init__(self, block):
        self.block = block


class _End(Exception):
    pass


class Sim:
    def __init__(self, project, env):
        self.p = project
        self.env = env
        self.s = State(project)
        self.s.v = [0] * len(project.var_names)
        self.s.max = list(project.var_max)
        self.depth = 0

    def run(self):
        run_game(self.run_scene, self.s, self.p.var_index["scene"], len(self.p.scenes))
        return self.s.trace, self.s.v

    def run_scene(self, n):
        scene = self.p.scenes[n - 1]
        self.blocks = scene["blocks"]
        self.scene_id = scene["id"]
        name = scene["entry"]
        while True:
            try:
                self.ops(self.blocks[name])
                raise RunError(f"{self.scene_id}: block {name} fell off its end")
            except _Goto as g:
                name = g.block
                self.depth = 0
            except _End:
                self.s.trace.append(("end",))
                return

    def test(self, t):
        if "bit" in t:
            return bool(self.s.v[self.p.var_index[self.p.clue_var]] >> self.p.bit_index[t["bit"]] & 1)
        a, n, c = self.s.v[self.p.var_index[t["var"]]], t["n"], CMP[t["cmp"]]
        return [a == n, a != n, a >= n, a < n][c]

    def ops(self, ops):
        p, s, tr = self.p, self.s, self.s.trace
        for op in ops:
            k = op["op"]
            if k == "say":
                who = op["who"]
                e = EXPR_NONE if not op.get("expr") else p.char_exprs[who].index(op["expr"])
                tr.append(("say", p.char_index[who], e, STYLE[op.get("style")], wrap(op["text"], p.config["text"]["cols"])))
            elif k == "map":
                tr.append(("map", p.map_index[op["id"]], p.maps[op["id"]]["spawns"].index(op["spawn"]), p.time_index[op["time"]]))
            elif k == "fade":
                tr.append(("fade", FADE_MODE[op["to"]], round(op.get("ms", DEFAULT_FADE_MS) / 10)))
            elif k == "music":
                tr.append(("music", p.music_index[op["id"]]))
            elif k == "sfx":
                tr.append(("sfx", p.sfx_index[op["id"]]))
            elif k == "cg":
                tr.append(("cg", p.cg_index[op["id"]]))
            elif k == "cg_off":
                tr.append(("cg_off",))
            elif k == "tutorial":
                tr.append(("tutorial", p.tutorial_index[op["id"]], wrap(op["text"], p.config["text"]["cols"])))
            elif k == "wait":
                tr.append(("wait", op.get("ticks", 1)))
            elif k == "set":
                s.write(p.var_index[op["var"]], op["n"])
            elif k == "add":
                s.add(p.var_index[op["var"]], op["n"])
            elif k == "sub":
                s.sub(p.var_index[op["var"]], op["n"])
            elif k == "copy":
                s.write(p.var_index[op["to"]], s.v[p.var_index[op["from"]]])
            elif k == "setbit":
                ci = p.var_index[p.clue_var]
                s.write(ci, s.v[ci] | (1 << p.bit_index[op["bit"]]))
            elif k == "pick_max":
                best = None
                for o in op["options"]:
                    val = s.v[p.var_index[o["var"]]]
                    if best is None or val > best[0]:
                        best = (val, o["route"])
                s.write(p.var_index["route"], best[1])
            elif k == "if":
                self.ops(op["then"] if self.test(op["test"]) else op.get("else", []))
            elif k == "choice":
                n = len(op["options"])
                pick = self.env.choose(n)
                tr.append(("choice", n, pick))
                self.ops(op["options"][pick].get("do", []))
            elif k == "explore":
                self.explore(op)
            elif k == "call":
                self.depth += 1
                if self.depth > CALL_DEPTH_MAX:
                    raise RunError("call depth exceeded")
                self.ops(self.blocks[op["block"]])
                self.depth -= 1
            elif k == "goto":
                raise _Goto(op["block"])
            elif k == "end":
                raise _End()
            else:
                raise RunError(f"unsupported op {k}")

    def explore(self, op):
        trigs = op["triggers"]
        clock = op.get("clock")
        mask = 0
        rounds = 0
        while True:
            rounds += 1
            if rounds > EXPLORE_ROUNDS_MAX:
                raise RunError(f"{self.scene_id}: explore did not finish in {EXPLORE_ROUNDS_MAX} rounds")
            avail = [i for i, t in enumerate(trigs) if not (t.get("once") and mask >> i & 1)]
            if not avail:
                raise RunError(f"{self.scene_id}: explore has no triggers left")
            t = avail[self.env.pick(len(avail))]
            if trigs[t].get("once"):
                mask |= 1 << t
            self.s.trace.append(("trigger", t))
            self.ops(trigs[t].get("do", []))
            if clock and self.s.v[self.p.var_index[clock["var"]]] >= clock["max"]:
                self.ops(clock.get("on_max", []))
                return


# ---------------------------------------------------------------------------
# Bytecode VM
# ---------------------------------------------------------------------------

class VM:
    def __init__(self, dat, env, scene_var, clue_var, coverage=None):
        self.dat = dat
        self.env = env
        self.s = State(dat)
        self.scene_var, self.clue_var = scene_var, clue_var
        self.coverage = coverage

    def run(self):
        run_game(self.run_scene, self.s, self.scene_var, self.dat.scene_count)
        return self.s.trace, self.s.v

    def run_scene(self, n):
        entry, code = self.dat.scene_code(n)
        strings = self.dat.strings(n)
        s, tr, v = self.s, self.s.trace, self.s.v
        pc, stack, ctx = entry, [], None
        steps = 0
        while True:
            steps += 1
            if steps > 2_000_000:
                raise RunError(f"scene {n}: step limit")
            name, a, ln = decode(code, pc)
            at, pc = pc, pc + ln
            if name == "SAY":
                e = a["ex"] & 0x1F
                tr.append(("say", a["who"], e, a["ex"] >> 5, strings[a["str"]]))
                if self.coverage is not None:
                    self.coverage["say"].add((n, a["str"]))
            elif name == "MAP":
                tr.append(("map", a["map"], a["spawn"], a["time"]))
            elif name == "FADE":
                tr.append(("fade", a["mode"], a["t"]))
            elif name in ("MUSIC", "SFX", "CG"):
                tr.append((name.lower(), a["id"]))
            elif name == "CG_OFF":
                tr.append(("cg_off",))
            elif name == "TUTOR":
                tr.append(("tutorial", a["id"], strings[a["str"]]))
            elif name == "WAIT":
                tr.append(("wait", a["ticks"]))
            elif name == "SET":
                s.write(a["var"], a["n"])
            elif name == "ADD":
                s.add(a["var"], a["n"])
            elif name == "SUB":
                s.sub(a["var"], a["n"])
            elif name == "COPY":
                s.write(a["dst"], v[a["src"]])
            elif name == "SETBIT":
                s.write(self.clue_var, v[self.clue_var] | (1 << a["bit"]))
            elif name == "PICKMAX":
                best = None
                for var, val in a["pairs"]:
                    if best is None or v[var] > best[0]:
                        best = (v[var], val)
                s.write(a["dst"], best[1])
            elif name == "JMP":
                pc = a["off"]
            elif name == "BRF":
                x, y = v[a["var"]], a["n"]
                ok = [x == y, x != y, x >= y, x < y][a["cond"]]
                if not ok:
                    pc = a["off"]
            elif name == "BRFB":
                if not (v[self.clue_var] >> a["bit"]) & 1:
                    pc = a["off"]
            elif name == "CALL":
                if len(stack) >= CALL_DEPTH_MAX:
                    raise RunError(f"scene {n}: call depth exceeded at {at:04x}")
                stack.append(pc)
                pc = a["off"]
            elif name == "RET":
                if not stack:
                    raise RunError(f"scene {n}: RET with empty call stack at {at:04x}")
                pc = stack.pop()
            elif name == "GOTO":
                stack.clear()
                ctx = None
                pc = a["off"]
            elif name == "END":
                tr.append(("end",))
                return
            elif name == "CHOICE":
                k = len(a["opts"])
                pick = self.env.choose(k)
                tr.append(("choice", k, pick))
                if self.coverage is not None:
                    self.coverage["choice"].add((n, at, pick))
                pc = a["opts"][pick][1]
            elif name == "EXPLORE":
                ctx = {"a": a, "mask": 0}
                pc = self.next_trigger(ctx, n)
            elif name == "XRET":
                if ctx is None:
                    raise RunError(f"scene {n}: XRET outside explore at {at:04x}")
                x = ctx["a"]
                if x["cvar"] != NO_VAR and v[x["cvar"]] >= x["cmax"]:
                    pc = x["onmax"]
                else:
                    pc = self.next_trigger(ctx, n)
            elif name == "XEXIT":
                if ctx is None:
                    raise RunError(f"scene {n}: XEXIT outside explore at {at:04x}")
                pc = ctx["a"]["exit"]
                ctx = None

    def next_trigger(self, ctx, n):
        ctx["rounds"] = ctx.get("rounds", 0) + 1
        if ctx["rounds"] > EXPLORE_ROUNDS_MAX:
            raise RunError(f"scene {n}: explore did not finish in {EXPLORE_ROUNDS_MAX} rounds")
        trigs = ctx["a"]["trigs"]
        avail = [i for i, (tid, fl, off) in enumerate(trigs) if not (fl & 1 and ctx["mask"] >> i & 1)]
        if not avail:
            raise RunError(f"scene {n}: explore has no triggers left")
        t = avail[self.env.pick(len(avail))]
        if trigs[t][1] & 1:
            ctx["mask"] |= 1 << t
        self.s.trace.append(("trigger", t))
        return trigs[t][2]
