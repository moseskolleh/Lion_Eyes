"""Static website for GitHub Pages: ``floodwatch site`` -> ``_site/``.

Pages: home (latest Outlook, key figures), interactive map (warning zones and
past flood places, Leaflet + OpenStreetMap), flood history, analysis write-ups
rendered from docs/*.md, and the Outlook archive. Everything is plain HTML so
GitHub Pages can serve it with no build tooling beyond this script.
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

import markdown
import pandas as pd

from floodwatch import config, events

OUT = config.REPO_ROOT / "_site"
DOCS = config.REPO_ROOT / "docs"
TITLE = "FloodWatch Freetown"

PAGES = [  # (source markdown, output path, nav label)
    (DOCS / "concept.md", "concept.html", "Concept"),
    (DOCS / "analysis" / "hindcast-v0.md", "analysis/hindcast.html", "Hindcast"),
    (DOCS / "analysis" / "zones-v0.md", "analysis/zones.html", "Zones"),
    (DOCS / "analysis" / "subdaily-v0.md", "analysis/subdaily.html", "Half-hourly rain"),
    (DOCS / "outlook.md", "outlook-method.html", "Outlook method"),
]

CSS = """
:root{--bg:#f7f8fa;--fg:#1b1f24;--muted:#5b6470;--card:#fff;--line:#dfe3e8;--accent:#1f5fa8;
--low:#2e7d32;--elev:#b26a00;--high:#c0392b}
@media (prefers-color-scheme:dark){:root{--bg:#111418;--fg:#e6e9ed;--muted:#9aa4b1;--card:#1a1f25;
--line:#2c333b;--accent:#6aa6ec;--low:#5fbf65;--elev:#e6a23c;--high:#ef6b5b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{background:var(--card);border-bottom:1px solid var(--line)}
.wrap{max-width:1040px;margin:0 auto;padding:0 16px}
header .wrap{display:flex;flex-wrap:wrap;align-items:center;gap:6px 18px;padding:12px 16px}
header a.brand{font-weight:700;color:var(--fg);text-decoration:none;margin-right:auto}
nav a{color:var(--muted);text-decoration:none;font-size:15px}nav a:hover{color:var(--accent)}
nav{display:flex;flex-wrap:wrap;gap:4px 14px}
main{padding:24px 0 48px}a{color:var(--accent)}
h1{font-size:1.7rem;line-height:1.25;margin:.2em 0 .4em}h2{margin-top:1.8em}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:16px 0}
.muted{color:var(--muted)}.small{font-size:.9rem}
table{border-collapse:collapse;width:100%;font-size:.92rem;display:block;overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{white-space:nowrap}img{max-width:100%;height:auto;border-radius:8px;border:1px solid var(--line)}
.lvl{display:inline-block;font-weight:700;padding:1px 8px;border-radius:999px;color:#fff;font-size:.85rem}
.LOW{background:var(--low)}.ELEVATED{background:var(--elev)}.HIGH{background:var(--high)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.grid .card{margin:0}code{font-size:.9em}
footer{border-top:1px solid var(--line);padding:18px 0;color:var(--muted);font-size:.85rem}
"""


def _shell(title: str, body: str, depth: int = 0, extra_head: str = "") -> str:
    up = "../" * depth
    nav = [("index.html", "Outlook"), ("map.html", "Map"), ("floods.html", "Flood history"),
           ("concept.html", "Concept"), ("analysis/hindcast.html", "Hindcast"), ("analysis/zones.html", "Zones"),
           ("analysis/subdaily.html", "Half-hourly rain"), ("outlook/index.html", "Archive")]
    links = "".join(f'<a href="{up}{href}">{label}</a>' for href, label in nav)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · {TITLE}</title><link rel="stylesheet" href="{up}style.css">{extra_head}</head>
<body><header><div class="wrap"><a class="brand" href="{up}index.html">{TITLE}</a><nav>{links}</nav></div></header>
<main><div class="wrap">{body}</div></main>
<footer><div class="wrap">Flash-flood early warning for Freetown, Sierra Leone, from open data. Prototype; not an official warning service.
Data: ECMWF open data, NASA IMERG, CHIRPS, Copernicus DEM, OpenStreetMap contributors. <a href="https://github.com/moseskolleh/Maji">Source code</a>.</div></footer>
</body></html>"""


def _md(path: Path) -> str:
    return markdown.markdown(path.read_text(), extensions=["tables", "fenced_code", "sane_lists"])


def _latest_outlook() -> dict | None:
    files = sorted((config.DATA_DIR / "outlook").glob("*.json"))
    return json.loads(files[-1].read_text()) if files else None


def _outlook_card(o: dict | None) -> str:
    if not o:
        return '<div class="card">No Outlook has been issued yet.</div>'
    rows = "".join(
        f"<tr><td>{pd.Timestamp(d['day']):%a %d %b}</td><td><span class='lvl {d['level']}'>{d['level']}</span></td>"
        f"<td>{d['p_wet']:.0%}</td><td>{d['p_very_wet']:.0%}</td><td>{d['median_mm']:.0f} mm</td>"
        f"<td>{d['prior_3d_mm']:.0f} mm</td><td>{html.escape(', '.join(d['high_tides']) or '-')}</td></tr>"
        for d in o["days"]
    )
    wet = o.get("observed_rain_last_3_days_mm")
    wet_text = f"{wet:.0f} mm" if wet is not None else "not available"
    return f"""<div class="card"><h2 style="margin-top:0">3-day Outlook, issued {o['issued']}</h2>
<p class="muted small">ECMWF ensemble run {o['forecast_run']}. Rain in the last 3 days (satellite): {wet_text}.</p>
<table><thead><tr><th>Day</th><th>Level</th><th>Chance of a wet day</th><th>Chance of a very wet day</th>
<th>Most likely rain</th><th>Ground wetness</th><th>High tides</th></tr></thead><tbody>{rows}</tbody></table>
<p class="small muted">Levels: LOW, ELEVATED, HIGH. Thresholds are provisional until calibrated against a rainy season of
archived forecasts. <a href="outlook-method.html">How the Outlook works</a>.</p></div>"""


def _home(o: dict | None) -> str:
    body = f"""<h1>Flash-flood warnings for Freetown, from open data</h1>
<p>Freetown's streams run off steep hills and reach the low neighbourhoods within the hour, so rain itself is the
warning signal. This prototype learns from past floods and today's satellite and forecast data which rain, tide and
ground conditions flood which places, with no sensors installed yet.</p>
{_outlook_card(o)}
<div class="grid">
<div class="card"><h3 style="margin-top:0"><a href="map.html">Interactive map</a></h3><p class="small">94 warning zones (one per stream
catchment) and the places named in past flood reports.</p><a href="map.html"><img src="figures/warning_zones.png" alt="Warning zones map"></a></div>
<div class="card"><h3 style="margin-top:0"><a href="analysis/subdaily.html">When the rain falls</a></h3><p class="small">Half-hourly satellite rain around 21 past
floods: heavy rain usually comes 1-6 hours before a flood is reported.</p><a href="analysis/subdaily.html"><img src="figures/flood_rain_timelines.png" alt="Rain timelines"></a></div>
<div class="card"><h3 style="margin-top:0"><a href="analysis/hindcast.html">Does open data see past floods?</a></h3><p class="small">Over 19 rainy seasons,
flood days were clearly wetter (AUC 0.81). Daily rules catch about half of floods at about 3 false alarms per season.</p>
<a href="analysis/hindcast.html"><img src="figures/streams_and_flood_places.png" alt="Streams and flood places"></a></div>
</div>"""
    return _shell("Outlook", body)


def _map_page(o: dict | None) -> str:
    level = ""
    if o:
        worst = max(o["days"], key=lambda d: ["LOW", "ELEVATED", "HIGH"].index(d["level"]))
        level = f"Outlook issued {o['issued']}: highest level in the next 3 days <span class='lvl {worst['level']}'>{worst['level']}</span>"
    head = """<link rel="stylesheet" href="vendor/leaflet/leaflet.css">
<style>#map{height:72vh;min-height:420px;border-radius:10px;border:1px solid var(--line)}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;margin-top:10px;font-size:14px}
.sw{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:6px;vertical-align:-1px}</style>"""
    body = f"""<h1>Warning zones and past flood places</h1>
<p class="small muted">{level}</p>
<div id="map"></div>
<div id="legend" class="legend"></div>
<p class="small muted">Zones are stream catchments traced from the Copernicus 30 m elevation model; colour shows what kind
of flooding to expect. Red circles are places named in past flood reports (bigger = more events); positions are
neighbourhood centres, not exact streets. Click anything for details.</p>
<script src="vendor/leaflet/leaflet.js"></script>
<script>
const map = L.map('map').setView([8.455, -13.22], 12);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{maxZoom: 18,
  attribution: '&copy; OpenStreetMap contributors'}}).addTo(map);
function kind(p) {{
  const low = p.low_ground_km2 >= 0.1, steep = p.steep_share >= 0.15;
  return low && steep ? 'both' : low ? 'low' : steep ? 'steep' : 'other';
}}
const colours = {{low: '#0b8a8f', steep: '#b5651d', both: '#7b3fb5', other: '#8a939e'}};
const labels = {{low: 'Low ground near streams / shore', steep: 'Steep hillsides', both: 'Both', other: 'Neither marked'}};
fetch('data/zones.geojson').then(r => r.json()).then(gj => {{
  L.geoJSON(gj, {{
    filter: f => f.properties.zone_id > 0,
    style: f => ({{color: '#333', weight: 1, fillColor: colours[kind(f.properties)], fillOpacity: 0.28}}),
    onEachFeature: (f, layer) => {{
      const p = f.properties;
      layer.bindPopup(`<b>Zone ${{p.zone_id}}: ${{p.name || ''}}</b><br>Area ${{p.area_km2}} km²` +
        `<br>Low ground near streams: ${{p.low_ground_km2}} km²<br>Steep share: ${{Math.round(p.steep_share*100)}}%` +
        (p.flood_places ? `<br>Past flood places: ${{p.flood_places}}` : ''));
    }}
  }}).addTo(map);
}});
fetch('data/flood_places.geojson').then(r => r.json()).then(gj => {{
  L.geoJSON(gj, {{
    pointToLayer: (f, ll) => L.circleMarker(ll, {{radius: 5 + 3 * f.properties.events, color: '#fff', weight: 1.5,
      fillColor: '#c0392b', fillOpacity: 0.9}}),
    onEachFeature: (f, layer) => layer.bindPopup(`<b>${{f.properties.place}}</b><br>${{f.properties.events}} reported flood(s):<br>` +
      f.properties.dates.join('<br>'))
  }}).addTo(map);
}});
document.getElementById('legend').innerHTML = Object.keys(colours).map(k =>
  `<span><span class="sw" style="background:${{colours[k]}}"></span>${{labels[k]}}</span>`).join('') +
  '<span><span class="sw" style="background:#c0392b;border-radius:50%"></span>Reported flood place</span>';
</script>"""
    return _shell("Map", body, extra_head=head)


def _floods_page() -> str:
    cat = events.load_catalogue().sort_values("date", ascending=False)
    rows = []
    for _, e in cat.iterrows():
        when = f"{e['date']:%d %b %Y}" if e["date_confidence"] != "month_only" else f"{e['date']:%b %Y}"
        deaths = "" if pd.isna(e["deaths"]) else int(e["deaths"])
        src = " ".join(f'<a href="{html.escape(u)}">[{i}]</a>' for i, u in enumerate(e["sources"], 1))
        rows.append(f"<tr><td>{when}</td><td>{html.escape(e['type'].replace('_', ' '))}</td>"
                    f"<td>{html.escape(', '.join(e['locations']))}</td><td>{deaths}</td>"
                    f"<td>{html.escape(str(e['summary']))}</td><td>{src}</td></tr>")
    body = f"""<h1>Flood history</h1>
<p>{len(cat)} floods on the Freetown peninsula, 2007-2026, each from public sources (news, NDMA, Red Cross/IFRC, OCHA).
The list is incomplete, especially before 2015 and for small floods. Know of a flood that is missing? Open an issue on
<a href="https://github.com/moseskolleh/Maji/issues">GitHub</a>.</p>
<table><thead><tr><th>Date</th><th>Type</th><th>Places</th><th>Deaths</th><th>Summary</th><th>Sources</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>"""
    return _shell("Flood history", body)


def _archive_page() -> str:
    items = []
    for f in sorted((config.DATA_DIR / "outlook").glob("*.json"), reverse=True):
        o = json.loads(f.read_text())
        levels = " ".join(f"<span class='lvl {d['level']}'>{pd.Timestamp(d['day']):%d %b}</span>" for d in o["days"])
        items.append(f"<tr><td><a href='{f.stem}.html'>{o['issued']}</a></td><td>{levels}</td></tr>")
    body = f"""<h1>Outlook archive</h1><p class="muted">Every daily Outlook, newest first.</p>
<table><thead><tr><th>Issued</th><th>Levels for the next 3 days</th></tr></thead><tbody>{''.join(items)}</tbody></table>"""
    return _shell("Outlook archive", body, depth=1)


def _places_geojson() -> dict:
    places = pd.read_csv(config.DERIVED_DIR / "flood_places.csv")
    places = places[places["geocoded"]]
    cat = events.load_catalogue()
    feats = []
    for _, p in places.iterrows():
        dates = [f"{e['date']:%d %b %Y}" for _, e in cat.iterrows() if p["place"] in e["locations"]]
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
                      "properties": {"place": p["place"], "events": int(p["events"]), "dates": dates}})
    return {"type": "FeatureCollection", "features": feats}


def build(out: Path = OUT) -> Path:
    if out.exists():
        shutil.rmtree(out)
    (out / "analysis").mkdir(parents=True)
    (out / "outlook").mkdir()
    (out / "data").mkdir()
    (out / "style.css").write_text(CSS)
    for target in (out / "figures", out / "analysis" / "figures"):
        shutil.copytree(DOCS / "analysis" / "figures", target)
    shutil.copytree(config.REPO_ROOT / "site_assets" / "leaflet", out / "vendor" / "leaflet")  # Leaflet 1.9.4, BSD-2
    shutil.copy(config.DERIVED_DIR / "zones.geojson", out / "data" / "zones.geojson")
    (out / "data" / "flood_places.geojson").write_text(json.dumps(_places_geojson()))

    latest = _latest_outlook()
    (out / "index.html").write_text(_home(latest))
    (out / "map.html").write_text(_map_page(latest))
    (out / "floods.html").write_text(_floods_page())
    for src, target, label in PAGES:
        depth = target.count("/")
        (out / target).write_text(_shell(label, _md(src), depth=depth))
    for f in sorted((config.DATA_DIR / "outlook").glob("*.md")):
        (out / "outlook" / f"{f.stem}.html").write_text(_shell(f"Outlook {f.stem}", _md(f), depth=1))
    (out / "outlook" / "index.html").write_text(_archive_page())
    (out / ".nojekyll").write_text("")
    print(f"site written to {out}")
    return out
