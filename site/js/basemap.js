// basemap.js — contre-carte : eau, parcs et trame des rues en sourdine ; la carte officielle (repères, axes dorés) reste cachée, révélable.
const STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty';

export const PALETTE = {
  dark: { bg: '#0a0e18', water: '#152a4c', waterLine: '#22395f', park: '#0f1d18', street: '#2a3757', official: '#d8b57a' },
  light: { bg: '#e8ecf1', water: '#c3d2e4', waterLine: '#a9bcd5', park: '#d9e3d9', street: '#c4cbd6', official: '#9a6b1f' },
};

// peinture d'une couche selon son rôle (préfixe d'identifiant) et le thème
export function paintOf(id, type, theme) {
  const c = PALETTE[theme];
  if (type === 'background') return { 'background-color': c.bg };
  if (id === 'water') return { 'fill-color': c.water };
  if (id === 'park') return { 'fill-color': c.park, 'fill-opacity': 0.8 };
  if (id === 'waterway_river') return { 'line-color': c.waterLine, 'line-width': 0.8 };
  if (id.startsWith('base-')) return { 'line-color': c.street, 'line-opacity': 0.9, 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 0.4, 16, 1.6] };
  if (id.startsWith('off-') && type === 'line') return { 'line-color': c.official, 'line-opacity': 0.45, 'line-width': 0.9 };
  if (id.startsWith('off-')) return { 'text-color': c.official, 'text-opacity': 0.85, 'text-halo-width': 0 };
  return null;
}

function counterMap(style, theme) {
  const keep = (l, id, layout = l.layout || {}) => ({ ...l, id, layout, paint: paintOf(id, l.type, theme) });
  const roads = style.layers.filter((l) => l.type === 'line' && /^(road|bridge)_(motorway|trunk|secondary|minor)/.test(l.id) && !/casing/.test(l.id));
  const layers = [{ id: 'background', type: 'background', paint: paintOf('background', 'background', theme) }];
  for (const l of style.layers) if (l.id === 'park' || l.id === 'water' || l.id === 'waterway_river') layers.push(keep(l, l.id));
  for (const l of roads) layers.push(keep(l, `base-${l.id}`));
  for (const l of roads) layers.push(keep(l, `off-${l.id}`, { ...l.layout, visibility: 'none' }));
  for (const l of style.layers.filter((x) => /^(poi_r1|poi_r7|poi_transit|label_city|highway-name-major)$/.test(x.id))) {
    layers.push(keep(l, `off-${l.id}`, { ...l.layout, visibility: 'none', 'icon-image': '', 'text-font': ['Noto Sans Regular'],
      'text-size': 10, 'text-transform': 'uppercase', 'text-letter-spacing': 0.2 }));
  }
  style.layers = layers;
  return style;
}

export function applyTheme(map, theme) {
  for (const l of map.getStyle().layers) {
    const p = paintOf(l.id, l.type, theme);
    if (p) for (const [k, v] of Object.entries(p)) map.setPaintProperty(l.id, k, v);
  }
}

export async function loadStyle(theme = 'dark') {
  try {
    const r = await fetch(STYLE_URL);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return { style: counterMap(await r.json(), theme), kind: 'styled' };
  } catch (e) {
    return { style: { version: 8, sources: {}, layers: [{ id: 'background', type: 'background', paint: paintOf('background', 'background', theme) }] }, kind: 'fallback' };
  }
}
