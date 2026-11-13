// app.js — assemble le modèle, la contre-carte, l'interface et les fonctions vivantes (météo, événements, écoute) ;
// expose window.__VESPERIA__ (contrat §2.7). Logique de la Phase 7 du brief, branchée sur l'interface contre-carte.
import { loadData } from './data.js';
import { createModel } from './state.js';
import { loadStyle } from './basemap.js';
import { createMap } from './map.js';
import { initHud } from './hud.js';
import { loadWeather } from './weather.js';
import { createAudio } from './audio.js';

const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
document.documentElement.dataset.motion = reduced ? 'reduced' : 'full';

const data = await loadData();
const model = createModel(data);
model.cells = data.cells;
const features = ['weather', 'events', 'listen'];
const audio = { state: 'off', level: 0 };
const sound = createAudio(audio);
model.setFeatures({ weather: true, events: true });
model.now();
const theme = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
const { style, kind } = await loadStyle(theme);
let hud = null;
const view = createMap({ style, cells: data.cells, reduced, theme, onHover: (i) => hud && hud.hover(i) });
hud = initHud(model, { view, meta: data.meta, cells: data.cells });
const paint = () => {
  hud.render(view.update(model.frame(), model.activeEvents()));
  sound.update(model.meanCold() / 100);
};
model.subscribe(paint);
const listen = document.getElementById('listen');
listen.hidden = false;
listen.addEventListener('click', async () => {
  await sound.toggle();
  listen.setAttribute('aria-pressed', String(audio.state === 'on'));
});
loadWeather().then((w) => model.setWeather(w)).catch(() => {});
paint();
await view.loaded;

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
