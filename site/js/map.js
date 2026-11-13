// map.js — champ lumineux : chaque cellule froide est une lumière additive, relative à l'heure affichée.
import { applyTheme } from './basemap.js';

// nuit : les vides s'allument (lumière additive) ; jour : ils se creusent à l'encre (mélange normal)
const RAMPS = {
  dark: [[55, [22, 30, 90]], [70, [47, 107, 255]], [85, [127, 227, 255]], [100, [255, 255, 255]]],
  light: [[55, [150, 172, 215]], [70, [70, 110, 225]], [85, [25, 55, 175]], [100, [8, 18, 80]]],
};
let RAMP = RAMPS.dark;
const NORMAL = { depthCompare: 'always', depthWriteEnabled: false };
const ADD = { blend: true, blendColorOperation: 'add', blendColorSrcFactor: 'src-alpha', blendColorDstFactor: 'one',
  blendAlphaOperation: 'add', blendAlphaSrcFactor: 'one', blendAlphaDstFactor: 'one', depthCompare: 'always', depthWriteEnabled: false };
// id, rayon (m), opacité, seuil d'intensité, rayon max (px)
const LAYERS = [['haze', 560, 0.035, 0.2, 44], ['glow', 260, 0.08, 0.1, 24], ['halo', 120, 0.22, 0.03, 16], ['core', 36, 0.9, 0.3, 5]];

export function coldColor(f) {
  for (let i = 0; i < RAMP.length - 1; i++) {
    const [a, ca] = RAMP[i]; const [b, cb] = RAMP[i + 1];
    if (f <= b) { const t = Math.max(0, (f - a) / (b - a)); return ca.map((x, j) => Math.round(x + (cb[j] - x) * t)); }
  }
  return RAMP[RAMP.length - 1][1];
}

export function createMap({ style, cells, reduced, onHover, theme = 'dark' }) {
  RAMP = RAMPS[theme];
  const map = new maplibregl.Map({
    container: 'map', style, center: [2.3433, 48.8566], zoom: 11.7, pitch: 38, bearing: -14,
    maxBounds: [[2.10, 48.74], [2.58, 48.97]], attributionControl: { compact: true },
  });
  const overlay = new deck.MapboxOverlay({ interleaved: false, layers: [] });
  map.addControl(overlay);
  const rows = cells.h.map((_, k) => ({ k, p: [cells.lon[k], cells.lat[k]], c: [0, 0, 0], v: 0 }));
  const loaded = new Promise((res) => { map.once('load', res); setTimeout(res, 8000); });
  let stamp = 0; let t = 0; let focus = -1; let marks = []; let cur = null;

  function draw() {
    const light = theme === 'light'; const gain = light ? 1.7 : 1;
    const layers = LAYERS.map(([id, r, a0, minV, maxPx], j) => { const a = Math.min(1, a0 * gain); return new deck.ScatterplotLayer({
      radiusScale: reduced ? 1 : 1 + 0.1 * Math.sin(t * 0.0011 + j * 1.7),
      id, data: rows, getPosition: (d) => d.p, radiusUnits: 'meters', radiusMaxPixels: maxPx, parameters: light ? NORMAL : ADD,
      pickable: id === 'halo', onHover: id === 'halo' ? onHover : undefined,
      onClick: id === 'halo' ? (i) => i.object && api.fly(i.object.k) : undefined,
      getRadius: (d) => (d.v < minV ? 0 : r * (0.35 + d.v)),
      getFillColor: (d) => [...d.c, d.v < minV ? 0 : Math.round(255 * a * d.v)],
      updateTriggers: { getRadius: [stamp], getFillColor: [stamp, theme] },
    }); });
    if (focus >= 0) {
      layers.push(new deck.ScatterplotLayer({ id: 'focus', data: [rows[focus]], getPosition: (d) => d.p, getRadius: 260,
        radiusUnits: 'meters', filled: false, stroked: true, getLineColor: light ? [8, 18, 80, 230] : [255, 255, 255, 220], lineWidthMinPixels: 1 }));
    }
    if (marks.length) {
      layers.push(new deck.ScatterplotLayer({ id: 'events', data: marks, getPosition: (d) => [d.lon, d.lat], getRadius: 300,
        radiusUnits: 'meters', stroked: true, filled: false, getLineColor: [201, 164, 106, 200], lineWidthMinPixels: 1 }));
    }
    overlay.setProps({ layers });
  }

  // lent souffle des lumières (uniforme GPU, rien n'est recalculé), ~3 images/s ; coupé si mouvement réduit ou onglet caché
  if (!reduced) {
    let last = 0;
    const loop = (now) => {
      if (now - last > 320 && !document.hidden) { t = now; last = now; draw(); }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  const api = {
    map, loaded,
    update(frame, events = []) {
      marks = events; cur = frame;
      // lumière relative : seul le tiers le plus froid de l'heure brille vraiment
      const lv = [];
      for (let k = 0; k < rows.length; k++) if (frame.ok[k] && frame.cold[k] >= 55) lv.push(frame.cold[k]);
      lv.sort((a, b) => a - b);
      const lo = lv.length ? lv[Math.floor(lv.length * 0.66)] - 4 : 55;
      const hi = lv.length ? lv[lv.length - 1] : 100;
      for (const r of rows) {
        const c = frame.cold[r.k]; const ok = frame.ok[r.k] === 1 && c >= 55;
        const x = ok ? Math.max(0, (c - lo) / (hi - lo || 1)) : 0;
        r.v = ok ? 0.04 + 0.96 * x * x : 0; r.c = coldColor(c);
      }
      stamp += 1; draw();
      return lv.length;
    },
    fly(k) { map.flyTo({ center: rows[k].p, zoom: 14.2, pitch: 55, speed: reduced ? 100 : 0.9 }); },
    focus(k) { focus = k; draw(); },
    setTheme(name) {
      theme = name; RAMP = RAMPS[name];
      if (map.isStyleLoaded()) applyTheme(map, name); else map.once('load', () => applyTheme(map, name));
      if (cur) for (const r of rows) r.c = coldColor(cur.cold[r.k]);
      stamp += 1; draw();
    },
    official(on) {
      for (const l of map.getStyle().layers) if (l.id.startsWith('off-')) map.setLayoutProperty(l.id, 'visibility', on ? 'visible' : 'none');
    },
  };
  return api;
}
