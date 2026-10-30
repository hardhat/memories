"""Rough playtime estimate (moved from validate.py)."""
from .flow import walk_ops

SECONDS_PER_BOX = 5
SECONDS_PER_MAP = 10


def count_say(scene):
    n = [0]

    def f(op, where):
        if op["op"] == "say":
            n[0] += 1

    for ops in scene["blocks"].values():
        walk_ops(ops, f)
    return n[0]


def typical_minutes(scene):
    """One typical playthrough: choices average their options, optional triggers count half,
    a clocked explore plays `max` of its stops."""
    blocks = scene["blocks"]
    seen = set()

    def block(name):
        if name in seen:
            return 0
        seen.add(name)
        total, _ = ops_time(blocks[name])
        seen.discard(name)
        return total

    def ops_time(ops):
        total = 0.0
        for op in ops:
            kind = op["op"]
            if kind in ("say", "tutorial"):
                total += SECONDS_PER_BOX
            elif kind == "map":
                total += SECONDS_PER_MAP
            elif kind == "choice":
                opts = [ops_time(o.get("do", []))[0] for o in op["options"]]
                total += SECONDS_PER_BOX + sum(opts) / len(opts)
            elif kind == "if":
                total += max(ops_time(op.get("then", []))[0], ops_time(op.get("else", []))[0])
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
                    avg = sum(stops) / len(stops) if stops else 0
                    on_max, _ = ops_time(clock["on_max"])
                    return total + walk + avg * clock["max"] + on_max, True
                for t in trigs:
                    t_time, jumped = ops_time(t["do"])
                    if jumped:
                        return total + walk + t_time, True
                    total += 0.5 * t_time
                total += walk
        return total, False

    return block(scene["entry"]) / 60.0
