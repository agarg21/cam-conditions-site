#!/usr/bin/env python3
"""Fetch the current camera image for every ready pass, plus official pass reports.

Writes to out/<UTC date>/<UTC time>/:
  <pass-slug>/<cam-index>.jpg   camera images (skipped if the camera is down)
  manifest.json                 what was fetched, sizes, hashes, HTTP status
  wsdot_pass_reports.json       WSDOT's official road/weather/restriction text
  idaho_winterroads.json        Idaho 511 road-condition segments (needs IDAHO511_KEY)
  odot_rw_reports.json          ODOT TripCheck road & weather reports (needs ODOT_KEY)
  odot_rw_metadata.json         ODOT code lists for those reports

Standard library only, so it runs on a bare GitHub Actions runner.
"""
import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "ConditionsNow/0.1 (+https://conditionsnow.com; hello@conditionsnow.com)"
WSDOT_REPORTS_PUBLIC = (
    "https://data.wsdot.wa.gov/arcgis/rest/services/TravelInformation/"
    "TravelInfoMtPassReports/FeatureServer/0/query?where=1%3D1&outFields=*&f=json"
)
WSDOT_REPORTS_API = (
    "https://wsdot.wa.gov/Traffic/api/MountainPassConditions/"
    "MountainPassConditionsREST.svc/GetMountainPassConditionsAsJson?AccessCode={code}"
)


def wsdot_reports():
    """Official pass reports: Traveler API when we have an access code, public layer otherwise."""
    code = os.environ.get("WSDOT_ACCESS_CODE")
    if code:
        _, body, _ = fetch(WSDOT_REPORTS_API.format(code=code), timeout=30)
        return "traveler-api", json.loads(body)
    _, body, _ = fetch(WSDOT_REPORTS_PUBLIC, timeout=30)
    return "arcgis", [f["attributes"] for f in json.loads(body).get("features", [])]


IDAHO_ROADS = "https://511.idaho.gov/api/v3/get/winterroads?key={key}&format=json"
ODOT_API = "https://api.odot.state.or.us/tripcheck/{path}"


def keyed_feeds():
    """Official condition feeds that need a developer key. Keys come from env and are never saved."""
    feeds = {}
    if os.environ.get("IDAHO511_KEY"):
        feeds["idaho_winterroads.json"] = (IDAHO_ROADS.format(key=os.environ["IDAHO511_KEY"]), {})
    if os.environ.get("ODOT_KEY"):
        hdr = {"Ocp-Apim-Subscription-Key": os.environ["ODOT_KEY"]}
        feeds["odot_rw_reports.json"] = (ODOT_API.format(path="RW/Reports"), hdr)
        feeds["odot_rw_metadata.json"] = (ODOT_API.format(path="RW/Metadata"), hdr)
    return feeds


def fetch(url, timeout=20, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(), r.headers.get("Content-Type", "")


def image_problem(body):
    """Why this body is not a complete JPEG (None if it is). DOTs sometimes send an HTML/placeholder body
    or a cut-off file with an image Content-Type; the 2026-11-28 label job hit one (Blewett 00:02Z)."""
    if len(body) <= 2000:
        return "too_small"
    if not body.startswith(b"\xff\xd8\xff"):
        return "not_jpeg"
    if b"\xff\xd9" not in body[-64:]:  # end-of-image marker; a few cameras pad a few bytes after it
        return "truncated"
    return None


def main():
    now = datetime.now(timezone.utc)
    out = os.path.join(ROOT, "out", now.strftime("%Y-%m-%d"), now.strftime("%H%M"))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(ROOT, "config", "passes.json")) as f:
        passes = json.load(f)["ready"]

    manifest = {"fetched_at": now.isoformat(), "cams": []}
    for p in passes:
        os.makedirs(os.path.join(out, p["slug"]), exist_ok=True)
        for i, cam in enumerate(p["cams"]):
            rec = {"pass": p["slug"], "cam": i, "title": cam["title"], "url": cam["image"]}
            try:
                status, body, ctype = fetch(cam["image"])
                rec.update(status=status, bytes=len(body), sha1=hashlib.sha1(body).hexdigest())
                problem = image_problem(body) if status == 200 and ctype.startswith("image") else "not_image"
                if problem is None:
                    with open(os.path.join(out, p["slug"], f"{i}.jpg"), "wb") as f:
                        f.write(body)
                    rec["saved"] = True
                else:
                    rec.update(saved=False, problem=problem)
            except Exception as e:  # camera offline, timeout, DNS
                rec.update(saved=False, error=str(e)[:200])
            manifest["cams"].append(rec)
            time.sleep(0.5)  # be polite to DOT servers

    try:
        source, rows = wsdot_reports()
        manifest["wsdot_reports_source"] = source
        with open(os.path.join(out, "wsdot_pass_reports.json"), "w") as f:
            json.dump(rows, f, indent=1)
    except Exception as e:
        manifest["wsdot_reports_error"] = str(e)[:200]

    manifest["feeds"] = {}
    for fname, (url, hdr) in keyed_feeds().items():
        try:
            status, body, _ = fetch(url, timeout=40, headers=hdr)
            json.loads(body)  # only keep valid JSON
            with open(os.path.join(out, fname), "wb") as f:
                f.write(body)
            manifest["feeds"][fname] = {"status": status, "bytes": len(body)}
        except Exception as e:  # keep going; the page falls back to "no current report"
            manifest["feeds"][fname] = {"error": type(e).__name__}

    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    ok = sum(c.get("saved", False) for c in manifest["cams"])
    print(f"saved {ok}/{len(manifest['cams'])} images to {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
