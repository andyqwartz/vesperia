// basemap.js — style OpenFreeMap « liberty » recoloré en JSON (direction artistique NÉGATIF, §2.8).
const STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty';
const BG = '#05070d';

function fallbackStyle() {
  return { version: 8, sources: {}, layers: [{ id: 'background', type: 'background', paint: { 'background-color': BG } }] };
}

function recolor(style) {
  style.layers = style.layers.map((l) => {
    const id = l.id.toLowerCase();
    const layout = { ...(l.layout || {}) };
    const paint = { ...(l.paint || {}) };
    const hide = () => ({ ...l, layout: { ...layout, visibility: 'none' } });
    if (l.type === 'background') return { ...l, paint: { 'background-color': BG } };
    if (l.type === 'symbol') {
      if (!id.includes('place')) return hide();
      paint['text-color'] = '#5a6478';
      paint['text-halo-width'] = 0;
      return { ...l, layout, paint };
    }
    if (l.type === 'fill' || l.type === 'fill-extrusion') {
      if (/building|boundary/.test(id)) return hide();
      delete paint['fill-pattern'];
      delete paint['fill-outline-color'];
      if (l.type === 'fill-extrusion') return hide();
      paint['fill-color'] = id.includes('water') ? '#02040a' : '#070b14';
      return { ...l, layout, paint };
    }
    if (l.type === 'line') {
      if (/boundary|admin/.test(id)) return hide();
      if (/road|street|bridge|tunnel|rail|highway|motorway|path|transit|ferry|aeroway/.test(id)) {
        delete paint['line-pattern'];
        delete paint['line-gradient'];
        paint['line-color'] = '#1b2438';
        paint['line-opacity'] = 0.8;
        return { ...l, layout, paint };
      }
      return hide();
    }
    return hide();
  });
  return style;
}

export async function loadStyle() {
  try {
    const r = await fetch(STYLE_URL);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return { style: recolor(await r.json()), kind: 'styled' };
  } catch (e) {
    return { style: fallbackStyle(), kind: 'fallback' };
  }
}