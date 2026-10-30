"""Compile scene JSON to bytecode and string tables (compiler-spec.md sections 5.3, 5.4, 6)."""
import struct

from .flow import falls
from .project import wrap
from .spec import (CMP, EXPR_NONE, FADE_MODE, DEFAULT_FADE_MS, NO_TRIGGER, NO_VAR, OP, STYLE)


class CompileError(Exception):
    pass


class Strings:
    """Per-scene string table. Identical strings share an id; ids follow first use."""

    def __init__(self):
        self.items = []
        self.index = {}
        self.where = []

    def add(self, text, cols, where=""):
        s = wrap(text, cols)
        if s not in self.index:
            self.index[s] = len(self.items)
            self.items.append(s)
            self.where.append(where)
        return self.index[s]

    def block(self):
        """STRINGS block bytes: u16 count, u16 offsets, NUL-terminated data."""
        offsets, data = [], bytearray()
        for s in self.items:
            offsets.append(len(data))
            data += s.encode("ascii") + b"\x00"
        if len(data) > 65535:
            raise CompileError("string data exceeds 64 KB")
        return struct.pack("<H", len(self.items)) + b"".join(struct.pack("<H", o) for o in offsets) + bytes(data)


class SceneCode:
    def __init__(self, scene_id, code, entry_pc, strings, labels, choices):
        self.scene_id = scene_id
        self.code = bytes(code)
        self.entry_pc = entry_pc
        self.strings = strings
        self.labels = labels      # block name -> offset
        self.choices = choices    # choice id -> offset of its CHOICE instruction

    def block(self):
        return struct.pack("<HHH", len(self.code), self.entry_pc, 0) + self.code


class Asm:
    def __init__(self):
        self.buf = bytearray()
        self.labels = {}
        self.fix = []
        self.counter = 0

    def here(self):
        return len(self.buf)

    def new(self, prefix):
        self.counter += 1
        return f"{prefix}#{self.counter}"

    def label(self, name):
        if name in self.labels:
            raise CompileError(f"duplicate label {name}")
        self.labels[name] = len(self.buf)

    def u8(self, v):
        if not 0 <= v <= 255:
            raise CompileError(f"operand {v} does not fit a byte")
        self.buf.append(v)

    def u16(self, v):
        if not 0 <= v <= 65535:
            raise CompileError(f"operand {v} does not fit 16 bits")
        self.buf += struct.pack("<H", v)

    def ref(self, label):
        self.fix.append((len(self.buf), label))
        self.buf += b"\x00\x00"

    def finish(self):
        if len(self.buf) > 65535:
            raise CompileError("scene code exceeds 64 KB")
        for pos, label in self.fix:
            if label not in self.labels:
                raise CompileError(f"undefined label {label}")
            self.buf[pos:pos + 2] = struct.pack("<H", self.labels[label])
        return bytes(self.buf)


class SceneCompiler:
    def __init__(self, project, scene):
        self.p = project
        self.scene = scene
        self.cols = project.config["text"]["cols"]
        self.asm = Asm()
        self.strings = Strings()
        self.choices = {}
        self.block = ""

    # ---- id lookups ------------------------------------------------------
    def var(self, name):
        return self.p.var_index[name]

    def string(self, text, where):
        return self.strings.add(text, self.cols, f"{self.scene['id']}:{where}")

    # ---- emit ------------------------------------------------------------
    def ops(self, ops, where):
        for i, op in enumerate(ops):
            self.op(op, f"{where}[{i}]")

    def ins(self, name):
        self.asm.u8(OP[name])

    def op(self, op, where):
        p, a = self.p, self.asm
        k = op["op"]
        if k == "say":
            who = op["who"]
            expr = op.get("expr")
            e = EXPR_NONE if not expr else p.char_exprs[who].index(expr)
            self.ins("SAY")
            a.u8(p.char_index[who])
            a.u8(e | (STYLE[op.get("style")] << 5))
            a.u16(self.string(op["text"], where))
        elif k == "map":
            self.ins("MAP")
            a.u8(p.map_index[op["id"]])
            a.u8(p.maps[op["id"]]["spawns"].index(op["spawn"]))
            a.u8(p.time_index[op["time"]])
        elif k == "fade":
            self.ins("FADE")
            a.u8(FADE_MODE[op["to"]])
            a.u8(round(op.get("ms", DEFAULT_FADE_MS) / 10))
        elif k == "music":
            self.ins("MUSIC")
            a.u8(p.music_index[op["id"]])
        elif k == "sfx":
            self.ins("SFX")
            a.u8(p.sfx_index[op["id"]])
        elif k == "cg":
            self.ins("CG")
            a.u8(p.cg_index[op["id"]])
        elif k == "cg_off":
            self.ins("CG_OFF")
        elif k == "tutorial":
            self.ins("TUTOR")
            a.u8(p.tutorial_index[op["id"]])
            a.u16(self.string(op["text"], where))
        elif k == "wait":
            self.ins("WAIT")
            a.u8(op.get("ticks", 1))
        elif k in ("set", "add", "sub"):
            self.ins(k.upper())
            a.u8(self.var(op["var"]))
            a.u8(op["n"])
        elif k == "copy":
            self.ins("COPY")
            a.u8(self.var(op["to"]))
            a.u8(self.var(op["from"]))
        elif k == "setbit":
            self.ins("SETBIT")
            a.u8(p.bit_index[op["bit"]])
        elif k == "pick_max":
            self.ins("PICKMAX")
            a.u8(self.var("route"))
            a.u8(len(op["options"]))
            for o in op["options"]:
                a.u8(self.var(o["var"]))
                a.u8(o["route"])
        elif k == "if":
            self.emit_if(op, where)
        elif k == "choice":
            self.emit_choice(op, where)
        elif k == "explore":
            self.emit_explore(op, where)
        elif k == "call":
            self.ins("CALL")
            a.ref(f"blk:{op['block']}")
        elif k == "goto":
            self.ins("GOTO")
            a.ref(f"blk:{op['block']}")
        elif k == "end":
            self.ins("END")
        else:
            raise CompileError(f"{where}: cannot compile op {k}")

    def emit_if(self, op, where):
        a = self.asm
        test = op["test"]
        has_else = bool(op.get("else"))
        l_else, l_end = a.new("else"), a.new("endif")
        if "bit" in test:
            self.ins("BRFB")
            a.u8(self.p.bit_index[test["bit"]])
        else:
            self.ins("BRF")
            a.u8(CMP[test["cmp"]])
            a.u8(self.var(test["var"]))
            a.u8(test["n"])
        a.ref(l_else)
        self.ops(op.get("then", []), where + ".then")
        if has_else:
            if falls(op["then"]):
                self.ins("JMP")
                a.ref(l_end)
            a.label(l_else)
            self.ops(op["else"], where + ".else")
            a.label(l_end)
        else:
            a.label(l_else)

    def emit_choice(self, op, where):
        a = self.asm
        opts = op["options"]
        self.choices[op["id"]] = a.here()
        join = a.new("join")
        labels = [a.new("opt") for _ in opts]
        self.ins("CHOICE")
        a.u16(self.string(op["prompt"], where + ".prompt"))
        a.u8(len(opts))
        for lab, o in zip(labels, opts):
            a.u16(self.string(o["text"], where + ".option"))
            a.ref(lab)
        for j, (lab, o) in enumerate(zip(labels, opts)):
            a.label(lab)
            self.ops(o.get("do", []), f"{where}.options[{j}]")
            if falls(o.get("do", [])):
                self.ins("JMP")
                a.ref(join)
        a.label(join)

    def emit_explore(self, op, where):
        a, p = self.asm, self.p
        trig = op["triggers"]
        clock = op.get("clock")
        l_exit = a.new("xexit")
        l_max = a.new("xmax")
        labels = [a.new("trig") for _ in trig]
        obj = p.trigger_index.get(op.get("objective"), NO_TRIGGER)
        self.ins("EXPLORE")
        a.u8(obj)
        a.u8(self.var(clock["var"]) if clock else NO_VAR)
        a.u8(clock["max"] if clock else 0)
        a.u8(len(trig))
        if clock:
            a.ref(l_max)
        else:
            a.u16(0)
        a.ref(l_exit)
        for lab, t in zip(labels, trig):
            a.u8(p.trigger_index[t["at"]])
            a.u8(1 if t.get("once") else 0)
            a.ref(lab)
        for j, (lab, t) in enumerate(zip(labels, trig)):
            a.label(lab)
            self.ops(t.get("do", []), f"{where}.triggers[{j}]")
            if falls(t.get("do", [])):
                self.ins("XRET")
        if clock:
            a.label(l_max)
            self.ops(clock.get("on_max", []), where + ".clock")
            if falls(clock.get("on_max", [])):
                self.ins("XEXIT")
        a.label(l_exit)

    def compile(self):
        s = self.scene
        for name, ops in s["blocks"].items():
            self.block = name
            self.asm.label(f"blk:{name}")
            self.ops(ops, name)
            if falls(ops):
                self.ins("RET")
        code = self.asm.finish()
        labels = {k[4:]: v for k, v in self.asm.labels.items() if k.startswith("blk:")}
        return SceneCode(s["id"], code, labels[s["entry"]], self.strings, labels, self.choices)


def compile_scene(project, scene):
    return SceneCompiler(project, scene).compile()


def compile_project(project):
    return [compile_scene(project, s) for s in project.scenes]
