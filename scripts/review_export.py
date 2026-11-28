#!/usr/bin/env python3
"""Human check set (Q6 gate): export 100 bake-off images for a person to label, blind.

export  -> review/<set>/img/<id>.jpg (640 px) + review/<set>/items.json (id, pass, cam, time, light).
           Model labels are NOT written here; they stay in the private HF dataset.
compare -> reads review/<set>/human.json (the person's answers, committed after the check) and the bake-off
           labels from HF, writes review/<set>/report.md (aggregate agreement only).
Env: HF_TOKEN. Trigger: push ops/review-request.json {"mode": "export"|"compare", "set": "..."}.
"""
import io, json, os, random, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "agarg20/conditionsnow-cams"
LABELS = "labels/bakeoff-2026-11-28/pass-v1.1.jsonl"
COLLAPSE = {"bare_dry": "bare", "bare_wet": "bare", "slush": "snow", "partly_snow_covered": "snow",
            "snow_covered": "snow", "ice_visible": "snow", "unknown": "unknown"}


def load_labels(api):
    from huggingface_hub import hf_hub_download
    p = hf_hub_download(REPO, LABELS, repo_type="dataset", token=os.environ["HF_TOKEN"])
    rows = [json.loads(l) for l in open(p) if l.strip()]
    return [r for r in rows if all("reading" in r["models"].get(m, {}) for m in ("opus", "sonnet", "haiku"))]


def export(set_name):
    from huggingface_hub import HfApi, hf_hub_download
    from PIL import Image
    api = HfApi(token=os.environ["HF_TOKEN"])
    rows = load_labels(api)
    rnd = random.Random(11)
    snowy = [r for r in rows if COLLAPSE.get(r["models"]["opus"]["reading"].get("road_surface")) == "snow"
             or COLLAPSE.get(r["models"]["sonnet"]["reading"].get("road_surface")) == "snow"
             or COLLAPSE.get(r["models"]["haiku"]["reading"].get("road_surface")) == "snow"]
    rest = [r for r in rows if r not in snowy]
    rnd.shuffle(snowy); rnd.shuffle(rest)
    want = {"day": 60, "twilight": 15, "night": 25}
    picked = []
    # every image any model called snowy (they are the hard cases), then fill each light bucket
    for r in snowy:
        if len([p for p in picked if p["light"] == r["light"]]) < want[r["light"]]:
            picked.append(r)
    for r in rest:
        if len([p for p in picked if p["light"] == r["light"]]) < want[r["light"]]:
            picked.append(r)
    rnd.shuffle(picked)
    out = os.path.join(ROOT, "review", set_name)
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    items = []
    for i, r in enumerate(picked[:100]):
        local = hf_hub_download(REPO, r["path"], repo_type="dataset", token=os.environ["HF_TOKEN"])
        im = Image.open(local).convert("RGB")
        im.thumbnail((640, 640))
        iid = f"{i + 1:03d}"
        im.save(os.path.join(out, "img", f"{iid}.jpg"), quality=82)
        items.append({"id": iid, "path": r["path"], "pass": r["pass"], "cam": r["cam"], "when": r["when"], "light": r["light"]})
    json.dump(items, open(os.path.join(out, "items.json"), "w"), indent=1)
    print("exported", len(items), Counter(x["light"] for x in items), "snowy candidates", len(snowy))


def compare(set_name):
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ["HF_TOKEN"])
    rows = {r["path"]: r for r in load_labels(api)}
    out = os.path.join(ROOT, "review", set_name)
    items = {x["id"]: x for x in json.load(open(os.path.join(out, "items.json")))}
    human = json.load(open(os.path.join(out, "human.json")))  # {id: {"road": bare|snow|unknown, "usable": ok|no, ...}}
    lines = [f"# Human check {set_name}", "", f"{len(human)} images answered by the owner. Road surface collapsed to bare / snow / can't tell.", ""]
    for light in ("all", "day", "twilight", "night"):
        ids = [i for i in human if i in items and (light == "all" or items[i]["light"] == light)]
        if not ids:
            continue
        lines += [f"## {light} ({len(ids)})", "", "| model | agrees with person | says snow, person bare | says bare, person snow | person sure, model unknown |",
                  "|---|---:|---:|---:|---:|"]
        for m in ("opus", "sonnet", "haiku"):
            agree = fs = ms = unk = 0
            for i in ids:
                h = human[i]["road"]
                g = COLLAPSE.get(rows[items[i]["path"]]["models"][m]["reading"].get("road_surface"), "unknown")
                agree += g == h
                fs += g == "snow" and h == "bare"
                ms += g == "bare" and h == "snow"
                unk += g == "unknown" and h != "unknown"
            lines.append(f"| {m} | {agree}/{len(ids)} ({agree/len(ids):.0%}) | {fs} | {ms} | {unk} |")
        c = Counter(human[i]["road"] for i in ids)
        lines += ["", "Person: " + ", ".join(f"{k} {v}" for k, v in c.most_common()), ""]
    open(os.path.join(out, "report.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    req = json.load(open(os.path.join(ROOT, "ops", "review-request.json")))
    {"export": export, "compare": compare}[req["mode"]](req["set"])
