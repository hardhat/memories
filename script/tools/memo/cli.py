"""Command line interface: check, build, dump, stats, trace."""
import argparse
import json
import sys
from pathlib import Path

from .assets import AssetError, load_assets
from .check import Diag, check_project
from .compile import CompileError, compile_project
from .datread import Dat, DatError
from .disasm import disassemble
from .estimate import count_say, typical_minutes
from .pack import PackError, build_dat
from .project import ROOT, load_json, load_project
from .sidecar import ids_header, layout_text, listing, sym_json
from .trace import compare

DEFAULT_OUT = ROOT / "build"
DEFAULT_MANIFEST = ROOT / "assets" / "manifest.json"


def print_diags(diags, strict):
    groups = (("error", "ERRORS"), ("warn", "WARNINGS"), ("missing", "Art still to do"), ("info", "Notes"))
    for level, title in groups:
        items = [d for d in diags if d.level == level]
        if items:
            print(f"\n{title}:")
            for d in items:
                print(f"  {d.where}: {d.msg}")
    bad = [d for d in diags if d.level == "error" or (strict and d.level in ("warn", "missing"))]
    return bad


def load_art(p, args):
    path = Path(args.assets) if getattr(args, "assets", None) else DEFAULT_MANIFEST
    return load_assets(p, path, convert=getattr(args, "convert", False),
                       keep_compression=getattr(args, "keep_compression", False))


def compile_checked(p, diags):
    """Compile all scenes; compile problems become error diagnostics."""
    if any(d.level == "error" for d in diags):
        return None
    try:
        codes = compile_project(p)
    except CompileError as e:
        diags.append(Diag("error", "compile", str(e)))
        return None
    limits = p.config["limits"]
    for sc in codes:
        if len(sc.code) > limits["code_buf"]:
            diags.append(Diag("error", sc.scene_id, f"code is {len(sc.code)} bytes (limit {limits['code_buf']})"))
        elif len(sc.code) > limits["code_warn"]:
            diags.append(Diag("warn", sc.scene_id, f"code is {len(sc.code)} bytes (warn above {limits['code_warn']})"))
    return codes


def cmd_check(args):
    p = load_project(scene_paths=args.scenes or None)
    if args.init_audio:
        path = ROOT / "common" / "audio.json"
        if path.exists() and not args.force:
            print(f"{path} exists; use --force to overwrite")
            return 1
        path.write_text(json.dumps(p.init_audio(), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")
        return 0
    diags = check_project(p)
    codes = compile_checked(p, diags)
    if not args.scenes:
        diags += load_art(p, args).diags
    for i, scene in enumerate(p.scenes):
        extra = ""
        if codes:
            sc = codes[i]
            sbytes = sum(len(s) + 1 for s in sc.strings.items)
            extra = f", code {len(sc.code)} B, {len(sc.strings.items)} strings ({sbytes} B)"
        print(f"{p.scene_files[i]}: {scene['title']}: {count_say(scene)} text boxes, "
              f"~{typical_minutes(scene):.1f} min typical{extra}")
    bad = print_diags(diags, args.strict)
    print("\n" + ("FAILED" if bad else "OK"))
    return 1 if bad else 0


def build_all(args):
    p = load_project()
    diags = check_project(p)
    codes = compile_checked(p, diags)
    assets = load_art(p, args)
    diags += assets.diags
    bad = print_diags([d for d in diags if d.level != "info"], args.strict)
    if bad or codes is None:
        print("\nFAILED: fix the problems above")
        return None
    data, layout = build_dat(p, codes, assets)
    return p, codes, data, layout


def cmd_build(args):
    built = build_all(args)
    if built is None:
        return 1
    p, codes, data, layout = built
    out = Path(args.out) if args.out else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    (out / "memo.dat").write_bytes(data)
    (out / "memo_ids.h").write_text(ids_header(p, data, codes), encoding="utf-8")
    (out / "memo.sym").write_text(sym_json(p, codes), encoding="utf-8")
    (out / "memo.lst").write_text(listing(p, codes), encoding="utf-8")
    (out / "memo.layout.txt").write_text(layout_text(p, layout, len(data)), encoding="utf-8")
    Dat(data)  # re-read our own output (CRC and structure)
    print(f"\nWrote {out / 'memo.dat'}: {len(data)} bytes, {len(layout)} blocks")
    print(f"Sidecars: memo_ids.h memo.sym memo.lst memo.layout.txt in {out}")
    return 0


def load_dat(path):
    path = Path(path) if path else DEFAULT_OUT / "memo.dat"
    return path, Dat(path.read_bytes())


def cmd_dump(args):
    path, dat = load_dat(args.file)
    syms = None
    sym_path = path.with_name("memo.sym")
    if sym_path.exists():
        syms = json.loads(sym_path.read_text(encoding="utf-8"))
    print(f"{path}: {len(dat.data)} bytes, format v{dat.version}, {dat.scene_count} scenes, "
          f"{dat.string_total} strings, crc {dat.crc:08x}")
    print(f"header: {dat.entry_count} entries ({dat.header_size} bytes)\n")
    from .sidecar import TYPE_NAMES
    for bid, (off, size, typ, flags) in enumerate(dat.entries):
        if typ == 0xFF:
            continue
        print(f"  {bid:>3} {TYPE_NAMES.get(typ, typ):<10} offset {off:>7} size {size:>6} flags {flags:#04x}")
    print(f"\nvariables: {dat.var_count}  characters: {len(dat.chars)}")
    print("index: " + ", ".join(f"{k} {len(v)}" for k, v in dat.index.items()))
    wanted = [args.scene] if args.scene else (range(1, dat.scene_count + 1) if args.all else [])
    for n in wanted:
        entry, code = dat.scene_code(n)
        strings = dat.strings(n)
        labels = None
        if syms and n - 1 < len(syms.get("scenes", [])):
            labels = syms["scenes"][n - 1]["blocks"]
        print(f"\n; scene {n}: entry {entry:04x}, {len(code)} bytes, {len(strings)} strings")
        for line in disassemble(code, syms, strings, labels):
            print(line)
    return 0


def cmd_stats(args):
    path, dat = load_dat(args.file)
    print(f"{path}: {len(dat.data)} bytes")
    print(f"header {dat.header_size} bytes ({dat.entry_count} entries)")
    print("\nscene   code    strings   string bytes")
    total_code = total_str = 0
    for n in range(1, dat.scene_count + 1):
        _, code = dat.scene_code(n)
        strings = dat.strings(n)
        sbytes = sum(len(s) + 1 for s in strings)
        total_code += len(code)
        total_str += sbytes
        print(f"s{n:02d} {len(code):>7} {len(strings):>9} {sbytes:>13}")
    print(f"total {total_code:>5} {dat.string_total:>9} {total_str:>13}")
    return 0


def cmd_trace(args):
    built = build_all(args)
    if built is None:
        return 1
    p, codes, data, layout = built
    policies = args.policies.split(",")
    result = compare(p, data, range(args.seeds), policies)
    if not result["ok"]:
        print("\nTRACE MISMATCH\n" + result["error"])
        return 1
    print(f"\n{result['runs']} playthroughs, {result['events']} events: interpreter and VM agree")
    print(f"say lines reached:      {result['say_hit']}/{result['say_total']}")
    print(f"choice options reached: {result['choice_hit']}/{result['choice_total']}")
    if result["endings"]:
        print("(route, ending) outcomes: " + ", ".join(f"{k}:{v}" for k, v in sorted(result["endings"].items())))
    return 0


def add_art_args(sp):
    sp.add_argument("--assets", help="art manifest (default script/assets/manifest.json)")
    sp.add_argument("--convert", action="store_true",
                    help="run gif2zeal.py on GIFs whose outputs are missing or stale")
    sp.add_argument("--keep-compression", action="store_true",
                    help="store the converter's RLE/LZ tile streams instead of raw tiles")


def cmd_ctrace(args):
    from .ctrace import CTraceError, compare_c
    built = build_all(args)
    if built is None:
        return 1
    p, codes, data, layout = built
    out = Path(args.out) if args.out else DEFAULT_OUT
    work = out / "ctrace"
    try:
        result = compare_c(p, data, ids_header(p, data, codes), work, range(args.seeds),
                           args.policies.split(","))
    except CTraceError as e:
        print(f"\n{e}")
        return 1
    if not result["ok"]:
        print("\nC ENGINE MISMATCH\n" + result["error"])
        return 1
    print(f"\nC loader: header, tables, code and strings of all {result['entries']} entries match the python reader")
    print(f"C vm: {result['runs']} playthroughs, {result['events']} events: engine and python vm agree")
    print(f"harness: {result['exe']}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser("memo_dat", description="Memories of Ravenwood resource compiler")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="validate and lint the script")
    c.add_argument("scenes", nargs="*", help="scene files (default: all)")
    c.add_argument("--strict", action="store_true", help="warnings fail the run")
    c.add_argument("--init-audio", action="store_true", help="write common/audio.json from the names the scripts use")
    c.add_argument("--force", action="store_true")
    add_art_args(c)
    c.set_defaults(fn=cmd_check)

    b = sub.add_parser("build", help="write memo.dat and sidecars")
    b.add_argument("--out", help="output directory (default script/build)")
    b.add_argument("--strict", action="store_true", help="warnings and missing art fail the build")
    add_art_args(b)
    b.set_defaults(fn=cmd_build)

    d = sub.add_parser("dump", help="read memo.dat with the independent reader")
    d.add_argument("file", nargs="?")
    d.add_argument("--scene", type=int)
    d.add_argument("--all", action="store_true", help="disassemble every scene")
    d.set_defaults(fn=cmd_dump)

    s = sub.add_parser("stats", help="size report")
    s.add_argument("file", nargs="?")
    s.set_defaults(fn=cmd_stats)

    t = sub.add_parser("trace", help="compare the JSON interpreter with the bytecode VM")
    t.add_argument("--seeds", type=int, default=200)
    t.add_argument("--policies", default="uniform,first")
    t.add_argument("--strict", action="store_true")
    add_art_args(t)
    t.set_defaults(fn=cmd_trace)

    ct = sub.add_parser("ctrace", help="compare the C engine (engine/) with the python reader and VM")
    ct.add_argument("--seeds", type=int, default=100)
    ct.add_argument("--policies", default="uniform,first")
    ct.add_argument("--out", help="work directory root (default script/build)")
    ct.add_argument("--strict", action="store_true")
    add_art_args(ct)
    ct.set_defaults(fn=cmd_ctrace)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except (DatError, PackError, CompileError, AssetError, json.JSONDecodeError) as e:
        print(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
