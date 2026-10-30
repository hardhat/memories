"""Trace equivalence: run the JSON interpreter and the bytecode VM on the same seeded play and
compare (compiler-spec.md section 9.2)."""
from .datread import Dat
from .disasm import decode
from .interp import Env, RunError, Sim, VM


def code_inventory(dat):
    """Say strings and choice options present in the compiled code: for coverage totals."""
    says, options = set(), set()
    for n in range(1, dat.scene_count + 1):
        _, code = dat.scene_code(n)
        pc = 0
        while pc < len(code):
            name, a, ln = decode(code, pc)
            if name == "SAY":
                says.add((n, a["str"]))
            elif name == "CHOICE":
                for i in range(len(a["opts"])):
                    options.add((n, pc, i))
            pc += ln
    return says, options


def first_difference(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i, x, y
    if len(a) != len(b):
        i = min(len(a), len(b))
        return i, a[i] if i < len(a) else None, b[i] if i < len(b) else None
    return None


def compare(project, dat_bytes, seeds, policies=("uniform",), invariants=True):
    dat = Dat(dat_bytes)
    p = project
    scene_var = p.var_index["scene"]
    clue_var = p.var_index[p.clue_var]
    coverage = {"say": set(), "choice": set()}
    says_total, options_total = code_inventory(dat)
    runs, events = 0, 0
    ending_counts = {}
    for policy in policies:
        for seed in seeds:
            try:
                s_trace, s_vars = Sim(p, Env(seed, policy)).run()
            except RunError as e:
                return {"ok": False, "error": f"sim seed {seed} {policy}: {e}"}
            try:
                v_trace, v_vars = VM(dat, Env(seed, policy), scene_var, clue_var, coverage).run()
            except RunError as e:
                return {"ok": False, "error": f"vm seed {seed} {policy}: {e}"}
            diff = first_difference(s_trace, v_trace)
            if diff:
                i, x, y = diff
                return {"ok": False, "error": f"seed {seed} {policy}: traces differ at event {i}:\n"
                                              f"   json: {x}\n   vm:   {y}"}
            if s_vars != v_vars:
                return {"ok": False, "error": f"seed {seed} {policy}: final variables differ"}
            if invariants and len(p.scenes) == 10 and "ending" in p.var_index and "route" in p.var_index:
                ending, route = v_vars[p.var_index["ending"]], v_vars[p.var_index["route"]]
                if ending not in (1, 2, 3, 4) or route not in (1, 2, 3, 4):
                    return {"ok": False, "error": f"seed {seed} {policy}: route={route} ending={ending}"}
                ending_counts[(route, ending)] = ending_counts.get((route, ending), 0) + 1
            runs += 1
            events += len(v_trace)
    return {
        "ok": True, "runs": runs, "events": events,
        "say_hit": len(coverage["say"]), "say_total": len(says_total),
        "choice_hit": len(coverage["choice"]), "choice_total": len(options_total),
        "endings": ending_counts,
    }
