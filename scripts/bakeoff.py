#!/usr/bin/env python3
"""Labeling bake-off: read the same camera images with Haiku, Sonnet and Opus and compare.

Modes
  count   list how many collected images exist per pass and light bucket (day / twilight / night)
  run     sample N images (stratified by light and pass), label each with every model,
          upload per-image labels to the private HF dataset, write an aggregate summary.

Opus is the reference. For each field we report how often Haiku and Sonnet agree with it,
split by light bucket, plus real token usage and cost from the API's usage numbers.

Env: HF_TOKEN (dataset read/write), ANTHROPIC_API_KEY. Output: docs/bakeoff/<date>-<mode>.md
(aggregates only; per-image labels stay in the private dataset).
"""
import base64
import concurrent.futures as cf
import io
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "agarg20/conditionsnow-cams"
PROMPT_VERSION = "pass-v1"
MODELS = {  # USD per million tokens: input, output, cache read, cache write (5 min); platform.claude.com pricing, 2026-11-27
    "haiku": ("claude-haiku-5-5", 0.10, 0.50, 0.01, 0.125),
    "sonnet": ("claude-sonnet-5-5", 2.00, 10.00, 0.10, 2.50),
    "opus": ("claude-opus-5-5", 4.00, 20.00, 0.20, 5.00),
}
REFERENCE = "opus"
MAX_SIDE = 640  # downscale so every camera costs about the same and matches what a small model sees

# What drivers ask, from the 2026-11-27 search-intent pass: is there snow on the road, is it snowing,
# can you see, is traffic moving, is there a crash, plows / chain-up, closure gates, snow banks, smoke,
# and is the picture even usable. Every field allows "unknown" so the model never has to guess.
FIELDS = {
    "image_usable": ["ok", "dark", "glare", "lens_obstructed", "frozen_or_stale", "offline_placeholder", "not_road_view"],
    "road_surface": ["bare_dry", "bare_wet", "slush", "partly_snow_covered", "snow_covered", "ice_visible", "unknown"],
    "precip_falling": ["none", "rain", "snow", "mixed", "unknown"],
    "visibility": ["good", "reduced", "poor", "unknown"],
    "traffic": ["none_visible", "light", "moderate", "heavy", "stopped", "unknown"],
    "incident_visible": ["none", "crash_or_disabled_vehicle", "emergency_vehicles", "unknown"],
    "plow_or_chainup": ["none", "plow", "chain_up_activity", "unknown"],
    "closure_visible": ["none", "closed_gate_or_barrier", "unknown"],
    "roadside_snow": ["none", "some", "deep", "unknown"],
    "smoke_haze": ["none", "present", "unknown"],
}
SYSTEM = """You read still images from state highway department cameras at mountain passes and report what a driver would want to know.

Rules:
- Report only what is visible in this one image. Never infer from season, location or the time of day.
- If a field cannot be judged from the image, answer "unknown". Unknown is always better than a guess.
- Dark night images: road surface is usually "unknown" unless headlights or lights clearly show it.
- "road_surface" is about the travel lanes, not the shoulders. "partly_snow_covered" = some lane area white/slushy; "snow_covered" = lanes mostly white.
- "bare_wet" = dark, shiny or reflective pavement with no snow on the lanes.
- "frozen_or_stale": the camera's own timestamp overlay is clearly old, or the picture is a stock/placeholder frame.
- "traffic": count only vehicles on the road in view. "stopped" = a queue of vehicles that are clearly not moving.
- Read overlay text if present: the camera's own timestamp and temperature (convert C to F).
- Keep "note" under 15 words, plain language, no speculation.
Call record_reading exactly once."""

TOOL = {
    "name": "record_reading",
    "description": "Record what this camera image shows.",
    "input_schema": {
        "type": "object",
        "properties": {
            **{k: {"type": "string", "enum": v} for k, v in FIELDS.items()},
            "road_surface_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "overlay_timestamp": {"type": ["string", "null"], "description": "Timestamp text shown on the image, as written"},
            "overlay_temp_f": {"type": ["number", "null"], "description": "Temperature shown on the image, in F"},
            "note": {"type": "string"},
        },
        "required": list(FIELDS) + ["road_surface_confidence", "overlay_timestamp", "overlay_temp_f", "note"],
    },
}


# ------------------------------------------------------------------ helpers

def sun_elevation(lat, lon, when):
    """Solar elevation in degrees (NOAA approximation, good to ~0.5 degree)."""
    d = when.timetuple().tm_yday
    hr = when.hour + when.minute / 60
    g = 2 * math.pi / 365 * (d - 1 + (hr - 12) / 24)
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                    - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    tst = hr * 60 + eqt + 4 * lon
    ha = math.radians(tst / 4 - 180)
    la = math.radians(lat)
    cz = math.sin(la) * math.sin(decl) + math.cos(la) * math.cos(decl) * math.cos(ha)
    return 90 - math.degrees(math.acos(max(-1, min(1, cz))))


def bucket(elev):
    return "day" if elev > 6 else ("night" if elev < -6 else "twilight")


def load_passes():
    with open(os.path.join(ROOT, "config", "passes.json")) as f:
        return {p["slug"]: p for p in json.load(f)["ready"]}


def inventory(api, passes):
    """Every collected image with its time, pass and light bucket."""
    rows = []
    for path in api.list_repo_files(REPO, repo_type="dataset"):
        m = re.match(r"raw/(\d{4}-\d{2}-\d{2})/(\d{4})/([^/]+)/(\d+)\.jpg$", path)
        if not m or m.group(3) not in passes:
            continue
        when = datetime.strptime(m.group(1) + m.group(2), "%Y-%m-%d%H%M").replace(tzinfo=timezone.utc)
        p = passes[m.group(3)]
        el = sun_elevation(p["lat"], p["lon"], when)
        rows.append({"path": path, "pass": m.group(3), "cam": int(m.group(4)), "when": when.isoformat(),
                     "sun_elev": round(el, 1), "light": bucket(el)})
    return rows


def sample(rows, n, seed=7):
    """Stratified: ~50% day, ~33% night, ~17% twilight; within each, spread over pass/cam and time."""
    rnd = random.Random(seed)
    want = {"day": n // 2, "night": n // 3}
    want["twilight"] = n - want["day"] - want["night"]
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by[r["light"]][(r["pass"], r["cam"])].append(r)
    picked = []
    for light, k in want.items():
        groups = by[light]
        for g in groups.values():
            rnd.shuffle(g)
        keys = sorted(groups)
        rnd.shuffle(keys)
        got = []
        while len(got) < k and any(groups[x] for x in keys):
            for x in keys:  # round-robin over cameras so no single camera dominates
                if groups[x] and len(got) < k:
                    got.append(groups[x].pop())
        picked += got
    short = n - len(picked)
    if short > 0:  # top up from whatever is left
        left = [r for r in rows if r not in picked]
        rnd.shuffle(left)
        picked += left[:short]
    return picked


def shrink(jpeg_bytes):
    from PIL import Image
    im = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    if max(im.size) > MAX_SIDE:
        im.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue(), im.size


def call(model_id, img_b64, key, retries=4):
    body = {
        "model": model_id, "max_tokens": 400,
        "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        "tools": [TOOL], "tool_choice": {"type": "tool", "name": "record_reading"},
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
            {"type": "text", "text": "Read this camera image."}]}],
    }
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    for attempt in range(retries):
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.loads(r.read())
            reading = next(c["input"] for c in out["content"] if c["type"] == "tool_use")
            return {"reading": reading, "usage": out.get("usage", {}), "secs": round(time.time() - t0, 2)}
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 529) and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            return {"error": f"HTTP {e.code}: {msg}"}
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
                continue
            return {"error": f"{type(e).__name__}: {e}"}


def cost(model, u):
    _, i, o, cr, cw = MODELS[model]
    return (u.get("input_tokens", 0) * i + u.get("output_tokens", 0) * o
            + u.get("cache_read_input_tokens", 0) * cr + u.get("cache_creation_input_tokens", 0) * cw) / 1e6


# ------------------------------------------------------------------ main

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "count"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    from huggingface_hub import HfApi, hf_hub_download
    api = HfApi(token=os.environ["HF_TOKEN"])
    passes = load_passes()
    rows = inventory(api, passes)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    os.makedirs(os.path.join(ROOT, "docs", "bakeoff"), exist_ok=True)
    out_md = os.path.join(ROOT, "docs", "bakeoff", f"{today}-{mode}.md")

    counts = Counter((r["light"]) for r in rows)
    per_pass = defaultdict(Counter)
    for r in rows:
        per_pass[r["pass"]][r["light"]] += 1
    lines = [f"# Bake-off {mode}, {today}", "", f"Collected images: **{len(rows)}** "
             f"(day {counts['day']}, twilight {counts['twilight']}, night {counts['night']})", "",
             "| pass | day | twilight | night |", "|---|---:|---:|---:|"]
    for s in sorted(per_pass):
        c = per_pass[s]
        lines.append(f"| {s} | {c['day']} | {c['twilight']} | {c['night']} |")
    if mode == "count":
        open(out_md, "w").write("\n".join(lines) + "\n")
        print("\n".join(lines))
        return

    key = os.environ["ANTHROPIC_API_KEY"]
    picked = sample(rows, n)
    print(f"sampled {len(picked)}: {Counter(r['light'] for r in picked)}")
    work = []
    for r in picked:
        local = hf_hub_download(REPO, r["path"], repo_type="dataset", token=os.environ["HF_TOKEN"])
        small, size = shrink(open(local, "rb").read())
        r["size"] = size
        work.append((r, base64.b64encode(small).decode()))

    results = []

    def job(item):
        r, b64 = item
        rec = dict(r, prompt=PROMPT_VERSION, models={})
        for m, spec in MODELS.items():
            rec["models"][m] = call(spec[0], b64, key)
        return rec

    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for i, rec in enumerate(ex.map(job, work)):
            results.append(rec)
            if i % 25 == 0:
                print(f"  {i + 1}/{len(work)}", flush=True)

    # per-image labels -> private dataset
    jsonl = "\n".join(json.dumps(x) for x in results) + "\n"
    label_path = f"labels/bakeoff-{today}/{PROMPT_VERSION}.jsonl"
    api.upload_file(path_or_fileobj=jsonl.encode(), path_in_repo=label_path, repo_id=REPO, repo_type="dataset",
                    commit_message=f"bake-off labels {today} ({len(results)} images x {len(MODELS)} models)")

    # aggregates
    lines += ["", f"Sampled **{len(results)}** images: " + ", ".join(
        f"{k} {v}" for k, v in Counter(r["light"] for r in results).items()),
        f"Prompt `{PROMPT_VERSION}`, images downscaled to max {MAX_SIDE}px. Reference model: **{REFERENCE}**.",
        f"Per-image labels: HF dataset `{REPO}` → `{label_path}` (private).", "", "## Cost and speed (from API usage)", "",
        "| model | ok calls | errors | input tok | cache read | output tok | cost | per 1,000 images | median secs |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m in MODELS:
        ok = [x["models"][m] for x in results if "reading" in x["models"][m]]
        err = [x["models"][m]["error"] for x in results if "error" in x["models"][m]]
        u = Counter()
        for x in ok:
            u.update({k: v for k, v in x["usage"].items() if isinstance(v, int)})
        c = sum(cost(m, x["usage"]) for x in ok)
        secs = sorted(x["secs"] for x in ok)
        lines.append(f"| {m} | {len(ok)} | {len(err)} | {u['input_tokens']:,} | {u['cache_read_input_tokens']:,} | "
                     f"{u['output_tokens']:,} | ${c:.2f} | ${(c / max(len(ok), 1)) * 1000:.2f} | "
                     f"{secs[len(secs) // 2] if secs else '-'} |")
        if err:
            lines.append(f"|  | first error: {err[0][:120]} |||||||")

    both = [x for x in results if all("reading" in x["models"][m] for m in MODELS)]
    lines += ["", f"## Agreement with {REFERENCE} ({len(both)} images where all models answered)", "",
              "Exact match on the field's value. `usable-only` = images the reference marked `image_usable: ok`.", ""]
    for light in ("all", "day", "twilight", "night"):
        sub = [x for x in both if light == "all" or x["light"] == light]
        if not sub:
            continue
        lines += [f"### {light} ({len(sub)} images)", "", "| field | " + " | ".join(
            f"{m}" for m in MODELS if m != REFERENCE) + " | " + " | ".join(
            f"{m} usable-only" for m in MODELS if m != REFERENCE) + f" | {REFERENCE} unknown rate |",
            "|---|" + "---:|" * (2 * (len(MODELS) - 1) + 1)]
        usable = [x for x in sub if x["models"][REFERENCE]["reading"].get("image_usable") == "ok"]
        for f in FIELDS:
            cells = []
            for group in (sub, usable):
                for m in MODELS:
                    if m == REFERENCE:
                        continue
                    agree = sum(x["models"][m]["reading"].get(f) == x["models"][REFERENCE]["reading"].get(f) for x in group)
                    cells.append(f"{agree / len(group):.0%}" if group else "-")
            unk = sum(x["models"][REFERENCE]["reading"].get(f) == "unknown" for x in sub) / len(sub)
            lines.append(f"| {f} | " + " | ".join(cells) + f" | {unk:.0%} |")
        lines.append("")

    lines += ["## Reference label distribution (all images)", ""]
    for f in FIELDS:
        c = Counter(x["models"][REFERENCE]["reading"].get(f) for x in both)
        lines.append(f"- **{f}**: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    lines += ["", "## Road surface confusion (rows = opus, columns = sonnet / haiku)", ""]
    for m in MODELS:
        if m == REFERENCE:
            continue
        cats = FIELDS["road_surface"]
        lines += [f"**{m}**", "", "| opus \\ " + m + " | " + " | ".join(cats) + " |", "|---|" + "---:|" * len(cats)]
        for a in cats:
            row = [sum(1 for x in both if x["models"][REFERENCE]["reading"].get("road_surface") == a
                       and x["models"][m]["reading"].get("road_surface") == b) for b in cats]
            if sum(row):
                lines.append(f"| {a} | " + " | ".join(str(v) for v in row) + " |")
        lines.append("")
    temps = [(x["models"][m]["reading"].get("overlay_temp_f"), m) for x in both for m in MODELS]
    lines += [f"Overlay temperature read: " + ", ".join(
        f"{m} {sum(1 for t, mm in temps if mm == m and t is not None)}" for m in MODELS) + " images.", ""]
    open(out_md, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
