"""Bytecode decoder and disassembler (compiler-spec.md section 6)."""
import struct

from .spec import CMP_NAME, EXPR_NONE, NO_TRIGGER, NO_VAR, OP, OP_NAME, STYLE_NAME

FIXED = {
    "SAY": ("BBH", ("who", "ex", "str")),
    "MAP": ("BBB", ("map", "spawn", "time")),
    "FADE": ("BB", ("mode", "t")),
    "MUSIC": ("B", ("id",)),
    "SFX": ("B", ("id",)),
    "CG": ("B", ("id",)),
    "CG_OFF": ("", ()),
    "TUTOR": ("BH", ("id", "str")),
    "WAIT": ("B", ("ticks",)),
    "SET": ("BB", ("var", "n")),
    "ADD": ("BB", ("var", "n")),
    "SUB": ("BB", ("var", "n")),
    "COPY": ("BB", ("dst", "src")),
    "SETBIT": ("B", ("bit",)),
    "JMP": ("H", ("off",)),
    "BRF": ("BBBH", ("cond", "var", "n", "off")),
    "BRFB": ("BH", ("bit", "off")),
    "CALL": ("H", ("off",)),
    "RET": ("", ()),
    "GOTO": ("H", ("off",)),
    "XRET": ("", ()),
    "XEXIT": ("", ()),
    "END": ("", ()),
}


class DecodeError(Exception):
    pass


def decode(code, pc):
    """Return (mnemonic, args dict, length) for the instruction at pc."""
    if pc >= len(code):
        raise DecodeError(f"pc {pc:04x} is past the end of the code")
    op = code[pc]
    if op not in OP_NAME:
        raise DecodeError(f"bad opcode {op:02x} at {pc:04x}")
    name = OP_NAME[op]
    try:
        if name in FIXED:
            fmt, keys = FIXED[name]
            vals = struct.unpack_from("<" + fmt, code, pc + 1) if fmt else ()
            return name, dict(zip(keys, vals)), 1 + struct.calcsize("<" + fmt)
        if name == "PICKMAX":
            dst, n = code[pc + 1], code[pc + 2]
            pairs = [(code[pc + 3 + 2 * i], code[pc + 4 + 2 * i]) for i in range(n)]
            return name, {"dst": dst, "pairs": pairs}, 3 + 2 * n
        if name == "CHOICE":
            prompt, n = struct.unpack_from("<HB", code, pc + 1)
            opts = [struct.unpack_from("<HH", code, pc + 4 + 4 * i) for i in range(n)]
            return name, {"prompt": prompt, "opts": opts}, 4 + 4 * n
        if name == "EXPLORE":
            obj, cvar, cmax, n, onmax, exit_ = struct.unpack_from("<BBBBHH", code, pc + 1)
            trigs = [struct.unpack_from("<BBH", code, pc + 9 + 4 * i) for i in range(n)]
            return name, {"obj": obj, "cvar": cvar, "cmax": cmax, "onmax": onmax, "exit": exit_,
                          "trigs": trigs}, 9 + 4 * n
    except (struct.error, IndexError):
        raise DecodeError(f"truncated {name} at {pc:04x}")
    raise DecodeError(f"cannot decode {name}")


def disassemble(code, syms=None, strings=None, labels=None):
    """Lines of '0000: bytes  mnemonic operands'. syms is the dict from make_syms (names), strings the
    scene's string list, labels a dict block name -> offset."""
    by_off = {v: k for k, v in (labels or {}).items()}
    lines, pc = [], 0
    while pc < len(code):
        if pc in by_off:
            lines.append(f"                   ; --- {by_off[pc]}")
        name, a, n = decode(code, pc)
        raw = code[pc:pc + n].hex(" ")
        lines.append(f"{pc:04x}: {raw:<24} {name:<7} {fmt_args(name, a, syms, strings)}".rstrip())
        pc += n
    return lines


def nm(syms, key, i, default=None):
    if syms and key in syms and 0 <= i < len(syms[key]):
        v = syms[key][i]
        return v["name"] if isinstance(v, dict) else v
    return default if default is not None else str(i)


def text(strings, i):
    if strings and 0 <= i < len(strings):
        s = strings[i].replace("\n", "|")
        return f'"{s}"'
    return f"str{i}"


def fmt_args(name, a, syms, strings):
    if name == "SAY":
        who = nm(syms, "chars", a["who"])
        e = a["ex"] & 0x1F
        style = STYLE_NAME[a["ex"] >> 5] if (a["ex"] >> 5) in STYLE_NAME else str(a["ex"] >> 5)
        expr = "" if e == EXPR_NONE else "/" + (syms["chars"][a["who"]]["exprs"][e] if syms else str(e))
        return f"{who}{expr}{' [' + style + ']' if style else ''} {text(strings, a['str'])}"
    if name == "MAP":
        m = a["map"]
        spawn = syms["maps"][m]["spawns"][a["spawn"]] if syms else a["spawn"]
        return f"{nm(syms, 'maps', m)} {spawn} {nm(syms, 'times', a['time'])}"
    if name == "FADE":
        return f"{'black' if a['mode'] else 'clear'} {a['t'] * 10}ms"
    if name == "MUSIC":
        return nm(syms, "music", a["id"])
    if name == "SFX":
        return nm(syms, "sfx", a["id"])
    if name == "CG":
        return nm(syms, "cgs", a["id"])
    if name == "TUTOR":
        return f"{nm(syms, 'tutorials', a['id'])} {text(strings, a['str'])}"
    if name in ("SET", "ADD", "SUB"):
        return f"{nm(syms, 'vars', a['var'])} {a['n']}"
    if name == "COPY":
        return f"{nm(syms, 'vars', a['dst'])} <- {nm(syms, 'vars', a['src'])}"
    if name == "SETBIT":
        return nm(syms, "bits", a["bit"])
    if name == "PICKMAX":
        pairs = ", ".join(f"{nm(syms, 'vars', v)}->{r}" for v, r in a["pairs"])
        return f"{nm(syms, 'vars', a['dst'])} = max of [{pairs}]"
    if name in ("JMP", "CALL", "GOTO"):
        return f"{a['off']:04x}"
    if name == "BRF":
        return f"unless {nm(syms, 'vars', a['var'])} {CMP_NAME[a['cond']]} {a['n']} -> {a['off']:04x}"
    if name == "BRFB":
        return f"unless bit {nm(syms, 'bits', a['bit'])} -> {a['off']:04x}"
    if name == "CHOICE":
        opts = "; ".join(f"{text(strings, s)} -> {o:04x}" for s, o in a["opts"])
        return f"{text(strings, a['prompt'])}  [{opts}]"
    if name == "EXPLORE":
        obj = "-" if a["obj"] == NO_TRIGGER else nm(syms, "triggers", a["obj"])
        clock = "none" if a["cvar"] == NO_VAR else f"{nm(syms, 'vars', a['cvar'])}>={a['cmax']} -> {a['onmax']:04x}"
        trigs = ", ".join(f"{nm(syms, 'triggers', t)}{'*' if f & 1 else ''}->{o:04x}" for t, f, o in a["trigs"])
        return f"objective={obj} clock={clock} exit={a['exit']:04x} [{trigs}]"
    return ""


def make_syms(p):
    """Names for the disassembler and the sidecar (memo.sym)."""
    return {
        "vars": list(p.var_names),
        "bits": [b for g in p.bit_groups.values() for b in g],
        "chars": [{"name": n, "exprs": list(p.char_exprs[n])} for n in p.char_names],
        "maps": [{"name": n, "spawns": list(p.maps[n].get("spawns", []))} for n in p.map_names],
        "triggers": list(p.trigger_names),
        "cgs": list(p.cg_names),
        "music": list(p.music),
        "sfx": list(p.sfx),
        "times": list(p.times),
        "tutorials": list(p.tutorial_names),
    }
