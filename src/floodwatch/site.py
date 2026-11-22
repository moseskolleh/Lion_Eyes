"""Static website for GitHub Pages: ``floodwatch site`` -> ``_site/``.

Lion Eyes ("Eyes of the mountains"): the home page is a full-screen map of
Freetown with the latest Outlook on top of it. The other pages are the Outlook
(latest bulletin and archive), the flood history, and "How it works" (method
and analysis write-ups rendered from docs/*.md). Everything is plain HTML so
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

from floodwatch import config, events, outlook

OUT = config.REPO_ROOT / "_site"
DOCS = config.REPO_ROOT / "docs"
TITLE = "Lion Eyes"
SLOGAN = "Eyes of the mountains"
SITE_URL = "https://moseskolleh.github.io/Lion_Eyes/"  # absolute links in the feed

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
.tagline{font-family:var(--font-mono);font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--text-dim);margin-right:auto;white-space:nowrap}
.brand{margin-right:0}
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
@media (max-width:640px){header.bar .wrap{gap:6px 14px}.brand{font-size:1.25rem}.tagline{font-size:.62rem;letter-spacing:.1em}.theme-toggle{order:1;width:36px;height:36px}
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
NAV = [("index.html", "Map"), ("outlook/index.html", "Outlook"), ("floods.html", "Floods"), ("about.html", "How it works")]
DISCLAIMER = ("Lion Eyes is an independent flood outlook built from open satellite and forecast data. It does not "
              "replace official warnings: in an emergency, follow the National Disaster Management Agency (NDMA) "
              "and local authorities.")


def _nav_for(path: str) -> str:
    """Which menu item a page belongs to."""
    if path.startswith("outlook/"):
        return "outlook/index.html"
    if path.startswith("analysis/") or path in ("concept.html", "outlook-method.html", "about.html"):
        return "about.html"
    return path


def _shell(title: str, body: str, depth: int = 0, extra_head: str = "", path: str = "", bare: bool = False) -> str:
    """A page. `bare` pages (the map) fill the window: no main column, no footer."""
    up = "../" * depth
    here = _nav_for(path)
    links = "".join(f'<a href="{up}{href}"{ACTIVE if href == here else ""}>{label}</a>' for href, label in NAV)
    header = (f'<header class="bar"><div class="wrap"><a class="brand" href="{up}index.html">Lion <em>Eyes</em></a>'
              f'<span class="tagline">{SLOGAN}</span><nav>{links}</nav>{THEME_BUTTON}</div></header>')
    if bare:
        content = body
    else:
        content = f"""<main><div class="wrap">{body}</div></main>
<footer><div class="wrap"><p class="mono">{TITLE} · {SLOGAN}</p>
<p>{DISCLAIMER}</p>
<p>Data: ECMWF open data, NASA IMERG, CHIRPS, Copernicus DEM, Overture Maps, Meta HRSL, OpenStreetMap contributors.
Get each Outlook as it is issued: <a href="{up}feed.xml">feed</a> · <a href="{up}latest.json">latest.json</a> ·
<a href="https://github.com/moseskolleh/Lion_Eyes">source code</a>.</p></div></footer>"""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{THEME_HEAD}
<title>{html.escape(title)} · {TITLE}</title><meta name="description" content="{TITLE}: {SLOGAN}. Flash-flood outlook for Freetown, Sierra Leone.">
<link rel="stylesheet" href="{up}style.css">
<link rel="alternate" type="application/atom+xml" title="{TITLE} flood outlook" href="{up}feed.xml">{extra_head}</head>
<body{' class="bare"' if bare else ''}>{header}
{content}
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


def _issued_key(o: dict) -> str:
    """Sort key for Outlooks: issue time; older files (morning only) have none."""
    return o.get("issued_at") or f"{o['issued']}T09:23Z"


def _outlooks() -> list[tuple[str, dict]]:
    """(file stem, Outlook) for every issued Outlook, newest first."""
    found = [(f.stem, json.loads(f.read_text())) for f in (config.DATA_DIR / "outlook").glob("*.json")]
    return sorted(found, key=lambda x: _issued_key(x[1]), reverse=True)


_LEVEL_HINT = {"HIGH": " <span class='small muted'>act</span>", "ELEVATED": " <span class='small muted'>watch</span>"}


def _period(d: dict) -> str:
    return d.get("label") or f"{pd.Timestamp(d['day']):%a %d %b}"


def _outlook_card(o: dict | None, up: str = "") -> str:
    if not o:
        return '<div class="card">No Outlook has been issued yet.</div>'
    rows = "".join(
        f"<tr><td class='nowrap'>{html.escape(_period(d))}</td>"
        f"<td class='nowrap'><span class='lvl {d['level']}'>{d['level']}</span>{_LEVEL_HINT.get(d['level'], '')}</td>"
        f"<td>{d['p_wet']:.0%}</td><td>{d['p_very_wet']:.0%}</td><td class='nowrap'>{d['median_mm']:.0f} mm</td>"
        f"<td class='nowrap'>{d['prior_3d_mm']:.0f} mm</td>"
        f"<td class='nowrap'>{'<br>'.join(html.escape(t) for t in d['high_tides']) or '-'}</td></tr>"
        for d in o["days"]
    )
    wet = o.get("observed_rain_last_3_days_mm")
    wet_text = f"{wet:.0f} mm" if wet is not None else "not available"
    edition = o.get("edition", "morning")
    first_col = "Period" if edition == "evening" else "Day"
    note = (" Periods run noon to noon (Freetown time = UTC); the first began at noon today."
            if edition == "evening" else "")
    sms = html.escape(outlook.sms_text(o))
    return f"""<div class="card"><p class="eyebrow">Latest outlook · {edition} · {o['issued']}</p>
<p class="muted small">ECMWF ensemble run {o['forecast_run']}. Rain in {o.get('observed_period', 'the last 3 days')}
(satellite): {wet_text}.{note}</p>
<table><thead><tr><th>{first_col}</th><th>Level</th><th>Wet chance</th>
<th>Very wet chance</th><th>Likely rain</th><th>Ground wetness</th><th>High tides</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="small"><span class="muted">Short message (SMS or WhatsApp):</span> <span class="mono">{sms}</span></p>
<p class="small muted">{outlook.level_meaning(("<strong>", "</strong>"))}
Issued twice a day, around 08:15 and 21:00 Freetown time. <a href="{up}outlook-method.html">How the Outlook works</a> ·
<a href="{up}analysis/backtest.html">how well it has done</a>.</p></div>"""


LEVEL_WORD = {"HIGH": "Act", "ELEVATED": "Watch", "LOW": "Normal"}
LEVEL_ORDER = ["LOW", "ELEVATED", "HIGH"]


def _worst(o: dict) -> dict:
    return max(o["days"], key=lambda d: LEVEL_ORDER.index(d["level"]))


def _what_to_do(o: dict) -> str:
    worst = _worst(o)["level"]
    if worst == "HIGH":
        low = ", ".join(o.get("low_ground_zones", [])[:4])
        steep = ", ".join(o.get("steep_zones", [])[:3])
        return (f"Be ready to move people from the lowest homes near streams and the shore{f' ({low})' if low else ''}. "
                f"On steep hillsides{f' ({steep})' if steep else ''}, watch for runoff, cracks and leaning walls.")
    if worst == "ELEVATED":
        nxt = "tomorrow morning's" if o.get("edition") == "evening" else "this evening's"
        return f"No action yet. Clear drains and gutters, watch the sky, and check {nxt} update."
    return "No heavy rain expected. No action needed."


MAP_HEAD = '<link rel="stylesheet" href="vendor/leaflet/leaflet.css"><link rel="stylesheet" href="map.css">'

# The layers panel: (id, group, name, note, key, on by default)
MAP_LAYERS = [
    ("zones", "Flood outlook", "Warning zones", "One per stream catchment. At Watch or Act, the zones named in the outlook light up.",
     "border:2px dashed #8a939e", True),
    ("floods", "Flood outlook", "Past flood places", "Neighbourhoods named in flood reports since 2007; bigger means more floods.",
     "background:#d23b3a;border-radius:50%;width:14px;height:14px", True),
    ("relief", "Ground", "Hills", "The Lion Mountains: the rain that falls on them reaches the city within the hour.",
     "background:linear-gradient(135deg,#fff 0,#999 50%,#222 100%)", True),
    ("low", "Ground", "Low ground", "Near a stream or the shore and under 3 m above it: water gathers here.",
     "background:#2a78d6;opacity:.75", True),
    ("steep", "Ground", "Steep slopes", "Steeper than 25 degrees: landslides and wall collapses are likelier.",
     "background:#eb6834;opacity:.7", True),
    ("streams", "Ground", "Streams", "Drainage lines traced from the terrain.", "background:#4cb4ff;height:3px;margin-top:9px", True),
    ("buildings", "People and places", "Buildings", "Every footprint, coloured by the ground it stands on.",
     "background:linear-gradient(90deg,#2a78d6 33%,#eb6834 33% 66%,#969ca4 66%)", True),
    ("pop", "People and places", "Population", "People per hectare, estimated from buildings (about 3.6 people each).", "background:linear-gradient(90deg,#f3e8ff,#a855f7,#4c1d95)", False),
    ("roads", "People and places", "Main roads", "Blue stretches run over low ground and may flood.",
     "background:linear-gradient(180deg,transparent 40%,#2a78d6 40% 70%,transparent 70%)", True),
    ("facilities", "People and places", "Hospitals, schools, police, worship", "A blue ring means it stands on low ground.",
     "background:#1f2937;border:2px solid #2a78d6;border-radius:50%;width:14px;height:14px", True),
]
ZOOM_HINTS = {"buildings": "Zoom in to see them", "facilities": "Zoom in to see them"}


def _layers_panel() -> str:
    rows, group = [], None
    for lid, grp, name, note, key, on in MAP_LAYERS:
        if grp != group:
            rows.append(f"<h3>{grp}</h3>")
            group = grp
        hint = (f'<span class="zoomhint" data-zoomhint="{lid}" hidden>{ZOOM_HINTS[lid]}</span>' if lid in ZOOM_HINTS else "")
        ramp = ""
        if lid == "pop":
            ramp = ('<span class="ramp">' + "".join(f'<span class="c" style="background:{c}"></span>' for _, c in
                    [(5, "#f3e8ff"), (25, "#d8b4fe"), (60, "#a855f7"), (120, "#7e22ce"), (200, "#4c1d95")]) +
                    " 5 → 200+ per ha</span>")
        rows.append(f'<label><input type="checkbox" data-layer="{lid}"{" checked" if on else ""}>'
                    f'<span class="key" style="{key}"></span><span class="name">{name}</span>'
                    f'<span class="note">{note}</span>{ramp}{hint}</label>')
    return ('<button id="layersBtn" class="btn layers-btn" type="button">Layers</button>'
            '<aside id="layers" class="layers" aria-label="Map layers">'
            '<div class="search"><input id="q" type="search" placeholder="Search a neighbourhood or place" '
            'aria-label="Search a neighbourhood or place" autocomplete="off"><ul id="results" class="results" hidden></ul></div>'
            + "".join(rows) + "</aside>"
            '<div id="hint" class="hint">Click anywhere on the map to see what is there</div>')


def _home(found: list[tuple[str, dict]]) -> str:
    """Full-screen map with the latest Outlook on top."""
    if not found:
        body = '<div id="map"></div><aside id="panel" class="panel state-LOW"><div class="stripe"></div><p>No outlook has been issued yet.</p><button id="fold" class="toggle" hidden></button></aside>'
        data = {"level": "LOW", "word": "Normal", "named": [], "issued_at": None, "alert": False}
    else:
        stem, o = found[0]
        worst = _worst(o)
        level = worst["level"]
        evening = o.get("edition") == "evening"
        when = pd.Timestamp(_issued_key(o).replace("Z", ""))
        periods = "".join(
            f"<li><span title='{html.escape(_period(d))}'>{html.escape(outlook._short_period(d, k, evening))}</span>"
            f"<span class='lvl {d['level']}'>{d['level']}</span></li>" for k, d in enumerate(o["days"]))
        first = outlook._short_period(worst, o["days"].index(worst), evening).lower()
        wet = o.get("observed_rain_last_3_days_mm")
        wet_text = (f"Rain in {o.get('observed_period', 'the last 3 days')}: {wet:.0f} mm (satellite)."
                    if wet is not None else "Recent rain: not available.")
        sms = html.escape(outlook.sms_text(o))
        named = (o.get("low_ground_zones", []) + o.get("steep_zones", [])) if level != "LOW" else []
        body = f"""<div id="map" role="application" aria-label="Map of Freetown's warning zones"></div>
<aside id="panel" class="panel state-{level}" aria-live="polite"><div class="stripe"></div>
<button id="fold" class="toggle" type="button">Details</button>
<p class="eyebrow">Freetown flood outlook · {'evening' if evening else 'morning'} · {when:%a %d %b, %H:%M}</p>
<div class="headline"><span class="word">{LEVEL_WORD[level]}</span>
<span class="what">{level}{'' if level == 'LOW' else ' · ' + html.escape(first)}</span></div>
<p class="todo">{html.escape(_what_to_do(o))}</p>
<div class="more">
<p id="stale" class="stale" hidden></p>
<ol class="periods">{periods}</ol>
<p class="facts">{html.escape(wet_text)} Forecast: ECMWF ensemble, run {html.escape(o['forecast_run'])}.</p>
<div class="sms"><span class="eyebrow">Short message · SMS or WhatsApp</span><p id="smstext">{sms}</p>
<button id="copy" type="button">Copy</button></div>
<p class="links"><a href="outlook/{stem}.html">Full bulletin</a> · <a href="outlook/index.html">Earlier outlooks</a> ·
<a href="about.html">How it works</a></p>
<p class="fine">{DISCLAIMER}</p></div></aside>"""
        data = {"level": level, "word": LEVEL_WORD[level], "named": named, "issued_at": o.get("issued_at"),
                "alert": level != "LOW"}
    body += _layers_panel() + f"""
<script src="vendor/leaflet/leaflet.js"></script>
<script>const LE = {json.dumps(data)};</script>
<script src="map.js"></script>"""
    return _shell("Freetown flood outlook", body, extra_head=MAP_HEAD, path="index.html", bare=True)


def _redirect(to: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={to}">'
            f'<link rel="canonical" href="{to}"><title>{TITLE}</title></head><body><a href="{to}">{TITLE}</a></body></html>')


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
<a href="https://github.com/moseskolleh/Lion_Eyes/issues">GitHub</a>.</p>
<table><thead><tr><th>Date</th><th>Type</th><th>Places</th><th>Deaths</th><th>Summary</th><th>Sources</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>"""
    return _shell("Flood history", body, path="floods.html")


def _outlook_page() -> str:
    found = _outlooks()
    items = []
    for stem, o in found:
        levels = " ".join(f"<span class='lvl {d['level']}'>{html.escape(_period(d))}</span>" for d in o["days"])
        items.append(f"<tr><td class='nowrap'><a href='{stem}.html'>{o['issued']}</a> {o.get('edition', 'morning')}</td>"
                     f"<td>{levels}</td></tr>")
    latest = _outlook_card(found[0][1], up="../") if found else ""
    body = f"""<p class="eyebrow">Outlook</p><h1>Freetown flood <em>outlook</em></h1>
<p class="lede">Issued every morning (about 08:15) and evening (about 21:00), Freetown time, for the next three days or
periods. <strong>HIGH</strong> means act, <strong>ELEVATED</strong> means watch. The short message can be forwarded as it is by
SMS or WhatsApp.</p>
{latest}
<h2>Earlier <em>outlooks</em></h2>
<table><thead><tr><th>Issued</th><th>Levels</th></tr></thead><tbody>{''.join(items)}</tbody></table>"""
    return _shell("Outlook", body, depth=1, path="outlook/index.html")


def _about_page() -> str:
    rates = outlook.level_rates()
    skill = ""
    if rates:
        skill = (f"<p>Replayed on 2024-2026 forecasts, with both daily issues, the Outlook gave a warning in time before "
                 f"{rates['floods_any']} of the {rates['floods_of']} floods in that period, {rates['floods_high']} of "
                 f"them at HIGH. HIGH came up on about "
                 f"{rates['high_pct']}% of rainy-season days. <a href='analysis/backtest.html'>How well it works</a>.</p>")
    cards = [
        ("outlook-method.html", "How the Outlook works", "The rules behind each level, the two daily issues, and the ways to receive it.", None),
        ("analysis/backtest.html", "How well it works", "The Outlook replayed on 2024-2026 forecasts: which floods it would have warned of, and how often it raises an alert.", None),
        ("analysis/hindcast.html", "What past floods teach", "Satellite rain on 19 rainy seasons against the flood record: flood days are clearly wetter.", "figures/streams_and_flood_places.png"),
        ("analysis/zones.html", "Warning zones", "94 stream catchments, with the people living on low ground and on steep slopes in each.", "figures/warning_zones.png"),
        ("analysis/subdaily.html", "When the rain falls", "Half-hourly satellite rain around past floods: heavy rain usually comes 1-6 hours before.", "figures/flood_rain_timelines.png"),
        ("concept.html", "The idea", "Why rain itself is the warning signal in Freetown, and what comes next.", None),
    ]
    grid = "".join(
        f'<div class="card"><h3><a href="{href}">{title}</a></h3><p class="small">{text}</p>'
        + (f'<a href="{href}"><img src="{img}" alt="{title}"></a>' if img else "") + "</div>"
        for href, title, text, img in cards)
    body = f"""<p class="eyebrow">How it works</p><h1>Watching the <em>mountains</em></h1>
<p class="lede">Sierra Leone is named after the Lion Mountains, the peninsula hills above Freetown. When heavy rain falls on
them, the streams reach the low neighbourhoods within the hour. Lion Eyes watches that rain from satellites and weather
forecasts, and turns it into a simple outlook twice a day.</p>
<div class="grid">
<div class="card"><h3>1 · Rain on the way</h3><p class="small">The European weather centre's (ECMWF) 51-member forecast says
how likely a wet or very wet day is, over the next three days.</p></div>
<div class="card"><h3>2 · Ground already wet</h3><p class="small">NASA satellite rain (IMERG) shows how much fell in the days
before. Soaked ground floods and slides with less rain.</p></div>
<div class="card"><h3>3 · Who is in the way</h3><p class="small">Stream catchments traced from elevation data, and the people
living on low ground and steep slopes in each, say where to act first.</p></div>
</div>
<h2>How good is it?</h2>
{skill}
<p>It cannot see short local downpours, which still cause some floods; storm tracking from geostationary satellites and
residents' reports are the next layers.</p>
<h2>Read more</h2>
<div class="grid">{grid}</div>
<h2>Get the outlook</h2>
<p>Every issue is on the <a href="index.html">map</a>, in the <a href="outlook/index.html">archive</a>, as a
<a href="feed.xml">feed</a> (for feed readers or tools that forward to WhatsApp, Telegram or email), and as
<a href="latest.json">latest.json</a> for other systems.</p>"""
    return _shell("How it works", body, path="about.html")


def _atom_time(o: dict) -> str:
    return pd.Timestamp(_issued_key(o)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _feed(limit: int = 60) -> str:
    """Atom feed of the latest Outlooks; each entry's summary is the short message."""
    entries = []
    for stem, o in _outlooks()[:limit]:
        worst = max(o["days"], key=lambda d: ["LOW", "ELEVATED", "HIGH"].index(d["level"]))["level"]
        url = f"{SITE_URL}outlook/{stem}.html"
        title = f"{o['issued']} {o.get('edition', 'morning')}: {outlook.LEVEL_WORDS.get(worst, worst)}"
        entries.append(
            f"<entry><title>{html.escape(title)}</title><link href=\"{url}\"/><id>{url}</id>"
            f"<updated>{_atom_time(o)}</updated>"
            f"<summary>{html.escape(outlook.sms_text(o))}</summary></entry>"
        )
    updated = _atom_time(_outlooks()[0][1]) if entries else "2026-11-22T00:00:00Z"
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">'
        f"<title>{TITLE} · Freetown flood outlook</title><subtitle>{SLOGAN}. Flash-flood outlook for Freetown, "
        "issued morning and evening. Not an official warning: follow NDMA and local authorities.</subtitle>"
        f'<link href="{SITE_URL}feed.xml" rel="self"/><link href="{SITE_URL}"/><id>{SITE_URL}</id>'
        f"<updated>{updated}</updated><author><name>{TITLE}</name></author>" + "".join(entries) + "</feed>\n"
    )


def _latest_json() -> dict | None:
    found = _outlooks()
    if not found:
        return None
    stem, o = found[0]
    return o | {"sms": outlook.sms_text(o), "bulletin_url": f"{SITE_URL}outlook/{stem}.html"}


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
    for name in ("map.css", "map.js"):
        shutil.copy(config.REPO_ROOT / "site_assets" / name, out / name)
    if (config.REPO_ROOT / "site_assets" / "layers").exists():  # `floodwatch layers`
        shutil.copytree(config.REPO_ROOT / "site_assets" / "layers", out / "layers")
    shutil.copy(config.DERIVED_DIR / "zones.geojson", out / "data" / "zones.geojson")
    (out / "data" / "flood_places.geojson").write_text(json.dumps(_places_geojson()))

    (out / "index.html").write_text(_home(_outlooks()))
    (out / "map.html").write_text(_redirect("index.html"))  # the map used to have its own page
    (out / "about.html").write_text(_about_page())
    (out / "floods.html").write_text(_floods_page())
    for src, target, label in PAGES:
        depth = target.count("/")
        (out / target).write_text(_shell(label, _md(src, target), depth=depth, path=target))
    for f in sorted((config.DATA_DIR / "outlook").glob("*.md")):
        (out / "outlook" / f"{f.stem}.html").write_text(_shell(f"Outlook {f.stem}", _md(f), depth=1,
                                                                path=f"outlook/{f.stem}.html"))
    (out / "outlook" / "index.html").write_text(_outlook_page())
    (out / "feed.xml").write_text(_feed())
    if (latest_json := _latest_json()) is not None:
        (out / "latest.json").write_text(json.dumps(latest_json, indent=2, default=str))
    (out / ".nojekyll").write_text("")
    print(f"site written to {out}")
    return out
