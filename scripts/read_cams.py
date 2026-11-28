#!/usr/bin/env python3
"""Our camera readings (Q13, owner D9): Claude Sonnet reads each camera of the passes marked "read": true in
config/passes.json, about once an hour, in daylight and twilight only.

Prompt pass-v4 (center line first). A reading is only shown as an answer when its confidence k >= 0.7
(owner check 2026-11-28: 39/40 right at k >= 0.7). Stored in the private HF dataset, readings/<UTC date>.jsonl,
one compact row per camera image:
  {"t": run time, "p": pass slug, "c": camera index, "s": lanes, "cl": center line, "b": beside road, "f": snow falling,
   "v": visibility, "u": image usable, "k": confidence, "m": model+prompt}
Spend: readings/ledger-<YYYY-MM>.json in the same dataset; stops at MONTH_CAP_USD (D9: up to $15/month).

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
MIN_GAP = timedelta(minutes=50)   # about hourly per camera
MIN_SUN = -6.0                    # read in day and civil twilight only
MONTH_CAP_USD = 15.0
SHOW_K = 0.7                      # below this a reading is "can't tell" on the page


def day_file(d):
    return os.path.join(DIR, f"{d.isoformat()}.jsonl")


def ledger_file(now):
    return os.path.join(DIR, f"ledger-{now:%Y-%m}.json")


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
    names.append(os.path.basename(ledger_file(now)))
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
        passes = {p["slug"]: p for p in json.load(f)["ready"] if p.get("read")}
    led_path = ledger_file(now)
    try:
        led = json.load(open(led_path))
    except (OSError, ValueError):
        led = {"month": f"{now:%Y-%m}", "budget_usd": MONTH_CAP_USD, "spent_usd": 0.0, "images": 0}
    if led["spent_usd"] >= MONTH_CAP_USD:
        print(f"monthly cap reached (${led['spent_usd']:.2f}); not reading")
        return 0
    last = {}
    for r in load(now, hours=3):
        last[(r["p"], r["c"])] = r["_t"]
    due = []
    for c in manifest.get("cams", []):
        p = passes.get(c["pass"])
        if not p or not c.get("saved"):
            continue
        if b.sun_elevation(p["lat"], p["lon"], now) < MIN_SUN:
            continue
        if now - last.get((c["pass"], c["cam"]), now - 2 * MIN_GAP) < MIN_GAP:
            continue
        due.append(c)
    if not due:
        print("no cameras due")
        return 0

    def one(c):
        raw = open(os.path.join(run_dir, c["pass"], f'{c["cam"]}.jpg'), "rb").read()
        b64 = base64.b64encode(b.shrink(raw)[0]).decode()
        try:
            out = b.parse_msg(b.http("POST", b.API, key, b.v4_params(MODEL, b64)))
        except Exception as ex:  # one camera failing must never stop the deploy
            return c, {"error": f"{type(ex).__name__}: {str(ex)[:150]}", "usage": {}}
        return c, out

    rows, usd = [], 0.0
    with cf.ThreadPoolExecutor(4) as ex:
        for c, out in ex.map(one, due):
            usd += b.cost(MODEL, out.get("usage", {}))
            r = out.get("reading")
            if not r:
                print("reading failed:", c["pass"], c["cam"], out.get("error"))
                continue
            rows.append({"t": now.isoformat(), "p": c["pass"], "c": c["cam"], "s": r.get("s"), "cl": r.get("cl"),
                         "b": r.get("b"), "f": r.get("f"), "v": r.get("v"), "u": r.get("u"),
                         "k": round(float(r.get("k") or 0), 2), "m": f"{MODEL}-{PROMPT}"})
    os.makedirs(DIR, exist_ok=True)
    with open(day_file(now.date()), "a") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    led["spent_usd"] = round(led["spent_usd"] + usd, 4)
    led["images"] += len(rows)
    json.dump(led, open(led_path, "w"), indent=1)
    with open(DIRTY, "w") as f:
        f.write("\n".join([os.path.basename(day_file(now.date())), os.path.basename(led_path)]))
    print(f"read {len(rows)}/{len(due)} cameras, ${usd:.3f}; month ${led['spent_usd']:.2f} of ${MONTH_CAP_USD:.0f}")
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
