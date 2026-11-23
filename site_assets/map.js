// Lion Eyes map. Needs Leaflet and `LE` (the latest outlook, written into the page).
// Data: layers/layers.json (bounds, building tiles), layers/*.png|geojson,
// data/zones.geojson, data/flood_places.geojson.
(function () {
  'use strict';
  const bar = document.querySelector('header.bar');
  const panel = document.getElementById('panel');
  const isLight = () => document.documentElement.classList.contains('light-mode');
  function sizes() {
    document.documentElement.style.setProperty('--bar-h', bar.offsetHeight + 'px');
    document.documentElement.style.setProperty('--sheet-h', (innerWidth <= 700 && panel ? panel.offsetHeight : 0) + 'px');
  }

  // --- the map -------------------------------------------------------------
  const map = L.map('map', {zoomControl: false, minZoom: 10, maxBounds: [[7.8, -13.8], [9.0, -12.4]]})
    .setView([8.44, -13.2], 12);
  L.control.zoom({position: 'bottomright'}).addTo(map);
  L.control.scale({position: 'bottomleft', imperial: false}).addTo(map);
  [['relief', 205], ['pop', 212], ['ground', 220], ['buildings', 230], ['water', 240],
   ['zones', 400], ['roads', 420], ['points', 620]].forEach(([name, z]) => {
    const p = map.createPane(name);
    p.style.zIndex = z;
    if (['relief', 'pop', 'ground', 'buildings'].includes(name)) p.style.pointerEvents = 'none';
  });
  // Basemap: OpenStreetMap's standard tiles (no API key); CSS mutes them, or darkens them in dark mode.
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · ' +
      'Overture Maps · Meta HRSL · Copernicus DEM'}).addTo(map);

  const C = {low: '#2a78d6', steep: '#c4531f', neutral: '#969ca4', flood: '#d23b3a',
             high: '#ff5a4f', elev: '#f2b705', ok: '#7CFC00'};
  const levelColour = {HIGH: C.high, ELEVATED: C.elev, LOW: C.ok}[LE.level];
  const onAlert = LE.level !== 'LOW';
  const named = new Set(LE.named);
  const fmt = v => (v === undefined || v === null) ? '?' :
    (Math.round(v / (v >= 1000 ? 100 : 10)) * (v >= 1000 ? 100 : 10)).toLocaleString('en');
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

  // --- "what is here": read the low-ground, steep and population images ----
  let B = null;  // [[south, west], [north, east]] of the raster layers
  function sampler(src) {
    const img = new Image(), canvas = document.createElement('canvas');
    let ctx = null;
    img.onload = () => { canvas.width = img.width; canvas.height = img.height;
      ctx = canvas.getContext('2d', {willReadFrequently: true}); ctx.drawImage(img, 0, 0); };
    img.src = src;
    return ll => {
      if (!ctx || !B) return null;
      const [[s, w], [n, e]] = B;
      const x = Math.floor((ll.lng - w) / (e - w) * canvas.width), y = Math.floor((n - ll.lat) / (n - s) * canvas.height);
      if (x < 0 || y < 0 || x >= canvas.width || y >= canvas.height) return null;
      return ctx.getImageData(x, y, 1, 1).data;
    };
  }
  const lowAt = sampler('layers/lowground.png'), steepAt = sampler('layers/steep.png'), popAt = sampler('layers/population.png');
  let popSteps = [];
  function whatsHere(ll) {
    const low = lowAt(ll), steep = steepAt(ll), pop = popAt(ll);
    let html = '';
    if (low && low[3] > 0) html += '<span class="tag low">Low ground</span> Water gathers here in heavy rain.<br>';
    if (steep && steep[3] > 0) html += '<span class="tag steep">Steep slope</span> Watch for landslides and wall collapses.<br>';
    if (!html) html = '<span class="tag ok">Higher, gentler ground</span> Less exposed to flooding here.<br>';
    if (pop && pop[3] > 0 && popSteps.length) {
      const hex = '#' + [pop[0], pop[1], pop[2]].map(v => v.toString(16).padStart(2, '0')).join('');
      const i = popSteps.findIndex(s => s[1].toLowerCase() === hex);
      if (i >= 0) html += `About ${popSteps[i][0]}${i + 1 < popSteps.length ? '–' + popSteps[i + 1][0] : '+'} people per hectare around here (estimated from buildings).`;
    }
    return html;
  }

  // --- layers -------------------------------------------------------------
  const L_ = {};  // id -> {layer, minZoom, on}
  function setOn(id, on) {
    const d = L_[id]; if (!d) return;
    d.on = on;
    const show = on && (!d.minZoom || map.getZoom() >= d.minZoom);
    if (show && !map.hasLayer(d.layer)) d.layer.addTo(map);
    if (!show && map.hasLayer(d.layer)) map.removeLayer(d.layer);
    const hint = document.querySelector(`[data-zoomhint="${id}"]`);
    if (hint) hint.hidden = !(on && d.minZoom && map.getZoom() < d.minZoom);
  }
  map.on('zoomend', () => Object.keys(L_).forEach(id => setOn(id, L_[id].on)));
  function register(id, layer, minZoom) {
    const box = document.querySelector(`input[data-layer="${id}"]`);
    L_[id] = {layer, minZoom, on: box ? box.checked : true};
    setOn(id, L_[id].on);
  }

  // Warning zones and past flood places.
  const search = [];
  function zonePopup(p, ll) {
    return `<h4>${esc(p.name || 'Zone ' + p.zone_id)}</h4>` +
      (onAlert && named.has(p.name) ? `<b style="color:${levelColour}">Named in this outlook: ${esc(LE.word)}</b><br>` : '') +
      `<div style="margin:6px 0">${whatsHere(ll)}</div>` +
      `<b>In this stream catchment</b><br>About ${fmt(p.people)} people · ${fmt(p.people_low_ground)} on low ground · ` +
      `${fmt(p.people_steep)} on steep slopes` + (p.flood_places ? `<br>Flooded before: ${esc(p.flood_places)}` : '');
  }
  fetch('data/zones.geojson').then(r => r.json()).then(gj => {
    const layer = L.geoJSON(gj, {
      pane: 'zones',
      filter: f => f.properties.zone_id > 0,
      style: f => (onAlert && named.has(f.properties.name))
        ? {color: levelColour, weight: 2.5, fillColor: levelColour, fillOpacity: 0.35}
        : {color: '#8a939e', weight: 0.8, opacity: 0.8, fill: true, fillOpacity: 0, dashArray: onAlert ? '3 4' : null},
      onEachFeature: (f, lyr) => {
        lyr.on('click', e => { L.DomEvent.stopPropagation(e); L.popup().setLatLng(e.latlng).setContent(zonePopup(f.properties, e.latlng)).openOn(map); });
        search.push({name: f.properties.name || 'Zone ' + f.properties.zone_id, kind: 'zone', go: () => map.fitBounds(lyr.getBounds(), {maxZoom: 15})});
      }
    });
    register('zones', layer);
  });
  fetch('data/flood_places.geojson').then(r => r.json()).then(gj => {
    const layer = L.geoJSON(gj, {
      pointToLayer: (f, ll) => L.circleMarker(ll, {pane: 'points', radius: 4 + 2 * f.properties.events, color: '#fff', weight: 1.5,
        fillColor: C.flood, fillOpacity: 0.9}),
      onEachFeature: (f, lyr) => {
        const p = f.properties;
        lyr.bindPopup(`<h4>${esc(p.place)}</h4><span class="tag flood">${p.events} reported flood${p.events > 1 ? 's' : ''}</span><br>` + p.dates.map(esc).join('<br>'));
        search.push({name: p.place, kind: 'past flood', go: () => { map.setView(lyr.getLatLng(), 15); lyr.openPopup(); }});
      }
    });
    register('floods', layer);
  });

  fetch('layers/layers.json').then(r => r.json()).then(meta => {
    B = meta.bounds; popSteps = meta.population_steps;
    const img = (file, pane, opacity) => L.imageOverlay('layers/' + file, B, {pane, opacity, interactive: false});
    register('relief', img('hillshade.png', 'relief', 0.9));
    register('pop', img('population.png', 'pop', 0.75));
    register('low', img('lowground.png', 'ground', 1));
    register('steep', img('steep.png', 'ground', 1));
    // Buildings: only the tiles that exist are requested.
    const have = new Set(meta.building_tiles);
    const EMPTY = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    const Tiles = L.TileLayer.extend({getTileUrl: c => {
      const k = `${c.z}/${c.x}/${c.y}`;
      return have.has(k) ? `layers/buildings/${k}.png` : EMPTY;
    }});
    register('buildings', new Tiles('', {pane: 'buildings', minZoom: 13, minNativeZoom: 13, maxNativeZoom: 16, maxZoom: 19,
      bounds: B, opacity: 0.95}), 13);
  });

  fetch('layers/streams.geojson').then(r => r.json()).then(gj => {
    register('streams', L.geoJSON(gj, {pane: 'water', interactive: false,
      style: f => ({color: isLight() ? '#0b6fb8' : '#4cb4ff', opacity: 0.85,
                    weight: f.properties.km2 >= 20 ? 3.2 : f.properties.km2 >= 5 ? 2.2 : 1.3})}));
  });

  const roadColour = () => isLight() ? '#3f4651' : '#aab1ba';
  let roadsLayer = null;
  fetch('layers/roads.geojson').then(r => r.json()).then(gj => {
    const w = {motorway: 3.4, trunk: 3.4, primary: 2.8, secondary: 2.2, tertiary: 1.7};
    roadsLayer = L.geoJSON(gj, {
      pane: 'roads',
      style: f => f.properties.kind === 'low_road'
        ? {color: C.low, weight: (w[f.properties.class] || 2) + 2.5, opacity: 0.95}
        : {color: roadColour(), weight: (w[f.properties.class] || 2) - 0.6, opacity: isLight() ? 0.7 : 0.5},
      onEachFeature: (f, lyr) => {
        const p = f.properties;
        lyr.bindPopup(p.kind === 'low_road'
          ? `<h4>${esc(p.name || 'Main road')}</h4><span class="tag low">May flood</span> This stretch runs over low ground.`
          : `<h4>${esc(p.name || 'Main road')}</h4>${esc(p['class'])} road`);
      }
    });
    register('roads', roadsLayer);
  });
  document.addEventListener('themechange', () => {
    if (roadsLayer) roadsLayer.setStyle(f => f.properties.kind === 'low_road' ? {} : {color: roadColour()});
    if (L_.streams) L_.streams.layer.setStyle({color: isLight() ? '#0b6fb8' : '#4cb4ff'});
  });

  const groupLetter = {health: '+', school: 'S', emergency: 'P', worship: 'W'};
  const groupName = {health: 'Health', school: 'School', emergency: 'Police', worship: 'Place of worship'};
  fetch('layers/facilities.geojson').then(r => r.json()).then(gj => {
    const layer = L.geoJSON(gj, {
      pointToLayer: (f, ll) => {
        const p = f.properties, ring = p.low ? C.low : p.steep ? C.steep : '#fff';
        const m = L.marker(ll, {pane: 'points', icon: L.divIcon({className: '', iconSize: [16, 16],
          html: `<div style="width:16px;height:16px;border-radius:50%;background:#1f2937;color:#fff;border:2px solid ${ring};` +
                `font:600 9px/12px Inter,sans-serif;text-align:center">${groupLetter[p.group]}</div>`})});
        m.group = p.group;
        return m;
      },
      onEachFeature: (f, lyr) => {
        const p = f.properties;
        lyr.bindPopup(`<h4>${esc(p.name || groupName[p.group])}</h4>${groupName[p.group]}<br>` +
          (p.low ? '<span class="tag low">On low ground</span> May be cut off or flooded.' :
           p.steep ? '<span class="tag steep">On a steep slope</span>' : '<span class="tag ok">Not on low ground</span>'));
        if (p.name) search.push({name: p.name, kind: groupName[p.group].toLowerCase(), go: () => { map.setView(lyr.getLatLng(), 17); lyr.openPopup(); }});
      }
    });
    register('facilities', layer, 14);
    // Places of worship are many; show them only close in.
    const thin = () => layer.eachLayer(m => m.setOpacity(m.group === 'worship' && map.getZoom() < 17 ? 0 : 1));
    map.on('zoomend', thin); thin();
  });

  // Click anywhere (outside a zone) for what is there.
  map.on('click', e => L.popup().setLatLng(e.latlng).setContent(`<h4>This spot</h4>${whatsHere(e.latlng)}`).openOn(map));
  const hint = document.getElementById('hint');
  map.once('click', () => { if (hint) hint.hidden = true; });

  // Layer checkboxes.
  document.querySelectorAll('input[data-layer]').forEach(box =>
    box.addEventListener('change', () => setOn(box.dataset.layer, box.checked)));
  const lp = document.getElementById('layers'), lb = document.getElementById('layersBtn');
  if (lb) lb.addEventListener('click', () => { lp.classList.toggle('open'); lb.textContent = lp.classList.contains('open') ? 'Close' : 'Layers'; });

  // Search: zones, past flood places, facilities.
  const input = document.getElementById('q'), list = document.getElementById('results');
  const norm = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  let hits = [], cur = -1;
  function show() {
    list.innerHTML = hits.map((h, i) => `<li data-i="${i}" class="${i === cur ? 'on' : ''}">${esc(h.name)}<small>${esc(h.kind)}</small></li>`).join('');
    list.hidden = !hits.length;
  }
  function pick(i) { const h = hits[i]; if (!h) return; h.go(); hits = []; show(); input.value = h.name;
    if (innerWidth <= 900) { lp.classList.remove('open'); if (lb) lb.textContent = 'Layers'; } }
  input.addEventListener('input', () => {
    const q = norm(input.value.trim());
    hits = q.length < 2 ? [] : search.filter(s => norm(s.name).includes(q))
      .sort((a, b) => norm(a.name).indexOf(q) - norm(b.name).indexOf(q)).slice(0, 8);
    cur = hits.length ? 0 : -1; show();
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown') { cur = Math.min(cur + 1, hits.length - 1); show(); e.preventDefault(); }
    if (e.key === 'ArrowUp') { cur = Math.max(cur - 1, 0); show(); e.preventDefault(); }
    if (e.key === 'Enter') { pick(cur); e.preventDefault(); }
    if (e.key === 'Escape') { hits = []; show(); }
  });
  list.addEventListener('click', e => { const li = e.target.closest('li'); if (li) pick(+li.dataset.i); });

  // My location.
  const Locate = L.Control.extend({options: {position: 'bottomright'}, onAdd: () => {
    const d = L.DomUtil.create('div', 'leaflet-bar locate'), a = L.DomUtil.create('a', '', d);
    a.href = '#'; a.title = 'Show my location'; a.setAttribute('role', 'button'); a.setAttribute('aria-label', 'Show my location');
    a.innerHTML = '&#9678;';
    L.DomEvent.on(a, 'click', e => { L.DomEvent.preventDefault(e); L.DomEvent.stopPropagation(e); map.locate({setView: true, maxZoom: 16}); });
    return d;
  }});
  map.addControl(new Locate());
  let me = null;
  map.on('locationfound', e => {
    if (me) map.removeLayer(me);
    me = L.layerGroup([L.circle(e.latlng, {radius: e.accuracy, color: C.low, weight: 1, fillOpacity: 0.08}),
                       L.circleMarker(e.latlng, {radius: 7, color: '#fff', weight: 2, fillColor: C.low, fillOpacity: 1})]).addTo(map);
    L.popup().setLatLng(e.latlng).setContent(`<h4>You are here</h4>${whatsHere(e.latlng)}`).openOn(map);
  });
  map.on('locationerror', () => L.popup().setLatLng(map.getCenter()).setContent('Your location is not available.').openOn(map));

  // --- the outlook panel ---------------------------------------------------
  const copy = document.getElementById('copy');
  if (copy) copy.addEventListener('click', () => {
    const t = document.getElementById('smstext').textContent;
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(
      () => { copy.textContent = 'Copied'; setTimeout(() => copy.textContent = 'Copy', 1500); },
      () => { const r = document.createRange(); r.selectNodeContents(document.getElementById('smstext'));
              const s = getSelection(); s.removeAllRanges(); s.addRange(r); });
  });
  const fold = document.getElementById('fold');
  if (panel && fold) {
    if (innerWidth <= 700 && !LE.alert) panel.classList.add('folded');
    const syncFold = () => { fold.textContent = panel.classList.contains('folded') ? 'Details' : 'Less'; sizes(); };
    fold.addEventListener('click', () => { panel.classList.toggle('folded'); syncFold(); });
    syncFold();
  }
  if (LE.issued_at) {
    const hours = (Date.now() - Date.parse(LE.issued_at)) / 36e5;
    if (hours > 15) {
      const s = document.getElementById('stale');
      s.hidden = false;
      s.textContent = `This outlook is ${Math.round(hours)} hours old; the next one is late.`;
    }
  }
  window.LEmap = map;  // for debugging and automated checks
  addEventListener('resize', sizes); sizes(); setTimeout(() => { sizes(); map.invalidateSize(); }, 200);
})();
