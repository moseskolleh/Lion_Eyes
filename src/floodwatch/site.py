"""Static website for GitHub Pages: ``floodwatch site`` -> ``_site/``.

Pages: home (latest Outlook, key figures), interactive map (warning zones and
past flood places, Leaflet + OpenStreetMap), flood history, analysis write-ups
rendered from docs/*.md, and the Outlook archive. Everything is plain HTML so
GitHub Pages can serve it with no build tooling beyond this script.

The look follows Moses Kolleh Sesay's sustaintheworld site: its colour tokens
(dark by default, ``html.light-mode`` for light, chosen the same way and
remembered under the same ``theme`` key), its three self-hosted typefaces, and
its header, card and label styles.
"""

from __future__ import annotations

import html
import json
import posixpath
import re
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
    (DOCS / "analysis" / "outlook-backtest-v0.md", "analysis/backtest.html", "Outlook backtest"),
    (DOCS / "outlook.md", "outlook-method.html", "Outlook method"),
]

CSS = """
/* Type and colour from Moses Kolleh Sesay's site (sustaintheworld): Newsreader
   for titles, Inter for text, IBM Plex Mono for what is measured. Dark by
   default; html.light-mode for light, chosen as that site chooses it. */
@font-face{font-family:'Newsreader';font-style:normal;font-weight:500;font-display:swap;src:url('fonts/newsreader-latin-500.woff2') format('woff2')}
@font-face{font-family:'Newsreader';font-style:italic;font-weight:400;font-display:swap;src:url('fonts/newsreader-italic-400.woff2') format('woff2')}
@font-face{font-family:'Inter';font-style:normal;font-weight:400 600;font-display:swap;src:url('fonts/inter-latin.woff2') format('woff2')}
@font-face{font-family:'IBM Plex Mono';font-style:normal;font-weight:400;font-display:swap;src:url('fonts/ibm-plex-mono-latin-400.woff2') format('woff2')}
:root{color-scheme:dark;--primary-green:#7CFC00;--dark-bg:#0a0a0a;--darker-bg:#000;--card-bg:#1a1a1a;--card-bg-alt:#141414;
--text-primary:#fff;--text-secondary:#b0b0b0;--text-dim:#8f8f8f;--accent-color:#7CFC00;--hover-color:#9FFF4D;--accent-amber:#f2b705;
--line-color:rgba(124,252,0,.18);--line-soft:rgba(124,252,0,.08);--border-radius:6px;--bar-bg:rgba(0,0,0,.85);
--font-display:'Newsreader',Georgia,'Times New Roman',serif;--font-body:'Inter','Segoe UI',sans-serif;
--font-mono:'IBM Plex Mono','Courier New',monospace;
--lvl-low:#7CFC00;--lvl-low-text:#0a0a0a;--lvl-elev:#f2b705;--lvl-elev-text:#0a0a0a;--lvl-high:#ff5a4f;--lvl-high-text:#0a0a0a}
html.light-mode{color-scheme:light;--primary-green:#1a7a1a;--dark-bg:#f5f6f3;--darker-bg:#fff;--card-bg:#fff;--card-bg-alt:#fafbf8;
--text-primary:#161914;--text-secondary:#54584f;--text-dim:#5f635a;--accent-color:#1a7a1a;--hover-color:#146414;--accent-amber:#8a6100;
--line-color:rgba(34,139,34,.25);--line-soft:rgba(34,139,34,.1);--bar-bg:rgba(255,255,255,.88);
--lvl-low:#1a7a1a;--lvl-low-text:#fff;--lvl-elev:#8a6100;--lvl-elev-text:#fff;--lvl-high:#b3261e;--lvl-high-text:#fff}
*{margin:0;padding:0;box-sizing:border-box}[hidden]{display:none!important}
html{font-size:16px}body{font-family:var(--font-body);background:var(--dark-bg);color:var(--text-primary);line-height:1.65}
::selection{background:var(--primary-green);color:var(--darker-bg)}
.wrap{max-width:1100px;margin:0 auto;padding:0 16px}
header.bar{position:sticky;top:0;z-index:1000;background:var(--bar-bg);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
border-bottom:1px solid var(--line-soft)}
header.bar .wrap{display:flex;flex-wrap:wrap;align-items:center;gap:6px 22px;min-height:64px;padding-top:8px;padding-bottom:8px}
.brand{margin-right:auto;text-decoration:none;font-family:var(--font-display);font-weight:500;font-size:1.45rem;letter-spacing:.01em;
line-height:1;color:var(--text-primary)}
.brand em{color:var(--primary-green);font-style:italic;font-weight:400}
nav{display:flex;flex-wrap:wrap;align-items:center;gap:4px 20px}
nav a{position:relative;white-space:nowrap;font-size:.92rem;font-weight:500;color:var(--text-secondary);text-decoration:none;padding:4px 0}
nav a::after{content:'';position:absolute;left:0;bottom:0;width:0;height:1px;background:var(--primary-green);transition:width .3s ease}
nav a:hover,nav a.active{color:var(--text-primary)}nav a:hover::after,nav a.active::after{width:100%}
.theme-toggle{flex:none;width:40px;height:40px;border:1px solid var(--line-color);border-radius:50%;background:none;
color:var(--primary-green);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;
transition:background-color .3s ease,color .3s ease}
.theme-toggle:hover{background:var(--primary-green);color:var(--darker-bg)}
.theme-toggle:focus-visible{outline:2px solid var(--primary-green);outline-offset:3px}
.theme-toggle svg{width:18px;height:18px;fill:currentColor}
html.light-mode .i-moon,html:not(.light-mode) .i-sun{display:none}
main{padding:36px 0 56px}
h1,h2,h3{font-family:var(--font-display);font-weight:500;line-height:1.12;letter-spacing:-.012em;font-synthesis:none}
h1{font-size:clamp(2rem,4.6vw,3rem);letter-spacing:-.02em;margin:.1em 0 .45em}
h2{font-size:clamp(1.45rem,3vw,1.9rem);margin:1.8em 0 .5em}h3{font-size:1.3rem;margin:1.4em 0 .4em}
h4{font-family:var(--font-body);font-weight:600}
h1 em,h2 em,.highlight{color:var(--primary-green);font-style:italic;font-weight:400}
p,ul,ol{margin:0 0 1em}ul,ol{padding-left:1.4em}li{margin:.25em 0}strong{font-weight:600}
a{color:var(--accent-color);text-underline-offset:3px}a:hover{color:var(--hover-color)}
.eyebrow{font-family:var(--font-mono);font-size:.8rem;letter-spacing:.14em;text-transform:uppercase;color:var(--text-secondary);margin-bottom:10px}
.lede{font-size:1.08rem;color:var(--text-secondary);max-width:780px}
.card{background:var(--card-bg);border:1px solid var(--line-soft);border-radius:var(--border-radius);padding:20px;margin:20px 0;
transition:border-color .3s ease}
.card:hover{border-color:var(--line-color)}.card h2,.card h3{margin-top:0}
.muted{color:var(--text-secondary)}.small{font-size:.9rem}.mono{font-family:var(--font-mono)}
table{border-collapse:collapse;width:100%;font-size:.92rem;display:block;overflow-x:auto;margin:0 0 1em}
th,td{border-bottom:1px solid var(--line-soft);padding:8px 10px;text-align:left;vertical-align:top}
th{font-family:var(--font-mono);font-weight:400;font-size:.74rem;letter-spacing:.08em;text-transform:uppercase;color:var(--text-dim);white-space:nowrap}
code{font-family:var(--font-mono);font-size:.88em;background:var(--card-bg-alt);border:1px solid var(--line-soft);border-radius:3px;padding:.05em .35em}
pre{background:var(--card-bg-alt);border:1px solid var(--line-soft);border-radius:var(--border-radius);padding:12px;overflow-x:auto;margin:0 0 1em}
pre code{border:0;padding:0;background:none}
img{max-width:100%;height:auto;border-radius:var(--border-radius);border:1px solid var(--line-soft);background:#fff}
blockquote{border-left:2px solid var(--primary-green);padding-left:14px;color:var(--text-secondary);margin:0 0 1em}
hr{border:0;border-top:1px solid var(--line-soft);margin:2em 0}
.lvl{display:inline-block;font-family:var(--font-mono);font-size:.74rem;letter-spacing:.08em;padding:2px 9px;border-radius:999px}
.LOW{background:var(--lvl-low);color:var(--lvl-low-text)}.ELEVATED{background:var(--lvl-elev);color:var(--lvl-elev-text)}
.HIGH{background:var(--lvl-high);color:var(--lvl-high-text)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin-top:20px}.grid .card{margin:0}
footer{border-top:1px solid var(--line-soft);padding:22px 0 30px;color:var(--text-dim);font-size:.85rem}
footer .mono{font-size:.76rem;letter-spacing:.06em;text-transform:uppercase}
.nowrap{white-space:nowrap}
@media (max-width:640px){header.bar .wrap{gap:6px 14px}.brand{font-size:1.25rem}.theme-toggle{order:1;width:36px;height:36px}
nav{order:2;width:100%;gap:2px 14px}nav a{font-size:.86rem}}
"""


# Set the theme before the page paints, as the sustaintheworld site does: the
# visitor's stored choice ("theme" in localStorage), else their system's.
THEME_HEAD = (
    '<meta name="theme-color" content="#0a0a0a">'
    "<script>(window.fw=window.fw||{}).theme=function(t){if(!t)try{t=localStorage.getItem('theme')}catch(e){}"
    "t=document.documentElement.classList.toggle('light-mode',t=='light'||t!='dark'&&!!window.matchMedia&&"
    "matchMedia('(prefers-color-scheme: light)').matches);var m=document.querySelector('meta[name=theme-color]');"
    "if(m)m.content=t?'#f4f6f0':'#0a0a0a';document.dispatchEvent(new CustomEvent('themechange',{detail:{light:t}}))};"
    "fw.theme()</script>"
)
THEME_BUTTON = (
    '<button type="button" class="theme-toggle" id="themeToggle" aria-label="Switch to light theme" hidden>'
    '<svg class="i-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'
    '<svg class="i-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5"/>'
    '<path d="M11 1h2v4h-2zM11 19h2v4h-2zM1 11h4v2H1zM19 11h4v2h-4zM4.2 5.6l1.4-1.4 2.8 2.8-1.4 1.4zM15.6 17l1.4-1.4 2.8 2.8-1.4 1.4z'
    'M4.2 18.4l2.8-2.8 1.4 1.4-2.8 2.8zM15.6 7l2.8-2.8 1.4 1.4L17 8.4z"/></svg></button>'
)
THEME_SCRIPT = (
    "<script>(function(){var b=document.getElementById('themeToggle');if(!b)return;b.hidden=false;"
    "function sync(){var l=document.documentElement.classList.contains('light-mode');"
    "b.setAttribute('aria-label',l?'Switch to dark theme':'Switch to light theme')}sync();"
    "b.addEventListener('click',function(){var n=document.documentElement.classList.contains('light-mode')?'dark':'light';"
    "try{localStorage.setItem('theme',n)}catch(e){}fw.theme(n);sync()})})();</script>"
)
ACTIVE = ' class="active"'
NAV = [("index.html", "Outlook"), ("map.html", "Map"), ("floods.html", "Flood history"),
       ("concept.html", "Concept"), ("analysis/hindcast.html", "Hindcast"), ("analysis/zones.html", "Zones"),
       ("analysis/subdaily.html", "Half-hourly rain"), ("analysis/backtest.html", "Backtest"),
       ("outlook/index.html", "Archive")]


def _shell(title: str, body: str, depth: int = 0, extra_head: str = "", path: str = "") -> str:
    up = "../" * depth
    links = "".join(f'<a href="{up}{href}"{ACTIVE if href == path else ""}>{label}</a>' for href, label in NAV)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{THEME_HEAD}
<title>{html.escape(title)} · {TITLE}</title><link rel="stylesheet" href="{up}style.css">{extra_head}</head>
<body><header class="bar"><div class="wrap"><a class="brand" href="{up}index.html">FloodWatch <em>Freetown</em></a>
<nav>{links}</nav>{THEME_BUTTON}</div></header>
<main><div class="wrap">{body}</div></main>
<footer><div class="wrap"><p class="mono">Prototype · not an official warning service</p>
<p>Flash-flood early warning for Freetown, Sierra Leone, from open data. Data: ECMWF open data, NASA IMERG, CHIRPS,
Copernicus DEM, Overture Maps, Meta HRSL, OpenStreetMap contributors. <a href="https://github.com/moseskolleh/Maji">Source code</a>.</p></div></footer>
{THEME_SCRIPT}</body></html>"""


_LIST_ITEM = re.compile(r"\s*([-*+]|\d+\.)\s")


def _blank_before_lists(text: str) -> str:
    """GitHub renders a list straight after a paragraph line; Python-Markdown
    needs a blank line first, or the items run into the paragraph."""
    out, prev, fence = [], "", False
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
        if (not fence and _LIST_ITEM.match(line) and prev.strip() and not _LIST_ITEM.match(prev)
                and not prev.startswith(("|", " ", "\t"))):
            out.append("")
        out.append(line)
        prev = line
    return "\n".join(out) + "\n"


def _md(path: Path, target: str | None = None) -> str:
    """Render a markdown doc. Links to other docs that are site pages are
    pointed at their HTML pages (relative to `target`, this page's output path)."""
    page = markdown.markdown(_blank_before_lists(path.read_text()), extensions=["tables", "fenced_code", "sane_lists"])
    if target is not None:
        here = posixpath.dirname(target) or "."
        for src, out, _ in PAGES:
            link = posixpath.relpath(src.as_posix(), path.parent.as_posix())
            page = page.replace(f'href="{link}"', f'href="{posixpath.relpath(out, here)}"')
    return page


def _latest_outlook() -> dict | None:
    files = sorted((config.DATA_DIR / "outlook").glob("*.json"))
    return json.loads(files[-1].read_text()) if files else None


def _outlook_card(o: dict | None) -> str:
    if not o:
        return '<div class="card">No Outlook has been issued yet.</div>'
    rows = "".join(
        f"<tr><td class='nowrap'>{pd.Timestamp(d['day']):%a %d %b}</td><td><span class='lvl {d['level']}'>{d['level']}</span></td>"
        f"<td>{d['p_wet']:.0%}</td><td>{d['p_very_wet']:.0%}</td><td class='nowrap'>{d['median_mm']:.0f} mm</td>"
        f"<td class='nowrap'>{d['prior_3d_mm']:.0f} mm</td>"
        f"<td class='nowrap'>{'<br>'.join(html.escape(t) for t in d['high_tides']) or '-'}</td></tr>"
        for d in o["days"]
    )
    wet = o.get("observed_rain_last_3_days_mm")
    wet_text = f"{wet:.0f} mm" if wet is not None else "not available"
    return f"""<div class="card"><p class="eyebrow">3-day Outlook · issued {o['issued']}</p>
<p class="muted small">ECMWF ensemble run {o['forecast_run']}. Rain in the last 3 days (satellite): {wet_text}.</p>
<table><thead><tr><th>Day</th><th>Level</th><th>Chance of a wet day</th><th>Chance of a very wet day</th>
<th>Most likely rain</th><th>Ground wetness</th><th>High tides</th></tr></thead><tbody>{rows}</tbody></table>
<p class="small muted">Levels: LOW, ELEVATED, HIGH. Thresholds are provisional until calibrated against a rainy season of
archived forecasts. <a href="outlook-method.html">How the Outlook works</a>.</p></div>"""


def _home(o: dict | None) -> str:
    body = f"""<p class="eyebrow">Flash-flood early warning · Freetown, Sierra Leone</p>
<h1>Rain is the <em>warning</em></h1>
<p class="lede">Freetown's streams run off steep hills and reach the low neighbourhoods within the hour, so rain itself is
the warning signal. This prototype learns from past floods, and from today's satellite and forecast data, which rain,
tide and ground conditions flood which places, with no sensors installed yet.</p>
{_outlook_card(o)}
<div class="grid">
<div class="card"><h3><a href="map.html">Interactive map</a></h3><p class="small">94 warning zones (one per stream
catchment) and the places named in past flood reports.</p><a href="map.html"><img src="figures/warning_zones.png" alt="Warning zones map"></a></div>
<div class="card"><h3><a href="analysis/subdaily.html">When the rain falls</a></h3><p class="small">Half-hourly satellite rain around 28 past
floods: heavy rain usually comes 1-6 hours before a flood is reported.</p><a href="analysis/subdaily.html"><img src="figures/flood_rain_timelines.png" alt="Rain timelines"></a></div>
<div class="card"><h3><a href="analysis/hindcast.html">Does open data see past floods?</a></h3><p class="small">Over 19 rainy seasons,
flood days were clearly wetter (AUC 0.82). Daily rules catch about half of floods at about 3 false alarms per season.</p>
<a href="analysis/hindcast.html"><img src="figures/streams_and_flood_places.png" alt="Streams and flood places"></a></div>
<div class="card"><h3><a href="analysis/backtest.html">Would the forecasts have warned?</a></h3><p class="small">Replaying this
Outlook on 2024-2026 forecasts: HIGH came in time before 4 of 9 floods, but on only about 1 in 9 ordinary rainy-season
mornings. ELEVATED is common (over a third of mornings), so treat it as "watch".</p></div>
</div>"""
    return _shell("Outlook", body, path="index.html")


def _map_page(o: dict | None) -> str:
    level = ""
    if o:
        worst = max(o["days"], key=lambda d: ["LOW", "ELEVATED", "HIGH"].index(d["level"]))
        level = f"Outlook issued {o['issued']}: highest level in the next 3 days <span class='lvl {worst['level']}'>{worst['level']}</span>"
    head = """<link rel="stylesheet" href="vendor/leaflet/leaflet.css">
<style>#map{height:72vh;min-height:420px;border-radius:var(--border-radius);border:1px solid var(--line-color)}
.leaflet-container{font-family:var(--font-body);background:var(--dark-bg)}
.leaflet-popup-content-wrapper,.leaflet-popup-tip{background:var(--card-bg);color:var(--text-primary);border:1px solid var(--line-color)}
.leaflet-popup-content{font-size:.88rem;line-height:1.5}
.leaflet-bar a{background:var(--card-bg);color:var(--text-primary);border-color:var(--line-soft)}
.leaflet-bar a:hover{background:var(--card-bg-alt)}
.leaflet-container img{border:0;border-radius:0;background:none}
.leaflet-tile-pane{filter:grayscale(.85) contrast(.9) brightness(1.03)}
html:not(.light-mode) .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) grayscale(.75) brightness(.8) contrast(.9)}
.leaflet-control-attribution{background:var(--bar-bg)!important;color:var(--text-dim)}
.leaflet-control-attribution a{color:var(--accent-color)}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;margin-top:10px;font-size:.86rem;color:var(--text-secondary)}
.sw{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:6px;vertical-align:-1px}</style>"""
    body = f"""<p class="eyebrow">Map</p>
<h1>Warning zones and <em>past floods</em></h1>
<p class="small muted">{level}</p>
<div id="map"></div>
<div id="legend" class="legend"></div>
<p class="small muted" style="margin-top:12px">Zones are stream catchments traced from the Copernicus 30 m elevation model; colour shows what kind
of flooding to expect. People counts are estimates from Meta's 30 m population map (HRSL). Red circles are places named in past flood reports (bigger = more events); positions are
neighbourhood centres, not exact streets. Click anything for details.</p>
<script src="vendor/leaflet/leaflet.js"></script>
<script>
const map = L.map('map').setView([8.455, -13.22], 12);
// Basemap: OpenStreetMap's standard tiles, which need no API key (CARTO's now do).
// The CSS above mutes them in light mode and turns them dark in dark mode.
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}}).addTo(map);
function kind(p) {{
  const low = p.low_ground_km2 >= 0.1, steep = p.steep_share >= 0.15;
  return low && steep ? 'both' : low ? 'low' : steep ? 'steep' : 'other';
}}
const colours = {{low: '#22b8c9', steep: '#f2b705', both: '#b48cff', other: '#8a939e'}};
const labels = {{low: 'Low ground near streams / shore', steep: 'Steep hillsides', both: 'Both', other: 'Neither marked'}};
fetch('data/zones.geojson').then(r => r.json()).then(gj => {{
  L.geoJSON(gj, {{
    filter: f => f.properties.zone_id > 0,
    style: f => ({{color: '#8a939e', weight: 0.8, fillColor: colours[kind(f.properties)], fillOpacity: 0.32}}),
    onEachFeature: (f, layer) => {{
      const p = f.properties;
      const fmt = v => {{  // estimates: round to the nearest 100 (or 10 below 1,000)
        if (v === undefined || v === null) return '?';
        const step = v >= 1000 ? 100 : 10;
        return (Math.round(v / step) * step).toLocaleString('en');
      }};
      layer.bindPopup(`<b>Zone ${{p.zone_id}}: ${{p.name || ''}}</b><br>Area ${{p.area_km2}} km²` +
        `<br>People: about ${{fmt(p.people)}}` +
        `<br>On low ground near streams: about ${{fmt(p.people_low_ground)}} people (${{p.low_ground_km2}} km²)` +
        `<br>On steep slopes: about ${{fmt(p.people_steep)}} people (${{Math.round(p.steep_share*100)}}% of the zone)` +
        (p.flood_places ? `<br>Past flood places: ${{p.flood_places}}` : ''));
    }}
  }}).addTo(map);
}});
fetch('data/flood_places.geojson').then(r => r.json()).then(gj => {{
  L.geoJSON(gj, {{
    pointToLayer: (f, ll) => L.circleMarker(ll, {{radius: 5 + 3 * f.properties.events, color: '#fff', weight: 1.5,
      fillColor: '#ff5a4f', fillOpacity: 0.9}}),
    onEachFeature: (f, layer) => layer.bindPopup(`<b>${{f.properties.place}}</b><br>${{f.properties.events}} reported flood(s):<br>` +
      f.properties.dates.join('<br>'))
  }}).addTo(map);
}});
document.getElementById('legend').innerHTML = Object.keys(colours).map(k =>
  `<span><span class="sw" style="background:${{colours[k]}}"></span>${{labels[k]}}</span>`).join('') +
  '<span><span class="sw" style="background:#ff5a4f;border-radius:50%"></span>Reported flood place</span>';
</script>"""
    return _shell("Map", body, extra_head=head, path="map.html")


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
    body = f"""<p class="eyebrow">Record</p><h1>Flood <em>history</em></h1>
<p>{len(cat)} floods on the Freetown peninsula, 2007-2026, each from public sources (news, NDMA, Red Cross/IFRC, OCHA).
The list is incomplete, especially before 2015 and for small floods. Know of a flood that is missing? Open an issue on
<a href="https://github.com/moseskolleh/Maji/issues">GitHub</a>.</p>
<table><thead><tr><th>Date</th><th>Type</th><th>Places</th><th>Deaths</th><th>Summary</th><th>Sources</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>"""
    return _shell("Flood history", body, path="floods.html")


def _archive_page() -> str:
    items = []
    for f in sorted((config.DATA_DIR / "outlook").glob("*.json"), reverse=True):
        o = json.loads(f.read_text())
        levels = " ".join(f"<span class='lvl {d['level']}'>{pd.Timestamp(d['day']):%d %b}</span>" for d in o["days"])
        items.append(f"<tr><td><a href='{f.stem}.html'>{o['issued']}</a></td><td>{levels}</td></tr>")
    body = f"""<p class="eyebrow">Record</p><h1>Outlook <em>archive</em></h1><p class="muted">Every daily Outlook, newest first.</p>
<table><thead><tr><th>Issued</th><th>Levels for the next 3 days</th></tr></thead><tbody>{''.join(items)}</tbody></table>"""
    return _shell("Outlook archive", body, depth=1, path="outlook/index.html")


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
    shutil.copytree(config.REPO_ROOT / "site_assets" / "fonts", out / "fonts")  # OFL fonts from sustaintheworld
    shutil.copy(config.DERIVED_DIR / "zones.geojson", out / "data" / "zones.geojson")
    (out / "data" / "flood_places.geojson").write_text(json.dumps(_places_geojson()))

    latest = _latest_outlook()
    (out / "index.html").write_text(_home(latest))
    (out / "map.html").write_text(_map_page(latest))
    (out / "floods.html").write_text(_floods_page())
    for src, target, label in PAGES:
        depth = target.count("/")
        (out / target).write_text(_shell(label, _md(src, target), depth=depth, path=target))
    for f in sorted((config.DATA_DIR / "outlook").glob("*.md")):
        (out / "outlook" / f"{f.stem}.html").write_text(_shell(f"Outlook {f.stem}", _md(f), depth=1))
    (out / "outlook" / "index.html").write_text(_archive_page())
    (out / ".nojekyll").write_text("")
    print(f"site written to {out}")
    return out
