#!/usr/bin/env python3
"""Official status history: what each pass's DOT report said at every collector run.

Stored as compact JSONL in the private Hugging Face dataset (status/<UTC date>.jsonl), one row per pass per run:
  {"t": run time, "p": pass slug, "lv": level, "lb": label, "op": open?, "ch": chains?, "sn": snow?, "road": wording,
   "up": report updated time}
Only official wording and our plain answers derived from it; no camera readings or per-image labels.

  history.py pull   download today's and yesterday's files into history/ (missing file = empty day)
  history.py push   upload the file build_site.py appended to, only if the pull succeeded
                    (so a failed pull can never overwrite a day's history with one row)
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "history")
REPO = os.environ.get("HF_DATASET", "agarg20/conditionsnow-cams")
PULLED = os.path.join(HIST, ".pulled")
DIRTY = os.path.join(HIST, ".dirty")


def day_file(d):
    return os.path.join(HIST, f"{d.isoformat()}.jsonl")


def load(now, hours=24):
    """Rows from the last `hours` before `now`, oldest first, de-duplicated by (time, pass)."""
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
                    if (r["t"], r.get("p")) in seen or not (now - timedelta(hours=hours) <= t <= now):
                        continue
                    seen.add((r["t"], r.get("p")))
                    r["_t"] = t
                    rows.append(r)
        except FileNotFoundError:
            pass
    rows.sort(key=lambda r: r["_t"])
    return rows


def append(now, rows):
    """Add this run's rows to today's file (skipping a run already recorded) and mark the file for upload."""
    os.makedirs(HIST, exist_ok=True)
    path = day_file(now.date())
    have = {(r["t"], r.get("p")) for r in load(now, hours=1)}
    new = [r for r in rows if (r["t"], r["p"]) not in have]
    with open(path, "a") as f:
        for r in new:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    with open(DIRTY, "w") as f:
        f.write(os.path.basename(path))
    return len(new)


def pull():
    from huggingface_hub import hf_hub_download
    try:  # only "the file isn't there" counts as an empty day; a network failure must stop the push
        from huggingface_hub.errors import RemoteEntryNotFoundError as Missing
    except ImportError:
        from huggingface_hub.utils import EntryNotFoundError as Missing
    try:
        from huggingface_hub.errors import LocalEntryNotFoundError as Offline
    except ImportError:
        from huggingface_hub.utils import LocalEntryNotFoundError as Offline
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF_TOKEN not set; no history this run")
        return 0
    os.makedirs(HIST, exist_ok=True)
    today = datetime.now(timezone.utc).date()
    for d in (today - timedelta(days=1), today):
        name = f"{d.isoformat()}.jsonl"
        try:
            hf_hub_download(REPO, f"status/{name}", repo_type="dataset", token=token, local_dir=HIST)
            os.replace(os.path.join(HIST, "status", name), os.path.join(HIST, name))
            print("pulled", name)
        except Missing as ex:
            if isinstance(ex, Offline):
                raise
            print("no history yet for", name)
    with open(PULLED, "w") as f:
        f.write(today.isoformat())
    return 0


def push():
    if not (os.path.exists(PULLED) and os.path.exists(DIRTY)):
        print("pull did not succeed or nothing appended; not uploading history")
        return 0
    from huggingface_hub import HfApi
    name = open(DIRTY).read().strip()
    HfApi(token=os.environ["HF_TOKEN"]).upload_file(
        path_or_fileobj=os.path.join(HIST, name), path_in_repo=f"status/{name}", repo_id=REPO,
        repo_type="dataset", commit_message=f"status {os.environ.get('GITHUB_RUN_ID', 'local')}")
    print("pushed", name)
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit({"pull": pull, "push": push}.get(cmd, lambda: print(__doc__) or 2)())
