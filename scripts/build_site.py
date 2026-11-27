#!/usr/bin/env python3
"""Build the static site from the latest collector run.

Reads config/passes.json and the newest out/<date>/<time>/ folder, adds official
DOT status (WSDOT pass reports, Caltrans chain controls, Idaho 511 road conditions,
ODOT TripCheck road & weather reports) and an NWS forecast, and writes _site/ for
GitHub Pages. Camera images are served from our own copies (ODOT requires mirroring).
"""
import glob
import html
import json
import math
import os
import re
import shutil
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "_site")
BASE = "https://conditionsnow.com"
UA = "ConditionsNow/0.1 (+https://conditionsnow.com; hello@conditionsnow.com)"
TZ = ZoneInfo("America/Los_Angeles")
CC_URL = "https://cwwp2.dot.ca.gov/data/d3/cc/ccStatusD03.json"
STATE_NAMES = {"WA": "Washington", "OR": "Oregon", "CA": "California", "ID": "Idaho", "WY": "Wyoming"}
STATE_ORDER = list(STATE_NAMES)
DOT_NAMES = {"WA": ("WSDOT", "https://wsdot.com/travel/real-time/mountainpasses"),
             "CA": ("Caltrans QuickMap", "https://quickmap.dot.ca.gov/"),
             "OR": ("ODOT TripCheck", "https://www.tripcheck.com/"),
             "ID": ("Idaho 511", "https://511.idaho.gov/"),
             "WY": ("WYDOT", "https://www.wyoroad.info/")}
# Who publishes the camera images, for the credit line under each camera grid.
CAM_CREDIT = {"wsdot-arcgis": "WSDOT", "caltrans-cwwp2-d3": "Caltrans",
              "odot-tripcheck": "Oregon Department of Transportation (TripCheck)",
              "idaho-511": "Idaho Transportation Department (Idaho 511)"}
# ODOT's terms require republishers to repeat this disclaimer (Disclaimer of Warranty; Limitation of Liability).
ODOT_DISCLAIMER = [
    "ODOT and public agencies providing the data on this portal attempt to provide the best service reasonably "
    "available, but situations will occur that disrupt service. The updating and dissemination of this information "
    "depends on a number of available resources, including Internet availability, communications networks, and "
    "interconnected computer systems which may be beyond the immediate control of ODOT. Availability at any given "
    "time is not guaranteed.",
    "Those relying on information presented on this site do so at their own risk, and the State of Oregon, ODOT, "
    "and the public agencies providing the data, and any of their officers, employees or agents shall be held "
    "harmless and released from liability for the accuracy or completeness of this information and from any "
    "actions taken based on the information.",
    "All information is provided \"as is\" without warranty of any kind, either express or implied, including, but "
    "not limited to, the implied warranties of merchantability, fitness for a particular purpose, or non-infringement.",
    "ODOT assumes no responsibility for errors or omissions in the information or software or other documents which "
    "are referenced by or linked to this portal. Under no circumstances, including, but not limited to, negligence, "
    "shall ODOT or any public agency contributing data to this portal be liable for any direct, indirect, incidental, "
    "special or consequential damages that result from the use of, or the inability to use, this portal or its content.",
]
e = html.escape


def get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def latest_run():
    runs = sorted(glob.glob(os.path.join(ROOT, "out", "*", "*", "manifest.json")))
    if not runs:
        return None, {}
    with open(runs[-1]) as f:
        return os.path.dirname(runs[-1]), json.load(f)


def local(ts, tz=TZ):
    return ts.astimezone(tz).strftime("%-I:%M %p %Z, %b %-d")


def km(lat1, lon1, lat2, lon2):
    r = math.pi / 180
    a = (math.sin((lat2 - lat1) * r / 2) ** 2
         + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin((lon2 - lon1) * r / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def seg_km(lat, lon, a, b):
    """Distance from a point to the segment a-b (lat/lon pairs), flat-earth approximation."""
    kx = 111.32 * math.cos(lat * math.pi / 180)
    ax, ay = (a[1] - lon) * kx, (a[0] - lat) * 110.57
    bx, by = (b[1] - lon) * kx, (b[0] - lat) * 110.57
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx, ay + t * dy)


def decode_polyline(s):
    pts, i, lat, lon = [], 0, 0, 0
    while i < len(s):
        for which in (0, 1):
            shift = result = 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            d = ~(result >> 1) if result & 1 else result >> 1
            if which == 0:
                lat += d
            else:
                lon += d
        pts.append((lat / 1e5, lon / 1e5))
    return pts


def norm_route(r):
    return re.sub(r"[^A-Z0-9]", "", (r or "").upper()).replace("SH", "ID").replace("HWY", "")


def load_run_json(run_dir, name):
    try:
        with open(os.path.join(run_dir, name)) as f:
            return json.load(f)
    except Exception:
        return None


def parse_ms_date(s):
    """WSDOT '/Date(1764100000000-0800)/' -> aware datetime."""
    m = re.search(r"(\d{10,13})", str(s or ""))
    return datetime.fromtimestamp(int(m.group(1)) / 1000, timezone.utc) if m else None


def wsdot_status(run_dir, name):
    try:
        with open(os.path.join(run_dir, "wsdot_pass_reports.json")) as f:
            rows = json.load(f)
    except Exception:
        return None
    for r in rows:
        if " ".join((r.get("MountainPassName") or r.get("PassName") or "").split()).lower() != name.lower():
            continue
        restr = []
        for k in ("RestrictionOne", "RestrictionTwo"):  # Traveler API shape
            if isinstance(r.get(k), dict) and r[k].get("RestrictionText"):
                restr.append((r[k].get("TravelDirection", ""), r[k]["RestrictionText"]))
        for d, m in (("TravelDirection1", "PublicMessage1"), ("TravelDirection2", "PublicMessage2")):  # public layer
            if r.get(m):
                restr.append((r.get(d, ""), r[m]))
        temp = r.get("TemperatureInFahrenheit")
        return {
            "road": (r.get("RoadCondition") or "").strip(),
            "weather": (r.get("WeatherCondition") or r.get("Weather") or "").strip(),
            "temp": f"{temp}°F" if isinstance(temp, (int, float)) and temp < 200 else "",
            "restrictions": restr,
            "updated": parse_ms_date(r.get("DateUpdated")),
        }
    return None


def caltrans_status(route, cc_rows):
    pts = [c["cc"] for c in cc_rows if c["cc"]["location"]["route"] == route and c["cc"]["inService"] == "true"]
    if not pts:
        return None
    active = [p for p in pts if p["statusData"]["status"] not in ("R-0", "")]
    pick = active or pts[:1]
    lines = sorted({p["statusData"]["statusDescription"] for p in pick})
    return {"road": " ".join(lines), "weather": "", "temp": "", "restrictions": [],
            "updated": None, "chain_points": len(active),
            "label": None if active else "No chain controls now"}


def txt(v):
    """Feed fields are sometimes a string, sometimes a list of strings."""
    if isinstance(v, list):
        return ", ".join(str(x).strip() for x in v if x)
    return str(v or "").strip()


def idaho_status(run_dir, p):
    """Nearest Idaho 511 road-condition segment on the pass's highway, within 3 km of the summit."""
    rows = load_run_json(run_dir, "idaho_winterroads.json")
    if not rows:
        return None
    best = None
    for r in rows:
        if norm_route(r.get("RoadwayName")) != norm_route(p["route"]):
            continue
        for line in r.get("EncodedPolyline") or []:
            pts = decode_polyline(line)
            for a, b in zip(pts, pts[1:]):
                d = seg_km(p["lat"], p["lon"], a, b)
                if best is None or d < best[0]:
                    best = (d, r)
    if not best or best[0] > 3:
        return None
    r = best[1]
    road = txt(r.get("Overall Status"))
    if road.lower() in ("", "no report"):
        return None
    special = txt(r.get("Special Conditions"))
    restr = [("Special conditions", special)] if special else []
    return {"road": road, "weather": txt(r.get("Weather Conditions")), "temp": "",
            "restrictions": restr, "where": r.get("LocationDescription", ""),
            "updated": datetime.fromtimestamp(r["LastUpdated"], timezone.utc) if r.get("LastUpdated") else None}


def odot_status(run_dir, p):
    """Nearest ODOT TripCheck road & weather report on the pass's highway, within 10 km."""
    data = load_run_json(run_dir, "odot_rw_reports.json") or {}
    meta = (load_run_json(run_dir, "odot_rw_metadata.json") or {}).get("road-weather-items", {})
    def lookup(lst, key, val, out="desc"):
        for x in meta.get(lst, []):
            if str(x.get(key)) == str(val).split(".")[0]:
                return next((v for k, v in x.items() if k.endswith(out)), "")
        return ""
    best = None
    for r in data.get("road-weather-reports", []):
        loc = r.get("location", {})
        if norm_route(loc.get("route-id")) != norm_route(p.get("odot_route") or p["route"]):
            continue
        a = (loc.get("start-location", {}).get("start-lat"), loc.get("start-location", {}).get("start-long"))
        b = (loc.get("end-location", {}).get("end-lat"), loc.get("end-location", {}).get("end-long"))
        if None in a + b:
            continue
        d = seg_km(p["lat"], p["lon"], a, b)
        if best is None or d < best[0]:
            best = (d, r)
    if not best or best[0] > 10:
        return None
    r = best[1]
    road = lookup("road-condition-list", "road-cond-id", r.get("road-conditions", {}).get("road-cond-id"))
    weather = lookup("weather-condition-list", "weather-id", r.get("weather-conditions", {}).get("weather-id"))
    restr = []
    drive = lookup("driving-restriction-list", "restriction-id", r.get("driving-restriction", {}).get("restriction-id"))
    if drive and not re.search(r"no restriction", drive, re.I):
        restr.append(("Chains and tires", drive))
    cv = r.get("commercial-vehicle-restriction", {}).get("restriction-type") or ""
    if cv and not re.search(r"no restriction", cv, re.I):
        restr.append(("Trucks", cv))
    if txt(r.get("comments")):
        restr.append(("Notes", txt(r.get("comments"))))
    if isinstance(r.get("adjacent-snow-depth"), (int, float)) and r["adjacent-snow-depth"] > 0:
        restr.append(("Snow beside the road", f'{r["adjacent-snow-depth"]:g} in'))
    try:
        updated = datetime.fromisoformat(r["entry-time"])
    except Exception:
        updated = None
    try:
        expired = datetime.fromisoformat(r["expiry-time"]) < datetime.now(timezone.utc)
    except Exception:
        expired = False
    if not road or re.fullmatch(r"(no report|none|n/?a)", road.strip(), re.I):
        if not restr:
            return None
    return {"road": road, "weather": "" if re.match(r"no report", weather or "", re.I) else weather,
            "temp": "", "restrictions": restr, "where": r.get("location", {}).get("location-name", "").title(),
            "updated": updated, "expired": expired}


def nws_forecast(lat, lon):
    try:
        pt = get_json(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}")
        fc = get_json(pt["properties"]["forecast"])
        return fc["properties"]["periods"][:4]
    except Exception:
        return []



# ---------------------------------------------------------------- status

LEVELS = {
    "closed":  ("is-closed",  "Closed"),
    "snowice": ("is-snowice", "Snow or ice on the road"),
    "caution": ("is-caution", "Wet road, take care"),
    "clear":   ("is-clear",   "Clear road"),
    "unknown": ("is-unknown", "No current report"),
}


INFO_ONLY = {"Notes", "Snow beside the road"}  # shown, but not used to pick the status colour


def classify(st):
    """Map official DOT wording to one of the five road-status levels."""
    if not st:
        return "unknown"
    text = " ".join([st.get("road", "")] + [t for k, t in st.get("restrictions", []) if k not in INFO_ONLY]).lower()
    text = text.replace("no chain controls", "").replace("no restrictions", "").replace("no report", "")
    if not text.strip():
        return "unknown"
    if re.search(r"\b(closed|closure)\b", text) and "not closed" not in text:
        return "closed"
    if re.search(r"snow|ice|icy|slush|chains? (are )?required|\br-[123]\b|chain control|traction tires required", text):
        return "snowice"
    if re.search(r"wet|standing water|traction tires|carry chains|fog|caution", text):
        return "caution"
    if re.search(r"bare|dry|no chain|open", text) or st.get("road"):
        return "clear"
    return "unknown"


# ---------------------------------------------------------------- pieces

WORDMARK = ('<svg viewBox="0 0 26 20" aria-hidden="true"><path d="M1 19 9 5l4 6 4-7 8 15z" fill="#0f5c45"/>'
            '<path d="m9 5 2.2 3.8-1.5-.6-1 1.2-.9-1.4-1.4.6z" fill="#fff"/></svg>')


STATE_ROUTE = {"OR": "Oregon", "WA": "Washington", "CA": "California", "ID": "Idaho", "WY": "Wyoming"}


def shield(route):
    """Inline SVG route marker: interstate shield for I-xx, US shield for US xx, plain oval for state routes."""
    num = route.split()[-1].replace("I-", "")
    prefix = route.split()[0]
    if prefix in STATE_ROUTE:
        return (f'<svg class="shield" viewBox="0 0 36 36" role="img" aria-label="{STATE_ROUTE[prefix]} Route {e(num)}">'
                '<ellipse cx="18" cy="18" rx="16" ry="13" fill="#fff" stroke="#1e2328" stroke-width="2"/>'
                f'<text x="18" y="23" text-anchor="middle" font-family="Overpass,Arial" font-weight="800" '
                f'font-size="{13 if len(num) < 3 else 11}" fill="#1e2328">{e(num)}</text></svg>')
    if route.startswith("I-"):
        return (f'<svg class="shield" viewBox="0 0 36 36" role="img" aria-label="Interstate {e(num)}">'
                '<path d="M3 4c5 1.5 10 1 15-1.5C23 5 28 5.5 33 4c1.5 12-1 23-15 30C4 27 1.5 16 3 4z" fill="#fff"/>'
                '<path d="M5 6c4.3 1.2 8.7.8 13-1.3 4.3 2.1 8.7 2.5 13 1.3l.3 5H4.7z" fill="#b42318"/>'
                '<path d="M4.8 12h26.4c-.4 9.6-3.4 16.4-13.2 20.4C8.2 28.4 5.2 21.6 4.8 12z" fill="#1d4f91"/>'
                f'<text x="18" y="26" text-anchor="middle" font-family="Overpass,Arial" font-weight="800" font-size="11" fill="#fff">{e(num)}</text></svg>')
    return (f'<svg class="shield" viewBox="0 0 36 36" role="img" aria-label="US Route {e(num)}">'
            '<path d="M5 3h26c.5 4 2 6 2 10 0 9-6 15-15 20C9 28 3 22 3 13c0-4 1.5-6 2-10z" fill="#fff" stroke="#1e2328" stroke-width="2"/>'
            f'<text x="18" y="23" text-anchor="middle" font-family="Overpass,Arial" font-weight="800" font-size="13" fill="#1e2328">{e(num)}</text></svg>')


def head(title, desc, path):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<link rel="canonical" href="{BASE}{path}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Overpass:wght@700;800&family=Public+Sans:wght@400;600&display=swap">
<link rel="stylesheet" href="/styles.css">
<meta name="theme-color" content="#0f5c45"></head>
<body><header class="site-header"><div class="wrap"><a class="wordmark" href="/" aria-label="Conditions Now, home">{WORDMARK}<span class="wordmark__a">Conditions</span><span class="wordmark__b">Now</span></a>
<nav><a href="/#passes">All passes</a></nav></div></header>
<main class="wrap">"""


FOOT = """</main><footer class="site-footer"><div class="wrap">
<p>Camera images and official reports belong to the state transportation departments that publish them.
Conditions change fast: always check official closures and chain rules before you drive.</p>
<p><a href="/sources/">Data sources and disclaimers</a> · Questions or corrections: <a href="mailto:hello@conditionsnow.com">hello@conditionsnow.com</a></p>
</div></footer></body></html>
"""


def verdict(st, level, state, tz=TZ):
    cls, label = LEVELS[level]
    label = (st or {}).get("label") or label
    dot, link = DOT_NAMES[state]
    if not st:
        return (f'<section class="verdict {cls}" aria-label="Current road status"><p class="verdict__label">{label}</p>'
                f'<p class="verdict__meta">We have no current official road report for this spot. Check the cameras below '
                f'and <a href="{link}">{dot}</a>.</p></section>')
    rows = []
    if st.get("weather"):
        rows.append(f"<dt>Weather</dt><dd>{e(st['weather'])}</dd>")
    if st.get("temp"):
        rows.append(f"<dt>Temperature</dt><dd>{e(st['temp'])}</dd>")
    for d, t in st.get("restrictions", []):
        rows.append(f"<dt>{e(d or 'Restrictions')}</dt><dd>{e(t)}</dd>")
    when = f"updated {local(st['updated'], tz)}" if st.get("updated") else "latest report"
    where = f" for {e(st['where'])}" if st.get("where") else ""
    return (f'<section class="verdict {cls}" aria-label="Current road status">'
            f'<p class="verdict__label">{label}</p>'
            f'<p class="verdict__official">{e(st.get("road") or "")}</p>'
            f'{"<dl>" + "".join(rows) + "</dl>" if rows else ""}'
            f'<p class="verdict__meta">Official {dot} report{where}, {when}.'
            f'{" ODOT marks this report as past its expiry time, so trust the cameras more." if st.get("expired") else ""}</p></section>')


# ---------------------------------------------------------------- build

LAZY = 'loading="lazy" '


def build():
    with open(os.path.join(ROOT, "config", "passes.json")) as f:
        passes = json.load(f)["ready"]
    run_dir, manifest = latest_run()
    fetched = datetime.fromisoformat(manifest["fetched_at"]) if manifest else datetime.now(timezone.utc)
    checked = fetched.astimezone(TZ).strftime("%-I:%M %p %Z")
    try:
        cc_rows = get_json(CC_URL, timeout=30)["data"]
    except Exception:
        cc_rows = []

    os.makedirs(SITE, exist_ok=True)
    shutil.copy(os.path.join(ROOT, "site", "styles.css"), os.path.join(SITE, "styles.css"))
    urls, summary = ["/"], []
    stamp = int(fetched.timestamp())

    def mirror(c):
        """Copy the collected image into the site and return its URL (we serve our own copies)."""
        src = os.path.join(run_dir, c["pass"], f'{c["cam"]}.jpg')
        rel = f'/cams/{c["pass"]}/{c["cam"]}.jpg'
        os.makedirs(os.path.join(SITE, "cams", c["pass"]), exist_ok=True)
        shutil.copy(src, os.path.join(SITE, rel.lstrip("/")))
        return f"{rel}?t={stamp}"

    for p in passes:
        tz = ZoneInfo(p.get("tz", "America/Los_Angeles"))
        src = p.get("source", "")
        st = None
        try:
            if not run_dir:
                pass
            elif p["state"] == "WA":
                st = wsdot_status(run_dir, p["wsdot_name"])
            elif p["state"] == "CA":
                st = caltrans_status(p["cc_route"], cc_rows)
            elif src == "odot-tripcheck":
                st = odot_status(run_dir, p)
            elif src == "idaho-511" and p["state"] == "ID":
                st = idaho_status(run_dir, p)
        except Exception as ex:  # a feed changing shape must never stop the deploy
            print(f"status failed for {p['slug']}: {type(ex).__name__}: {ex}")
        level = classify(st)
        cams = [c for c in manifest.get("cams", []) if c["pass"] == p["slug"] and c.get("saved")]
        for c in cams:
            c["site_url"] = mirror(c)
        checked = fetched.astimezone(tz).strftime("%-I:%M %p %Z")
        fc = nws_forecast(p["lat"], p["lon"])
        name = p["name"].split(" (")[0]
        title = f"{name} conditions and live cameras ({p['route']}) | Conditions Now"
        desc = (f"Is {name} snowy right now? Live {STATE_NAMES[p['state']]} DOT cameras, the official road report, "
                f"chain rules and the forecast for {p['route']} between {p['between']}.")
        cam_html = "".join(
            f'<figure class="cam"><img src="{c["site_url"]}" alt="Live camera: {e(c["title"])}" '
            f'width="640" height="480" {LAZY if i else ""}decoding="async">'
            f'<figcaption><span>{e(c["title"])}</span><time datetime="{fetched.isoformat()}">checked {checked}</time></figcaption></figure>'
            for i, c in enumerate(cams)) or '<p class="note">These cameras are offline right now.</p>'
        credit = CAM_CREDIT.get(src, DOT_NAMES[p["state"]][0])
        fc_html = "".join(
            f'<div class="forecast__period"><div class="forecast__name">{e(x["name"])}</div>'
            f'<div class="forecast__temp">{x["temperature"]}°{e(x["temperatureUnit"])}</div>'
            f'<div class="forecast__text">{e(x["shortForecast"])}</div></div>' for x in fc)
        summit = p.get("summit", True)
        sign = (f'<div class="summit-sign"><div class="summit-sign__face"><h1>{e(name)}</h1>'
                f'<p class="summit-sign__sub">{"<span>Summit</span>" if summit else ""}<span>Elev {p["elev_ft"]:,} ft</span></p></div></div>')
        disclaimer = ""
        if src == "odot-tripcheck":
            disclaimer = ('<details class="disclaimer"><summary>ODOT data disclaimer</summary>'
                          + "".join(f"<p>{e(t)}</p>" for t in ODOT_DISCLAIMER) + "</details>")
        dot_name, dot_link = DOT_NAMES[p["state"]]
        body = f"""
{sign}
<p class="route-line">{shield(p['route'])}<span>{e(p['route'])} between {e(p['between'])}</span></p>
{verdict(st, level, p['state'], tz)}
<h2>Live cameras</h2>
<div class="cams">{cam_html}</div>
<p class="note">Camera images from {e(credit)}. Soon each camera will get its own reading: snow on the road, visibility and traffic.</p>
<h2>{"Summit forecast" if summit else "Forecast"}</h2>
{f'<div class="forecast">{fc_html}</div><p class="note">From the National Weather Service.</p>' if fc_html else '<p class="note">The forecast did not load. Try again in a few minutes.</p>'}
<h2>Before you go</h2>
<ul class="checklist"><li>Check the official report on <a href="{dot_link}">{dot_name}</a> right before you leave.</li>
<li>Carry chains from November to April. Rules can change within the hour.</li>
<li>Fill up before the climb; services near the top are limited.</li></ul>
{disclaimer}
"""
        path = f"/passes/{p['slug']}/"
        os.makedirs(os.path.join(SITE, "passes", p["slug"]), exist_ok=True)
        with open(os.path.join(SITE, "passes", p["slug"], "index.html"), "w") as f:
            f.write(head(title, desc, path) + body + FOOT)
        urls.append(path)
        summary.append((p, st, level))

    checked = fetched.astimezone(TZ).strftime("%-I:%M %p %Z")

    def thumb(slug):
        c = next((c for c in manifest.get("cams", []) if c["pass"] == slug and c.get("saved")), None)
        return (f'<img class="pass-row__thumb" src="{c["site_url"]}" alt="" '
                f'width="112" height="84" loading="lazy" decoding="async">') if c else ""

    counts = {k: sum(1 for *_, lv in summary if lv == k) for k in LEVELS}
    tally_words = {"closed": "closed", "snowice": "with snow or ice", "caution": "wet",
                   "clear": "clear or no chain controls", "unknown": "without a report"}
    tally = "".join(f'<li class="{LEVELS[k][0]}"><span class="status-mark">{n} {tally_words[k]}</span></li>'
                    for k, n in counts.items() if n)
    groups = ""
    for state in sorted(dict.fromkeys(p["state"] for p, *_ in summary), key=STATE_ORDER.index):
        rows = "".join(
            f'<li><a class="pass-row" href="/passes/{p["slug"]}/">{shield(p["route"])}'
            f'<span class="pass-row__name">{e(p["name"].split(" (")[0])}</span>'
            f'<span class="pass-row__status {LEVELS[lv][0]}"><span class="status-mark">{(st or {}).get("label") or LEVELS[lv][1]}</span>'
            f'<span class="pass-row__road">{"" if (st or {}).get("label") else e((st or {}).get("road") or "")}</span></span>'
            f'{thumb(p["slug"])}</a></li>'
            for p, st, lv in summary if p["state"] == state)
        groups += f"<h2>{STATE_NAMES[state]}</h2><ul>{rows}</ul>"
    home = f"""
<div class="board-intro"><h1>Mountain passes right now</h1>
<p>Live DOT cameras and official road reports, checked every 15 minutes. Last check {checked}.</p>
<ul class="tally">{tally}</ul></div>
<section class="board" id="passes">{groups}</section>
"""
    with open(os.path.join(SITE, "index.html"), "w") as f:
        f.write(head("Mountain pass conditions and live cameras | Conditions Now",
                     "Is the pass snowy right now? Live DOT cameras, official road reports and chain rules for Snoqualmie, Stevens, Donner, Santiam, Lookout and more, checked every 15 minutes.",
                     "/") + home + FOOT)
    sources = f"""
<h1>Data sources</h1>
<p>Conditions Now brings together information that state transportation departments and the National Weather Service publish.
We download camera images every 15 minutes and serve our own copies, credited to the agency that took them.</p>
<ul class="checklist">
<li><strong>Washington:</strong> cameras and mountain pass reports from <a href="https://wsdot.com/travel/real-time/mountainpasses">WSDOT</a>.</li>
<li><strong>Oregon:</strong> cameras and road and weather reports from the Oregon Department of Transportation, via the <a href="https://www.tripcheck.com/">TripCheck</a> API.</li>
<li><strong>California:</strong> cameras and chain controls from <a href="https://quickmap.dot.ca.gov/">Caltrans</a>.</li>
<li><strong>Idaho, and Teton Pass in Wyoming:</strong> cameras and road conditions from the Idaho Transportation Department, via <a href="https://511.idaho.gov/">Idaho 511</a>. The Teton Pass camera is operated by <a href="https://www.wyoroad.info/">WYDOT</a>.</li>
<li><strong>Forecasts:</strong> the <a href="https://www.weather.gov/">National Weather Service</a>.</li>
</ul>
<p>Conditions change fast. Always check official closures and chain rules before you drive.</p>
<h2>ODOT data disclaimer</h2>
{"".join(f"<p>{e(t)}</p>" for t in ODOT_DISCLAIMER)}
"""
    os.makedirs(os.path.join(SITE, "sources"), exist_ok=True)
    with open(os.path.join(SITE, "sources", "index.html"), "w") as f:
        f.write(head("Data sources and disclaimers | Conditions Now",
                     "Where Conditions Now gets its camera images, road reports and forecasts.", "/sources/") + sources + FOOT)
    urls.append("/sources/")
    today = fetched.date().isoformat()
    with open(os.path.join(SITE, "sitemap.xml"), "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                + "".join(f"<url><loc>{BASE}{u}</loc><lastmod>{today}</lastmod></url>" for u in urls) + "</urlset>\n")
    with open(os.path.join(SITE, "robots.txt"), "w") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    with open(os.path.join(SITE, "CNAME"), "w") as f:
        f.write("conditionsnow.com\n")
    print(f"built {len(urls)} pages into {SITE}")


if __name__ == "__main__":
    build()
