"""Structural helpers for scene op trees (control flow, call graph)."""


def children(op):
    """(suffix, op list) for every nested op list of an op."""
    k = op["op"]
    if k == "if":
        yield ".then", op.get("then", [])
        yield ".else", op.get("else", [])
    elif k == "choice":
        for j, o in enumerate(op.get("options", [])):
            yield f".options[{j}]", o.get("do", [])
    elif k == "explore":
        c = op.get("clock")
        if c:
            yield ".clock", c.get("on_max", [])
        for j, t in enumerate(op.get("triggers", [])):
            yield f".triggers[{j}]", t.get("do", [])


def walk_ops(ops, fn, where=""):
    """Call fn(op, where) for every op, depth first, with a readable position."""
    for i, op in enumerate(ops):
        w = f"{where}[{i}]"
        fn(op, w)
        for suffix, sub in children(op):
            walk_ops(sub, fn, w + suffix)


def falls(ops):
    """True if control can reach the end of the op list (fall through)."""
    for op in ops:
        k = op["op"]
        if k in ("goto", "end"):
            return False
        if k == "if":
            then_falls = falls(op.get("then", []))
            else_falls = falls(op["else"]) if op.get("else") else True
            if not (then_falls or else_falls):
                return False
        elif k == "choice":
            if not any(falls(o.get("do", [])) for o in op.get("options", [])):
                return False
        elif k == "explore":
            clock = op.get("clock")
            if not clock or not falls(clock.get("on_max", [])):
                return False
    return True


def collect(ops, kind):
    """Names referenced by ops of the given kind ('call' or 'goto') anywhere in the tree."""
    out = []

    def f(op, where):
        if op["op"] == kind:
            out.append(op["block"])

    walk_ops(ops, f)
    return out


def has_op(ops, kind):
    found = []

    def f(op, where):
        if op["op"] == kind:
            found.append(op)

    walk_ops(ops, f)
    return bool(found)
