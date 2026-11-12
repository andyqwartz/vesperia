// map.js — carte MapLibre + colonnes deck.gl (direction artistique NÉGATIF, §2.8).
const STOPS = [[55, [0x16, 0x24, 0x4a], 0.35], [70, [0x2f, 0x6b, 0xff], 0.70], [85, [0x7f, 0xe3, 0xff], 0.90], [100, [255, 255, 255], 1.0]];

export function coldColor(f, eligible) {
  if (f < 55) return [0, 0, 0, 0];
  let lo = STOPS[0];
  let hi = STOPS[1];
  for (let i = 0; i < STOPS.length - 1; i++) {
    if (f <= STOPS[i + 1][0]) { lo = STOPS[i]; hi = STOPS[i + 1]; break; }
  }
  const t = (Math.min(f, 100) - lo[0]) / (hi[0] - lo[0]);
  const mix = (a, b) => Math.round(a + (b - a) * t);
  const alpha = lo[2] + (hi[2] - lo[2]) * t;
  return [mix(lo[1][0], hi[1][0]), mix(lo[1][1], hi[1][1]), mix(lo[1][2], hi[1][2]), Math.round(255 * alpha * (eligible ? 1 : 0.25))];
}

export const coldHeight = (f, eligible) => (eligible && f >= 55 ? ((f / 100) ** 3) * 600 : 0);

export function createMap({ style, cells, reduced }) {
  const map = new maplibregl.Map({
    container: 'map', style, center: [2.3433, 48.8566], zoom: 11.6, pitch: 52, bearing: -18,
    maxBounds: [[2.10, 48.74], [2.58, 48.97]], attributionControl: { compact: true },
  });
  const overlay = new deck.MapboxOverlay({ interleaved: false, layers: [] });
  map.addControl(overlay);
  const rows = cells.poly.map((poly, i) => ({ poly, rgba: [0, 0, 0, 0], elev: 0, i }));
  let stamp = 0;
  let marks = [];
  const loaded = new Promise((res) => { map.once('load', res); setTimeout(res, 8000); });

  function draw() {
    stamp += 1;
    const layers = [new deck.PolygonLayer({
      id: 'cold', data: rows, getPolygon: (d) => d.poly, getFillColor: (d) => d.rgba, getElevation: (d) => d.elev,
      extruded: true, stroked: false, pickable: false, material: false,
      updateTriggers: { getFillColor: [stamp], getElevation: [stamp] },
      transitions: reduced ? {} : { getFillColor: 300, getElevation: 300 },
    })];
    if (marks.length) {
      layers.push(new deck.ScatterplotLayer({
        id: 'events', data: marks, getPosition: (d) => [d.lon, d.lat], getRadius: 300, radiusUnits: 'meters',
        stroked: true, filled: false, getLineColor: [95, 243, 255, 200], lineWidthMinPixels: 1, pickable: false,
      }));
    }
    overlay.setProps({ layers });
  }

  return {
    map, loaded,
    update(frame, events = []) {
      marks = events;
      for (const r of rows) {
        const ok = frame.ok[r.i] === 1;
        r.rgba = coldColor(frame.cold[r.i], ok);
        r.elev = coldHeight(frame.cold[r.i], ok);
      }
      draw();
    },
    fly(lat, lon) { map.flyTo({ center: [lon, lat], zoom: 15.2, speed: reduced ? 100 : 1.2 }); },
  };
}