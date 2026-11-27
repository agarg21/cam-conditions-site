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
            "updated": None, "chain_points": len(active),
            "label": None if active else "No chain controls now"}


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


def classify(st):
    """Map official DOT wording to one of the five road-status levels."""
    if not st:
        return "unknown"
    text = " ".join([st.get("road", "")] + [t for _, t in st.get("restrictions", [])]).lower()
    text = text.replace("no chain controls", "").replace("no restrictions", "")
    if re.search(r"\b(closed|closure)\b", text) and "not closed" not in text:
        return "closed"
    if re.search(r"snow|ice|icy|slush|chains? (are )?required|\br-[123]\b|chain control", text):
        return "snowice"
    if re.search(r"wet|standing water|traction tires|fog|caution", text):
        return "caution"
    if re.search(r"bare|dry|no chain|open", text) or st.get("road"):
        return "clear"
    return "unknown"


# ---------------------------------------------------------------- pieces

WORDMARK = ('<svg viewBox="0 0 26 20" aria-hidden="true"><path d="M1 19 9 5l4 6 4-7 8 15z" fill="#0f5c45"/>'
            '<path d="m9 5 2.2 3.8-1.5-.6-1 1.2-.9-1.4-1.4.6z" fill="#fff"/></svg>')


def shield(route):
    """Inline SVG route marker: interstate shield for I-xx, US shield for US xx."""
    num = route.split()[-1].replace("I-", "")
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
<body><header class="site-header"><div class="wrap"><a class="wordmark" href="/">{WORDMARK}Conditions Now</a>
<nav><a href="/#passes">All passes</a></nav></div></header>
<main class="wrap">"""


FOOT = """</main><footer class="site-footer"><div class="wrap">
<p>Camera images and official reports belong to the state transportation departments that publish them.
Conditions change fast: always check official closures and chain rules before you drive.</p>
<p>Questions or corrections: <a href="mailto:hello@conditionsnow.com">hello@conditionsnow.com</a></p>
</div></footer></body></html>
"""


def verdict(st, level, state):
    cls, label = LEVELS[level]
    label = (st or {}).get("label") or label
    dot, link = DOT_NAMES[state]
    if not st:
        return (f'<section class="verdict {cls}" aria-label="Current road status"><p class="verdict__label">{label}</p>'
                f'<p class="verdict__meta">The official report did not load. Check <a href="{link}">{dot}</a>.</p></section>')
    rows = []
    if st.get("weather"):
        rows.append(f"<dt>Weather</dt><dd>{e(st['weather'])}</dd>")
    if st.get("temp"):
        rows.append(f"<dt>Temperature</dt><dd>{e(st['temp'])}</dd>")
    for d, t in st.get("restrictions", []):
        rows.append(f"<dt>{e(d or 'Restrictions')}</dt><dd>{e(t)}</dd>")
    when = f"updated {local(st['updated'])}" if st.get("updated") else "latest report"
    return (f'<section class="verdict {cls}" aria-label="Current road status">'
            f'<p class="verdict__label">{label}</p>'
            f'<p class="verdict__official">{e(st.get("road") or "")}</p>'
            f'{"<dl>" + "".join(rows) + "</dl>" if rows else ""}'
            f'<p class="verdict__meta">Official {dot} report, {when}.</p></section>')


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
    for p in passes:
        st = wsdot_status(run_dir, p["wsdot_name"]) if p["state"] == "WA" and run_dir else (
            caltrans_status(p["cc_route"], cc_rows) if p["state"] == "CA" else None)
        level = classify(st)
        cams = [c for c in manifest.get("cams", []) if c["pass"] == p["slug"] and c.get("saved")]
        fc = nws_forecast(p["lat"], p["lon"])
        name = p["name"].split(" (")[0]
        title = f"{name} conditions and live cameras ({p['route']}) | Conditions Now"
        desc = (f"Is {name} snowy right now? Live {STATE_NAMES[p['state']]} DOT cameras, the official road report, "
                f"chain rules and the summit forecast for {p['route']} between {p['between']}.")
        cam_html = "".join(
            f'<figure class="cam"><img src="{e(c["url"])}?t={int(fetched.timestamp())}" alt="Live camera: {e(c["title"])}" '
            f'width="640" height="480" {LAZY if i else ""}decoding="async">'
            f'<figcaption><span>{e(c["title"])}</span><time datetime="{fetched.isoformat()}">checked {checked}</time></figcaption></figure>'
            for i, c in enumerate(cams)) or '<p class="note">These cameras are offline right now.</p>'
        fc_html = "".join(
            f'<div class="forecast__period"><div class="forecast__name">{e(x["name"])}</div>'
            f'<div class="forecast__temp">{x["temperature"]}°{e(x["temperatureUnit"])}</div>'
            f'<div class="forecast__text">{e(x["shortForecast"])}</div></div>' for x in fc)
        sign = (f'<div class="summit-sign"><div class="summit-sign__face"><h1>{e(name)}</h1>'
                f'<p class="summit-sign__sub"><span>Summit</span><span>Elev {p["elev_ft"]:,} ft</span></p></div></div>')
        body = f"""
{sign}
<p class="route-line">{shield(p['route'])}<span>{e(p['route'])} between {e(p['between'])}, {e(STATE_NAMES[p['state']])}</span></p>
{verdict(st, level, p['state'])}
<h2>Live cameras</h2>
<div class="cams">{cam_html}</div>
<p class="note">Soon each camera will get its own reading: snow on the road, visibility and traffic.</p>
<h2>Summit forecast</h2>
{f'<div class="forecast">{fc_html}</div><p class="note">From the National Weather Service.</p>' if fc_html else '<p class="note">The forecast did not load. Try again in a few minutes.</p>'}
<h2>Before you go</h2>
<ul class="checklist"><li>Check the official report on <a href="{DOT_NAMES[p['state']][1]}">{DOT_NAMES[p['state']][0]}</a> right before you leave.</li>
<li>Carry chains from November to April. Rules can change within the hour.</li>
<li>Fill up before the climb; services near the summit are limited.</li></ul>
"""
        path = f"/passes/{p['slug']}/"
        os.makedirs(os.path.join(SITE, "passes", p["slug"]), exist_ok=True)
        with open(os.path.join(SITE, "passes", p["slug"], "index.html"), "w") as f:
            f.write(head(title, desc, path) + body + FOOT)
        urls.append(path)
        summary.append((p, st, level))

    def thumb(slug):
        c = next((c for c in manifest.get("cams", []) if c["pass"] == slug and c.get("saved")), None)
        return (f'<img class="pass-row__thumb" src="{e(c["url"])}?t={int(fetched.timestamp())}" alt="" '
                f'width="112" height="84" loading="lazy" decoding="async">') if c else ""

    counts = {k: sum(1 for *_, lv in summary if lv == k) for k in LEVELS}
    tally_words = {"closed": "closed", "snowice": "with snow or ice", "caution": "wet",
                   "clear": "clear or no chain controls", "unknown": "without a report"}
    tally = "".join(f'<li class="{LEVELS[k][0]}"><span class="status-mark">{n} {tally_words[k]}</span></li>'
                    for k, n in counts.items() if n)
    groups = ""
    for state in dict.fromkeys(p["state"] for p, *_ in summary):
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
                     "Is the pass snowy right now? Live DOT cameras, official road reports and chain rules for Snoqualmie, Stevens, Donner and more, checked every 15 minutes.",
                     "/") + home + FOOT)
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
