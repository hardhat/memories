"""Compare the C engine (engine/memo_dat.c, engine/memo_vm.c) with the Python reader and VM
(compiler-spec.md sections 9 and 13, milestone M5).

The C harness replays the menu and trigger decisions that the Python VM made, so both execute the
same play. Each run is compared by event count, a CRC-32 of the formatted event lines, the final
variables and the fault code. On a mismatch the run is repeated in text mode and the first
differing line is reported.
"""
import os
import shutil
import subprocess
import sys
import zlib
from pathlib import Path

from .datread import Dat
from .interp import Env, RunError, VM
from .project import ROOT

ENGINE = ROOT.parent / "engine"
SOURCES = ["memo_dat.c", "memo_vm.c", "dat_io_stdio.c", "test/trace_main.c"]
TABLES = ("maps", "cgs", "portraits", "sprites", "tilesets", "music", "sfx")


class CTraceError(Exception):
    pass


def esc(text):
    return text.replace("\\", "\\\\").replace("\n", "\\n")


def format_event(ev):
    return " ".join(esc(x) if isinstance(x, str) else str(x) for x in ev)


def trace_crc(trace):
    crc = 0
    for ev in trace:
        crc = zlib.crc32((format_event(ev) + "\n").encode("ascii"), crc)
    return crc


class RecordingEnv(Env):
    """Env that remembers every decision as (options offered, index picked)."""

    def __init__(self, seed, policy):
        super().__init__(seed, policy)
        self.log = []

    def choose(self, n):
        k = super().choose(n)
        self.log.append((n, k))
        return k

    def pick(self, n):
        k = super().pick(n)
        self.log.append((n, k))
        return k


def find_compiler():
    cc = os.environ.get("CC")
    for name in ([cc] if cc else []) + ["gcc", "cc", "clang"]:
        path = shutil.which(name)
        if path:
            return path
    return None


def build_harness(work, ids_header):
    """Write memo_ids.h into `work` and compile the harness there. Returns the executable path."""
    cc = find_compiler()
    if cc is None:
        raise CTraceError("no C compiler found (set CC, or install gcc or clang)")
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    (work / "memo_ids.h").write_text(ids_header, encoding="utf-8")
    exe = work / ("memo_trace.exe" if sys.platform == "win32" else "memo_trace")
    cmd = [cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic", "-DMEMO_TRACE_VARS",
           "-I", str(ENGINE), "-I", str(work)]
    cmd += [str(ENGINE / s) for s in SOURCES] + ["-o", str(exe)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise CTraceError("C build failed:\n" + (r.stderr or r.stdout))
    return exe


def expected_inspect(dat):
    out = [f"meta scenes {dat.scene_count} crc {dat.crc:08X} entries {dat.entry_count}"]
    for i, (off, size, typ, flags) in enumerate(dat.entries):
        out.append(f"entry {i} {off} {size} {typ} {flags}")
    out.append(f"vars {dat.var_count}")
    for i in range(dat.var_count):
        out.append(f"var {i} {dat.var_max[i]} {dat.var_init[i]}")
    for t, name in enumerate(TABLES):
        rows = dat.index[name]
        out.append(f"table {t} {len(rows)}")
        for i, row in enumerate(rows):
            out.append(f"index {t} {i} " + " ".join(str(v) for v in row))
    for n in range(1, dat.scene_count + 1):
        entry, code = dat.scene_code(n)
        out.append(f"scene {n} entry {entry} size {len(code)} crc {zlib.crc32(code):08X}")
        for i, s in enumerate(dat.strings(n)):
            out.append(f"str {n} {i} {esc(s)}")
    return out


def run_exe(exe, *args):
    r = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True)
    return r


def check_inspect(exe, dat_path, dat):
    """Loader check: header, VARS, INDEX, scene code and strings as the C loader reads them."""
    r = run_exe(exe, dat_path, "--inspect", "--crc", f"0x{dat.crc:08X}")
    if r.returncode != 0:
        return f"harness failed ({r.returncode}): {r.stdout.strip()} {r.stderr.strip()}"
    got = r.stdout.splitlines()
    want = expected_inspect(dat)
    for i, (g, w) in enumerate(zip(got, want)):
        if g != w:
            return f"loader line {i} differs:\n   C:      {g}\n   python: {w}"
    if len(got) != len(want):
        return f"loader printed {len(got)} lines, expected {len(want)}"
    return None


def check_streams(exe, dat_path, dat):
    """Every block through the chunked art reader (1000 byte chunks), against the python bytes."""
    ids = range(1, dat.entry_count)
    args = []
    for i in ids:
        args += ["--stream", i]
    r = run_exe(exe, dat_path, *args)
    got = r.stdout.splitlines()
    want = []
    for i in ids:
        if dat.entries[i][2] == 0xFF:
            want.append(f"stream {i} error")
        else:
            data = dat.block(i)
            want.append(f"stream {i} bytes {len(data)} crc {zlib.crc32(data):08X}")
    for g, w in zip(got, want):
        if g != w:
            return f"art stream differs:\n   C:      {g}\n   python: {w}"
    if len(got) != len(want):
        return f"C streamed {len(got)} blocks, expected {len(want)}"
    return None


def record_runs(dat, project, seeds, policies):
    """Run the Python VM and keep, per run: decisions, trace, final variables."""
    scene_var = project.var_index["scene"]
    clue_var = project.var_index[project.clue_var]
    runs = []
    for policy in policies:
        for seed in seeds:
            env = RecordingEnv(seed, policy)
            trace, v = VM(dat, env, scene_var, clue_var).run()
            runs.append({"seed": seed, "policy": policy, "log": env.log, "trace": trace, "vars": list(v)})
    return runs


def write_decisions(path, runs):
    with open(path, "w", encoding="ascii") as f:
        for i, r in enumerate(runs):
            f.write(f"R {i} {len(r['log'])}\n")
            f.write(" ".join(f"{n} {k}" for n, k in r["log"]) + "\n")


def parse_run_line(line):
    t = line.split()
    # RUN id events N crc X rc N scene N pc N vars ...
    return {"id": int(t[1]), "events": int(t[3]), "crc": int(t[5], 16), "rc": int(t[7]),
            "scene": int(t[9]), "pc": int(t[11]), "vars": [int(x) for x in t[13:]]}


def first_text_difference(exe, dat_path, work, run, index):
    one = Path(work) / "one.txt"
    write_decisions(one, [run])
    r = run_exe(exe, dat_path, "--decisions", one, "--text")
    got = [l for l in r.stdout.splitlines() if not l.startswith("RUN ")]
    want = [format_event(e) for e in run["trace"]]
    for i, (g, w) in enumerate(zip(got, want)):
        if g != w:
            return f"event {i}:\n   C:      {g}\n   python: {w}"
    if len(got) != len(want):
        return f"C produced {len(got)} events, python {len(want)}"
    return "no textual difference (crc or variables differ)"


def compare_c(project, dat_bytes, ids_header, work, seeds, policies=("uniform", "first")):
    """Full M5 check. Returns {"ok": bool, ...}."""
    work = Path(work)
    dat = Dat(dat_bytes)
    exe = build_harness(work, ids_header)
    dat_path = work / "memo_under_test.dat"
    dat_path.write_bytes(dat_bytes)

    problem = check_inspect(exe, dat_path, dat) or check_streams(exe, dat_path, dat)
    if problem:
        return {"ok": False, "error": problem}
    bad = run_exe(exe, dat_path, "--inspect", "--crc", f"0x{dat.crc ^ 1:08X}")
    if "open error 5" not in bad.stdout:
        return {"ok": False, "error": "the C loader accepted a wrong content CRC"}

    try:
        runs = record_runs(dat, project, seeds, policies)
    except RunError as e:
        return {"ok": False, "error": f"python vm: {e}"}
    decisions = work / "decisions.txt"
    write_decisions(decisions, runs)
    r = run_exe(exe, dat_path, "--decisions", decisions)
    if r.returncode != 0:
        return {"ok": False, "error": f"harness failed ({r.returncode}): {r.stderr.strip()}"}
    lines = [l for l in r.stdout.splitlines() if l.startswith(("RUN ", "LEFTOVER "))]
    results = [parse_run_line(l) for l in lines if l.startswith("RUN ")]
    if len(results) != len(runs) or any(l.startswith("LEFTOVER ") for l in lines):
        return {"ok": False, "error": f"C ran {len(results)} of {len(runs)} plays "
                                      f"or left decisions unused:\n" + "\n".join(lines[-3:])}
    events = 0
    for i, (res, run) in enumerate(zip(results, runs)):
        who = f"seed {run['seed']} {run['policy']}"
        want = {"events": len(run["trace"]), "crc": trace_crc(run["trace"]), "rc": 0, "vars": run["vars"]}
        got = {k: res[k] for k in want}
        if got != want:
            detail = first_text_difference(exe, dat_path, work, run, i)
            return {"ok": False, "error": f"{who}: C engine differs from the python vm "
                                          f"(rc {res['rc']} scene {res['scene']} pc {res['pc']}) at {detail}"}
        events += want["events"]
    return {"ok": True, "runs": len(runs), "events": events, "exe": str(exe),
            "entries": dat.entry_count, "strings": dat.string_total}
