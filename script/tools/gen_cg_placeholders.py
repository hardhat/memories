#!/usr/bin/env python3
"""Generate placeholder CG images with a local ComfyUI server.

Reads every CG from common/cgs.json, builds a prompt from its description, runs the ComfyUI
workflow z-image_1280x960.json (saved from the ComfyUI editor, "UI" format) and saves
art/cg-placeholders/<CG id>.png at 1280x960. Downscale and palette-limit them separately.

  python tools/gen_cg_placeholders.py                 all CGs that have no image yet
  python tools/gen_cg_placeholders.py CG-01 CG-04a    only these
  python tools/gen_cg_placeholders.py --variants 3    CG-01_v1.png ... (3 seeds each)
  python tools/gen_cg_placeholders.py --list          show the prompts, do not contact the server
  python tools/gen_cg_placeholders.py --force         regenerate existing images

Only the Python standard library is needed.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # .../script
DEFAULT_WORKFLOW = ROOT / "z-image_1280x768.json"
DEFAULT_OUT = ROOT.parent / "art" / "cg-placeholders"
DEFAULT_SERVER = "http://10.0.0.140:8188"

STYLE = "anime RPG game style, visual novel event illustration, wide cinematic composition, warm detailed colors"
NEGATIVE = ("low quality, bad anatomy, extra digits, missing digits, extra limbs, missing limbs, "
            "text, watermark, logo, signature, blurry, user interface, dialogue box, caption, subtitle")

# Short looks for the recurring cast, appended when a description names them. Edit freely: the aim
# is only a consistent placeholder, the real art is drawn separately.
CAST = {
    "Brad": "Brad (young man, short dark hair, black t-shirt)",
    "Jane": "Jane (young woman with long red hair, green top)",
    "Sandra": "Sandra (young woman, tavern keeper, sharp wit)",
    "Georgia": "Georgia (young woman, cafe owner, apron)",
    "Patricia": "Professor Patricia (poised woman with glasses)",
    "Gord": "Gord (middle-aged farmer, flannel shirt)",
    "Daniel": "Daniel (young man, 1990s style)",
    "Eleanor": "Eleanor (young woman, 1990s style, lab coat)",
    "Gourd": "Mr. Gourd (man in a trench coat, sunglasses and a fake mustache)",
}
WORLD = "autumn, Halloween atmosphere, softly glowing orange pumpkin light"
SETTING = {"CG-11": "twenty five years ago, 1990s fashion", "CG-08": "night, van headlights"}

# Simple fix-ups so descriptions written for the script read well as a picture prompt.
def prompt_for(cg_id, cg):
    desc = cg["desc"].strip().rstrip(".")
    head, sep, rest = desc.partition(": ")
    if sep and head.endswith(" ending"):      # a script label ("Good Friends ending:"), not picture content
        desc = rest
    looks = [v for k, v in CAST.items() if k in desc]
    parts = [STYLE, desc]
    if looks:
        parts.append("characters: " + "; ".join(looks))
    if cg_id in SETTING:
        parts.append(SETTING[cg_id])
    parts.append(WORLD)
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# ComfyUI client
# ---------------------------------------------------------------------------

class Comfy:
    def __init__(self, server):
        self.server = server.rstrip("/")

    def get(self, path):
        with urllib.request.urlopen(self.server + path, timeout=30) as r:
            return r.read()

    def get_json(self, path):
        return json.loads(self.get(path))

    def post_json(self, path, payload):
        req = urllib.request.Request(self.server + path, json.dumps(payload).encode("utf-8"),
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise SystemExit(f"server rejected the workflow ({e.code}): {e.read().decode('utf-8', 'replace')[:2000]}")


def widget_names(info):
    """Names of a node class's widget inputs in editor order (links are not widgets)."""
    names = []
    for group in ("required", "optional"):
        for name, spec in (info.get("input", {}).get(group) or {}).items():
            kind = spec[0]
            opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            if isinstance(kind, list) or kind in ("INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"):
                names.append((name, bool(opts.get("control_after_generate"))))
    return names


def to_api(ui, object_info):
    """Convert an editor-format workflow ('nodes' and 'links') to the API prompt format."""
    link_src = {l[0]: (l[1], l[2]) for l in ui["links"]}
    prompt = {}
    for node in ui["nodes"]:
        if node.get("mode", 0) == 4:        # bypassed
            continue
        cls = node["type"]
        info = object_info.get(cls)
        if info is None:
            raise SystemExit(f"the server has no node type {cls}")
        inputs = {}
        for slot in node.get("inputs", []):
            if slot.get("link") is not None:
                src, out = link_src[slot["link"]]
                inputs[slot["name"]] = [str(src), out]
        values = list(node.get("widgets_values") or [])
        for name, has_control in widget_names(info):
            if not values:
                break
            value = values.pop(0)
            if has_control and values:
                values.pop(0)               # the 'fixed/randomize' selector after a seed
            inputs.setdefault(name, value)
        prompt[str(node["id"])] = {"class_type": cls, "inputs": inputs}
    return prompt


def find_node(prompt, cls, index=0):
    ids = [i for i, n in prompt.items() if n["class_type"] == cls]
    return prompt[ids[index]]


def text_nodes(prompt, ui):
    """(positive, negative) CLIPTextEncode nodes, told apart by the KSampler wiring."""
    sampler = find_node(prompt, "KSampler")
    pos = prompt[sampler["inputs"]["positive"][0]]
    neg = prompt[sampler["inputs"]["negative"][0]]
    return pos, neg


def generate(comfy, prompt, timeout):
    pid = comfy.post_json("/prompt", {"prompt": prompt})["prompt_id"]
    start = time.time()
    while time.time() - start < timeout:
        hist = comfy.get_json(f"/history/{pid}")
        if pid in hist:
            entry = hist[pid]
            if entry.get("status", {}).get("status_str") == "error":
                raise RuntimeError(f"ComfyUI reported an error: {json.dumps(entry['status'])[:1500]}")
            for out in entry.get("outputs", {}).values():
                for img in out.get("images", []):
                    q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                                                "type": img.get("type", "output")})
                    return comfy.get("/view?" + q)
            raise RuntimeError("the workflow finished without an image")
        time.sleep(1.0)
    raise RuntimeError(f"timed out after {timeout} s")


# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="CG ids to generate (default: all)")
    ap.add_argument("--server", default=DEFAULT_SERVER)
    ap.add_argument("--workflow", default=str(DEFAULT_WORKFLOW))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--seed", type=int, default=1000, help="base seed; each CG adds its number (default 1000)")
    ap.add_argument("--variants", type=int, default=1, help="images per CG, with different seeds")
    ap.add_argument("--force", action="store_true", help="regenerate images that already exist")
    ap.add_argument("--list", action="store_true", help="print the prompts and exit")
    ap.add_argument("--timeout", type=int, default=300, help="seconds to wait per image")
    args = ap.parse_args(argv)

    cgs = {k: v for k, v in json.loads((ROOT / "common" / "cgs.json").read_text(encoding="utf-8")).items()
           if not k.startswith("_")}
    wanted = args.ids or list(cgs)
    unknown = [i for i in wanted if i not in cgs]
    if unknown:
        raise SystemExit(f"unknown CG ids: {', '.join(unknown)}")

    if args.list:
        for i in wanted:
            print(f"{i}: {prompt_for(i, cgs[i])}\n")
        return 0

    ui = json.loads(Path(args.workflow).read_text(encoding="utf-8"))
    comfy = Comfy(args.server)
    try:
        object_info = comfy.get_json("/object_info")
    except (urllib.error.URLError, OSError) as e:
        raise SystemExit(f"cannot reach ComfyUI at {args.server}: {e}")
    template = to_api(ui, object_info)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    order = list(cgs)
    made = skipped = failed = 0
    for cg_id in wanted:
        for v in range(args.variants):
            name = f"{cg_id}.png" if args.variants == 1 else f"{cg_id}_v{v + 1}.png"
            path = out / name
            if path.exists() and not args.force:
                print(f"{name}: exists, skipping (--force to redo)")
                skipped += 1
                continue
            prompt = json.loads(json.dumps(template))
            pos, neg = text_nodes(prompt, ui)
            pos["inputs"]["text"] = prompt_for(cg_id, cgs[cg_id])
            neg["inputs"]["text"] = NEGATIVE
            sampler = find_node(prompt, "KSampler")
            sampler["inputs"]["seed"] = args.seed + order.index(cg_id) * 100 + v
            find_node(prompt, "SaveImage")["inputs"]["filename_prefix"] = f"memories/{cg_id}"
            t0 = time.time()
            print(f"{name}: generating ...", end=" ", flush=True)
            try:
                path.write_bytes(generate(comfy, prompt, args.timeout))
            except (RuntimeError, urllib.error.URLError, OSError) as e:
                print(f"FAILED: {e}")
                failed += 1
                continue
            print(f"done in {time.time() - t0:.0f} s")
            made += 1
    print(f"\n{made} generated, {skipped} skipped, {failed} failed; images in {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
