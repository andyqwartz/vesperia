// hud.js — heure en toutes lettres, semaine-spectrogramme, fenêtres de silence, dérive, réglages, fondement.
import { SRC } from './state.js';

const $ = (id) => document.getElementById(id);
const LABEL = { road: 'voirie', bike: 'vélo', rail: 'métro', poi: 'commerces' };
const DAYS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'];
const HOURS = ['minuit', 'une heure', 'deux heures', 'trois heures', 'quatre heures', 'cinq heures', 'six heures', 'sept heures',
  'huit heures', 'neuf heures', 'dix heures', 'onze heures', 'midi', 'treize heures', 'quatorze heures', 'quinze heures',
  'seize heures', 'dix-sept heures', 'dix-huit heures', 'dix-neuf heures', 'vingt heures', 'vingt et une heures',
  'vingt-deux heures', 'vingt-trois heures'];
const SILENCE = 70; // seuil de froid d'une heure « silencieuse »
const HORIZON = 24;
const place = (a) => (a === 0 ? 'paris' : `paris ${a}${a === 1 ? 'er' : 'e'}`);
const coord = (cells, k) => `${cells.lat[k].toFixed(4)} N · ${cells.lon[k].toFixed(4)} E`;

// fenêtres de silence : parmi les cellules froides maintenant, combien d'heures le silence tient-il ?
export function silenceWindows(model, count) {
  const cand = model.topCold(60);
  if (!cand.length) return [];
  const i0 = model.state.index; const run = new Map(cand.map((r) => [r.k, 0])); const alive = new Set(run.keys());
  for (let d = 0; d < HORIZON && alive.size; d++) {
    const f = model.frame((i0 + d) % 168);
    for (const k of [...alive]) if (f.ok[k] && f.cold[k] >= SILENCE) run.set(k, run.get(k) + 1); else alive.delete(k);
  }
  return cand.map((r) => ({ ...r, hours: run.get(r.k) }))
    .sort((a, b) => b.hours - a.hours || b.cold - a.cold).slice(0, count);
}

export function initHud(model, { view, meta, cells }) {
  const m = model.state;
  let timer = null; let windows = [];
  const until = (h) => `${String((model.wh() + h) % 24).padStart(2, '0')}:00`;
  const span = (h) => (h >= HORIZON ? `${HORIZON} h et plus` : h ? `jusqu'à ${until(h)}` : 'silence fragile');
  const play = () => {
    const on = timer === null;
    clearInterval(timer);
    timer = on ? setInterval(() => model.setIndex(m.index + 1), 350) : null;
    $('btn-play').setAttribute('aria-pressed', String(on));
    $('btn-play').textContent = on ? 'PAUSE' : 'LECTURE';
  };

  $('ribbon').innerHTML = Array.from({ length: 168 }, (_, i) => `<div data-i="${i}"${i % 24 ? '' : ' class="day"'}><i></i></div>`).join('');
  $('days').innerHTML = DAYS.map((d) => `<span>${d}</span>`).join('');
  $('weights').innerHTML = SRC.map((s) => `<label><span>${LABEL[s]}</span><output></output><input type="range" min="0" max="100" data-src="${s}"></label>`).join('');
  $('sources').innerHTML = '<p class="h">fondement</p>'
    + '<p class="lead">Une carte officielle montre ce que l\'autorité juge utile : axes, commerces, monuments. Vesperia montre l\'inverse, les lieux et les heures où la ville se relâche.</p>'
    + '<p>L\'indice est un a priori statistique construit à partir de données ouvertes agrégées ; il ne voit aucune personne, ne suit personne, ne descend pas sous terre.</p>'
    + '<p class="h">sources</p>' + meta.attribution.map((a) => `<p>${a}</p>`).join('')
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
  $('btn-tune').addEventListener('click', () => {
    const p = $('panel-left'); p.classList.toggle('open');
    $('btn-tune').setAttribute('aria-expanded', String(p.classList.contains('open')));
  });
  $('btn-official').addEventListener('click', () => {
    const on = $('btn-official').getAttribute('aria-pressed') !== 'true';
    $('btn-official').setAttribute('aria-pressed', String(on)); view.official(on);
  });
  $('btn-derive').addEventListener('click', () => {
    const d = $('derive'); d.hidden = false;
    const pool = windows.filter((w) => w.hours > 0);
    if (!pool.length) {
      d.innerHTML = '<p class="h">pas de dérive possible</p><p>Aucun silence ne tient à cette heure-ci. Avancez dans la semaine.</p><button type="button" data-close>fermer</button>';
      return;
    }
    const r = pool[Math.floor(Math.random() * pool.length)];
    view.focus(r.k); view.fly(r.k);
    d.innerHTML = `<p class="h">dérive tirée au sort</p><p class="big">${place(r.arr)}</p>
      <p>${coord(cells, r.k)}<br>${r.hours >= HORIZON ? `dès ${until(0)}, silence probable sur ${HORIZON} h et plus` : `de ${until(0)} à ${until(r.hours)}, ${r.hours} h de silence probable`}</p>
      <p class="rule">Ne cherchez pas, soyez prêt à percevoir. Notez les sons, la lumière, les traces. N'observez personne, ne photographiez personne, ne laissez rien. Si le vide est vide, c'est aussi un résultat.</p>
      <button type="button" data-close>fermer</button>`;
  });
  $('derive').addEventListener('click', (e) => { if (e.target.dataset.close !== undefined) { $('derive').hidden = true; view.focus(-1); } });
  $('sources-link').addEventListener('click', (e) => { e.preventDefault(); $('sources').hidden = !$('sources').hidden; });
  $('top').addEventListener('click', (e) => { const li = e.target.closest('li'); if (li) view.fly(Number(li.dataset.k)); });
  $('top').addEventListener('pointerover', (e) => { const li = e.target.closest('li'); view.focus(li ? Number(li.dataset.k) : -1); });
  $('top').addEventListener('pointerleave', () => view.focus(-1));
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    const d = { ArrowRight: 1, ArrowLeft: -1, ArrowUp: 24, ArrowDown: -24 }[e.key];
    if (d) { e.preventDefault(); model.setIndex(m.index + d); return; }
    if (e.key === ' ' && (e.target === document.body || e.target.id === 'ribbon')) { e.preventDefault(); play(); return; }
    const b = { d: 'btn-derive', o: 'btn-official', r: 'btn-tune' }[e.key];
    if (b && !e.metaKey && !e.ctrlKey) $(b).click();
  });

  function render(lit) {
    const wh = model.wh();
    $('clock-words').innerHTML = `${DAYS[Math.floor(wh / 24)]}, <em>${HOURS[wh % 24]}</em>`;
    $('clock').textContent = model.clock();
    $('btn-mode').textContent = m.mode === 'typical' ? 'TYPIQUE' : 'RÉEL';
    $('toggle-isolated').checked = m.hide;
    $('mean').textContent = model.meanCold().toFixed(1);
    $('lit').textContent = lit;
    document.querySelectorAll('#weights input').forEach((el) => {
      el.value = Math.round(m.w[el.dataset.src] * 100);
      el.previousElementSibling.textContent = el.value;
    });
    windows = silenceWindows(model, 10);
    const hmax = Math.max(1, ...windows.map((w) => w.hours));
    $('top').innerHTML = windows.map((r, i) => `<li data-k="${r.k}"><span class="rk">${i + 1}</span>`
      + `<span class="ar">${place(r.arr)}<small>${span(r.hours)} · froid ${Math.round(r.cold)} · ${coord(cells, r.k)}</small></span>`
      + `<span class="f">${r.hours}<sub>h</sub></span><span class="cf" style="width:${Math.round((r.hours / hmax) * 180)}px"></span></li>`).join('');
    const fx = $('fx');
    if (m.mode === 'real' && (m.fx.weather || m.fx.events)) {
      const parts = [];
      if (m.fx.weather) {
        const w = model.weatherNow();
        parts.push(w ? `pluie ${w.precip.toFixed(1)} mm · ${Math.round(w.temp)} °C` : 'météo indisponible');
      }
      if (m.fx.events) {
        const n = model.activeEvents().length;
        parts.push(n === 0 ? 'aucun événement actif' : `${n} événement${n > 1 ? 's' : ''} actif${n > 1 ? 's' : ''}`);
      }
      fx.textContent = parts.join(' · ');
      fx.hidden = false;
    } else {
      fx.hidden = true;
    }
    const rb = model.ribbon(); const lo = Math.min(...rb); const hi = Math.max(...rb);
    document.querySelectorAll('#ribbon [data-i]').forEach((el) => {
      const i = Number(el.dataset.i); const x = (rb[i] - lo) / (hi - lo || 1);
      el.classList.toggle('cur', i === m.index);
      el.firstElementChild.style.setProperty('--h', `${8 + 92 * x}%`);
      el.firstElementChild.style.setProperty('--o', (0.12 + 0.75 * x).toFixed(2));
    });
    document.querySelectorAll('#days span').forEach((s, d) => s.classList.toggle('on', d === Math.floor(wh / 24)));
  }

  function hover(info) {
    const c = $('cursor');
    if (!info.object) { c.hidden = true; return; }
    const k = info.object.k; const f = model.frame();
    c.hidden = false; c.style.left = `${info.x}px`; c.style.top = `${info.y}px`;
    c.innerHTML = `<b>${Math.round(f.cold[k])}</b>${place(cells.arr[k])} · confiance ${f.conf[k].toFixed(2)}`;
  }
  return { play, render, hover };
}
