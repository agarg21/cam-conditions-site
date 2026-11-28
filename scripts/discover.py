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

# Oregon passes to check (Q16 batch 2026-11-28): name, lat, lon = USGS GNIS gap point
OREGON = [
    ("Sexton Summit I-5 (GNIS Sexton Mountain Pass)", 42.60123, -123.38313),
    ("Smith Hill Summit I-5", 42.66512, -123.37897),
    ("Stage Road Pass I-5", 42.73040, -123.36925),
    ("Canyon Creek Pass I-5", 42.82790, -123.26008),
    ("Bennett Pass OR 35", 45.31068, -121.64287),
    ("Ochoco Pass US 26", 44.50153, -120.38670),
    ("Dixie Summit US 26", 44.53683, -118.59774),
    ("Blue Mountain Summit US 26", 44.54822, -118.35023),
    ("Battle Mountain Summit US 395", 45.27097, -118.97584),
    ("Ritter Butte Summit US 395", 44.83655, -119.06499),
    ("Beech Creek Summit US 395", 44.57127, -119.12470),
    ("Tombstone Pass US 20", 44.39568, -122.14119),
    ("Stinkingwater Pass US 20", 43.69155, -118.53994),
    ("Drinkwater Pass US 20", 43.78461, -118.27854),
    ("Hayes Hill Summit US 199", 42.33262, -123.58536),
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
        # Which pass has an official winter-road segment on its own highway near the summit (build_site uses <= 3 km).
        from build_site import decode_polyline, norm_route, seg_km
        print("\n=== Idaho winterroads nearest each mountain pass (same route; build_site uses <= 3 km)")
        for p in passes:
            best = None
            for r in rows:
                if norm_route(r.get("RoadwayName")) != norm_route(p["Roadway"]):
                    continue
                for line in r.get("EncodedPolyline") or []:
                    pts = decode_polyline(line)
                    for a, b in zip(pts, pts[1:]):
                        d = seg_km(p["Latitude"], p["Longitude"], a, b)
                        if best is None or d < best[0]:
                            best = (d, r)
            if not best:
                print(f"  {p['Name']} ({p['Roadway']}): no segment on this route")
                continue
            d, r = best
            print(f"  {p['Name']} ({p['Roadway']}): {d:.1f} km | {r.get('RoadwayName')} | {r.get('LocationDescription')}"
                  f" | {r.get('Overall Status')} | updated {r.get('LastUpdated')}")


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
        for d, c in [x for x in near if x[0] < 8][:8]:
            print(f"     {d:4.1f} km | {c['device-id']} | {c['device-name']} | {c['route-id']}"
                  f" MP {c.get('milepoint')} | {c['cctv-url']} | {c.get('cctv-other')}")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_site import seg_km
    st, body = get("https://api.odot.state.or.us/tripcheck/RW/Reports", hdr)
    reports = json.loads(body).get("road-weather-reports", []) if st == 200 else []
    print(f"\n=== ODOT RW/Reports nearest each pass above (build_site uses same route <= 10 km)")
    for name, lat, lon in OREGON:
        near = []
        for r in reports:
            loc = r.get("location", {})
            a = (loc.get("start-location", {}).get("start-lat"), loc.get("start-location", {}).get("start-long"))
            b = (loc.get("end-location", {}).get("end-lat"), loc.get("end-location", {}).get("end-long"))
            if None in a + b:
                continue
            near.append((seg_km(lat, lon, a, b), r))
        near.sort(key=lambda x: x[0])
        for d, r in near[:2]:
            loc = r["location"]
            print(f"  {name}: {d:.1f} km | {loc.get('location-name')} | {loc.get('route-id')} MP {loc['start-location'].get('start-milepost')}"
                  f"-{loc['end-location'].get('end-milepost')} | road {r.get('road-conditions', {}).get('road-cond-id')}"
                  f" | entry {r.get('entry-time')}")
    for path in ["RW/Reports", "RW/Metadata"]:
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
