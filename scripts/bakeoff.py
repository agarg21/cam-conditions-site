#!/usr/bin/env python3
"""Labeling bake-off: read the same camera images with Haiku, Sonnet and Opus and compare.

Modes
  count   list how many collected images exist per pass and light bucket (day / twilight / night)
  run     sample N images (stratified by light and pass), label each with every model,
          upload per-image labels to the private HF dataset, write an aggregate summary.
  v2test  (Q6a) re-read the bake-off images with prompt v2 (short codes) via the Message Batches API at several
          image sizes and compare with the v1.1 Opus readings; "batches" in the request file collects earlier ids.

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
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "agarg20/conditionsnow-cams"
PROMPT_VERSION = "pass-v1.1"  # v1.1: tool_choice auto + strict tool (5.5 models reject forced tool use)
MODELS = {  # USD per million tokens: input, output, cache read, cache write (5 min); platform.claude.com pricing, 2026-11-27
    "haiku": ("claude-haiku-5-5", 0.10, 0.50, 0.01, 0.125),
    "sonnet": ("claude-sonnet-5-5", 2.00, 10.00, 0.10, 2.50),
    "opus": ("claude-opus-5-5", 4.00, 20.00, 0.20, 5.00),
}
REFERENCE = "opus"
MAX_TOKENS = 2000  # room for any default thinking plus the tool call; stop_reason is recorded
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
            "road_surface_confidence": {"type": "number", "description": "0 to 1"},  # strict tools: no min/max
            "overlay_timestamp": {"type": ["string", "null"], "description": "Timestamp text shown on the image, as written"},
            "overlay_temp_f": {"type": ["number", "null"], "description": "Temperature shown on the image, in F"},
            "note": {"type": "string"},
        },
        "required": list(FIELDS) + ["road_surface_confidence", "overlay_timestamp", "overlay_temp_f", "note"],
        "additionalProperties": False,
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


def shrink(jpeg_bytes, side=None):
    from PIL import Image
    side = side or MAX_SIDE
    im = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    if max(im.size) > side:
        im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue(), im.size


def call(model_id, img_b64, key, retries=4, extra=None):
    """One reading. Claude 5.5 models reject forced tool_choice ("tool"/"any") with HTTP 400, so we use
    tool_choice auto + a strict tool and tell the model to call it. A reply without a tool call, or one cut
    off at max_tokens, is an error (not retried: it would cost the same again)."""
    body = {
        "model": model_id, "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        "tools": [dict(TOOL, strict=True)], "tool_choice": {"type": "auto"},
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
            {"type": "text", "text": "Read this camera image and call record_reading."}]}],
    }
    body.update(extra or {})
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    for attempt in range(retries):
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                out = json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read()[:600].decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 529) and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            return {"error": f"HTTP {e.code}: {msg}"}
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
                continue
            return {"error": f"{type(e).__name__}: {e}"}
        usage, stop = out.get("usage", {}), out.get("stop_reason")
        kinds = [c.get("type") for c in out.get("content", [])]
        base = {"usage": usage, "stop_reason": stop, "blocks": kinds, "secs": round(time.time() - t0, 2)}
        reading = next((c.get("input") for c in out.get("content", []) if c.get("type") == "tool_use"), None)
        if reading is None:
            return dict(base, error=f"no tool call (stop_reason {stop}, blocks {kinds})")
        missing = [k for k in TOOL["input_schema"]["required"] if k not in reading]
        if stop == "max_tokens" or missing:
            return dict(base, error=f"incomplete reading (stop_reason {stop}, missing {missing[:4]})")
        return dict(base, reading=reading)
    return {"error": "retries exhausted"}


def cost(model, u, batch=False):
    _, i, o, cr, cw = MODELS[model]
    full = (u.get("input_tokens", 0) * i + u.get("output_tokens", 0) * o
            + u.get("cache_read_input_tokens", 0) * cr + u.get("cache_creation_input_tokens", 0) * cw) / 1e6
    return full * 0.5 if batch else full  # Message Batches: 50% off every token type


# ------------------------------------------------------------------ prompt v2 (Q6a: short output)

PROMPT_V2 = "pass-v2"
FIELDS_V2 = {  # short keys and codes; the key in brackets is the v1 field it replaces
    "u": ["ok", "dark", "glare", "obst", "stale", "off", "nr"],          # image_usable
    "s": ["bare", "partly", "covered", "ice", "u"],                       # road_surface (collapsed)
    "w": ["y", "n", "u"],                                                 # lanes wet (was bare_wet)
    "f": ["y", "n", "u"],                                                 # snow falling visible (was precip_falling)
    "v": ["good", "reduced", "poor", "u"],                                # visibility
    "t": ["none", "light", "mod", "heavy", "stop", "u"],                  # traffic
    "x": ["none", "crash", "emerg", "u"],                                 # incident_visible
    "p": ["none", "plow", "chain", "u"],                                  # plow_or_chainup
    "c": ["none", "gate", "u"],                                           # closure_visible
    "b": ["none", "some", "deep", "u"],                                   # roadside_snow
}
SYSTEM_V2 = """You read one still image from a state highway department camera at a mountain pass.
Report only what is visible in this image; never infer from season, place or time. If a field cannot be judged,
answer "u" (unknown). Unknown always beats a guess.

Fields and codes:
- u image: ok | dark | glare | obst (lens blocked by snow, ice, water or dirt) | stale (overlay time clearly old, or a stock/placeholder frame) | off (offline placeholder) | nr (not a road view)
- s road surface of the travel lanes, not the shoulders: bare | partly (some lane area white or slushy) | covered (lanes mostly white) | ice (ice clearly visible) | u
- w lanes wet (dark, shiny or reflective pavement): y | n | u
- f snow falling: y (flakes or streaks visible) | n (air looks clear, no flakes or streaks) | u
- v visibility along the road: good | reduced | poor | u. At night answer u unless lights show the road ahead.
- t traffic, vehicles on the road in view: none | light | mod | heavy | stop (a queue clearly not moving) | u
- x incident: none | crash (crash or disabled vehicle) | emerg (emergency vehicles) | u
- p plow or chain-up: none | plow | chain | u
- c closure: none | gate (closed gate or barrier) | u
- b snow beside the road: none | some | deep | u
- k your confidence in s, 0 to 1
- tf temperature shown in the image overlay, in F (convert C), or null if none
Dark night images: s is usually u unless headlights or lights clearly show the lanes.
Call r exactly once. Write no other text."""
TOOL_V2 = {
    "name": "r",
    "description": "Record what this camera image shows.",
    "input_schema": {
        "type": "object",
        "properties": {**{k: {"type": "string", "enum": v} for k, v in FIELDS_V2.items()},
                       "k": {"type": "number"}, "tf": {"type": ["number", "null"]}},
        "required": list(FIELDS_V2) + ["k", "tf"],
        "additionalProperties": False,
    },
}
V2_VARIANTS = {  # name: (model, max side px). Dropped from the end when the projected cost passes the cap.
    "haiku640": ("haiku", 640), "sonnet640": ("sonnet", 640), "sonnet512": ("sonnet", 512), "sonnet448": ("sonnet", 448),
    "opus640": ("opus", 640),
}
API = "https://api.anthropic.com/v1/messages"


def v2_params(model, img_b64):
    return {
        "model": MODELS[model][0], "max_tokens": 1500,
        "system": [{"type": "text", "text": SYSTEM_V2, "cache_control": {"type": "ephemeral"}}],
        "tools": [dict(TOOL_V2, strict=True)], "tool_choice": {"type": "auto"},
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
            {"type": "text", "text": "Read this camera image and call r."}]}],
    }


def http(method, url, key, body=None, raw=False):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = r.read()
            return data if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < 3:
                time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read()[:400].decode('utf-8', 'replace')}")


def parse_msg(out):
    """Message -> {reading} or {error}, with usage. Same checks as call()."""
    usage, stop = out.get("usage", {}), out.get("stop_reason")
    kinds = [c.get("type") for c in out.get("content", [])]
    base = {"usage": usage, "stop_reason": stop, "blocks": kinds}
    reading = next((c.get("input") for c in out.get("content", []) if c.get("type") == "tool_use"), None)
    if reading is None:
        return dict(base, error=f"no tool call (stop_reason {stop}, blocks {kinds})")
    missing = [k for k in TOOL_V2["input_schema"]["required"] if k not in reading]
    if stop == "max_tokens" or missing:
        return dict(base, error=f"incomplete reading (stop_reason {stop}, missing {missing[:4]})")
    return dict(base, reading=reading)


def collapse_v1(rs):
    if rs in ("bare_dry", "bare_wet"):
        return "bare"
    if rs in ("slush", "partly_snow_covered", "snow_covered", "ice_visible"):
        return "snow"
    return "unknown"


def collapse_v2(s):
    return {"bare": "bare", "partly": "snow", "covered": "snow", "ice": "snow"}.get(s, "unknown")


V2_TO_V1 = {  # v2 code -> v1 value, per field, for agreement with the v1.1 Opus reference
    "u": ("image_usable", {"obst": "lens_obstructed", "stale": "frozen_or_stale", "off": "offline_placeholder",
                           "nr": "not_road_view"}),
    "v": ("visibility", {"u": "unknown"}),
    "t": ("traffic", {"none": "none_visible", "mod": "moderate", "stop": "stopped", "u": "unknown"}),
    "b": ("roadside_snow", {"u": "unknown"}),
    "x": ("incident_visible", {"crash": "crash_or_disabled_vehicle", "emerg": "emergency_vehicles", "u": "unknown"}),
    "p": ("plow_or_chainup", {"chain": "chain_up_activity", "u": "unknown"}),
    "c": ("closure_visible", {"gate": "closed_gate_or_barrier", "u": "unknown"}),
}


def v2test(req, key, api, hf_hub_download, lines, out_md, today):
    """Q6a: re-read the 300 bake-off images with prompt v2 (short codes) through the Message Batches API at
    640/512/448 px (Sonnet) and 640 px (Haiku); compare with the v1.1 Opus readings; simulate a Haiku cascade.
    Spend: a 4-image sync probe measures tokens, the batch is sized to stay under max_usd."""
    max_usd = float(req.get("max_usd", 3.0))
    src = req.get("labels", "labels/bakeoff-2026-11-28/pass-v1.1.jsonl")
    ref = [json.loads(x) for x in open(hf_hub_download(REPO, src, repo_type="dataset",
                                                         token=os.environ["HF_TOKEN"])) if x.strip()]
    ref = [r for r in ref if "reading" in r["models"].get(REFERENCE, {})]
    n = len(ref)
    raw = {}
    for r in ref:
        raw[r["path"]] = open(hf_hub_download(REPO, r["path"], repo_type="dataset", token=os.environ["HF_TOKEN"]), "rb").read()
    spent = 0.0
    state_path = os.path.join(ROOT, "docs", "bakeoff", f"{today}-v2test-batches.json")
    batches = req.get("batches") or {}
    probe_rows = []
    want = [v for v in req.get("variants", list(V2_VARIANTS)[:4]) if v in V2_VARIANTS]
    if not batches:
        # 1. sync probe: 2 day + 2 night images per model, to measure real output tokens
        pick = [r for r in ref if r["light"] == "day"][:2] + [r for r in ref if r["light"] == "night"][:2]
        per_img = defaultdict(list)
        for r in pick:
            for m in sorted({V2_VARIANTS[v][0] for v in want}):
                b64 = base64.b64encode(shrink(raw[r["path"]], 640)[0]).decode()
                try:
                    res = parse_msg(http("POST", API, key, v2_params(m, b64)))
                except RuntimeError as e:
                    res = {"error": str(e), "usage": {}}
                c = cost(m, res.get("usage", {}))
                spent += c
                u = res.get("usage", {})
                probe_rows.append((m, r["light"], "reading" in res, u.get("input_tokens", 0),
                                   u.get("cache_read_input_tokens", 0), u.get("output_tokens", 0), c,
                                   res.get("error", "")[:200]))
                if "reading" in res and req.get("assume_cache"):  # batch caching held in the first v2 test
                    per_img[m].append(cost(m, u, batch=True))
                elif "reading" in res:
                    # conservative projection: charge cache reads as fresh input (batch caching is best effort)
                    uu = dict(u, input_tokens=u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                              + u.get("cache_creation_input_tokens", 0), cache_read_input_tokens=0,
                              cache_creation_input_tokens=0)
                    per_img[m].append(cost(m, uu, batch=True))
        if any(not per_img[V2_VARIANTS[v][0]] for v in want):
            lines += ["", "## v2 probe failed: a model gave no reading; nothing submitted", ""] + [str(x) for x in probe_rows]
            open(out_md, "w").write("\n".join(lines) + "\n")
            print("\n".join(lines))
            return
        est = {m: max(v) * 1.15 for m, v in per_img.items()}  # worst probe image + 15%
        variants = {v: V2_VARIANTS[v] for v in want}
        while len(variants) > 1 and spent + sum(est[m] * n for m, _ in variants.values()) > max_usd:
            variants.popitem()
        per = sum(est[m] for m, _ in variants.values())
        if spent + per * n > max_usd and (max_usd - spent) / per >= 150:  # one variant left: sample fewer images
            n = int((max_usd - spent) / per)
            ref = random.Random(5).sample(ref, n)
        elif spent + per * n > max_usd:
            variants = {}
        if not variants:
            lines += ["", f"## v2: projected cost over cap ${max_usd}; nothing submitted", ""]
            open(out_md, "w").write("\n".join(lines) + "\n")
            return
        for name, (m, side) in variants.items():
            reqs = [{"custom_id": f"{name}-{i}", "params": v2_params(
                m, base64.b64encode(shrink(raw[r["path"]], side)[0]).decode())} for i, r in enumerate(ref)]
            b = http("POST", API + "/batches", key, {"requests": reqs})
            batches[name] = b["id"]
            print(f"submitted {name}: {b['id']} ({len(reqs)} requests)", flush=True)
        json.dump({"batches": batches, "n": n, "paths": [r["path"] for r in ref], "probe_usd": round(spent, 4),
                   "submitted": today}, open(state_path, "w"))
    elif os.path.exists(state_path):  # collect run: same image subset as the submit run
        keep = json.load(open(state_path)).get("paths")
        if keep:
            byp = {r["path"]: r for r in ref}
            ref = [byp[p] for p in keep if p in byp]
            n = len(ref)
    # 2. poll (up to ~140 min); if not done, leave the ids for a later collect run
    deadline = time.time() + float(req.get("poll_minutes", 140)) * 60
    status = {}
    while True:
        status = {k: http("GET", f"{API}/batches/{v}", key) for k, v in batches.items()}
        if all(s.get("processing_status") == "ended" for s in status.values()):
            break
        if time.time() > deadline:
            lines += ["", "## v2 batches still processing; re-push ops/bakeoff-request.json with these ids to collect", "",
                      json.dumps(batches), ""]
            open(out_md, "w").write("\n".join(lines) + "\n")
            print("\n".join(lines))
            return
        print("waiting:", {k: s.get("request_counts") for k, s in status.items()}, flush=True)
        time.sleep(60)
    # 3. results
    got = defaultdict(dict)  # variant -> idx -> parsed
    for name, s in status.items():
        body = http("GET", s["results_url"], key, raw=True).decode()
        for line in body.splitlines():
            if not line.strip():
                continue
            x = json.loads(line)
            idx = int(x["custom_id"].rsplit("-", 1)[1])
            res = x.get("result", {})
            got[name][idx] = parse_msg(res["message"]) if res.get("type") == "succeeded" else \
                {"error": json.dumps(res)[:300], "usage": {}}
    variants = list(batches)
    if req.get("merge"):  # earlier v2 test labels for the same images (by path): compare against them too
        idx = {r["path"]: i for i, r in enumerate(ref)}
        for x in open(hf_hub_download(REPO, req["merge"], repo_type="dataset", token=os.environ["HF_TOKEN"])):
            if x.strip():
                rec = json.loads(x)
                if rec["path"] in idx:
                    for v, val in rec["v2"].items():
                        if v not in batches:
                            got[v][idx[rec["path"]]] = val
        variants = list(batches) + sorted(v for v in got if v not in batches)
    out = []
    for i, r in enumerate(ref):
        out.append({"path": r["path"], "pass": r["pass"], "cam": r["cam"], "when": r["when"], "light": r["light"],
                    "prompt": PROMPT_V2, "batch": True, "v2": {v: got[v].get(i, {"error": "missing"}) for v in batches}})
    label_path = f"labels/bakeoff-{today}/{PROMPT_V2}-test{req.get('tag', '')}.jsonl"
    api.upload_file(path_or_fileobj=("\n".join(json.dumps(x) for x in out) + "\n").encode(), path_in_repo=label_path,
                    repo_id=REPO, repo_type="dataset", commit_message=f"v2 test labels {today} ({len(out)} images)")

    def opus(i):
        return ref[i]["models"][REFERENCE]["reading"]

    def v1(i, m):
        return ref[i]["models"].get(m, {}).get("reading")

    batch_usd = {v: sum(cost(V2_VARIANTS[v][0], got[v][i].get("usage", {}), batch=True) for i in got[v]) for v in variants}
    spent_total = spent + sum(batch_usd[v] for v in batches)
    if not probe_rows:  # collect run: the probe was paid by the submit run
        try:
            spent_total += json.load(open(state_path)).get("probe_usd", 0)
        except (OSError, ValueError):
            pass
    lines += ["", f"## Prompt v2 test ({PROMPT_V2}, Message Batches), {n} bake-off images", "",
              f"Reference: v1.1 Opus readings (`{src}`). Per-image v2 labels: `{label_path}` (private).",
              f"Batches: `{json.dumps(batches)}`. Spend this test: **${spent_total:.2f}** (cap ${max_usd:.2f}; "
              f"probe ${spent:.3f}, batches ${sum(batch_usd[v] for v in batches):.2f}). Variants from earlier runs "
              f"(costs shown but not counted here): {', '.join(v for v in variants if v not in batches) or 'none'}.", ""]
    if probe_rows:
        lines += ["Sync probe (prompt v2, 640 px):", "", "| model | light | ok | in tok | cache read | out tok | cost | error |",
                  "|---|---|---|---:|---:|---:|---:|---|"]
        lines += [f"| {a} | {b} | {'yes' if c else 'no'} | {d:,} | {e:,} | {f:,} | ${g:.4f} | {h.replace('|', '/')} |"
                  for a, b, c, d, e, f, g, h in probe_rows] + [""]
    lines += ["### Cost (batch prices, from usage)", "",
              "| variant | ok | errors | input tok | cache read | output tok | out tok / image | cost | per 1,000 images |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for v in variants:
        ok = [got[v][i] for i in got[v] if "reading" in got[v][i]]
        u = Counter()
        for x in ok:
            u.update({k: val for k, val in x["usage"].items() if isinstance(val, int)})
        errs = [got[v][i]["error"] for i in got[v] if "error" in got[v][i]]
        lines.append(f"| {v} | {len(ok)} | {len(errs)} | {u['input_tokens']:,} | {u['cache_read_input_tokens']:,} | "
                     f"{u['output_tokens']:,} | {u['output_tokens'] / max(len(ok), 1):.0f} | ${batch_usd[v]:.2f} | "
                     f"${batch_usd[v] / max(len(ok), 1) * 1000:.2f} |")
        if errs:
            lines.append(f"|  | first error: {errs[0][:120].replace('|', '/')} ||||||||")
    lines += ["", "v1.1 sync for comparison: Sonnet $5.98 and Haiku $0.47 per 1,000; Sonnet 529 output tokens per image.", ""]

    def rd(v, i):
        return got[v].get(i, {}).get("reading")

    lines += ["### Road surface, collapsed (bare / snow / unknown), agreement with v1.1 Opus", "",
              "| reader | all | day | twilight | night | snow on Opus-bare | missed snow (Opus snow -> bare) | unknown rate |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    opus_c = [collapse_v1(opus(i).get("road_surface")) for i in range(n)]
    readers = {f"{v} (v2)": [collapse_v2(rd(v, i)["s"]) if rd(v, i) else None for i in range(n)] for v in variants}
    for m in ("sonnet", "haiku"):
        readers[f"{m} v1.1 sync"] = [collapse_v1(v1(i, m).get("road_surface")) if v1(i, m) else None for i in range(n)]
    if "haiku640" in variants and "sonnet640" in variants:  # cascade: keep Haiku "bare", send the rest to Sonnet
        readers["cascade haiku640 bare + sonnet640"] = [
            (h if h == "bare" else s) if h and s else None
            for h, s in zip(readers["haiku640 (v2)"], readers["sonnet640 (v2)"])]
        sent = sum(1 for h in readers["haiku640 (v2)"] if h != "bare")
        lines_cascade = f"Cascade sends {sent}/{n} images ({sent / n:.0%}) to Sonnet."
    else:
        lines_cascade = ""
    for name, vals in readers.items():
        cells = []
        for light in ("all", "day", "twilight", "night"):
            idx = [i for i in range(n) if vals[i] is not None and (light == "all" or ref[i]["light"] == light)]
            cells.append(f"{sum(vals[i] == opus_c[i] for i in idx) / len(idx):.0%} ({len(idx)})" if idx else "-")
        ob = [i for i in range(n) if vals[i] is not None and opus_c[i] == "bare"]
        os_ = [i for i in range(n) if vals[i] is not None and opus_c[i] == "snow"]
        fs = sum(vals[i] == "snow" for i in ob)
        ms = sum(vals[i] == "bare" for i in os_)
        un = sum(1 for x in vals if x == "unknown") / max(sum(1 for x in vals if x is not None), 1)
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {fs}/{len(ob)} | {ms}/{len(os_)} | {un:.0%} |")
    if "opus640" in variants:
        lines += ["", "#### Same table with **Opus v2** (opus640) as the reference", "",
                  "| reader | all | day | twilight | night | snow on Opus-bare | missed snow | unknown rate |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        o2 = [collapse_v2(rd("opus640", i)["s"]) if rd("opus640", i) else None for i in range(n)]
        for name, vals in readers.items():
            if name.startswith("opus640"):
                continue
            cells = []
            for light in ("all", "day", "twilight", "night"):
                idx = [i for i in range(n) if vals[i] and o2[i] and (light == "all" or ref[i]["light"] == light)]
                cells.append(f"{sum(vals[i] == o2[i] for i in idx) / len(idx):.0%} ({len(idx)})" if idx else "-")
            ob = [i for i in range(n) if vals[i] and o2[i] == "bare"]
            os_ = [i for i in range(n) if vals[i] and o2[i] == "snow"]
            un = sum(1 for x in vals if x == "unknown") / max(sum(1 for x in vals if x is not None), 1)
            lines.append(f"| {name} | " + " | ".join(cells) + f" | {sum(vals[i] == 'snow' for i in ob)}/{len(ob)} | "
                         f"{sum(vals[i] == 'bare' for i in os_)}/{len(os_)} | {un:.0%} |")
        lines.append("Opus v2 collapsed: " + ", ".join(f"{k} {v}" for k, v in Counter(x for x in o2 if x).most_common()) + ".")
    lines += ["", f"Opus v1.1 collapsed: " + ", ".join(f"{k} {v}" for k, v in Counter(opus_c).most_common()) + ". "
              + lines_cascade, ""]

    lines += ["### Other fields vs v1.1 Opus (exact, mapped to v1 values; day in brackets)", "",
              "| field | " + " | ".join(variants) + " |", "|---|" + "---:|" * len(variants)]
    day = [i for i in range(n) if ref[i]["light"] == "day"]
    for code, (f, mp) in V2_TO_V1.items():
        cells = []
        for v in variants:
            def agree(idx):
                ok = [i for i in idx if rd(v, i)]
                return sum(mp.get(rd(v, i)[code], rd(v, i)[code]) == opus(i).get(f) for i in ok) / max(len(ok), 1)
            cells.append(f"{agree(range(n)):.0%} [{agree(day):.0%}]")
        lines.append(f"| {f} ({code}) | " + " | ".join(cells) + " |")
    # wet vs Opus bare_wet/bare_dry; snow falling vs Opus precip
    for code, label, ref_map in (("w", "wet (w) on Opus-bare lanes", {"bare_wet": "y", "bare_dry": "n"}),):
        cells = []
        for v in variants:
            idx = [i for i in range(n) if rd(v, i) and opus(i).get("road_surface") in ref_map]
            cells.append(f"{sum(rd(v, i)[code] == ref_map[opus(i)['road_surface']] for i in idx) / max(len(idx), 1):.0%} ({len(idx)})")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines += ["", "### Snow falling (f): unknown rate, and vs Opus precip (snow/mixed = y, none/rain = n)", "",
              "| variant | y | n | u | unknown rate day | agrees where Opus judged |", "|---|---:|---:|---:|---:|---:|"]
    pm = {"snow": "y", "mixed": "y", "none": "n", "rain": "n"}
    for v in variants:
        c = Counter(rd(v, i)["f"] for i in range(n) if rd(v, i))
        ud = [i for i in day if rd(v, i)]
        judged = [i for i in range(n) if rd(v, i) and opus(i).get("precip_falling") in pm]
        lines.append(f"| {v} | {c['y']} | {c['n']} | {c['u']} | "
                     f"{sum(rd(v, i)['f'] == 'u' for i in ud) / max(len(ud), 1):.0%} | "
                     f"{sum(rd(v, i)['f'] == pm[opus(i)['precip_falling']] for i in judged) / max(len(judged), 1):.0%} ({len(judged)}) |")
    lines += ["", "Opus v1.1 precip_falling was unknown on 67% of images (59% of daytime).", ""]
    open(out_md, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


def run_batches(key, batches, deadline):
    """Poll until every batch ended or the deadline passes. Returns {name: status} or None on timeout."""
    while True:
        status = {k: http("GET", f"{API}/batches/{v}", key) for k, v in batches.items()}
        if all(x.get("processing_status") == "ended" for x in status.values()):
            return status
        if time.time() > deadline:
            return None
        print("waiting:", {k: x.get("request_counts") for k, x in status.items()}, flush=True)
        time.sleep(60)


def batch_results(key, status):
    got = defaultdict(dict)
    for name, st in status.items():
        for line in http("GET", st["results_url"], key, raw=True).decode().splitlines():
            if line.strip():
                x = json.loads(line)
                res = x.get("result", {})
                got[name][x["custom_id"]] = parse_msg(res["message"]) if res.get("type") == "succeeded" else \
                    {"error": json.dumps(res)[:300], "usage": {}}
    return got


def label(req, key, api, rows, hf_hub_download, lines, out_md, today):
    """D8 labeling job (Q6a): prompt v2 via Message Batches on day + twilight images not labeled before and not in
    the bake-off set (kept as the eval set), spread round-robin over cameras; a random audit share also goes to
    Opus. Per-image labels -> private HF labels/train/; spend -> docs/bakeoff/label-ledger.json (aggregate)."""
    model, side = req.get("model", "sonnet"), int(req.get("side", 640))
    audit, n, cap = float(req.get("audit", 0.1)), int(req.get("n", 1000)), float(req.get("max_usd", 10))
    lights = set(req.get("lights", ["day", "twilight"]))
    ledger_path = os.path.join(ROOT, "docs", "bakeoff", "label-ledger.json")
    try:
        ledger = json.load(open(ledger_path))
    except (OSError, ValueError):
        ledger = {"budget_usd": 40.0, "spent_usd": 0.0, "images": 0, "jobs": []}
    room = ledger["budget_usd"] - ledger["spent_usd"]
    cap = min(cap, room)
    done = set()
    for f in api.list_repo_files(REPO, repo_type="dataset"):
        if f.startswith("labels/") and f.endswith(".jsonl"):
            for x in open(hf_hub_download(REPO, f, repo_type="dataset", token=os.environ["HF_TOKEN"])):
                if x.strip():
                    done.add(json.loads(x).get("path"))
    pool = [r for r in rows if r["light"] in lights and r["path"] not in done]
    by = defaultdict(list)
    for r in pool:
        by[(r["pass"], r["cam"])].append(r)
    rnd = random.Random(int(req.get("seed", 11)))
    for g in by.values():
        rnd.shuffle(g)
    picked = []
    while len(picked) < n and any(by.values()):
        for k in sorted(by):
            if by[k] and len(picked) < n:
                picked.append(by[k].pop())
    est_per = float(req.get("est_usd_per_image", 0.003))  # from the v2 test; Opus ~2x Sonnet
    n_audit = int(len(picked) * audit)
    projected = len(picked) * est_per + n_audit * est_per * 2
    lines += ["", f"## Labeling job {today}: {model} {side}px, prompt {PROMPT_V2}, Message Batches", "",
              f"Pool: {len(pool)} unlabeled {'/'.join(sorted(lights))} images over {len(by)} cameras; picked {len(picked)}; "
              f"audit {n_audit} with Opus. Projected ${projected:.2f}; cap ${cap:.2f} (D8 ledger: ${ledger['spent_usd']:.2f} "
              f"of ${ledger['budget_usd']:.0f} spent)."]
    if not picked or projected > cap:
        lines += ["", "Nothing submitted (empty pool or projected cost over cap).", ""]
        open(out_md, "w").write("\n".join(lines) + "\n")
        print("\n".join(lines))
        return
    imgs, bad = [], 0
    for r in picked:
        try:
            imgs.append((r, base64.b64encode(shrink(open(hf_hub_download(REPO, r["path"], repo_type="dataset",
                         token=os.environ["HF_TOKEN"]), "rb").read(), side)[0]).decode()))
        except Exception as e:  # truncated or non-image file in the dataset: skip it, count it
            bad += 1
            print("skip", r["path"], type(e).__name__, flush=True)
    picked = [r for r, _ in imgs]
    n_audit = int(len(picked) * audit)
    lines.append(f"Skipped {bad} undecodable image files.")
    audit_idx = set(rnd.sample(range(len(picked)), n_audit))
    reqs = {model: [], "opus": []}
    for i, (r, b64) in enumerate(imgs):
        reqs[model].append({"custom_id": f"m-{i}", "params": v2_params(model, b64)})
        if i in audit_idx:
            reqs["opus"].append({"custom_id": f"a-{i}", "params": v2_params("opus", b64)})
    batches = {}
    for name, rq in reqs.items():
        for j in range(0, len(rq), 1000):  # keep each request body well under the 256 MB batch limit
            batches[f"{name}-{j // 1000}"] = http("POST", API + "/batches", key, {"requests": rq[j:j + 1000]})["id"]
    print("submitted", batches, flush=True)
    status = run_batches(key, batches, time.time() + float(req.get("poll_minutes", 140)) * 60)
    if status is None:
        lines += ["", "Batches still processing (ids below); cost not yet recorded. Collect in a later run.", "",
                  json.dumps(batches), ""]
        ledger["jobs"].append({"date": today, "batches": batches, "pending": True, "projected_usd": round(projected, 2)})
        json.dump(ledger, open(ledger_path, "w"), indent=1)
        open(out_md, "w").write("\n".join(lines) + "\n")
        return
    got = batch_results(key, status)
    res = {}
    for name, d in got.items():
        res.update(d)
    usd = {"main": sum(cost(model, res[k].get("usage", {}), batch=True) for k in res if k.startswith("m-")),
           "audit": sum(cost("opus", res[k].get("usage", {}), batch=True) for k in res if k.startswith("a-"))}
    out = []
    for i, r in enumerate(picked):
        rec = dict(r, prompt=PROMPT_V2, model=model, side=side, batch=True, reading=res.get(f"m-{i}", {}).get("reading"),
                   error=res.get(f"m-{i}", {}).get("error"))
        if i in audit_idx:
            rec["audit_opus"] = res.get(f"a-{i}", {}).get("reading")
        out.append(rec)
    ok = sum(1 for x in out if x["reading"])
    label_path = f"labels/train/{today}-{model}{side}-{len(out)}.jsonl"
    api.upload_file(path_or_fileobj=("\n".join(json.dumps(x) for x in out) + "\n").encode(), path_in_repo=label_path,
                    repo_id=REPO, repo_type="dataset", commit_message=f"training labels {today} ({ok} images)")
    total = usd["main"] + usd["audit"]
    ledger["spent_usd"] = round(ledger["spent_usd"] + total, 4)
    ledger["images"] += ok
    ledger["jobs"].append({"date": today, "model": model, "side": side, "images_ok": ok, "audit": n_audit,
                           "usd_main": round(usd["main"], 4), "usd_audit": round(usd["audit"], 4), "batches": batches})
    json.dump(ledger, open(ledger_path, "w"), indent=1)
    aud = [x for x in out if x.get("audit_opus") and x["reading"]]
    agree = sum(collapse_v2(x["reading"]["s"]) == collapse_v2(x["audit_opus"]["s"]) for x in aud)
    surf = Counter(collapse_v2(x["reading"]["s"]) for x in out if x["reading"])
    lines += [f"Labelled **{ok}** of {len(out)} ({len(out) - ok} errors) -> `{label_path}` (private).",
              f"Cost: {model} ${usd['main']:.2f} (${usd['main'] / max(ok, 1) * 1000:.2f} per 1,000), Opus audit "
              f"${usd['audit']:.2f}; total **${total:.2f}**. D8 ledger now ${ledger['spent_usd']:.2f} of $40.",
              f"Opus audit, road surface collapsed: {agree}/{len(aud)} agree" + (f" ({agree / len(aud):.0%})." if aud else "."),
              "Road surface (collapsed): " + ", ".join(f"{k} {v}" for k, v in surf.most_common()) + ".", ""]
    open(out_md, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


# ------------------------------------------------------------------ main

def probe(rows, key, lines, out_md, hf_hub_download):
    """Tiny API check before a full run: 1 day + 1 night image x every model x two request variants.
    Writes only call metadata (stop reason, block types, tokens, cost, error text), never label values."""
    variants = {"default": {}, "effort-low": {"output_config": {"effort": "low"}}}
    pick = []
    for light in ("day", "night"):
        cand = [r for r in rows if r["light"] == light]
        if cand:
            pick.append(random.Random(3).choice(cand))
    lines += ["", f"## Probe ({len(pick)} images: " + ", ".join(r["light"] for r in pick) + ")", "",
              "| variant | model | light | ok | stop | blocks | in tok | cache read | out tok | cost | secs | error |",
              "|---|---|---|---|---|---|---:|---:|---:|---:|---:|---|"]
    total = 0.0
    for r in pick:
        local = hf_hub_download(REPO, r["path"], repo_type="dataset", token=os.environ["HF_TOKEN"])
        b64 = base64.b64encode(shrink(open(local, "rb").read())[0]).decode()
        for vname, extra in variants.items():
            for m, spec in MODELS.items():
                res = call(spec[0], b64, key, retries=2, extra=extra)
                u = res.get("usage", {})
                c = cost(m, u)
                total += c
                err = res.get("error", "").replace("|", "/").replace("\n", " ")[:400]
                lines.append(f"| {vname} | {m} | {r['light']} | {'yes' if 'reading' in res else 'no'} | "
                             f"{res.get('stop_reason', '-')} | {','.join(res.get('blocks', [])) or '-'} | "
                             f"{u.get('input_tokens', 0):,} | {u.get('cache_read_input_tokens', 0):,} | "
                             f"{u.get('output_tokens', 0):,} | ${c:.4f} | {res.get('secs', '-')} | {err} |")
    lines += ["", f"Probe API spend: **${total:.3f}**", ""]
    open(out_md, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))



# ------------------------------------------------------------------ prompt v3 (owner check: roadside snow != lane snow)

PROMPT_V3 = "pass-v3"
FIELDS_V3 = {"b": FIELDS_V2["b"], **{k: v for k, v in FIELDS_V2.items() if k != "b"}}  # roadside first, then lanes
SYSTEM_V3 = SYSTEM_V2.replace(
    "- s road surface of the travel lanes, not the shoulders: bare | partly (some lane area white or slushy) | covered (lanes mostly white) | ice (ice clearly visible) | u",
    "- s road surface of the travel lanes ONLY: judge the pavement between the lane lines and the wheel tracks. Snow on\n"
    "  shoulders, banks, medians, guardrails, signs or the ground beside the road does NOT count, however deep (that is b).\n"
    "  White paint, salt or sand residue, and wet pavement shining in sun, glare or headlights are not snow.\n"
    "  bare | partly (snow, slush or ice visible in the lanes or wheel tracks themselves) | covered (lanes mostly white) | ice (ice clearly visible) | u",
).replace("- b snow beside the road: none | some | deep | u\n", "")
SYSTEM_V3 = SYSTEM_V3.replace("Fields and codes:\n", "Fields and codes (answer b first, then judge the lanes separately):\n- b snow beside the road: none | some | deep | u\n")
assert "ONLY" in SYSTEM_V3 and SYSTEM_V3.count("- b snow beside") == 1
TOOL_V3 = dict(TOOL_V2, input_schema=dict(TOOL_V2["input_schema"],
    properties={**{k: {"type": "string", "enum": v} for k, v in FIELDS_V3.items()}, "k": {"type": "number"},
                "tf": {"type": ["number", "null"]}},
    required=list(FIELDS_V3) + ["k", "tf"]))


def v3_params(model, img_b64):
    p = v2_params(model, img_b64)
    p["system"] = [{"type": "text", "text": SYSTEM_V3, "cache_control": {"type": "ephemeral"}}]
    p["tools"] = [dict(TOOL_V3, strict=True)]
    return p


# ------------------------------------------------------------------ prompt v4 (owner: read the road from the center line)

PROMPT_V4 = "pass-v4"
FIELDS_V4 = {"cl": ["vis", "part", "hid", "none", "u"], **FIELDS_V3}
SYSTEM_V4 = SYSTEM_V2.replace(
    "- s road surface of the travel lanes, not the shoulders: bare | partly (some lane area white or slushy) | covered (lanes mostly white) | ice (ice clearly visible) | u",
    "- s road surface: judge the pavement within about one car width either side of the center line; if there is no center\n"
    "  line, the strip where vehicles drive. Ignore shoulders and anything beside the road.\n"
    "  bare | partly (snow, slush or ice on that pavement) | covered (mostly white) | ice (ice clearly visible) | u.\n"
    "  If cl is hid, s cannot be bare.",
).replace("- b snow beside the road: none | some | deep | u\n", "").replace(
    "Fields and codes:\n",
    "Fields and codes (answer cl first, then b, then the rest):\n"
    "- cl center line, the painted line between the two directions (usually the clearest mark on the road):\n"
    "  vis (clearly visible) | part (partly hidden by snow or slush) | hid (hidden under snow) | none (no center line in view) | u\n"
    "- b snow beside the road: none | some | deep | u\n")
assert SYSTEM_V4.count("- cl center") == 1 and SYSTEM_V4.count("- b snow beside") == 1 and "If cl is hid" in SYSTEM_V4
TOOL_V4 = dict(TOOL_V2, input_schema=dict(TOOL_V2["input_schema"],
    properties={**{k: {"type": "string", "enum": v} for k, v in FIELDS_V4.items()}, "k": {"type": "number"},
                "tf": {"type": ["number", "null"]}},
    required=list(FIELDS_V4) + ["k", "tf"]))


def v4_params(model, img_b64):
    p = v2_params(model, img_b64)
    p["system"] = [{"type": "text", "text": SYSTEM_V4, "cache_control": {"type": "ephemeral"}}]
    p["tools"] = [dict(TOOL_V4, strict=True)]
    return p


def humantest(req, key, hf_hub_download, lines, out_md, today):
    """Owner check re-test: Sonnet prompt v2 vs v3 on the owner's answered review set, via Message Batches.
    Per-image readings -> private HF labels/humancheck/; aggregates only -> docs/bakeoff."""
    set_name = req.get("set", "2026-11-28")
    model = req.get("model", "sonnet")
    rdir = os.path.join(ROOT, "review", set_name)
    items = {x["id"]: x for x in json.load(open(os.path.join(rdir, "items.json")))}
    human = json.load(open(os.path.join(rdir, "human.json")))
    ids = sorted(i for i in human if i in items)
    builders = {"v2": v2_params, "v3": v3_params, "v4": v4_params}
    pv = req.get("prompts", ["v2", "v3"])
    reqs = {v: [] for v in pv}
    for i in ids:
        local = hf_hub_download(REPO, items[i]["path"], repo_type="dataset", token=os.environ["HF_TOKEN"])
        b64 = base64.b64encode(shrink(open(local, "rb").read())[0]).decode()
        for v in pv:
            reqs[v].append({"custom_id": f"h-{i}", "params": builders[v](model, b64)})
    batches = {k: http("POST", f"{API}/batches", key, {"requests": v})["id"] for k, v in reqs.items()}
    status = run_batches(key, batches, time.time() + 60 * float(req.get("poll_minutes", 120)))
    if status is None:
        lines += ["", f"## Human-check re-test: batches did not finish in time: {batches}", ""]
        open(out_md, "w").write("\n".join(lines) + "\n")
        return
    got = batch_results(key, status)
    usd = sum(cost(model, r.get("usage", {}), batch=True) for v in got.values() for r in v.values())
    lp = os.path.join(ROOT, "docs", "bakeoff", "label-ledger.json")
    if os.path.exists(lp):
        led = json.load(open(lp))
        led["spent_usd"] = round(led["spent_usd"] + usd, 4)
        led["jobs"].append({"date": today, "kind": "eval", "note": f"human-check re-test {'+'.join(pv)}, {set_name}", "usd": round(usd, 4)})
        json.dump(led, open(lp, "w"), indent=1)
    # per-image readings stay private
    import tempfile
    tmp = os.path.join(tempfile.mkdtemp(), "h.jsonl")
    with open(tmp, "w") as f:
        for i in ids:
            f.write(json.dumps({"id": i, "path": items[i]["path"], "light": items[i]["light"], "human": human[i],
                                **{v: got[v].get(f"h-{i}", {}) for v in pv}}) + "\n")
    from huggingface_hub import HfApi
    HfApi(token=os.environ["HF_TOKEN"]).upload_file(path_or_fileobj=tmp, repo_id=REPO, repo_type="dataset",
        path_in_repo=f"labels/humancheck/{set_name}-{model}-{''.join(pv)}.jsonl", commit_message="human-check re-test")

    def rd(v, i):
        return got[v].get(f"h-{i}", {}).get("reading") or {}

    def g(v, i, kmin=0.0):
        r = rd(v, i)
        if not r:
            return "error"
        c = collapse_v2(r.get("s"))
        return c if (c == "unknown" or float(r.get("k") or 0) >= kmin) else "unknown"

    errs = {v: sum(1 for i in ids if not rd(v, i)) for v in got}
    lines += ["", f"## Human-check re-test {today}: {model}, prompts {', '.join(pv)}, set {set_name}", "",
              f"{len(ids)} images the owner answered. Cost ${usd:.2f} (Message Batches). Failed readings: {errs}.", "",
              "| light | prompt | agrees (person sure) | says snow, person bare | says bare, person snow | model unknown, person sure |",
              "|---|---|---:|---:|---:|---:|"]
    for light in ("day", "twilight", "night"):
        sure = [i for i in ids if items[i]["light"] == light and human[i]["road"] != "unknown"]
        for v in pv:
            a = sum(g(v, i) == human[i]["road"] for i in sure)
            fs = sum(g(v, i) == "snow" and human[i]["road"] == "bare" for i in sure)
            ms = sum(g(v, i) == "bare" and human[i]["road"] == "snow" for i in sure)
            un = sum(g(v, i) == "unknown" for i in sure)
            lines.append(f"| {light} | {v} | {a}/{len(sure)} ({a / max(len(sure), 1):.0%}) | {fs} | {ms} | {un} |")
    trap = [i for i in ids if human[i]["road"] == "bare" and human[i].get("side") == "yes"]
    lines += ["", f"Snow beside the road, lanes bare (person), {len(trap)} images; model says snow on lanes:"]
    for v in pv:
        w = sum(g(v, i) == "snow" for i in trap)
        lines.append(f"- {v}: {w}/{len(trap)} ({w / max(len(trap), 1):.0%})")
    lines += ["", "Day + twilight, person sure: answer only when confidence k >= threshold, else \"can't tell\":", "",
              "| prompt | k >= | answered | right when answered | says snow, person bare |", "|---|---:|---:|---:|---:|"]
    dt = [i for i in ids if items[i]["light"] in ("day", "twilight") and human[i]["road"] != "unknown"]
    for v in pv:
        for kmin in (0.0, 0.6, 0.7, 0.8, 0.9):
            ans = [i for i in dt if g(v, i, kmin) in ("bare", "snow")]
            right = sum(g(v, i, kmin) == human[i]["road"] for i in ans)
            fs = sum(g(v, i, kmin) == "snow" and human[i]["road"] == "bare" for i in ans)
            lines.append(f"| {v} | {kmin} | {len(ans)}/{len(dt)} | {right}/{max(len(ans), 1)} ({right / max(len(ans), 1):.0%}) | {fs} |")
    if "v4" in pv:
        lines += ["", "v4 center line (cl) vs the person's lane answer, all lights:", "",
                  "| cl | person bare | person snow | person can't tell |", "|---|---:|---:|---:|"]
        for c in FIELDS_V4["cl"]:
            sel = [i for i in ids if rd("v4", i).get("cl") == c]
            lines.append(f"| {c} | " + " | ".join(str(sum(human[i]["road"] == h for i in sel)) for h in ("bare", "snow", "unknown")) + " |")
    open(out_md, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


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
    if mode == "humantest":  # one file per prompt set, so re-tests never overwrite each other
        try:
            out_md = out_md[:-3] + "-" + "".join(json.load(open(os.path.join(ROOT, "ops", "bakeoff-request.json"))).get("prompts", ["v2", "v3"])) + ".md"
        except (OSError, ValueError):
            pass

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
    try:
        req = json.load(open(os.path.join(ROOT, "ops", "bakeoff-request.json")))
    except (OSError, ValueError):
        req = {}
    max_usd = float(req.get("max_usd", 9.0))  # hard stop on API spend for this run (owner budget D2)
    extra = req.get("extra") or {}  # optional request fields, e.g. {"output_config": {"effort": "low"}}
    if mode == "probe":
        return probe(rows, key, lines, out_md, hf_hub_download)
    if mode == "label":
        return label(req, key, api, rows, hf_hub_download, lines, out_md, today)
    if mode == "v2test":
        return v2test(req, key, api, hf_hub_download, lines, out_md, today)
    if mode == "humantest":
        return humantest(req, key, hf_hub_download, lines, out_md, today)
    picked = sample(rows, n)
    print(f"sampled {len(picked)}: {Counter(r['light'] for r in picked)}")
    work = []
    for r in picked:
        local = hf_hub_download(REPO, r["path"], repo_type="dataset", token=os.environ["HF_TOKEN"])
        small, size = shrink(open(local, "rb").read())
        r["size"] = size
        work.append((r, base64.b64encode(small).decode()))

    results = []

    spent = [0.0]
    lock = threading.Lock()

    def job(item):
        r, b64 = item
        with lock:
            if spent[0] >= max_usd:
                return None  # budget reached: skip the rest
        rec = dict(r, prompt=PROMPT_VERSION, extra=extra, models={})
        for m, spec in MODELS.items():
            rec["models"][m] = call(spec[0], b64, key, extra=extra)
            with lock:
                spent[0] += cost(m, rec["models"][m].get("usage", {}))
        return rec

    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for i, rec in enumerate(ex.map(job, work)):
            if rec is not None:
                results.append(rec)
            if i % 25 == 0:
                print(f"  {i + 1}/{len(work)} spent ${spent[0]:.2f}", flush=True)
    print(f"total API spend ${spent[0]:.2f} (cap ${max_usd:.2f}); labelled {len(results)}/{len(work)}")

    # per-image labels -> private dataset
    jsonl = "\n".join(json.dumps(x) for x in results) + "\n"
    label_path = f"labels/bakeoff-{today}/{PROMPT_VERSION}.jsonl"
    api.upload_file(path_or_fileobj=jsonl.encode(), path_in_repo=label_path, repo_id=REPO, repo_type="dataset",
                    commit_message=f"bake-off labels {today} ({len(results)} images x {len(MODELS)} models)")

    # aggregates
    lines += ["", f"Sampled **{len(results)}** images: " + ", ".join(
        f"{k} {v}" for k, v in Counter(r["light"] for r in results).items()),
        f"Prompt `{PROMPT_VERSION}`, images downscaled to max {MAX_SIDE}px. Reference model: **{REFERENCE}**.",
        f"Per-image labels: HF dataset `{REPO}` → `{label_path}` (private).",
        f"Extra request fields: `{json.dumps(extra)}`. Total API spend this run (all calls, incl. errors): "
        f"**${spent[0]:.2f}** (cap ${max_usd:.2f}); labelled {len(results)} of {len(work)} sampled.",
        "", "## Cost and speed (from API usage)", "",
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
