// basemap.js — contre-carte : seule l'eau reste ; la carte officielle (axes, repères) est gardée cachée, révélable.
const STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty';
const BG = '#020306';
const OFFICIAL = '#c9a46a';
const bg = { id: 'background', type: 'background', paint: { 'background-color': BG } };

function fallbackStyle() {
  return { version: 8, sources: {}, layers: [bg] };
}

function counterMap(style) {
  const water = style.layers.filter((l) => l.id === 'water' || l.id === 'waterway_river').map((l) => (l.type === 'fill'
    ? { ...l, paint: { 'fill-color': '#0a1424' } }
    : { ...l, paint: { 'line-color': '#0f1a2e', 'line-width': 0.6 } }));
  const roads = style.layers
    .filter((l) => l.type === 'line' && /^(road|bridge)_(motorway|trunk|secondary|minor)/.test(l.id) && !/casing/.test(l.id))
    .map((l) => ({ ...l, id: `off-${l.id}`, layout: { ...l.layout, visibility: 'none' },
      paint: { 'line-color': OFFICIAL, 'line-opacity': 0.22, 'line-width': 0.7 } }));
  const labels = style.layers
    .filter((l) => /^(poi_r1|poi_r7|poi_transit|label_city|highway-name-major)$/.test(l.id))
    .map((l) => ({ ...l, id: `off-${l.id}`,
      layout: { ...l.layout, visibility: 'none', 'icon-image': '', 'text-font': ['Noto Sans Regular'], 'text-size': 10,
        'text-transform': 'uppercase', 'text-letter-spacing': 0.2 },
      paint: { 'text-color': OFFICIAL, 'text-opacity': 0.55, 'text-halo-width': 0 } }));
  style.layers = [bg, ...water, ...roads, ...labels];
  return style;
}

export async function loadStyle() {
  try {
    const r = await fetch(STYLE_URL);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return { style: counterMap(await r.json()), kind: 'styled' };
  } catch (e) {
    return { style: fallbackStyle(), kind: 'fallback' };
  }
}
