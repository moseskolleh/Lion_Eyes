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
from urllib.parse import quote

import markdown
import pandas as pd

from floodwatch import config, events, outlook, places

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
    (DOCS / "map.md", "map-guide.html", "Reading the map"),
]

CSS = """
/* Warning levels use the international colour code (ISO 22324, WMO and CAP
   practice, MeteoAlarm): green = no warning, yellow = be aware (Watch),
   orange = be prepared (Act); red is kept for a future flood warning (flooding
   imminent or under way). The same colours in light and dark, always with the
   level named in text. Water and flood hazard are blue, slopes brown.
   Type and colour from Moses Kolleh Sesay's site (sustaintheworld): Newsreader
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
--lvl-low:#00a651;--lvl-low-text:#04130a;--lvl-elev:#ffdd00;--lvl-elev-text:#1a1600;--lvl-high:#ff8c00;--lvl-high-text:#1f1000;--lvl-red:#e3000f;--lvl-red-text:#fff;
--flood:#4fa3e0;--flood-deep:#9ecae1;--steep:#c48a3f;--dead:#ff6b6b}
html.light-mode{color-scheme:light;--primary-green:#1a7a1a;--dark-bg:#f5f6f3;--darker-bg:#fff;--card-bg:#fff;--card-bg-alt:#fafbf8;
--text-primary:#161914;--text-secondary:#54584f;--text-dim:#5f635a;--accent-color:#1a7a1a;--hover-color:#146414;--accent-amber:#8a6100;
--line-color:rgba(34,139,34,.25);--line-soft:rgba(34,139,34,.1);--bar-bg:rgba(255,255,255,.88);
--lvl-low:#00a651;--lvl-low-text:#04130a;--lvl-elev:#ffdd00;--lvl-elev-text:#1a1600;--lvl-high:#ff8c00;--lvl-high-text:#1f1000;--lvl-red:#e3000f;--lvl-red-text:#fff;
--flood:#2c7fb8;--flood-deep:#08306b;--steep:#8c510a;--dead:#c8102e}
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
code{overflow-wrap:anywhere;font-family:var(--font-mono);font-size:.88em;background:var(--card-bg-alt);border:1px solid var(--line-soft);border-radius:3px;padding:.05em .35em}
pre{background:var(--card-bg-alt);border:1px solid var(--line-soft);border-radius:var(--border-radius);padding:12px;overflow-x:auto;margin:0 0 1em}
pre code{border:0;padding:0;background:none}
img{max-width:100%;height:auto;border-radius:var(--border-radius);border:1px solid var(--line-soft);background:#fff}
blockquote{border-left:2px solid var(--primary-green);padding-left:14px;color:var(--text-secondary);margin:0 0 1em}
hr{border:0;border-top:1px solid var(--line-soft);margin:2em 0}
.lvl{display:inline-block;font-family:var(--font-mono);font-size:.74rem;letter-spacing:.08em;padding:2px 9px;border-radius:999px;
box-shadow:inset 0 0 0 1px rgba(0,0,0,.18);font-weight:600}
.LOW{background:var(--lvl-low);color:var(--lvl-low-text)}.ELEVATED{background:var(--lvl-elev);color:var(--lvl-elev-text)}
.HIGH{background:var(--lvl-high);color:var(--lvl-high-text)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin-top:20px}.grid .card{margin:0}
footer{border-top:1px solid var(--line-soft);padding:22px 0 30px;color:var(--text-dim);font-size:.85rem}
footer .mono{font-size:.76rem;letter-spacing:.06em;text-transform:uppercase}
.nowrap{white-space:nowrap}
/* Page furniture shared by the content pages */
.hero{margin:8px 0 28px}.hero .lede{max-width:760px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin:22px 0 30px}
.stat{background:var(--card-bg);border:1px solid var(--line-soft);border-radius:10px;padding:16px 16px 14px}
.stat .n{font-family:var(--font-display);font-size:2.4rem;line-height:1;color:var(--text-primary)}
.stat .l{font-size:.86rem;color:var(--text-secondary);margin-top:6px;line-height:1.4}
.stat.accent .n{color:var(--accent-color)}
.panelbox{background:var(--card-bg);border:1px solid var(--line-soft);border-radius:10px;padding:18px 20px;margin:0 0 22px}
.panelbox h2,.panelbox h3{margin-top:0}
.two{display:grid;grid-template-columns:2fr 1fr;gap:20px}@media (max-width:860px){.two{grid-template-columns:1fr}}
.chart{width:100%;height:auto;display:block;overflow:visible}
.chart .bar{fill:var(--series-1)}.chart .bar:hover{fill:var(--series-1-hover)}
.chart .gap{fill:none;stroke:var(--text-dim);stroke-dasharray:2 3}
.chart text{fill:var(--text-dim);font-family:var(--font-mono);font-size:10px}
.chart .grid{stroke:var(--line-soft)}
.chart .val{fill:var(--text-secondary);font-size:10px}
.tip{position:fixed;z-index:2000;pointer-events:none;background:var(--card-bg);border:1px solid var(--line-color);border-radius:6px;
padding:6px 9px;font-size:.82rem;color:var(--text-primary);box-shadow:0 6px 20px rgba(0,0,0,.3)}
:root{--series-1:#4fa3e0;--series-1-hover:#7dbbe8}html.light-mode{--series-1:#2c7fb8;--series-1-hover:#1f5f8b}
.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.chip{font:inherit;font-size:.84rem;cursor:pointer;border:1px solid var(--line-color);background:none;color:var(--text-secondary);
border-radius:999px;padding:4px 12px}
.chip.on,.chip:hover{background:var(--accent-color);color:var(--darker-bg);border-color:var(--accent-color)}
.filters input{font:inherit;font-size:.88rem;padding:6px 10px;border-radius:8px;border:1px solid var(--line-color);
background:var(--card-bg-alt);color:var(--text-primary);min-width:220px}
.filters{position:sticky;top:var(--bar-h,64px);z-index:20;background:var(--dark-bg);padding:10px 0;margin:6px 0 8px;
border-bottom:1px solid var(--line-soft)}
.yearnav{display:flex;flex-wrap:wrap;gap:4px 10px;font-family:var(--font-mono);font-size:.78rem;margin:0 0 14px}
.yearnav a{color:var(--text-secondary);text-decoration:none;padding:2px 6px;border-radius:6px;border:1px solid var(--line-soft)}
.yearnav a:hover{color:var(--text-primary);border-color:var(--line-color)}
.events{display:grid;gap:12px}
.event{scroll-margin-top:calc(var(--bar-h,64px) + 70px)}.event.hit{outline:2px solid var(--flood);outline-offset:2px}
.event .foot{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.event .onmap,.event .permalink{font-size:.82rem}.event .permalink{color:var(--text-dim);text-decoration:none}
.totop{position:fixed;right:18px;bottom:18px;z-index:30;background:var(--card-bg);border:1px solid var(--line-color);
border-radius:999px;padding:6px 14px;font-size:.85rem;text-decoration:none;box-shadow:0 6px 20px rgba(0,0,0,.25)}
.event{display:grid;grid-template-columns:120px 1fr;gap:4px 18px;background:var(--card-bg);border:1px solid var(--line-soft);
border-radius:10px;padding:14px 16px}
.event .when{font-family:var(--font-display);font-size:1.25rem;line-height:1.2}
.event .when small{display:block;font-family:var(--font-mono);font-size:.7rem;letter-spacing:.08em;color:var(--text-dim);margin-top:4px}
.event .places{font-weight:600;margin-bottom:2px}
.event .sum{color:var(--text-secondary);font-size:.94rem;margin:2px 0 6px}
.event details{font-size:.82rem;color:var(--text-dim)}.event details a{word-break:break-all}
.badge{display:inline-block;font-family:var(--font-mono);font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;
border:1px solid var(--line-color);border-radius:999px;padding:1px 8px;margin-right:6px;color:var(--text-secondary)}
.badge.dead{border-color:var(--dead);color:var(--dead)}
@media (max-width:560px){.event{grid-template-columns:1fr}}
/* Outlook page */
.bigword{display:inline-block;font-family:var(--font-display);font-size:clamp(2.6rem,7vw,4.4rem);line-height:1;
background:var(--lvl);color:var(--lvl-txt);padding:.08em .32em .14em;border-radius:10px}
.state-HIGH{--lvl:var(--lvl-high);--lvl-txt:var(--lvl-high-text)}.state-ELEVATED{--lvl:var(--lvl-elev);--lvl-txt:var(--lvl-elev-text)}
.state-LOW{--lvl:var(--lvl-low);--lvl-txt:var(--lvl-low-text)}
.periodcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin:18px 0 24px}
.pcard{background:var(--card-bg);border:1px solid var(--line-soft);border-top:4px solid var(--lvl);border-radius:10px;padding:14px 16px}
.pcard h3{font-family:var(--font-body);font-weight:600;font-size:1rem;margin:0 0 6px}
.pcard dl{display:grid;grid-template-columns:1fr auto;gap:4px 10px;font-size:.88rem;margin:10px 0 0}
.pcard dt{color:var(--text-secondary)}.pcard dd{margin:0;text-align:right;font-family:var(--font-mono);font-size:.84rem}
.meter{height:6px;background:var(--line-soft);border-radius:999px;overflow:hidden;margin-top:2px}
.meter i{display:block;height:100%;background:var(--lvl)}
.strip{display:flex;flex-wrap:wrap;gap:3px;margin:8px 0 18px}
.strip a{width:14px;height:22px;border-radius:3px;display:block}
.strip a.LOW{background:var(--lvl-low)}.strip a.ELEVATED{background:var(--lvl-elev)}.strip a.HIGH{background:var(--lvl-high)}
/* Flow diagram (How it works) */
.flow{display:grid;grid-template-columns:repeat(3,1fr) auto 1fr;gap:12px;align-items:stretch;margin:18px 0 26px}
.flow .step{background:var(--card-bg);border:1px solid var(--line-soft);border-radius:10px;padding:14px}
.flow .step b{display:block;font-family:var(--font-display);font-weight:500;font-size:1.15rem;margin-bottom:4px}
.flow .step span{font-size:.86rem;color:var(--text-secondary)}
.flow .arrow{align-self:center;font-size:1.6rem;color:var(--accent-color)}
.flow .out{border-color:var(--accent-color)}
@media (max-width:860px){.flow{grid-template-columns:1fr}.flow .arrow{transform:rotate(90deg);justify-self:center}}
/* Analysis pages: article layout with a contents list */
.doc{display:grid;grid-template-columns:minmax(0,1fr) 220px;gap:40px}
.doc .toc{position:sticky;top:90px;align-self:start;font-size:.84rem;border-left:1px solid var(--line-soft);padding-left:14px}
.doc .toc b{display:block;font-family:var(--font-mono);font-weight:400;font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;
color:var(--text-dim);margin-bottom:8px}
.doc .toc a{display:block;color:var(--text-secondary);text-decoration:none;padding:3px 0;line-height:1.35}
.doc .toc a:hover{color:var(--accent-color)}
.doc article>p,.doc article>ul,.doc article>ol,.doc article>blockquote{max-width:760px}
.doc article h1+p em,.doc article>p:first-of-type em{color:var(--text-dim)}
.doc article h2{padding-top:10px;border-top:1px solid var(--line-soft)}
.doc article img{display:block;margin:10px 0 4px;background:#fff}
.doc article img+em,.doc article p:has(>img)+p>em:only-child{display:block;font-size:.86rem;color:var(--text-dim)}
.doc article table{font-size:.88rem}
.doc article tbody tr:nth-child(odd){background:var(--card-bg-alt)}
.doc article tbody tr:hover{background:var(--line-soft)}
.doc article thead th{position:sticky;top:0;background:var(--card-bg)}
@media (max-width:980px){.doc{grid-template-columns:1fr}.doc .toc{position:static;border-left:0;padding:0 0 12px;
border-bottom:1px solid var(--line-soft)}}
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
    if path.startswith("analysis/") or path in ("concept.html", "outlook-method.html", "about.html", "map-guide.html"):
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
<link rel="stylesheet" href="{up}style.css"><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22%3E%3Crect width=%2232%22 height=%2232%22 rx=%227%22 fill=%22%2308306b%22/%3E%3Cpath d=%22M4 16c3.5-6 8-9 12-9s8.5 3 12 9c-3.5 6-8 9-12 9s-8.5-3-12-9z%22 fill=%22%23fff%22/%3E%3Ccircle cx=%2216%22 cy=%2216%22 r=%225%22 fill=%22%232c7fb8%22/%3E%3C/svg%3E">
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


def _doc(path: Path, target: str) -> str:
    """A markdown doc as an article with a contents list built from its section headings."""
    page = _md(path, target)
    heads = []

    def anchor(m: re.Match) -> str:
        text = re.sub(r"<[^>]+>", "", m.group(1))
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or f"s{len(heads)}"
        heads.append((slug, text))
        return f'<h2 id="{slug}">{m.group(1)}</h2>'

    page = re.sub(r"<h2>(.*?)</h2>", anchor, page)
    toc = "".join(f'<a href="#{slug}">{html.escape(html.unescape(text))}</a>' for slug, text in heads)
    return (f'<div class="doc"><article>{page}</article>'
            + (f'<aside class="toc" aria-label="On this page"><b>On this page</b>{toc}</aside>' if heads else "") + "</div>")


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

# The layers panel, by what a reader asks of the map: today's outlook, where
# water goes, where slopes fail, who and what is in the way, and the base map.
# Rows: (id, name, note, legend-key class, on by default, shown from zoom).
MAP_GROUPS = [
    ("outlook", "Today's outlook", [
        ("zones", "Warning zones", "One per stream catchment. In a Watch or Act outlook, the zones it names fill "
         "with the warning colour.", "k-zones", True, None),
    ]),
    ("flood", "Flood hazard", [
        ("low", "Flood-prone low ground", "Within 3 m of a stream or the shore: water gathers here in heavy rain.",
         "k-low", True, None),
        ("streams", "Streams", "Drainage lines traced from the terrain; thicker drains more land.", "k-streams", True, None),
        ("floods", "Past floods", "Places named in flood reports since 2007; the number is how many floods. "
         "A ring means the report named a street or landmark there.", "k-floods", True, None),
    ]),
    ("slope", "Landslide hazard", [
        ("steep", "Steep slopes", "Steeper than 25\u00b0: landslides, rockfalls and wall collapses are likelier.",
         "k-steep", True, None),
    ]),
    ("people", "People and places", [
        ("buildings", "Buildings", "Every footprint: blue on flood-prone ground, brown on steep slopes.",
         "k-buildings", True, 14),
        ("roads", "Roads that may flood", "Main roads; blue stretches cross flood-prone ground.", "k-roads", True, None),
        ("facilities", "Health, schools, police", "A blue ring: on flood-prone ground; brown: on a steep slope. "
         "Schools appear from a closer zoom.",
         "k-facilities", True, 14),
        ("worship", "Places of worship", "Often used as shelters.", "k-worship", False, 16),
        ("pop", "Population density", "People per hectare, estimated from buildings (about 3.6 people each).",
         "k-pop", False, None),
    ]),
]
BASEMAPS = [("streets", "Streets"), ("hot", "Humanitarian"), ("satellite", "Satellite"), ("none", "None")]
POP_RAMP = ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"]  # ColorBrewer Purples, 5 classes


def _layers_panel() -> str:
    groups = []
    for gid, title, rows in MAP_GROUPS:
        items = []
        for lid, name, note, key, on, zoom in rows:
            extra = ""
            if lid == "pop":
                extra = ('<span class="ramp">' + "".join(f'<i style="background:{c}"></i>' for c in POP_RAMP)
                         + "<em>5</em><em>200+ per ha</em></span>")
            if lid == "floods":
                extra = ('<span class="since"><input id="since" type="range" min="2007" max="2026" value="2007" step="1" '
                         'aria-label="Show floods from this year"><output id="sinceOut">since 2007</output></span>')
            hint = f'<span class="zoomhint" data-zoomhint="{lid}" hidden>Zoom in to see them</span>' if zoom else ""
            items.append(f'<label class="row"><input type="checkbox" data-layer="{lid}"{" checked" if on else ""}'
                         f'{f" data-minzoom={zoom}" if zoom else ""}><span class="key {key}" aria-hidden="true"></span>'
                         f'<span class="name">{name}</span><span class="note">{note}</span>{extra}{hint}</label>')
        groups.append(f'<details class="grp" open><summary>{title}</summary>{"".join(items)}</details>')
    base = "".join(f'<label class="seg"><input type="radio" name="basemap" value="{v}"{" checked" if v == "streets" else ""}>'
                   f'<span>{t}</span></label>' for v, t in BASEMAPS)
    groups.append('<details class="grp" open><summary>Base map</summary>'
                  f'<div class="segs" role="radiogroup" aria-label="Base map">{base}</div>'
                  '<label class="row"><input type="checkbox" data-layer="relief" checked><span class="key k-relief" aria-hidden="true">'
                  '</span><span class="name">Relief shading</span><span class="note">The Lion Mountains: rain on them reaches '
                  'the city within the hour.</span></label>'
                  '<label class="slider"><span>Hazard layers</span><input id="opacity" type="range" min="20" max="100" '
                  'value="80" aria-label="Hazard layer opacity"><output id="opacityOut">80%</output></label></details>'
                  '<p class="guide"><a href="map-guide.html">How to read this map</a> · press <kbd>/</kbd> to search</p>')
    search = ('<div id="searchbox" class="searchbox" role="search">'
              '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/></svg>'
              '<input id="q" type="search" placeholder="Search a place or street" '
              'aria-label="Search the map" autocomplete="off" spellcheck="false" enterkeyhint="search" '
              'role="combobox" aria-expanded="false" aria-controls="results" aria-autocomplete="list">'
              '<kbd class="slash" title="Press / to search">/</kbd>'
              '<button id="qclear" class="qclear" type="button" aria-label="Clear search" hidden>&times;</button>'
              '<button id="layersBtn" class="layers-btn" type="button" aria-controls="layers" aria-expanded="false">'
              '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2 8l10 5 10-5-10-5zM2 13l10 5 10-5M2 17.5l10 5 10-5"/></svg>'
              '<span>Layers</span></button>'
              '<ul id="results" class="results" role="listbox" hidden></ul></div>')
    return (search + '<aside id="layers" class="layers" aria-label="Map layers"><div class="layers-head">'
            '<b>Map layers</b><button id="layersClose" class="x" type="button" aria-label="Close layers">&times;</button></div>'
            + "".join(groups) + "</aside>"
            '<div id="hint" class="hint">Tap or click anywhere on the map to see what is there</div>')


LEVEL_KEY = ('<details class="levelkey"><summary><span class="eyebrow">What the colours mean</span>'
             '<span class="lvl LOW">LOW</span><span class="lvl ELEVATED">ELEVATED</span><span class="lvl HIGH">HIGH</span></summary>'
             '<div><span class="lvl LOW">LOW</span> Normal: no flood threat expected.</div>'
             '<div><span class="lvl ELEVATED">ELEVATED</span> Watch: be aware; heavy rain is possible.</div>'
             '<div><span class="lvl HIGH">HIGH</span> Act: be prepared to move people from low ground.</div>'
             '<p class="fine">The international colour code for public warnings (ISO 22324, WMO): green, yellow, orange, '
             'red. Red is kept for a flood warning when flooding is imminent or under way, which Lion Eyes does not '
             'issue yet. The level is always written out as well, for readers who do not see colour.</p></details>')


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
{LEVEL_KEY}
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


TIP_SCRIPT = """<div id="tip" class="tip" hidden></div><script>(function(){var t=document.getElementById('tip');
document.addEventListener('mousemove',function(e){var el=e.target.closest&&e.target.closest('[data-tip]');
if(!el){t.hidden=true;return}t.hidden=false;t.textContent=el.getAttribute('data-tip');
var x=Math.min(e.clientX+12,innerWidth-t.offsetWidth-8);t.style.left=x+'px';t.style.top=(e.clientY+14)+'px'})})();</script>"""


def _bar_chart(items: list[tuple[str, int, str]], label_every: int = 1, height: int = 170, width: int = 760) -> str:
    """A single-series bar chart as SVG. items: (label, value, tooltip). Zero
    values are drawn as a dashed outline when their tooltip says why."""
    top, bottom, left = 14, 24, 26
    n = len(items)
    peak = max(1, max(v for _, v, _ in items))
    step = (width - left) / n
    bw = max(4, step * 0.62)
    scale = (height - top - bottom) / peak
    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img">']
    for g in range(0, peak + 1, max(1, peak // 3)):
        y = height - bottom - g * scale
        parts.append(f'<line class="grid" x1="{left}" x2="{width}" y1="{y:.1f}" y2="{y:.1f}"/>'
                     f'<text x="{left - 6}" y="{y + 3:.1f}" text-anchor="end">{g}</text>')
    for i, (lab, v, tip) in enumerate(items):
        x = left + i * step + (step - bw) / 2
        base = height - bottom
        if v > 0:
            h = v * scale
            r = min(4, bw / 2, h)
            parts.append(f'<path class="bar" data-tip="{html.escape(tip)}" d="M{x:.1f},{base} V{base - h + r:.1f} '
                         f'Q{x:.1f},{base - h:.1f} {x + r:.1f},{base - h:.1f} H{x + bw - r:.1f} '
                         f'Q{x + bw:.1f},{base - h:.1f} {x + bw:.1f},{base - h + r:.1f} V{base} Z"/>')
        elif tip:
            parts.append(f'<rect class="gap" data-tip="{html.escape(tip)}" x="{x:.1f}" y="{base - 3 * scale * 0.6:.1f}" '
                         f'width="{bw:.1f}" height="{3 * scale * 0.6:.1f}" rx="2"/>')
        if i % label_every == 0:
            parts.append(f'<text x="{x + bw / 2:.1f}" y="{height - 8}" text-anchor="middle">{html.escape(lab)}</text>')
    parts.append("</svg>")
    return "".join(parts)


FLOODS_SCRIPT = """<script>(function(){var bar=document.querySelector('header.bar');function bh(){
document.documentElement.style.setProperty('--bar-h',bar.offsetHeight+'px')}bh();addEventListener('resize',bh);var cards=[].slice.call(document.querySelectorAll('.event')),kind='all',
q=document.getElementById('fq'),yr=document.getElementById('fy'),count=document.getElementById('fcount');
function apply(){var t=q.value.trim().toLowerCase(),y=yr.value,n=0;cards.forEach(function(c){
var ok=(kind==='all'||(kind==='deadly'?c.dataset.dead==='1':c.dataset.kind===kind))&&(!y||c.dataset.year===y)&&
(!t||c.textContent.toLowerCase().indexOf(t)>=0);c.hidden=!ok;if(ok)n++});count.textContent=n+' of '+cards.length+' floods'}
[].forEach.call(document.querySelectorAll('.chip[data-kind]'),function(b){b.addEventListener('click',function(){
kind=b.dataset.kind;[].forEach.call(document.querySelectorAll('.chip[data-kind]'),function(o){o.classList.toggle('on',o===b)});apply()})});
q.addEventListener('input',apply);yr.addEventListener('change',apply);
[].forEach.call(document.querySelectorAll('.yearnav a'),function(a){a.addEventListener('click',function(){
if(yr.value&&yr.value!==a.dataset.y){yr.value='';apply()}})});
var top=document.getElementById('totop');addEventListener('scroll',function(){top.hidden=scrollY<900},{passive:true});
top.addEventListener('click',function(e){e.preventDefault();scrollTo({top:0,behavior:'smooth'})});
function mark(){var h=location.hash.slice(1),c=h&&document.getElementById(h);cards.forEach(function(x){x.classList.toggle('hit',x===c)});
if(c&&c.hidden){kind='all';q.value='';yr.value='';apply();c.scrollIntoView()}}addEventListener('hashchange',mark);
apply();mark()})();</script>"""


def _floods_page() -> str:
    cat = events.load_catalogue().sort_values("date", ascending=False)
    years = range(2007, int(cat["date"].dt.year.max()) + 1)
    by_year = cat.groupby(cat["date"].dt.year).size()
    year_items = [(f"'{y % 100:02d}", int(by_year.get(y, 0)),
                   f"{y}: {int(by_year.get(y, 0))} flood{'s' if by_year.get(y, 0) != 1 else ''}"
                   if by_year.get(y, 0) else f"{y}: no flood reports found online yet") for y in years]
    months = ["May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"]
    by_month = cat.groupby(cat["date"].dt.month).size()
    month_items = [(m, int(by_month.get(i, 0)), f"{m}: {int(by_month.get(i, 0))} floods") for i, m in enumerate(months, 5)]
    deaths = int(cat["deaths"].fillna(0).sum())
    worst = cat.loc[cat["deaths"].fillna(0).idxmax()]
    place_counts = pd.Series([pl for locs in cat["locations"] for pl in locs]).value_counts()
    top_place, top_n = place_counts.index[0], int(place_counts.iloc[0])
    aug = int(by_month.get(8, 0))
    cards = []
    placed = _placed()
    for _, e in cat.iterrows():
        month_only = e["date_confidence"] == "month_only"
        when = f"{e['date']:%b %Y}" if month_only else f"{e['date']:%d %b %Y}"
        dead = 0 if pd.isna(e["deaths"]) else int(e["deaths"])
        kind = "flash_flood" if e["type"] == "flash_flood" else "other"
        kind_label = {"flash_flood": "flash flood", "landslide": "landslide", "mixed": "flood and collapse"}.get(e["type"], e["type"])
        srcs = "".join(f'<li><a href="{html.escape(u)}" rel="noopener">{html.escape(u.split("//")[-1][:70])}</a></li>'
                       for u in e["sources"])
        time = "" if pd.isna(e["time_of_day"]) else f"<small>{html.escape(str(e['time_of_day'])[:40])}</small>"
        on_map = next((pl for pl in e["locations"] if pl in placed), None)
        map_link = (f'<a class="onmap" href="index.html#place={html.escape(quote(on_map))}">Show on map</a>'
                    if on_map else "")
        cards.append(
            f'<div class="event" id="{e["event_id"]}" data-kind="{kind}" data-dead="{1 if dead else 0}" data-year="{e["date"].year}">'
            f'<div class="when">{when}{time}</div><div>'
            f'<div class="places">{html.escape(", ".join(e["locations"][:6]))}</div>'
            f'<span class="badge">{kind_label}</span>' + (f'<span class="badge dead">{dead} dead</span>' if dead else "")
            + f'<p class="sum">{html.escape(str(e["summary"]))}</p>'
            f'<div class="foot"><details><summary>{len(e["sources"])} source{"s" if len(e["sources"]) != 1 else ""}</summary><ul>{srcs}</ul></details>'
            f'{map_link}<a class="permalink" href="#{e["event_id"]}" aria-label="Link to this flood">#</a></div>'
            "</div></div>")
    gap_note = ('<p class="small muted">Dashed: no flood reports found online for that year. That is a gap in the record, '
                'not a dry year.</p>' if any(n == 0 for _, n, _ in year_items) else
                '<p class="small muted">Every year has at least one report, but small floods and the years before 2014 '
                'are still under-recorded.</p>')
    first_of_year = {}
    for _, e in cat.iterrows():
        first_of_year.setdefault(int(e["date"].year), e["event_id"])
    year_nav = "".join(f'<a href="#{eid}" data-y="{y}">{y}</a>' for y, eid in first_of_year.items())
    year_opts = "".join(f'<option value="{y}">{y}</option>' for y in sorted(set(cat["date"].dt.year), reverse=True))
    body = f"""<div class="hero"><p class="eyebrow">Flood history</p><h1>Every flood we could <em>find</em></h1>
<p class="lede">Floods on the Freetown peninsula since 2007, each from public sources: news, the National Disaster
Management Agency, the Red Cross and the UN, and residents' posts. This record is what Lion Eyes learns from. It is
incomplete, above all before 2015 and for small floods. <a href="https://github.com/moseskolleh/Lion_Eyes/issues">Tell us
about a flood that is missing</a>.</p></div>
<div class="stats">
<div class="stat"><div class="n">{len(cat)}</div><div class="l">floods recorded, 2007-{int(cat['date'].dt.year.max())}</div></div>
<div class="stat"><div class="n">{deaths:,}</div><div class="l">deaths reported; {int(worst['deaths']):,} in the {worst['date']:%B %Y} Regent mudslide</div></div>
<div class="stat"><div class="n">{aug}</div><div class="l">in August, the worst month; July and September follow</div></div>
<div class="stat"><div class="n">{top_n}</div><div class="l">floods at {html.escape(top_place)}, the most-hit place</div></div>
</div>
<div class="two">
<div class="panelbox"><h3>Floods per year</h3>{_bar_chart(year_items, label_every=2)}
{gap_note}</div>
<div class="panelbox"><h3>By month</h3>{_bar_chart(month_items, width=340, height=200)}
<p class="small muted">The rainy season runs May to November.</p></div>
</div>
<div class="filters"><button class="chip on" data-kind="all" type="button">All</button>
<button class="chip" data-kind="flash_flood" type="button">Flash floods</button>
<button class="chip" data-kind="other" type="button">Landslides and collapses</button>
<button class="chip" data-kind="deadly" type="button">With deaths</button>
<select id="fy" class="chip" aria-label="Year"><option value="">Any year</option>{year_opts}</select>
<input id="fq" type="search" placeholder="Search places or words" aria-label="Search the flood history">
<span id="fcount" class="small muted"></span></div>
<nav class="yearnav" aria-label="Jump to a year">{year_nav}</nav>
<div class="events">{''.join(cards)}</div>
<a href="#top" class="totop" id="totop" hidden>Back to top</a>
{TIP_SCRIPT}{FLOODS_SCRIPT}"""
    return _shell("Flood history", body, path="floods.html")


COPY_SCRIPT = """<script>(function(){var b=document.getElementById('copy');if(!b)return;b.addEventListener('click',function(){
var t=document.getElementById('smstext').textContent;(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(
function(){b.textContent='Copied';setTimeout(function(){b.textContent='Copy'},1500)},function(){})})})();</script>"""


def _period_card(d: dict, label: str) -> str:
    tides = ", ".join(d["high_tides"]) or "none above 1.1 m"
    return (f'<div class="pcard state-{d["level"]}"><h3>{html.escape(label)}</h3>'
            f'<span class="lvl {d["level"]}">{d["level"]}</span> <span class="small muted">{LEVEL_WORD[d["level"]]}</span>'
            f'<dl><dt>Chance of a wet {"period" if d.get("start", "").endswith("12:00:00") else "day"}</dt><dd>{d["p_wet"]:.0%}</dd>'
            f'<dd style="grid-column:1/-1"><div class="meter"><i style="width:{d["p_wet"] * 100:.0f}%"></i></div></dd>'
            f'<dt>Chance of a very wet one</dt><dd>{d["p_very_wet"]:.0%}</dd>'
            f'<dd style="grid-column:1/-1"><div class="meter"><i style="width:{d["p_very_wet"] * 100:.0f}%"></i></div></dd>'
            f'<dt>Most likely rain</dt><dd>{d["median_mm"]:.0f} mm</dd>'
            f'<dt>Rain in the days before</dt><dd>{d["prior_3d_mm"]:.0f} mm</dd>'
            f'</dl><p class="small muted" style="margin:10px 0 0">High tides: {html.escape(tides)}</p></div>')


def _outlook_page() -> str:
    found = _outlooks()
    if not found:
        return _shell("Outlook", "<h1>Outlook</h1><p>No outlook has been issued yet.</p>", depth=1, path="outlook/index.html")
    stem, o = found[0]
    worst = _worst(o)
    level, evening = worst["level"], o.get("edition") == "evening"
    when = pd.Timestamp(_issued_key(o).replace("Z", ""))
    cards = "".join(_period_card(d, _period(d)) for d in o["days"])
    wet = o.get("observed_rain_last_3_days_mm")
    wet_text = (f"{wet:.0f} mm of rain fell in {o.get('observed_period', 'the last 3 days')} (satellite)."
                if wet is not None else "Recent rain is not available.")
    strip = "".join(
        f'<a class="{_worst(x)["level"]}" href="{st}.html" data-tip="{x["issued"]} {x.get("edition", "morning")}: '
        f'{LEVEL_WORD[_worst(x)["level"]]}" aria-label="{x["issued"]} {x.get("edition", "morning")}"></a>'
        for st, x in reversed(found[:90]))
    rows = "".join(
        f"<tr><td class='nowrap'><a href='{st}.html'>{x['issued']}</a> {x.get('edition', 'morning')}</td><td>"
        + " ".join(f"<span class='lvl {d['level']}'>{html.escape(_period(d))}</span>" for d in x["days"]) + "</td></tr>"
        for st, x in found)
    body = f"""<div class="hero state-{level}"><p class="eyebrow">Latest outlook · {'evening' if evening else 'morning'} ·
{when:%a %d %b %Y, %H:%M}</p>
<div class="bigword">{LEVEL_WORD[level]}</div>
<p class="lede" style="margin-top:10px">{html.escape(_what_to_do(o))}</p></div>
<div class="periodcards">{cards}</div>
<div class="two">
<div class="panelbox"><h3>Short message</h3><p class="small muted">Forward it as it is, by SMS or WhatsApp.</p>
<p id="smstext" class="mono">{html.escape(outlook.sms_text(o))}</p><button id="copy" class="chip" type="button">Copy</button></div>
<div class="panelbox"><h3>Behind this outlook</h3><p class="small">{html.escape(wet_text)} Forecast: the European
weather centre's 51-member ensemble, run {html.escape(o['forecast_run'])}. <a href="{stem}.html">Full bulletin</a>.</p></div>
</div>
<div class="panelbox"><h3>What the levels mean</h3><p class="small">{outlook.level_meaning(("<strong>", "</strong>"))}</p></div>
<h2>Earlier <em>outlooks</em></h2>
<p class="small muted">One block per issue, oldest on the left; the colour is its highest level. Issued every morning
(about 08:15) and evening (about 21:00), Freetown time.</p>
<div class="strip">{strip}</div>
<table><thead><tr><th>Issued</th><th>Levels</th></tr></thead><tbody>{rows}</tbody></table>
{TIP_SCRIPT}{COPY_SCRIPT}"""
    return _shell("Outlook", body, depth=1, path="outlook/index.html")


def _about_page() -> str:
    rates = outlook.level_rates()
    zones_df = pd.read_csv(config.DERIVED_DIR / "zones.csv")
    n_floods = len(events.load_catalogue())
    stats = f"""<div class="stats">
<div class="stat"><div class="n">{n_floods}</div><div class="l">past floods in the record the outlook is tested on</div></div>
<div class="stat accent"><div class="n">{rates['floods_any'] if rates else '-'} of {rates['floods_of'] if rates else '-'}</div>
<div class="l">recent floods warned of in time (2024-2026 replay)</div></div>
<div class="stat"><div class="n">{round(zones_df['people_low_ground'].sum(), -3):,.0f}</div><div class="l">people living on low ground near streams or the shore</div></div>
<div class="stat"><div class="n">{round(zones_df['people_steep'].sum(), -3):,.0f}</div><div class="l">people living on steep slopes</div></div>
</div>"""
    skill = ""
    if rates:
        skill = (f"<p>Replayed on 2024-2026 forecasts, with both daily issues, the Outlook gave a warning in time before "
                 f"{rates['floods_any']} of the {rates['floods_of']} floods in that period, {rates['floods_high']} of "
                 f"them at HIGH. HIGH came up on about "
                 f"{rates['high_pct']}% of rainy-season days. <a href='analysis/backtest.html'>How well it works</a>.</p>")
    cards = [
        ("outlook-method.html", "How the Outlook works", "The rules behind each level, the two daily issues, and the ways to receive it.", None),
        ("map-guide.html", "Reading the map", "The warning colours (the international code), what each hazard layer shows, and how to search and share a place.", None),
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
    body = f"""<div class="hero"><p class="eyebrow">How it works</p><h1>Watching the <em>mountains</em></h1>
<p class="lede">Sierra Leone is named after the Lion Mountains, the peninsula hills above Freetown. When heavy rain falls on
them, the streams reach the low neighbourhoods within the hour. Lion Eyes watches that rain from satellites and weather
forecasts, and turns it into a simple outlook twice a day.</p></div>
<div class="flow">
<div class="step"><b>Rain on the way</b><span>The European weather centre's 51-member forecast: how likely a wet or very
wet day is, over the next three days.</span></div>
<div class="step"><b>Ground already wet</b><span>NASA satellite rain from the days before. Soaked ground floods and slides
with less rain.</span></div>
<div class="step"><b>Who is in the way</b><span>94 stream catchments traced from elevation data, with the people on low
ground and steep slopes in each.</span></div>
<div class="arrow" aria-hidden="true">&rarr;</div>
<div class="step out"><b>Act · Watch · Normal</b><span>Twice a day, on the map, as a short message and as a feed.</span></div>
</div>
{stats}
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


def _placed() -> dict[str, tuple[float, float, str]]:
    """Reported place name -> (lat, lon, precision), for names the map can show."""
    df = places.load()
    return {r["place"]: (float(r["lat"]), float(r["lon"]), str(r.get("precision") or "area")) for _, r in df.iterrows()}


def _places_geojson() -> dict:
    """One point per location; names that geocode to the same spot are merged."""
    cat = events.load_catalogue().sort_values("date", ascending=False)
    spots: dict[tuple[float, float], dict] = {}
    for name, (lat, lon, precision) in _placed().items():
        spot = spots.setdefault((round(lat, 4), round(lon, 4)), {"names": [], "precision": precision, "events": {}})
        spot["names"].append(name)
        if precision == "area":
            spot["precision"] = "area"
        for _, e in cat.iterrows():
            if name in e["locations"]:
                month_only = e["date_confidence"] == "month_only"
                spot["events"][e["event_id"]] = {
                    "id": e["event_id"], "date": f"{e['date']:%b %Y}" if month_only else f"{e['date']:%d %b %Y}",
                    "year": int(e["date"].year), "type": e["type"],
                    "deaths": None if pd.isna(e["deaths"]) else int(e["deaths"])}
    feats = []
    for (lat, lon), spot in spots.items():
        evs = sorted(spot["events"].values(), key=lambda e: e["id"], reverse=True)
        if not evs:
            continue
        names = sorted(spot["names"], key=len)
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                      "properties": {"place": names[0], "aka": names[1:], "precision": spot["precision"],
                                     "events": len(evs), "list": evs}})
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
        (out / target).write_text(_shell(label, _doc(src, target), depth=depth, path=target))
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
