"""Project model: loads the script data and assigns the small integer ids that the
bytecode and tables use (compiler-spec.md section 5.6)."""
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # .../script

DEFAULT_CONFIG = {
    "text": {"cols": 36, "lines": 3, "max_len": 127},
    "choice": {"options_max": 3, "lines_max": 6},
    "name_max": 16,
    "times": ["dawn", "morning", "noon", "midday", "afternoon", "golden", "dusk", "evening",
              "night", "midnight", "snow"],
    "limits": {"code_buf": 4096, "code_warn": 3072, "call_depth": 8,
               "explore_triggers": 16, "strings_bytes": 65000},
    # Portrait: base image and the alternate-head region, in 16x16 tiles (x, y, w, h for the head).
    # CG modes: bits per pixel -> image size in tiles.
    "art": {"portrait": {"base": [2, 5], "head": [0, 0, 2, 2], "max_colors": 32},
            "cg_modes": {"4": [20, 15], "8": [20, 12]}},
}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def public(d):
    """Dict without documentation keys (names starting with '_')."""
    return {k: v for k, v in d.items() if not k.startswith("_")}


def merge(base, over):
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = v
    return out


def wrap(text, cols):
    """Greedy word wrap, lines joined with newline (the stored string form)."""
    return "\n".join(textwrap.wrap(text, cols))


class Project:
    def __init__(self, chars, variables, maps, cgs, scenes, config=None, audio=None, scene_files=None):
        self.config = merge(DEFAULT_CONFIG, config or {})
        self.audio = audio
        self.scene_files = scene_files or [s.get("id", f"s{i + 1:02d}") for i, s in enumerate(scenes)]
        self.scenes = scenes

        self.chars_raw = public(chars)
        self.char_names = list(self.chars_raw)
        self.char_index = {n: i for i, n in enumerate(self.char_names)}
        self.char_exprs = {n: list(c.get("have", [])) + list(c.get("todo", []))
                           for n, c in self.chars_raw.items()}

        counters = variables["counters"]
        flags = variables["flags"]
        self.counter_names = list(counters)
        self.flag_names = list(flags)
        self.bit_groups = {g: list(bits) for g, bits in variables["bits"].items()}
        self.var_names = self.counter_names + self.flag_names + list(self.bit_groups)
        self.var_index = {n: i for i, n in enumerate(self.var_names)}
        self.var_max = []
        for n in self.var_names:
            if n in counters:
                self.var_max.append(int(counters[n].get("max", 255)))
            elif n in flags:
                self.var_max.append(1)
            else:
                self.var_max.append(255)
        self.clue_var = next(iter(self.bit_groups)) if self.bit_groups else None
        self.bit_index = {}
        for group, bits in self.bit_groups.items():
            for i, b in enumerate(bits):
                self.bit_index[b] = i

        self.maps = public(maps)
        self.map_names = list(self.maps)
        self.map_index = {n: i for i, n in enumerate(self.map_names)}
        self.trigger_names = []
        for m in self.maps.values():
            for t in m.get("triggers", []):
                if t not in self.trigger_names:
                    self.trigger_names.append(t)
        self.trigger_index = {n: i for i, n in enumerate(self.trigger_names)}

        self.cgs = public(cgs)
        self.cg_names = list(self.cgs)
        self.cg_index = {n: i for i, n in enumerate(self.cg_names)}

        self.times = list(self.config["times"])
        self.time_index = {n: i for i, n in enumerate(self.times)}

        self.music, self.sfx = self._audio_names(audio)
        self.music_index = {n: i for i, n in enumerate(self.music)}
        self.sfx_index = {n: i for i, n in enumerate(self.sfx)}
        self.tutorial_names = self._tutorial_names()
        self.tutorial_index = {n: i for i, n in enumerate(self.tutorial_names)}

    # ---- ids -------------------------------------------------------------
    def _audio_names(self, audio):
        if audio is not None:
            return list(public(audio.get("music", {}))), list(public(audio.get("sfx", {})))
        music, sfx = [], []
        from .flow import walk_ops
        for s in self.scenes:
            for ops in s["blocks"].values():
                def f(op, where):
                    if op["op"] == "music" and op["id"] not in music:
                        music.append(op["id"])
                    if op["op"] == "sfx" and op["id"] not in sfx:
                        sfx.append(op["id"])
                walk_ops(ops, f)
        return sorted(music), sorted(sfx)

    def _tutorial_names(self):
        names = []
        from .flow import walk_ops
        for s in self.scenes:
            for ops in s["blocks"].values():
                def f(op, where):
                    if op["op"] == "tutorial" and op.get("id") not in names:
                        names.append(op.get("id"))
                walk_ops(ops, f)
        return names

    def init_audio(self):
        """Registry skeleton built from the names used by the scripts."""
        from .flow import walk_ops
        music, sfx = set(), set()
        for s in self.scenes:
            for ops in s["blocks"].values():
                def f(op, where):
                    if op["op"] == "music":
                        music.add(op["id"])
                    if op["op"] == "sfx":
                        sfx.add(op["id"])
                walk_ops(ops, f)
        return {"_doc": "Music and sound effect registry. 'file' is null until the asset exists.",
                "music": {n: {"file": None} for n in sorted(music)},
                "sfx": {n: {"file": None} for n in sorted(sfx)}}


def load_project(root=ROOT, scene_paths=None):
    common = Path(root) / "common"
    config = load_json(common / "config.json") if (common / "config.json").exists() else {}
    audio = load_json(common / "audio.json") if (common / "audio.json").exists() else None
    paths = [Path(p) for p in scene_paths] if scene_paths else sorted((Path(root) / "scenes").glob("*.json"))
    scenes = [load_json(p) for p in paths]
    return Project(
        load_json(common / "characters.json"),
        load_json(common / "variables.json"),
        load_json(common / "maps.json"),
        load_json(common / "cgs.json"),
        scenes,
        config=config,
        audio=audio,
        scene_files=[p.name for p in paths],
    )
