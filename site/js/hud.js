// hud.js — interface : horloge, ruban, classement, réglages, boutons, clavier, panneau des sources.
import { SRC } from './state.js';

const $ = (id) => document.getElementById(id);
const LABEL = { road: 'VOIRIE', bike: 'VÉLO', rail: 'MÉTRO', poi: 'COMMERCES' };
const ordinal = (a) => (a === 0 ? 'Paris' : `Paris ${a}${a === 1 ? 'er' : 'e'}`);

export function initHud(model, { fly, meta }) {
  const m = model.state;
  let timer = null;
  const play = () => {
    const on = timer === null;
    clearInterval(timer);
    timer = on ? setInterval(() => model.setIndex(m.index + 1), 350) : null;
    $('btn-play').setAttribute('aria-pressed', String(on));
    $('btn-play').textContent = on ? 'PAUSE' : 'LECTURE';
  };

  $('ribbon').innerHTML = Array.from({ length: 168 }, (_, i) => `<div data-i="${i}"><i></i></div>`).join('');
  $('days').innerHTML = ['L', 'M', 'M', 'J', 'V', 'S', 'D'].map((d) => `<span>${d}</span>`).join('');
  $('weights').innerHTML = SRC.map((s) => `<label><span>${LABEL[s]}</span><output></output><input type="range" min="0" max="100" data-src="${s}"></label>`).join('');
  $('sources').innerHTML = `<h2>SOURCES</h2>${meta.attribution.map((a) => `<p>${a}</p>`).join('')}`
    + '<p>L\'indice est un a priori statistique construit à partir de données ouvertes agrégées ; il ne voit aucune personne.</p>'
    + `<p>Données générées le ${meta.generated_at.slice(0, 10)}${meta.mode === 'fixture' ? ' (jeu synthétique de démonstration)' : ''}.</p>`;
  $('demo').hidden = meta.mode !== 'fixture';

  const atX = (e) => {
    const r = $('ribbon').getBoundingClientRect();
    return Math.min(167, Math.max(0, Math.floor(((e.clientX - r.left) / r.width) * 168)));
  };
  let drag = false;
  $('ribbon').addEventListener('pointerdown', (e) => { drag = true; $('ribbon').setPointerCapture(e.pointerId); model.setIndex(atX(e)); });
  $('ribbon').addEventListener('pointermove', (e) => { if (drag) model.setIndex(atX(e)); });
  $('ribbon').addEventListener('pointerup', () => { drag = false; });
  $('weights').addEventListener('input', (e) => model.setWeights({ [e.target.dataset.src]: Number(e.target.value) / 100 }));
  $('toggle-isolated').addEventListener('change', (e) => model.setHide(e.target.checked));
  $('btn-mode').addEventListener('click', () => model.setMode(m.mode === 'typical' ? 'real' : 'typical'));
  $('btn-now').addEventListener('click', () => model.now());
  $('btn-play').addEventListener('click', play);
  $('sources-link').addEventListener('click', (e) => { e.preventDefault(); $('sources').hidden = !$('sources').hidden; });
  $('top').addEventListener('click', (e) => {
    const li = e.target.closest('li');
    if (li) fly(Number(li.dataset.lat), Number(li.dataset.lon));
  });
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    const d = { ArrowRight: 1, ArrowLeft: -1, ArrowUp: 24, ArrowDown: -24 }[e.key];
    if (d) { e.preventDefault(); model.setIndex(m.index + d); return; }
    if (e.key === ' ' && (e.target === document.body || e.target.id === 'ribbon')) { e.preventDefault(); play(); }
  });
  return { play };
}

export function renderHud(model) {
  const m = model.state;
  $('clock').textContent = model.clock();
  $('btn-mode').textContent = m.mode === 'typical' ? 'TYPIQUE' : 'RÉEL';
  $('toggle-isolated').checked = m.hide;
  document.querySelectorAll('#weights input').forEach((el) => {
    el.value = Math.round(m.w[el.dataset.src] * 100);
    el.previousElementSibling.textContent = el.value;
  });
  const top = model.topCold(10);
  $('top').innerHTML = top.map((r, i) => {
    const lat = model.cells.lat[r.k]; const lon = model.cells.lon[r.k];
    return `<li data-lat="${lat}" data-lon="${lon}"><span>${String(i + 1).padStart(2, '0')}</span><span>${ordinal(r.arr)}</span>`
      + `<span>${Math.round(r.cold)}</span><span class="cf"><i style="width:${Math.round(r.conf * 100)}%"></i></span></li>`;
  }).join('');
  const fx = $('fx');
  if (m.mode === 'real' && (m.fx.weather || m.fx.events)) {
    const parts = [];
    if (m.fx.weather) {
      const w = model.weatherNow();
      parts.push(w ? `PLUIE ${w.precip.toFixed(1)} MM · ${Math.round(w.temp)} °C` : 'MÉTÉO INDISPONIBLE');
    }
    if (m.fx.events) {
      const n = model.activeEvents().length;
      parts.push(n === 0 ? 'AUCUN ÉVÉNEMENT ACTIF' : `${n} ÉVÉNEMENT${n > 1 ? 'S' : ''} ACTIF${n > 1 ? 'S' : ''}`);
    }
    fx.textContent = parts.join(' · ');
    fx.hidden = false;
  } else {
    fx.hidden = true;
  }
  const rb = model.ribbon();
  document.querySelectorAll('#ribbon [data-i]').forEach((el) => {
    const i = Number(el.dataset.i);
    el.classList.toggle('cur', i === m.index);
    el.firstElementChild.style.setProperty('--h', `${Math.max(3, rb[i])}%`);
  });
}