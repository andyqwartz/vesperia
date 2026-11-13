// app.js — assemble le modèle, la contre-carte et l'interface, puis expose window.__VESPERIA__ (contrat §2.7).
import { loadData } from './data.js';
import { createModel } from './state.js';
import { loadStyle } from './basemap.js';
import { createMap } from './map.js';
import { initHud } from './hud.js';

const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
document.documentElement.dataset.motion = reduced ? 'reduced' : 'full';

const data = await loadData();
const model = createModel(data);
model.cells = data.cells;
model.now();
const { style, kind } = await loadStyle();
let hud = null;
const view = createMap({ style, cells: data.cells, reduced, onHover: (i) => hud && hud.hover(i) });
hud = initHud(model, { view, meta: data.meta, cells: data.cells });
const paint = () => hud.render(view.update(model.frame(), model.activeEvents()));
model.subscribe(paint);
paint();
await view.loaded;

const features = [];
const audio = { state: 'off', level: 0 };
window.__VESPERIA__ = {
  ready: true, cells: model.n, features, audio,
  setMode: (x) => model.setMode(x), mode: () => model.state.mode,
  setIndex: (i) => model.setIndex(i), index: () => model.state.index,
  meanCold: () => model.meanCold(), visible: () => model.visible(),
  topCold: (n) => model.topCold(n).map(({ h, cold, conf, iso, arr }) => ({ h, cold, conf, iso, arr })),
  coldOf: (h) => model.coldOf(h),
  setHideIsolated: (b) => model.setHide(b), setWeights: (w) => model.setWeights(w),
  basemap: () => kind, weatherLoaded: () => model.state.weather !== null,
};
