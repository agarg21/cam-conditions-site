#!/usr/bin/env python3
"""One-off discovery for keyed feeds (Idaho 511, ODOT TripCheck).

Writes to docs/discovery/feeds.txt (committed by the workflow), what each feed returns near the passes we plan to
add: pass records, nearby cameras with their image URLs, and the shape of the
road-condition records. Keys come from env vars and are never printed (GitHub
also masks secrets in logs). Run by .github/workflows/discover.yml.
"""
import json
import math
import os
import urllib.error
import urllib.request
import builtins
import sys

UA = "ConditionsNow/0.1 (+https://conditionsnow.com; hello@conditionsnow.com)"

# Oregon passes we want first: name, lat, lon
OREGON = [
    ("Santiam Pass US 20", 44.4246, -121.8556),
    ("Willamette Pass OR 58", 43.5990, -122.0367),
    ("Government Camp / Mt Hood US 26", 45.3029, -121.7535),
    ("Bennett Pass OR 35", 45.3130, -121.6360),
    ("Siskiyou Summit I-5", 42.0780, -122.5960),
    ("Sexton Summit I-5", 42.6040, -123.3660),
    ("Cabbage Hill / Deadman Pass I-84", 45.6030, -118.5050),
    ("Tollgate OR 204", 45.7810, -118.0900),
    ("Santiam Junction OR 22", 44.4350, -121.9460),
]


def get(url, headers=None, timeout=40):
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300]


def km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def shape(obj, depth=0):
    """Key structure of a JSON value, for reading an undocumented feed."""
    if isinstance(obj, dict):
        return {k: shape(v, depth + 1) if depth < 3 else type(v).__name__ for k, v in obj.items()}
    if isinstance(obj, list):
        return [shape(obj[0], depth + 1)] if obj else []
    return type(obj).__name__


def idaho():
    key = os.environ.get("IDAHO511_KEY")
    if not key:
        print("IDAHO511_KEY not set; skipping Idaho")
        return
    base = "https://511.idaho.gov/api/v2/get/{}?key=" + key + "&format=json"
    st, body = get(base.format("mountainpasses"))
    print(f"\n=== Idaho mountainpasses: HTTP {st}")
    passes = json.loads(body) if st == 200 else []
    for p in passes:
        print(f"  {p['Id']} | {p['Name']} | {p['Roadway']} | {p['Latitude']},{p['Longitude']}"
              f" | elev {p['MaxElevation']} | cam {p['CameraSource']} {p['CameraSourceId']}")
    st, body = get(base.format("cameras"))
    print(f"\n=== Idaho cameras: HTTP {st}")
    cams = json.loads(body) if st == 200 else []
    print(f"  {len(cams)} cameras")
    for p in passes:
        near = sorted(((km(p["Latitude"], p["Longitude"], c["Latitude"], c["Longitude"]), c)
                       for c in cams), key=lambda x: x[0])
        near = [(d, c) for d, c in near if d < 6][:6]
        print(f"\n  -- near {p['Name']} ({p['Roadway']})")
        for d, c in near:
            for v in c.get("Views", []):
                print(f"     {d:4.1f} km | cam {c['Id']} {c['Source']} {c['SourceId']} | {c['Location']}"
                      f" | {c['Direction']} | view {v['Id']} {v['Status']} {v['Url']} | {v['Description']}")
    st, body = get("https://511.idaho.gov/api/v3/get/winterroads?key=" + key + "&format=json")
    print(f"\n=== Idaho winterroads: HTTP {st}")
    if st == 200:
        rows = json.loads(body)
        print(f"  {len(rows)} segments; statuses:",
              sorted({r.get("Overall Status") for r in rows if r.get("Overall Status")}))
        for r in rows[:3]:
            print("  ", {k: v for k, v in r.items() if k != "EncodedPolyline"})


def oregon():
    key = os.environ.get("ODOT_KEY")
    if not key:
        print("ODOT_KEY not set; skipping Oregon")
        return
    hdr = {"Ocp-Apim-Subscription-Key": key, "Cache-Control": "no-cache"}
    st, body = get("https://api.odot.state.or.us/tripcheck/Cctv/Inventory", hdr)
    print(f"\n=== ODOT Cctv/Inventory: HTTP {st}")
    cams = []
    if st == 200:
        cams = json.loads(body).get("CCTVInventoryRequest", [])
        print(f"  {len(cams)} cameras; first: {cams[0] if cams else None}")
    for name, lat, lon in OREGON:
        near = sorted(((km(lat, lon, c["latitude"], c["longitude"]), c) for c in cams
                       if c.get("latitude") and c.get("longitude")), key=lambda x: x[0])
        print(f"\n  -- near {name}")
        for d, c in [x for x in near if x[0] < 8][:6]:
            print(f"     {d:4.1f} km | {c['device-id']} | {c['device-name']} | {c['route-id']}"
                  f" MP {c.get('milepoint')} | {c['cctv-url']} | {c.get('cctv-other')}")
    for path in ["RW/Reports", "RW/Metadata", "Rwis/Status/v2", "Incd"]:
        st, body = get("https://api.odot.state.or.us/tripcheck/" + path, hdr)
        print(f"\n=== ODOT {path}: HTTP {st}")
        if st == 200:
            try:
                data = json.loads(body)
            except ValueError:
                print("  not JSON:", body[:200])
                continue
            print("  shape:", json.dumps(shape(data))[:1500])
            items = next((v for v in data.values() if isinstance(v, list)), []) \
                if isinstance(data, dict) else data
            print(f"  {len(items)} items")
            for it in items[:2]:
                print("  ", json.dumps(it)[:1200])
        else:
            print("  ", body[:200])


OUT = open(sys.argv[1], "w") if len(sys.argv) > 1 else sys.stdout


def print(*a, **k):  # noqa: A001 - route all output to the discovery file
    builtins.print(*a, **k, file=OUT)


if __name__ == "__main__":
    for fn in (idaho, oregon):
        try:
            fn()
        except Exception as e:
            print(f"!! {fn.__name__} failed: {type(e).__name__}: {e}")
