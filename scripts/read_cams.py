#!/usr/bin/env python3
"""Our camera readings (Q13, owner D9): Claude Sonnet reads each camera of the passes marked "read": true in
config/passes.json, about once an hour, in daylight and twilight only.

Prompt pass-v4 (center line first). A reading is only shown as an answer when its confidence k >= 0.7
(owner check 2026-11-28: 39/40 right at k >= 0.7). Stored in the private HF dataset, readings/<UTC date>.jsonl,
one compact row per camera image:
  {"t": run time, "p": pass slug, "c": camera index, "s": lanes, "cl": center line, "b": beside road, "f": snow falling,
   "v": visibility, "u": image usable, "k": confidence, "m": model+prompt}
Spend: readings/ledger-<YYYY-MM>.json in the same dataset; stops at MONTH_CAP_USD (D11: up to $40/month).
Every ready pass is read unless it sets "read": false in config/passes.json (D11).

Opus re-reads (Q13 audit, Q14 storm check) go to readings/audit-<UTC date>.jsonl, same row shape plus "why"
("storm" or "audit"); the site never shows them. Storm mode (Q14): while NWS has a winter storm / winter weather alert
for the pass point, or forecasts >= 2 in of snow in the next 24 h, and for 12 h after, every reading gets an Opus
re-read. Storm windows are kept in readings/storms.json. Outside storms about AUDIT_SHARE of readings get one, only
while the month's spend is under pace for the cap. Both count in the same D9 ledger.

  read_cams.py pull   download today's and yesterday's readings and this month's ledger (missing = empty)
  read_cams.py read   read the cameras that are due in the latest collector run, append rows
  read_cams.py push   upload what `read` changed, only if `pull` succeeded
"""
import base64
import concurrent.futures as cf
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "readings")
REPO = os.environ.get("HF_DATASET", "agarg20/conditionsnow-cams")
PULLED, DIRTY = os.path.join(DIR, ".pulled"), os.path.join(DIR, ".dirty")
MODEL, PROMPT = "sonnet", "pass-v4"
MIN_GAP = timedelta(minutes=50)   # about hourly per camera when snow is forecast (storm mode) or seen
CALM_GAP = timedelta(minutes=170) # about every 3 hours otherwise (D11)
MIN_SUN = -6.0                    # read in day and civil twilight only
MONTH_CAP_USD = 40.0             # D11 (was D9: 15)
SHOW_K = 0.7                      # below this a reading is "can't tell" on the page
READ_CAMS = [0, 1]                # D9: 2 cameras per pass; a pass can name its two with "read_cams" in passes.json
AUDIT_MODEL = "opus"
AUDIT_SHARE = 0.10                # routine Opus re-reads outside storms (only while spend is under pace)
STORM_EVENTS = {"Winter Storm Warning", "Winter Weather Advisory", "Blizzard Warning", "Ice Storm Warning"}
STORM_SNOW_MM = 50.8              # NWS forecast of >= 2 in of snow in the next 24 h also starts storm mode
STORM_AFTER = timedelta(hours=12) # storm mode lasts this long after the last trigger
UA = "conditionsnow.com (hello@conditionsnow.com)"


def day_file(d):
    return os.path.join(DIR, f"{d.isoformat()}.jsonl")


def ledger_file(now):
    return os.path.join(DIR, f"ledger-{now:%Y-%m}.json")


def audit_file(d):
    return os.path.join(DIR, f"audit-{d.isoformat()}.jsonl")


STORMS = os.path.join(DIR, "storms.json")


def nws(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/geo+json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def storm_trigger(p, now):
    """Why storm mode should be on for this pass right now, or "" (NWS alerts, then gridpoint snowfall)."""
    pt = f'{p["lat"]:.4f},{p["lon"]:.4f}'
    for f in nws(f"https://api.weather.gov/alerts/active?point={pt}").get("features", []):
        ev = f["properties"].get("event", "")
        if ev in STORM_EVENTS:
            return f'{ev} until {f["properties"].get("ends") or f["properties"].get("expires")}'
    grid = nws(nws(f"https://api.weather.gov/points/{pt}")["properties"]["forecastGridData"])
    mm = 0.0
    for v in grid["properties"].get("snowfallAmount", {}).get("values", []):
        start = datetime.fromisoformat(v["validTime"].split("/")[0])
        if now - timedelta(hours=1) <= start < now + timedelta(hours=24):
            mm += v.get("value") or 0.0
    return f"NWS forecast {mm / 25.4:.1f} in of snow in 24 h" if mm >= STORM_SNOW_MM else ""


def update_storms(passes, now):
    """Refresh readings/storms.json; returns {pass slug: reason} for passes in storm mode now (incl. the 12 h after)."""
    try:
        storms = json.load(open(STORMS))
    except (OSError, ValueError):
        storms = {}
    for slug, p in passes.items():
        try:
            why = storm_trigger(p, now)
        except Exception as ex:  # NWS down: keep what we knew
            print("storm check failed:", slug, type(ex).__name__)
            continue
        if not why:
            continue
        hist = storms.setdefault(slug, [])
        if hist and now - datetime.fromisoformat(hist[-1]["last"]) <= STORM_AFTER:
            hist[-1].update(last=now.isoformat(), why=why)
        else:
            hist.append({"since": now.isoformat(), "last": now.isoformat(), "why": why})
            print("storm mode on:", slug, why)
    os.makedirs(DIR, exist_ok=True)
    json.dump(storms, open(STORMS, "w"), indent=1)
    return {slug: h[-1]["why"] for slug, h in storms.items()
            if h and now - datetime.fromisoformat(h[-1]["last"]) <= STORM_AFTER}


def audit_pick(now, c):
    """Deterministic ~AUDIT_SHARE sample of routine readings."""
    import hashlib
    h = hashlib.sha256(f'{now.isoformat()}|{c["pass"]}|{c["cam"]}'.encode()).digest()
    return h[0] < 256 * AUDIT_SHARE


def load(now, hours=24):
    """Rows from the last `hours` before `now`, oldest first, de-duplicated by (time, pass, camera)."""
    rows, seen = [], set()
    for d in sorted({(now - timedelta(hours=hours)).date(), now.date()}):
        try:
            with open(day_file(d)) as f:
                for line in f:
                    try:
                        r = json.loads(line)
                        t = datetime.fromisoformat(r["t"])
                    except (ValueError, KeyError):
                        continue
                    k = (r["t"], r.get("p"), r.get("c"))
                    if k in seen or not (now - timedelta(hours=hours) <= t <= now):
                        continue
                    seen.add(k)
                    r["_t"] = t
                    rows.append(r)
        except FileNotFoundError:
            pass
    rows.sort(key=lambda r: r["_t"])
    return rows


def pull():
    from huggingface_hub import hf_hub_download
    try:
        from huggingface_hub.errors import RemoteEntryNotFoundError as Missing
    except ImportError:
        from huggingface_hub.utils import EntryNotFoundError as Missing
    try:
        from huggingface_hub.errors import LocalEntryNotFoundError as Offline
    except ImportError:
        from huggingface_hub.utils import LocalEntryNotFoundError as Offline
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF_TOKEN not set; no readings this run")
        return 0
    os.makedirs(DIR, exist_ok=True)
    now = datetime.now(timezone.utc)
    names = [f"{d.isoformat()}.jsonl" for d in (now.date() - timedelta(days=1), now.date())]
    names += [f"audit-{d.isoformat()}.jsonl" for d in (now.date() - timedelta(days=1), now.date())]
    names += [os.path.basename(ledger_file(now)), "storms.json"]
    for name in names:
        try:
            hf_hub_download(REPO, f"readings/{name}", repo_type="dataset", token=token, local_dir=DIR)
            os.replace(os.path.join(DIR, "readings", name), os.path.join(DIR, name))
            print("pulled", name)
        except Missing as ex:
            if isinstance(ex, Offline):
                raise
            print("none yet:", name)
    with open(PULLED, "w") as f:
        f.write(now.isoformat())
    return 0


def latest_run():
    runs = sorted(glob.glob(os.path.join(ROOT, "out", "*", "*", "manifest.json")))
    if not runs:
        return None, {}
    with open(runs[-1]) as f:
        return os.path.dirname(runs[-1]), json.load(f)


def read():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not (key and os.path.exists(PULLED)):
        print("no API key or readings pull failed; not reading cameras")
        return 0
    import bakeoff as b
    run_dir, manifest = latest_run()
    if not run_dir:
        return 0
    now = datetime.fromisoformat(manifest["fetched_at"])
    with open(os.path.join(ROOT, "config", "passes.json")) as f:
        passes = {p["slug"]: p for p in json.load(f)["ready"] if p.get("read", True)}
    led_path = ledger_file(now)
    try:
        led = json.load(open(led_path))
    except (OSError, ValueError):
        led = {"month": f"{now:%Y-%m}", "budget_usd": MONTH_CAP_USD, "spent_usd": 0.0, "images": 0}
    if led["spent_usd"] >= MONTH_CAP_USD:
        print(f"monthly cap reached (${led['spent_usd']:.2f}); not reading")
        return 0
    last, snowy = {}, set()
    for r in load(now, hours=3):
        last[(r["p"], r["c"])] = r["_t"]
        if r.get("f") == "y" or (r.get("s") in ("partly", "covered", "ice") and float(r.get("k") or 0) >= SHOW_K):
            snowy.add(r["p"])
    cand = []
    for c in manifest.get("cams", []):
        p = passes.get(c["pass"])
        if not p or not c.get("saved") or c["cam"] not in p.get("read_cams", READ_CAMS):
            continue
        if b.sun_elevation(p["lat"], p["lon"], now) < MIN_SUN:
            continue
        if now - last.get((c["pass"], c["cam"]), now - 2 * CALM_GAP) < MIN_GAP:
            continue
        cand.append(c)
    if not cand:
        print("no cameras due")
        return 0
    storm = update_storms({c['pass']: passes[c['pass']] for c in cand}, now)
    due = [c for c in cand if c["pass"] in storm or c["pass"] in snowy
           or now - last.get((c["pass"], c["cam"]), now - 2 * CALM_GAP) >= CALM_GAP]
    if not due:
        print("no cameras due (calm: every 3 h)")
        return 0
    month_days = ((now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
    pace = MONTH_CAP_USD * ((now.day - 1) + now.hour / 24) / month_days
    routine_ok = led["spent_usd"] < pace

    def call(model, b64):
        try:
            return b.parse_msg(b.http("POST", b.API, key, b.v4_params(model, b64)))
        except Exception as ex:  # one camera failing must never stop the deploy
            return {"error": f"{type(ex).__name__}: {str(ex)[:150]}", "usage": {}}

    def one(c):
        raw = open(os.path.join(run_dir, c["pass"], f'{c["cam"]}.jpg'), "rb").read()
        b64 = base64.b64encode(b.shrink(raw)[0]).decode()
        out = call(MODEL, b64)
        why = "storm" if c["pass"] in storm else "audit" if routine_ok and audit_pick(now, c) else ""
        return c, out, (why, call(AUDIT_MODEL, b64)) if why and out.get("reading") else None

    def row(c, r, model):
        return {"t": now.isoformat(), "p": c["pass"], "c": c["cam"], "s": r.get("s"), "cl": r.get("cl"),
                "b": r.get("b"), "f": r.get("f"), "v": r.get("v"), "u": r.get("u"),
                "k": round(float(r.get("k") or 0), 2), "m": f"{model}-{PROMPT}"}

    rows, audits, usd, ausd = [], [], 0.0, 0.0
    with cf.ThreadPoolExecutor(4) as ex:
        for c, out, aud in ex.map(one, due):
            usd += b.cost(MODEL, out.get("usage", {}))
            r = out.get("reading")
            if not r:
                print("reading failed:", c["pass"], c["cam"], out.get("error"))
                continue
            rows.append(row(c, r, MODEL))
            if aud:
                why, aout = aud
                ausd += b.cost(AUDIT_MODEL, aout.get("usage", {}))
                if aout.get("reading"):
                    audits.append(dict(row(c, aout["reading"], AUDIT_MODEL), why=why))
                else:
                    print("audit failed:", c["pass"], c["cam"], aout.get("error"))
    os.makedirs(DIR, exist_ok=True)
    with open(day_file(now.date()), "a") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    dirty = [os.path.basename(day_file(now.date())), os.path.basename(led_path), os.path.basename(STORMS)]
    if audits:
        with open(audit_file(now.date()), "a") as f:
            for r in audits:
                f.write(json.dumps(r, separators=(",", ":")) + "\n")
        dirty.append(os.path.basename(audit_file(now.date())))
    led["spent_usd"] = round(led["spent_usd"] + usd + ausd, 4)
    led["images"] += len(rows)
    led["audit_usd"] = round(led.get("audit_usd", 0.0) + ausd, 4)
    led["audit_images"] = led.get("audit_images", 0) + len(audits)
    json.dump(led, open(led_path, "w"), indent=1)
    with open(DIRTY, "w") as f:
        f.write("\n".join(dirty))
    print(f"read {len(rows)}/{len(due)} cameras, ${usd:.3f}; opus re-reads {len(audits)} (storm: "
          f"{', '.join(sorted(storm)) or 'none'}), ${ausd:.3f}; month ${led['spent_usd']:.2f} of ${MONTH_CAP_USD:.0f}")
    return 0


def push():
    if not (os.path.exists(PULLED) and os.path.exists(DIRTY)):
        print("nothing to upload")
        return 0
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ["HF_TOKEN"])
    for name in open(DIRTY).read().split():
        api.upload_file(path_or_fileobj=os.path.join(DIR, name), path_in_repo=f"readings/{name}", repo_id=REPO,
                        repo_type="dataset", commit_message=f"readings {os.environ.get('GITHUB_RUN_ID', 'local')}")
        print("pushed", name)
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit({"pull": pull, "read": read, "push": push}.get(cmd, lambda: print(__doc__) or 2)())
