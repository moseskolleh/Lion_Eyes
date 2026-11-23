// Lion Eyes map. Needs Leaflet and `LE` (the latest outlook, written into the page).
// Data: layers/layers.json (bounds, building tiles), layers/*.png|geojson,
// data/zones.geojson, data/flood_places.geojson.
//
// Colours follow two conventions:
// - Warning levels: the international colour code (ISO 22324, WMO/CAP practice,
//   MeteoAlarm): green = no warning, yellow = be aware (Watch), orange = be
//   prepared (Act). Red is kept for a flood warning (flooding imminent or under way).
// - Hazard maps: blue is kept for water only (flood-zone maps such as the UK
//   Environment Agency's: the darker the blue, the likelier the flooding), brown
//   hatching for steep, landslide-prone ground, a sequential purple ramp for
//   population (ColorBrewer; purple clashes with neither water nor warnings).
//   Things that are not hazards (past-flood markers, facilities) are neutral
//   dark grey, so a colour on the map always means the ground under it.
(function () {
  'use strict';
  const $ = s => document.querySelector(s);
  const bar = $('header.bar'), panel = $('#panel'), layersEl = $('#layers'), box = $('#searchbox');
  const isLight = () => document.documentElement.classList.contains('light-mode');
  const narrow = () => innerWidth <= 760;
  const store = {get: k => { try { return localStorage.getItem('le-' + k); } catch (e) { return null; } },
                 set: (k, v) => { try { localStorage.setItem('le-' + k, v); } catch (e) { /* private mode */ } }};

  const WARN = {LOW: '#00a651', ELEVATED: '#ffdd00', HIGH: '#ff8c00'};
  const WARN_EDGE = {LOW: '#007a3c', ELEVATED: '#b89c00', HIGH: '#c46a00'};
  // ColorBrewer Blues for water: light = floods in heavy rain, mid = floods first,
  // darkest for stream lines and the buildings and roads on flood-prone ground.
  const PAL = () => isLight()
    ? {water: '#08306b', low: '#9ecae1', lowCore: '#4292c6', roadLow: '#2171b5', bldLow: '#08519c', steep: '#8c510a',
       bldSteep: '#8c510a', bld: '#8e9297', zone: '#5b6470', road: '#4b5360'}
    : {water: '#9ecae1', low: '#21507d', lowCore: '#3b8fd9', roadLow: '#4ea3e6', bldLow: '#6baed6', steep: '#d8a65b',
       bldSteep: '#d8a65b', bld: '#9aa0a6', zone: '#9aa3ad', road: '#aab1ba'};
  // People per hectare: ColorBrewer Purples (the 6-class ramp without its near-white step,
  // which vanished on the grey base map). Must match site.POP_RAMP.
  const POP = ['#dadaeb', '#bcbddc', '#9e9ac8', '#756bb1', '#54278f'];
  const MARK = '#2b2f36';  // past floods and facilities: neutral, not a hazard colour

  function sizes() {
    const root = document.documentElement.style;
    root.setProperty('--bar-h', bar.offsetHeight + 'px');
    root.setProperty('--search-h', (box ? box.offsetHeight : 0) + 'px');
    root.setProperty('--sheet-h', (narrow() && panel ? panel.offsetHeight : 0) + 'px');
  }

  // --- the map -------------------------------------------------------------
  // Fractional zoom and a gentler wheel make scroll-zooming smooth on trackpads and mice.
  const map = L.map('map', {zoomControl: false, minZoom: 10, maxZoom: 19, maxBounds: [[7.8, -13.8], [9.0, -12.4]],
                            zoomSnap: 0.25, zoomDelta: 0.5, wheelPxPerZoomLevel: 110, wheelDebounceTime: 20})
    .setView(innerWidth <= 760 ? [8.462, -13.228] : [8.45, -13.2], innerWidth <= 760 ? 12.5 : 12);
  L.control.zoom({position: 'bottomright'}).addTo(map);
  L.control.scale({position: 'bottomleft', imperial: false}).addTo(map);
  [['relief', 205], ['pop', 210], ['ground', 220], ['hatch', 225], ['buildings', 230], ['water', 240],
   ['zones', 400], ['roads', 420], ['points', 620], ['top', 640]].forEach(([name, z]) => {
    const p = map.createPane(name);
    p.style.zIndex = z;
    if (['relief', 'pop', 'ground', 'hatch', 'buildings', 'water'].includes(name)) p.style.pointerEvents = 'none';
  });
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
  map.attributionControl.addAttribution('Overture Maps · Meta HRSL · Copernicus DEM');

  // Base maps: the street map is greyed so the hazard colours stand out.
  const BASE = {
    streets: () => L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, className: 'bm-streets',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}),
    hot: () => L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', {maxZoom: 19, subdomains: 'abc',
      className: 'bm-hot', attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, ' +
      'style <a href="https://www.hotosm.org/">Humanitarian OpenStreetMap Team</a>, hosted by OSM France'}),
    satellite: () => L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {maxZoom: 19, maxNativeZoom: 18, className: 'bm-sat', attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics'}),
    none: () => null,
  };
  let baseLayer = null;
  function setBase(name) {
    if (!BASE[name]) name = 'streets';
    if (baseLayer) map.removeLayer(baseLayer);
    baseLayer = BASE[name]();
    if (baseLayer) baseLayer.addTo(map).bringToBack();
    document.documentElement.dataset.basemap = name;
    const r = document.querySelector(`input[name="basemap"][value="${name}"]`);
    if (r) r.checked = true;
    store.set('basemap', name);
  }
  setBase(store.get('basemap') || 'streets');
  document.querySelectorAll('input[name="basemap"]').forEach(r => r.addEventListener('change', () => setBase(r.value)));

  const level = LE.level, onAlert = level !== 'LOW';
  const named = new Set(LE.named);
  const fmt = v => (v === undefined || v === null) ? '?' :
    (Math.round(v / (v >= 1000 ? 100 : 10)) * (v >= 1000 ? 100 : 10)).toLocaleString('en');
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const popupOpts = () => ({maxWidth: 300, autoPanPaddingTopLeft: [narrow() ? 12 : 410, bar.offsetHeight + 70],
    autoPanPaddingBottomRight: [narrow() || !layersEl.classList.contains('open') ? 12 : 330, narrow() && panel ? panel.offsetHeight + 12 : 12]});
  const openPopup = (ll, html) => L.popup(popupOpts()).setLatLng(ll).setContent(html).openOn(map);

  // --- rasters: masks recoloured in the browser ---------------------------
  let B = null;  // [[south, west], [north, east]] of the raster layers
  const loadImg = src => new Promise((ok, bad) => { const i = new Image(); i.onload = () => ok(i); i.onerror = bad; i.src = src; });
  function sampler(imgPromise) {
    let ctx = null, w = 0, h = 0;
    imgPromise.then(img => {
      const c = document.createElement('canvas'); c.width = w = img.width; c.height = h = img.height;
      ctx = c.getContext('2d', {willReadFrequently: true}); ctx.drawImage(img, 0, 0);
    }).catch(() => {});
    return ll => {
      if (!ctx || !B) return null;
      const [[s, wst], [n, e]] = B;
      const x = Math.floor((ll.lng - wst) / (e - wst) * w), y = Math.floor((n - ll.lat) / (n - s) * h);
      if (x < 0 || y < 0 || x >= w || y >= h) return null;
      return ctx.getImageData(x, y, 1, 1).data;
    };
  }
  const IMG = {low: loadImg('layers/lowground.png'), core: loadImg('layers/lowground_core.png'),
               steep: loadImg('layers/steep.png'), pop: loadImg('layers/population.png')};
  const lowAt = sampler(IMG.low), coreAt = sampler(IMG.core), steepAt = sampler(IMG.steep), popAt = sampler(IMG.pop);
  let popSteps = [], coreM = 1, lowM = 3;

  // A tile layer drawn from whole-area masks: each [mask, style] pair is a solid fill
  // or hatching, painted in order (later pairs on top), crisp at any zoom.
  const MaskLayer = L.GridLayer.extend({
    initialize(parts, opts) { this._parts = parts; L.GridLayer.prototype.initialize.call(this, opts); },
    createTile(coords) {
      const t = document.createElement('canvas'), size = this.getTileSize();
      t.width = size.x; t.height = size.y;
      const [[s, w], [n, e]] = B, out = t.getContext('2d');
      const nw = map.unproject(coords.scaleBy(size), coords.z), se = map.unproject(coords.add([1, 1]).scaleBy(size), coords.z);
      this._parts.forEach(([img, style]) => {
        const sx = (nw.lng - w) / (e - w) * img.width, sy = (n - nw.lat) / (n - s) * img.height;
        const sw = (se.lng - nw.lng) / (e - w) * img.width, sh = (nw.lat - se.lat) / (n - s) * img.height;
        const c = document.createElement('canvas'); c.width = size.x; c.height = size.y;
        const ctx = c.getContext('2d');
        ctx.drawImage(img, sx, sy, sw, sh, 0, 0, size.x, size.y);
        ctx.globalCompositeOperation = 'source-in';
        ctx.fillStyle = style(ctx);
        ctx.fillRect(0, 0, size.x, size.y);
        out.drawImage(c, 0, 0);
      });
      return t;
    },
  });
  function hatch(ctx, colour) {
    const p = document.createElement('canvas'); p.width = p.height = 8;
    const c = p.getContext('2d'); c.strokeStyle = colour; c.lineWidth = 2; c.lineCap = 'square';
    c.beginPath(); c.moveTo(0, 8); c.lineTo(8, 0); c.moveTo(-2, 2); c.lineTo(2, -2); c.moveTo(6, 10); c.lineTo(10, 6); c.stroke();
    return ctx.createPattern(p, 'repeat');
  }

  // Building tiles store a class colour (low ground, steep, other); repaint them in the current palette.
  const BuildingTiles = L.GridLayer.extend({
    initialize(have, opts) { this._have = have; L.GridLayer.prototype.initialize.call(this, opts); },
    createTile(coords, done) {
      const t = document.createElement('canvas'); t.width = t.height = 256;
      const z = Math.min(Math.max(Math.round(coords.z), 13), 16);
      const k = Math.pow(2, coords.z - z), x = Math.floor(coords.x / k), y = Math.floor(coords.y / k);
      const key = `${z}/${x}/${y}`;
      if (!this._have.has(key)) { setTimeout(() => done(null, t), 0); return t; }
      loadImg(`layers/buildings/${key}.png`).then(img => {
        const ctx = t.getContext('2d', {willReadFrequently: true});
        ctx.imageSmoothingEnabled = false;
        const part = 256 / k;
        ctx.drawImage(img, (coords.x - x * k) * part, (coords.y - y * k) * part, part, part, 0, 0, 256, 256);
        const d = ctx.getImageData(0, 0, 256, 256), px = d.data, P = PAL();
        const rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
        const cols = [rgb(P.bld), rgb(P.bldLow), rgb(P.bldSteep)];
        for (let i = 0; i < px.length; i += 4) {
          if (!px[i + 3]) continue;
          const r = px[i], b = px[i + 2], c = b > r + 40 ? 1 : r > b + 60 ? 2 : 0;
          px[i] = cols[c][0]; px[i + 1] = cols[c][1]; px[i + 2] = cols[c][2];
        }
        ctx.putImageData(d, 0, 0);
        done(null, t);
      }).catch(() => done(null, t));
      return t;
    },
  });

  function whatsHere(ll) {
    const low = lowAt(ll), core = coreAt(ll), steep = steepAt(ll), pop = popAt(ll);
    let html = '';
    if (core && core[3] > 0) html += `<span class="tag core">Floods first</span> Less than ${coreM} m above the nearest stream or the shore: the first ground to flood in heavy rain.<br>`;
    else if (low && low[3] > 0) html += `<span class="tag low">Floods in heavy rain</span> ${coreM}-${lowM} m above the nearest stream or the shore: water reaches here in a big storm.<br>`;
    if (steep && steep[3] > 0) html += '<span class="tag steep">Steep slope</span> Watch for landslides, rockfalls and wall collapses.<br>';
    if (!html) html = '<span class="tag ok">Higher, gentler ground</span> Less exposed to flooding here.<br>';
    if (pop && pop[3] > 0 && popSteps.length) {
      const hex = '#' + [pop[0], pop[1], pop[2]].map(v => v.toString(16).padStart(2, '0')).join('');
      const i = popSteps.findIndex(s => s[1].toLowerCase() === hex);
      if (i >= 0) html += `About ${popSteps[i][0]}${i + 1 < popSteps.length ? '–' + popSteps[i + 1][0] : '+'} people per hectare around here (estimated from buildings).`;
    }
    return html;
  }

  // --- layer switching ----------------------------------------------------
  const L_ = {};  // id -> {layer, minZoom, on, raster}
  let overlayOpacity = (+store.get('opacity') || 80) / 100;
  function setOn(id, on) {
    const d = L_[id]; if (!d) return;
    d.on = on;
    const show = on && (!d.minZoom || map.getZoom() >= d.minZoom);
    if (show && !map.hasLayer(d.layer)) d.layer.addTo(map);
    if (!show && map.hasLayer(d.layer)) map.removeLayer(d.layer);
    const hint = document.querySelector(`[data-zoomhint="${id}"]`);
    if (hint) hint.hidden = !(on && d.minZoom && map.getZoom() < d.minZoom);
    store.set('layer-' + id, on ? '1' : '0');
    keySoon();
  }

  // --- map key: what each colour now on the map means ------------------------
  // Only the layers showing at this zoom are listed, each colour with its meaning
  // in words, so no colour on the map needs guessing.
  const keyEl = $('#mapkey'), keyList = keyEl && keyEl.querySelector('.keybody'), keyBtn = $('#keyBtn');
  const keyPop = keyEl && keyEl.querySelector('.keypop');
  let keyTimer = 0;
  function keySoon() { if (keyList) { cancelAnimationFrame(keyTimer); keyTimer = requestAnimationFrame(renderKey); } }
  const sw = (bg, cls = '') => `<i class="sw ${cls}" style="background:${bg}"></i>`;
  const ln = (c, h) => `<i class="ln" style="background:${c};height:${h}px"></i>`;
  const hatchBg = c => `repeating-linear-gradient(-45deg,${c} 0 2px,transparent 2px 6px)`;
  function renderKey() {
    const P = PAL(), on = id => L_[id] && map.hasLayer(L_[id].layer), rows = [];
    const row = (sym, text) => rows.push(`<li><span class="sym">${sym}</span><span>${text}</span></li>`);
    if (on('zones')) {
      if (onAlert) row(sw(WARN[level], 'zone'), `<b>${esc(LE.word)}</b> zone in today's outlook`);
      row('<i class="sw dash"></i>', 'Warning zone (a stream catchment)');
    }
    if (on('low')) {
      row(sw(P.lowCore), `<b>Floods first</b> (under ${coreM} m above a stream)`);
      row(sw(P.low), `<b>Floods in heavy rain</b> (${coreM}-${lowM} m above)`);
    }
    if (on('streams')) row(ln(P.water, 3), 'Stream');
    if (on('floods')) row('<i class="sw flk">3</i>', 'Past floods here (how many)');
    if (on('steep')) row(`<i class="sw" style="background:${hatchBg(P.steep)};box-shadow:inset 0 0 0 1px ${P.steep}"></i>`,
      '<b>Landslide-prone</b> slope (over 25°)');
    if (on('buildings')) row(sw(P.bldLow) + sw(P.bldSteep) + sw(P.bld),
      'Buildings: on flood-prone ground, steep slope, elsewhere');
    if (on('roads')) row(ln(P.roadLow, 6), 'Main road that may flood');
    if (on('facilities') || on('worship')) row(`<i class="sw fck" style="box-shadow:0 0 0 2.5px ${P.roadLow}">H</i>`,
      'Clinic, school, police (ring: <b>blue</b> flood-prone, <b>brown</b> steep)');
    let popHtml = '';
    if (on('pop') && popSteps.length) {
      const cells = POP.map((c, i) => `<span><i style="background:${c}"></i>${popSteps[i] ? popSteps[i][0] +
        (i + 1 < popSteps.length ? '-' + popSteps[i + 1][0] : '+') : ''}</span>`).join('');
      popHtml = `<span>People per hectare <small>(a hectare is about a football pitch)</small></span><span class="steps">${cells}</span>`;
    }
    keyList.innerHTML = rows.join('');
    // Two columns read top to bottom, so pairs (the two flood shades) stay together.
    keyList.style.gridTemplateRows = `repeat(${Math.ceil(rows.length / 2)}, auto)`;
    keyPop.innerHTML = popHtml; keyPop.hidden = !popHtml;
    keyEl.hidden = !rows.length && !popHtml;
  }
  if (keyEl) {
    const wide = () => innerWidth > 1180;
    const saved = store.get('key');
    keyEl.classList.toggle('closed', saved ? saved === 'closed' : !wide());
    keyBtn.setAttribute('aria-expanded', String(!keyEl.classList.contains('closed')));
    keyBtn.addEventListener('click', () => {
      const closed = keyEl.classList.toggle('closed');
      keyBtn.setAttribute('aria-expanded', String(!closed));
      store.set('key', closed ? 'closed' : 'open');
    });
  }
  map.on('zoomend', () => Object.keys(L_).forEach(id => setOn(id, L_[id].on)));
  function register(id, layer, minZoom, raster) {
    const boxEl = document.querySelector(`input[data-layer="${id}"]`);
    const saved = store.get('layer-' + id);
    if (boxEl && saved !== null) boxEl.checked = saved === '1';
    L_[id] = {layer, minZoom, on: boxEl ? boxEl.checked : true, raster};
    if (raster && layer.setOpacity) layer.setOpacity(raster * overlayOpacity);
    setOn(id, L_[id].on);
  }
  document.querySelectorAll('input[data-layer]').forEach(b => b.addEventListener('change', () => setOn(b.dataset.layer, b.checked)));
  const op = $('#opacity'), opOut = $('#opacityOut');
  if (op) {
    op.value = Math.round(overlayOpacity * 100); opOut.textContent = op.value + '%';
    op.addEventListener('input', () => {
      overlayOpacity = op.value / 100; opOut.textContent = op.value + '%'; store.set('opacity', op.value);
      Object.values(L_).forEach(d => { if (d.raster && d.layer.setOpacity) d.layer.setOpacity(d.raster * overlayOpacity); });
    });
  }

  // --- search index ---------------------------------------------------------
  const index = [];  // {name, aka, kind, rank, sub, go}
  const ready = [];  // promises: everything the search and #links need

  // Warning zones.
  function zoneStyle(f) {
    const hit = onAlert && named.has(f.properties.name);
    return hit ? {color: WARN_EDGE[level], weight: 2.5, opacity: 1, fillColor: WARN[level], fillOpacity: 0.4}
               : {color: PAL().zone, weight: 0.9, opacity: 0.85, fill: true, fillOpacity: 0, dashArray: '4 4'};
  }
  function zonePopup(p, ll) {
    return `<h4>${esc(p.name || 'Zone ' + p.zone_id)}</h4><p class="pk">Warning zone · stream catchment</p>` +
      (onAlert && named.has(p.name) ? `<p><span class="lvl ${level}">${level}</span> Named in this outlook: ${esc(LE.word)}</p>` : '') +
      `<div class="here">${whatsHere(ll)}</div>` +
      `<p>About <b>${fmt(p.people)}</b> people live in this catchment: ${fmt(p.people_low_ground)} on flood-prone ground, ` +
      `${fmt(p.people_steep)} on steep slopes.</p>`;
  }
  ready.push(fetch('data/zones.geojson').then(r => r.json()).then(gj => {
    const layer = L.geoJSON(gj, {
      pane: 'zones', filter: f => f.properties.zone_id > 0, style: zoneStyle,
      onEachFeature: (f, lyr) => {
        lyr.on('click', e => { L.DomEvent.stopPropagation(e); openPopup(e.latlng, zonePopup(f.properties, e.latlng)); });
        index.push({name: f.properties.name || 'Zone ' + f.properties.zone_id, kind: 'Warning zone', rank: 2, icon: 'zone',
                    sub: `${fmt(f.properties.people)} people`,
                    go: () => { map.fitBounds(lyr.getBounds(), {maxZoom: 15.5, paddingTopLeft: [narrow() ? 0 : 400, 60]});
                                setTimeout(() => openPopup(lyr.getBounds().getCenter(), zonePopup(f.properties, lyr.getBounds().getCenter())), 350); }});
      }
    });
    register('zones', layer);
  }));

  // Past floods: one marker per place, the number of floods inside.
  let floodLayer = null, floodFeatures = [];
  const TYPE = {flash_flood: 'flash flood', landslide: 'landslide', mixed: 'flood and collapse', coastal_flood: 'coastal flood'};
  function floodIcon(n) {
    const d = Math.round(16 + 6 * Math.sqrt(n));
    return L.divIcon({className: 'fl', iconSize: [d, d], html: `<b>${n}</b>`});
  }
  function floodPopup(p, list) {
    const items = list.map(e => `<li><a href="floods.html#${e.id}">${esc(e.date)}</a> · ${TYPE[e.type] || e.type}` +
      (e.deaths ? ` · <span class="dead">${e.deaths} dead</span>` : '') + '</li>').join('');
    return `<h4>${esc(p.place)}</h4><p class="pk">${list.length} reported flood${list.length > 1 ? 's' : ''}` +
      (p.aka.length ? ` · also reported as ${p.aka.map(esc).join(', ')}` : '') + '</p>' +
      `<ul class="evlist">${items}</ul>` +
      (p.precision !== 'area' ? `<p class="fine">Placed on the ${p.precision} of that name in OpenStreetMap: approximate.</p>` : '');
  }
  function drawFloods(since) {
    if (!floodLayer) return;
    floodLayer.clearLayers();
    floodFeatures.forEach(f => {
      const p = f.properties, list = p.list.filter(e => e.year >= since);
      if (!list.length) return;
      const m = L.marker([f.geometry.coordinates[1], f.geometry.coordinates[0]],
        {pane: 'points', icon: floodIcon(list.length), title: `${p.place}: ${list.length} flood${list.length > 1 ? 's' : ''}`,
         riseOnHover: true, keyboard: true, zIndexOffset: list.length * 10});
      m.bindPopup(() => floodPopup(p, list), popupOpts());
      p._marker = m;
      floodLayer.addLayer(m);
    });
  }
  ready.push(fetch('data/flood_places.geojson').then(r => r.json()).then(gj => {
    floodFeatures = gj.features;
    floodLayer = L.layerGroup();
    const since = $('#since'), out = $('#sinceOut');
    const years = gj.features.flatMap(f => f.properties.list.map(e => e.year));
    if (since && years.length) {
      since.min = Math.min(...years); since.max = Math.max(...years); since.value = since.min;
      out.textContent = 'since ' + since.min;
      since.addEventListener('input', () => { out.textContent = 'since ' + since.value; drawFloods(+since.value); });
    }
    drawFloods(since ? +since.value : 0);
    register('floods', floodLayer);
    gj.features.forEach(f => {
      const p = f.properties, ll = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
      const go = () => { setOn('floods', true); const b = document.querySelector('input[data-layer="floods"]'); if (b) b.checked = true;
        map.setView(ll, 16); if (p._marker) setTimeout(() => p._marker.openPopup(), 300); };
      index.push({name: p.place, aka: p.aka, kind: 'Past flood place', rank: 0, icon: 'flood',
                  sub: `${p.events} flood${p.events > 1 ? 's' : ''}`, go});
    });
  }));

  ready.push(fetch('layers/layers.json').then(r => r.json()).then(async meta => {
    B = meta.bounds; popSteps = meta.population_steps;
    coreM = meta.core_hand_m || coreM; lowM = meta.low_hand_m || lowM;
    const [low, core, steep, pop] = await Promise.all([IMG.low, IMG.core, IMG.steep, IMG.pop]);
    register('low', new MaskLayer([[low, () => PAL().low], [core, () => PAL().lowCore]],
      {pane: 'ground', bounds: B, opacity: 0.85, maxZoom: 19}), null, 0.85);
    register('steep', new MaskLayer([[steep, ctx => hatch(ctx, PAL().steep)]], {pane: 'hatch', bounds: B, maxZoom: 19}), null, 1);
    // Population: the class colours in the image are swapped for the Purples ramp.
    const c = document.createElement('canvas'); c.width = pop.width; c.height = pop.height;
    const cx = c.getContext('2d'); cx.drawImage(pop, 0, 0);
    const d = cx.getImageData(0, 0, c.width, c.height), px = d.data;
    const src = popSteps.map(s => [1, 3, 5].map(i => parseInt(s[1].slice(i, i + 2), 16)));
    const dst = POP.map(h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)));
    for (let i = 0; i < px.length; i += 4) {
      if (!px[i + 3]) continue;
      let best = 0, bd = 1e9;
      src.forEach((s, j) => { const dd = (s[0] - px[i]) ** 2 + (s[1] - px[i + 1]) ** 2 + (s[2] - px[i + 2]) ** 2; if (dd < bd) { bd = dd; best = j; } });
      [px[i], px[i + 1], px[i + 2]] = dst[Math.min(best, dst.length - 1)]; px[i + 3] = 215;
    }
    cx.putImageData(d, 0, 0);
    register('pop', L.imageOverlay(c.toDataURL(), B, {pane: 'pop', interactive: false}), null, 0.9);
    register('relief', L.imageOverlay('layers/hillshade.png', B, {pane: 'relief', opacity: 0.85, interactive: false}));
    register('buildings', new BuildingTiles(new Set(meta.building_tiles), {pane: 'buildings', minZoom: 13, maxZoom: 19,
      bounds: B, opacity: 0.95}), 14);
  }));

  let streams = null;
  ready.push(fetch('layers/streams.geojson').then(r => r.json()).then(gj => {
    streams = L.geoJSON(gj, {pane: 'water', interactive: false,
      style: f => ({color: PAL().water, opacity: 0.9, weight: f.properties.km2 >= 20 ? 3.2 : f.properties.km2 >= 5 ? 2.2 : 1.2})});
    register('streams', streams);
  }));

  // Roads: grey, with the stretches over flood-prone ground in blue.
  const RW = {motorway: 3.4, trunk: 3.4, primary: 2.8, secondary: 2.2, tertiary: 1.7};
  const roadStyle = f => f.properties.kind === 'low_road'
    ? {color: PAL().roadLow, weight: (RW[f.properties.class] || 2) + 2.2, opacity: 0.95, lineCap: 'butt'}
    : {color: PAL().road, weight: (RW[f.properties.class] || 2) - 0.6, opacity: isLight() ? 0.75 : 0.55};
  let roads = null, flash = null;
  ready.push(fetch('layers/roads.geojson').then(r => r.json()).then(gj => {
    const byName = {};
    roads = L.geoJSON(gj, {
      pane: 'roads', style: roadStyle,
      onEachFeature: (f, lyr) => {
        const p = f.properties;
        lyr.bindPopup(() => p.kind === 'low_road'
          ? `<h4>${esc(p.name || 'Main road')}</h4><p><span class="tag low">May flood</span> This stretch crosses flood-prone ground.</p>`
          : `<h4>${esc(p.name || 'Main road')}</h4><p class="pk">${esc(p['class'])} road</p>`, popupOpts());
        if (p.name) (byName[p.name] = byName[p.name] || []).push(lyr);
      }
    });
    register('roads', roads);
    Object.entries(byName).forEach(([name, parts]) => {
      const low = parts.some(l => l.feature.properties.kind === 'low_road');
      index.push({name, kind: 'Road', rank: 3, icon: 'road', sub: low ? 'parts may flood' : '', go: () => {
        const g = L.featureGroup(parts); map.fitBounds(g.getBounds(), {maxZoom: 16.5, paddingTopLeft: [narrow() ? 0 : 400, 60]});
        if (flash) map.removeLayer(flash);
        flash = L.geoJSON(L.featureGroup(parts).toGeoJSON(), {pane: 'top', interactive: false,
          style: {color: '#00c8ff', weight: 10, opacity: 0.5}}).addTo(map);
        setTimeout(() => { if (flash) { map.removeLayer(flash); flash = null; } }, 4000);
      }});
    });
  }));

  // Facilities: the international hospital "H", a book for schools, a shield for police; all
  // dark grey, with a ring in the hazard colour of the ground they stand on.
  const GLYPH = {
    health: '<text x="12" y="16.5" text-anchor="middle" font-size="13" font-weight="700" font-family="Inter,Arial,sans-serif" fill="#fff">H</text>',
    school: '<path d="M5 7.5c2.4-1 4.8-1 7 .6 2.2-1.6 4.6-1.6 7-.6v9c-2.4-1-4.8-1-7 .6-2.2-1.6-4.6-1.6-7-.6z" fill="none" stroke="#fff" stroke-width="1.6"/><path d="M12 8.1v9" stroke="#fff" stroke-width="1.4"/>',
    emergency: '<path d="M12 5l6 2.2v4.3c0 3.6-2.5 6.1-6 7.5-3.5-1.4-6-3.9-6-7.5V7.2z" fill="#fff"/>',
    worship: '<path d="M7 18v-6l5-4 5 4v6zM12 5v3" fill="none" stroke="#fff" stroke-width="1.6"/>',
  };
  const FILL = {health: MARK, school: MARK, emergency: MARK, worship: '#6b7280'};
  const GROUP = {health: 'Health facility', school: 'School', emergency: 'Police', worship: 'Place of worship'};
  ready.push(fetch('layers/facilities.geojson').then(r => r.json()).then(gj => {
    const groups = {facilities: L.layerGroup(), schools: L.layerGroup(), worship: L.layerGroup()};
    gj.features.forEach(f => {
      const p = f.properties, ll = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
      const ring = p.low ? PAL().roadLow : p.steep ? PAL().steep : '#fff';
      const m = L.marker(ll, {pane: 'points', title: p.name || GROUP[p.group], keyboard: false,
        icon: L.divIcon({className: 'fac', iconSize: [22, 22],
          html: `<svg viewBox="0 0 24 24" width="22" height="22"><circle cx="12" cy="12" r="10.2" fill="${FILL[p.group]}" stroke="${ring}" stroke-width="2.8"/>${GLYPH[p.group]}</svg>`})});
      m.bindPopup(() => `<h4>${esc(p.name || GROUP[p.group])}</h4><p class="pk">${GROUP[p.group]}</p><p>` +
        (p.low ? '<span class="tag low">On flood-prone ground</span> May be cut off or flooded.' :
         p.steep ? '<span class="tag steep">On a steep slope</span>' : '<span class="tag ok">Not on flood-prone ground</span>') + '</p>', popupOpts());
      (p.group === 'worship' ? groups.worship : p.group === 'school' ? groups.schools : groups.facilities).addLayer(m);
      if (p.name) index.push({name: p.name.replace(/, Sierra Leone$/, ''), kind: GROUP[p.group], rank: 4, icon: p.group,
        sub: p.low ? 'on flood-prone ground' : '', go: () => {
          const id = p.group === 'worship' ? 'worship' : 'facilities'; setOn(id, true);
          const b = document.querySelector(`input[data-layer="${id}"]`); if (b) b.checked = true;
          map.setView(ll, 17); setTimeout(() => m.openPopup(), 300); }});
    });
    register('facilities', groups.facilities, 14);
    register('worship', groups.worship, 16);
    // Schools are many (180): they join from zoom 15.5, when there is room for them.
    const schools = () => { const want = map.getZoom() >= 15.5, has = groups.facilities.hasLayer(groups.schools);
      if (want && !has) groups.facilities.addLayer(groups.schools); if (!want && has) groups.facilities.removeLayer(groups.schools); };
    map.on('zoomend', schools); schools();
  }));

  // Click anywhere for what is there.
  map.on('click', e => openPopup(e.latlng, `<h4>This spot</h4><div class="here">${whatsHere(e.latlng)}</div>`));
  const hint = $('#hint');
  map.once('click', () => { if (hint) hint.hidden = true; });
  setTimeout(() => { if (hint) hint.hidden = true; }, 9000);

  document.addEventListener('themechange', () => {
    Object.values(L_).forEach(d => { if (d.layer.redraw && !(d.layer instanceof L.TileLayer)) d.layer.redraw(); });
    if (L_.zones) L_.zones.layer.setStyle(zoneStyle);
    if (roads) roads.setStyle(roadStyle);
    if (streams) streams.setStyle({color: PAL().water});
    keySoon();
  });

  // --- search -----------------------------------------------------------------
  const input = $('#q'), list = $('#results'), clearBtn = $('#qclear');
  const norm = s => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
  function near(a, b) {  // edit distance <= 1 (<= 2 for long words), for spelling variants such as Dwarzark/Dworzark
    if (Math.abs(a.length - b.length) > 2) return false;
    const m = a.length, n = b.length, row = Array.from({length: n + 1}, (_, j) => j);
    for (let i = 1; i <= m; i++) {
      let prev = row[0]; row[0] = i;
      for (let j = 1; j <= n; j++) { const t = row[j]; row[j] = Math.min(row[j] + 1, row[j - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1)); prev = t; }
    }
    return row[n] <= (a.length >= 7 ? 2 : 1);
  }
  function score(item, q) {
    let best = 9;
    [item.name].concat(item.aka || []).forEach(name => {
      const n = norm(name);
      if (n === q) best = Math.min(best, 0);
      else if (n.startsWith(q)) best = Math.min(best, 1);
      else if (n.split(' ').some(w => w.startsWith(q))) best = Math.min(best, 2);
      else if (n.includes(q)) best = Math.min(best, 3);
      else if (q.length >= 4 && n.split(' ').some(w => w.length >= 4 && near(w, q))) best = Math.min(best, 4);
    });
    return best;
  }
  const ICON = {flood: '●', zone: '⬚', road: '═', health: 'H', school: '▤', emergency: '◆', worship: '⌂', osm: '⌖', coords: '✛'};
  const COORD = /^\s*(-?\d{1,2}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$/;
  let hits = [], cur = -1, osmFor = null;
  function render() {
    const q = input.value.trim();
    const rows = hits.map((h, i) => `<li id="r${i}" role="option" data-i="${i}" class="${i === cur ? 'on' : ''}" aria-selected="${i === cur}">` +
      `<span class="ri ri-${h.icon}" aria-hidden="true">${ICON[h.icon] || '•'}</span><span class="rn">${esc(h.name)}</span>` +
      `<small>${esc(h.kind)}${h.sub ? ' · ' + esc(h.sub) : ''}</small></li>`);
    if (q.length >= 3 && osmFor !== q && !COORD.test(q)) rows.push(`<li data-osm="1" role="option" class="osm${cur === hits.length ? ' on' : ''}">` +
      `<span class="ri" aria-hidden="true">${ICON.osm}</span><span class="rn">Search OpenStreetMap for “${esc(q)}”</span></li>`);
    if (q.length >= 2 && !hits.length && osmFor === q) rows.push('<li class="none">Nothing found on the peninsula.</li>');
    list.innerHTML = rows.join('');
    list.hidden = !rows.length;
    input.setAttribute('aria-expanded', String(!list.hidden));
    input.setAttribute('aria-activedescendant', cur >= 0 && cur < hits.length ? 'r' + cur : '');
    const on = list.querySelector('li.on'); if (on) on.scrollIntoView({block: 'nearest'});
  }
  let pin = null;
  function dropPin(ll, label) {
    if (pin) map.removeLayer(pin);
    pin = L.marker(ll, {pane: 'top', icon: L.divIcon({className: 'pin', iconSize: [26, 26]}), keyboard: false}).addTo(map);
    map.setView(ll, Math.max(map.getZoom(), 16));
    setTimeout(() => openPopup(ll, `<h4>${esc(label)}</h4><div class="here">${whatsHere(L.latLng(ll))}</div>`), 300);
  }
  function find() {
    const raw = input.value.trim(), q = norm(raw);
    clearBtn.hidden = !raw; osmFor = null;
    const c = raw.match(COORD);
    if (c && Math.abs(+c[1]) <= 90) {
      hits = [{name: `${(+c[1]).toFixed(5)}, ${(+c[2]).toFixed(5)}`, kind: 'Coordinates', icon: 'coords', go: () => dropPin([+c[1], +c[2]], 'This spot')}];
    } else {
      hits = q.length < 2 ? [] : index.map(it => ({it, s: score(it, q)})).filter(x => x.s < 9)
        .sort((a, b) => a.s - b.s || a.it.rank - b.it.rank || a.it.name.length - b.it.name.length)
        .slice(0, 12).map(x => x.it);
      const seen = new Set(); hits = hits.filter(h => { const k = h.kind + '|' + norm(h.name); if (seen.has(k)) return false; seen.add(k); return true; });
    }
    cur = hits.length ? 0 : -1; render();
  }
  // OpenStreetMap search, only on request (Nominatim's usage policy rules out search-as-you-type).
  function osm() {
    const q = input.value.trim(); if (q.length < 3) return;
    osmFor = q; list.innerHTML = '<li class="none">Searching OpenStreetMap…</li>'; list.hidden = false;
    const url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=8&countrycodes=sl&bounded=1' +
      '&viewbox=-13.32,8.56,-12.98,8.20&q=' + encodeURIComponent(q);
    const stale = () => input.value.trim() !== q;  // the box changed while OpenStreetMap was answering
    fetch(url, {headers: {'Accept-Language': 'en'}}).then(r => r.json()).then(res => {
      if (stale()) return;
      hits = res.map(h => ({name: h.name || h.display_name.split(',')[0], kind: 'OpenStreetMap', icon: 'osm',
        sub: [h.type && h.type !== 'yes' ? h.type.replace(/_/g, ' ') : '', h.display_name.split(',').slice(1, 3).join(',').trim()].filter(Boolean).join(' · '),
        go: () => dropPin([+h.lat, +h.lon], h.name || h.display_name.split(',')[0])}));
      cur = hits.length ? 0 : -1; render();
    }).catch(() => { if (!stale()) list.innerHTML = '<li class="none">OpenStreetMap search is not available right now.</li>'; });
  }
  function pick(i) {
    if (i === hits.length && !list.hidden && list.querySelector('[data-osm]')) { osm(); return; }
    const h = hits[i]; if (!h) { if (input.value.trim().length >= 3) osm(); return; }
    h.go(); input.value = h.name; hits = []; list.innerHTML = ''; list.hidden = true; input.setAttribute('aria-expanded', 'false');
    clearBtn.hidden = false;
    if (narrow()) { input.blur(); closeLayers(); }
  }
  input.addEventListener('input', find);
  input.addEventListener('focus', () => { if (input.value.trim()) find(); });
  input.addEventListener('keydown', e => {
    const n = hits.length + (list.querySelector('[data-osm]') ? 1 : 0);
    if (e.key === 'ArrowDown') { cur = Math.min(cur + 1, n - 1); render(); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { cur = Math.max(cur - 1, 0); render(); e.preventDefault(); }
    else if (e.key === 'Enter') { pick(cur < 0 ? 0 : cur); e.preventDefault(); }
    else if (e.key === 'Escape') { if (list.hidden) { input.value = ''; clearBtn.hidden = true; input.blur(); } hits = []; render(); }
  });
  list.addEventListener('mousedown', e => e.preventDefault());  // keep focus in the box while choosing
  list.addEventListener('click', e => { const li = e.target.closest('li'); if (!li || li.classList.contains('none')) return;
    if (li.dataset.osm) osm(); else pick(+li.dataset.i); });
  document.addEventListener('click', e => { if (!box.contains(e.target)) { list.hidden = true; input.setAttribute('aria-expanded', 'false'); } });
  clearBtn.addEventListener('click', () => { input.value = ''; hits = []; render(); clearBtn.hidden = true; input.focus();
    if (pin) { map.removeLayer(pin); pin = null; } });
  document.addEventListener('keydown', e => {
    if (e.key === '/' && document.activeElement !== input && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      e.preventDefault(); input.focus(); input.select();
    }
  });

  // --- layers panel -------------------------------------------------------------
  const lb = $('#layersBtn');
  function openLayers() { layersEl.classList.add('open'); lb.setAttribute('aria-expanded', 'true'); store.set('layers-open', '1'); }
  function closeLayers() { layersEl.classList.remove('open'); lb.setAttribute('aria-expanded', 'false'); store.set('layers-open', '0'); }
  lb.addEventListener('click', () => layersEl.classList.contains('open') ? closeLayers() : openLayers());
  $('#layersClose').addEventListener('click', closeLayers);
  if (!narrow() && store.get('layers-open') !== '0') openLayers();
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && narrow() && layersEl.classList.contains('open')) closeLayers(); });
  // Remember which groups were folded.
  layersEl.querySelectorAll('details.grp').forEach((d, i) => {
    if (store.get('grp-' + i) === '0') d.open = false;
    d.addEventListener('toggle', () => store.set('grp-' + i, d.open ? '1' : '0'));
  });

  // My location.
  const Locate = L.Control.extend({options: {position: 'bottomright'}, onAdd: () => {
    const d = L.DomUtil.create('div', 'leaflet-bar locate'), a = L.DomUtil.create('a', '', d);
    a.href = '#'; a.title = 'Show my location'; a.setAttribute('role', 'button'); a.setAttribute('aria-label', 'Show my location');
    a.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>';
    L.DomEvent.on(a, 'click', e => { L.DomEvent.preventDefault(e); L.DomEvent.stopPropagation(e); map.locate({setView: true, maxZoom: 16}); });
    return d;
  }});
  map.addControl(new Locate());
  let me = null;
  map.on('locationfound', e => {
    if (me) map.removeLayer(me);
    me = L.layerGroup([L.circle(e.latlng, {radius: e.accuracy, color: '#2c7fb8', weight: 1, fillOpacity: 0.08}),
                       L.circleMarker(e.latlng, {radius: 7, color: '#fff', weight: 2, fillColor: '#2c7fb8', fillOpacity: 1})]).addTo(map);
    openPopup(e.latlng, `<h4>You are here</h4><div class="here">${whatsHere(e.latlng)}</div>`);
  });
  map.on('locationerror', () => openPopup(map.getCenter(), 'Your location is not available.'));

  // --- links: #place=Kroo%20Bay, #q=Kissy, #map=15/8.48/-13.24 ----------------------
  function fromHash() {
    const h = new URLSearchParams(location.hash.slice(1));
    const mv = (h.get('map') || '').split('/').map(Number);
    if (mv.length === 3 && mv.every(isFinite)) map.setView([mv[1], mv[2]], mv[0]);
    const q = h.get('place') || h.get('q');
    if (q) Promise.allSettled(ready).then(() => {
      input.value = q; find();
      const exact = hits.findIndex(x => norm(x.name) === norm(q) || (x.aka || []).some(a => norm(a) === norm(q)));
      if (exact >= 0 || (h.get('q') && hits.length)) pick(exact >= 0 ? exact : 0);
      history.replaceState(null, '', location.pathname + location.search);  // from here on the hash follows the view
    });
  }
  fromHash();
  addEventListener('hashchange', fromHash);
  map.on('moveend', () => {
    const c = map.getCenter(), h = new URLSearchParams(location.hash.slice(1));
    if (h.get('place') || h.get('q')) return;  // a shared link is still being opened
    history.replaceState(null, '', `#map=${map.getZoom()}/${c.lat.toFixed(5)}/${c.lng.toFixed(5)}`);
  });

  // --- the outlook panel ---------------------------------------------------
  const copy = $('#copy');
  if (copy) copy.addEventListener('click', () => {
    const t = $('#smstext').textContent;
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(
      () => { copy.textContent = 'Copied'; setTimeout(() => copy.textContent = 'Copy', 1500); },
      () => { const r = document.createRange(); r.selectNodeContents($('#smstext'));
              const s = getSelection(); s.removeAllRanges(); s.addRange(r); });
  });
  const fold = $('#fold');
  if (panel && fold) {
    if (narrow() && !LE.alert) panel.classList.add('folded');
    const syncFold = () => { fold.textContent = panel.classList.contains('folded') ? 'Details' : 'Less'; sizes(); };
    fold.addEventListener('click', () => { panel.classList.toggle('folded'); syncFold(); });
    syncFold();
  }
  if (LE.issued_at) {
    const hours = (Date.now() - Date.parse(LE.issued_at)) / 36e5;
    if (hours > 15) {
      const s = $('#stale');
      s.hidden = false;
      s.textContent = `This outlook is ${Math.round(hours)} hours old; the next one is late.`;
    }
  }
  window.LEmap = map;  // for debugging and automated checks
  window.LEsearch = index;
  addEventListener('resize', () => { sizes(); map.invalidateSize(); });
  sizes(); setTimeout(() => { sizes(); map.invalidateSize(); }, 200);
})();
