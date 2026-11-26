#!/usr/bin/env python3
"""Build the static site from the latest collector run.

Reads config/passes.json and the newest out/<date>/<time>/ folder, adds official
DOT status (WSDOT pass reports, Caltrans chain controls) and an NWS forecast,
and writes _site/ for GitHub Pages.
"""
import glob
import html
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "_site")
BASE = "https://conditionsnow.com"
UA = "ConditionsNow/0.1 (+https://conditionsnow.com; hello@conditionsnow.com)"
TZ = ZoneInfo("America/Los_Angeles")
CC_URL = "https://cwwp2.dot.ca.gov/data/d3/cc/ccStatusD03.json"
STATE_NAMES = {"WA": "Washington", "CA": "California"}
DOT_NAMES = {"WA": ("WSDOT", "https://wsdot.com/travel/real-time/mountainpasses"),
             "CA": ("Caltrans QuickMap", "https://quickmap.dot.ca.gov/")}
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


def local(ts):
    return ts.astimezone(TZ).strftime("%-I:%M %p %Z, %b %-d")


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
            "updated": None, "chain_points": len(active)}


def nws_forecast(lat, lon):
    try:
        pt = get_json(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}")
        fc = get_json(pt["properties"]["forecast"])
        return fc["properties"]["periods"][:4]
    except Exception:
        return []


CSS = """
:root{color-scheme:light dark;--fg:#111;--muted:#666;--card:#f5f6f8;--line:#e3e5e8;--accent:#0b5cad}
@media (prefers-color-scheme:dark){:root{--fg:#eee;--muted:#aaa;--card:#1c1f24;--line:#2c3038;--accent:#6aa8ff}}
*{box-sizing:border-box}body{margin:0;font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--fg)}
header,main,footer{max-width:60rem;margin:0 auto;padding:1rem}
header a{color:inherit;text-decoration:none;font-weight:700}
h1{font-size:1.6rem;line-height:1.25;margin:.5rem 0}h2{font-size:1.15rem;margin:1.5rem 0 .5rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:1rem;margin:.75rem 0}
.status{font-size:1.1rem;font-weight:600}.muted{color:var(--muted);font-size:.9rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(16rem,1fr));gap:.75rem}
.cam img{width:100%;height:auto;border-radius:8px;display:block;background:#000}
.cam p{margin:.35rem 0 0;font-size:.9rem}
ul.passes{list-style:none;padding:0}ul.passes li{margin:.5rem 0}
a{color:var(--accent)}table{border-collapse:collapse}td{padding:.2rem .6rem .2rem 0;vertical-align:top}
"""


def page(title, desc, path, body):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<link rel="canonical" href="{BASE}{path}"><style>{CSS}</style></head>
<body><header><a href="/">Conditions Now</a></header><main>{body}</main>
<footer class="muted">Camera images and official reports belong to the state transportation departments that publish them.
Always check official closures and chain requirements before you drive. Contact: hello@conditionsnow.com</footer></body></html>
"""


def status_block(st, state):
    dot, link = DOT_NAMES[state]
    if not st:
        return f'<div class="card"><p class="status">Official report unavailable right now</p><p class="muted">Check <a href="{link}">{dot}</a>.</p></div>'
    rows = []
    if st["road"]:
        rows.append(f"<tr><td>Road</td><td><b>{e(st['road'])}</b></td></tr>")
    if st["weather"]:
        rows.append(f"<tr><td>Weather</td><td>{e(st['weather'])}</td></tr>")
    if st["temp"]:
        rows.append(f"<tr><td>Temperature</td><td>{e(st['temp'])}</td></tr>")
    for d, t in st["restrictions"]:
        rows.append(f"<tr><td>{e(d or 'Restrictions')}</td><td>{e(t)}</td></tr>")
    when = f"updated {local(st['updated'])}" if st.get("updated") else "latest report"
    return (f'<div class="card"><p class="muted">Official {dot} report, {when}</p>'
            f'<table>{"".join(rows)}</table></div>')


def build():
    with open(os.path.join(ROOT, "config", "passes.json")) as f:
        passes = json.load(f)["ready"]
    run_dir, manifest = latest_run()
    fetched = datetime.fromisoformat(manifest["fetched_at"]) if manifest else datetime.now(timezone.utc)
    try:
        cc_rows = get_json(CC_URL, timeout=30)["data"]
    except Exception:
        cc_rows = []

    os.makedirs(SITE, exist_ok=True)
    urls, summary = ["/"], []
    for p in passes:
        st = wsdot_status(run_dir, p["wsdot_name"]) if p["state"] == "WA" and run_dir else (
            caltrans_status(p["cc_route"], cc_rows) if p["state"] == "CA" else None)
        cams = [c for c in manifest.get("cams", []) if c["pass"] == p["slug"] and c.get("saved")]
        fc = nws_forecast(p["lat"], p["lon"])
        name = p["name"].split(" (")[0]
        title = f"{name} conditions & live cameras ({p['route']}) | Conditions Now"
        desc = (f"{name} road conditions now: live {STATE_NAMES[p['state']]} DOT cameras, official report, "
                f"chain requirements and forecast for {p['route']} between {p['between']}.")
        cam_html = "".join(
            f'<figure class="cam"><img src="{e(c["url"])}?t={int(fetched.timestamp())}" alt="{e(c["title"])} camera" loading="lazy">'
            f'<p>{e(c["title"])}</p></figure>' for c in cams) or '<p class="muted">Cameras offline right now.</p>'
        fc_html = "".join(f"<tr><td>{e(x['name'])}</td><td>{e(x['shortForecast'])}, {x['temperature']}°{x['temperatureUnit']}</td></tr>" for x in fc)
        body = f"""
<h1>{e(name)} conditions & live cameras</h1>
<p class="muted">{e(p['route'])} · elevation {p['elev_ft']:,} ft · between {e(p['between'])} · cameras checked {local(fetched)}</p>
{status_block(st, p['state'])}
<h2>Live cameras</h2><div class="grid">{cam_html}</div>
<p class="muted">Automatic camera readings (snow on road, visibility, traffic) are coming soon.</p>
<h2>Forecast at the summit</h2>{f'<div class="card"><table>{fc_html}</table><p class="muted">National Weather Service</p></div>' if fc_html else '<p class="muted">Forecast unavailable right now.</p>'}
<h2>Before you go</h2>
<ul><li>Official report: <a href="{DOT_NAMES[p['state']][1]}">{DOT_NAMES[p['state']][0]}</a></li>
<li>Carry chains in winter; restrictions can change within the hour.</li></ul>
"""
        path = f"/passes/{p['slug']}/"
        os.makedirs(os.path.join(SITE, "passes", p["slug"]), exist_ok=True)
        with open(os.path.join(SITE, "passes", p["slug"], "index.html"), "w") as f:
            f.write(page(title, desc, path, body))
        urls.append(path)
        summary.append((p, st))

    items = "".join(
        f'<li><a href="/passes/{p["slug"]}/"><b>{e(p["name"])}</b></a> — {e(STATE_NAMES[p["state"]])}'
        f'<br><span class="muted">{e((st or {}).get("road") or "Official report unavailable")}</span></li>'
        for p, st in summary)
    home = f"""<h1>Mountain pass conditions, live</h1>
<p>Live DOT cameras and official reports for the passes people drive most, updated every 15 minutes.
Automatic camera readings are coming soon.</p><ul class="passes">{items}</ul>
<p class="muted">Updated {local(fetched)}.</p>"""
    with open(os.path.join(SITE, "index.html"), "w") as f:
        f.write(page("Conditions Now — live mountain pass conditions and cameras",
                     "Live mountain pass conditions: DOT cameras, official road reports and chain requirements for Snoqualmie, Stevens, Donner and more.",
                     "/", home))
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
