// state.js — modèle pur, sans DOM : temps, poids, fusion, froid, éligibilité (contrats §2.5 et §2.7).
export const SRC = ['road', 'bike', 'rail', 'poi'];
export const DEFAULT_W = { road: 0.30, bike: 0.15, rail: 0.30, poi: 0.25 };
const DAYS = ['LUN', 'MAR', 'MER', 'JEU', 'VEN', 'SAM', 'DIM'];
const EN_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const HOUR = 3600e3;
const M_PER_DEG = Math.PI / 180 * 6371000;
const FMT = new Intl.DateTimeFormat('en-US', { timeZone: 'Europe/Paris', weekday: 'long', hour: 'numeric', hourCycle: 'h23' });
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));

export function parisWeekHour(ms) {
  const p = {};
  for (const x of FMT.formatToParts(new Date(ms))) p[x.type] = x.value;
  return EN_DAYS.indexOf(p.weekday) * 24 + (Number(p.hour) % 24);
}

export function clockLabel(wh) {
  return `${DAYS[Math.floor(wh / 24)]} ${String(wh % 24).padStart(2, '0')}:00`;
}

export function createModel(data) {
  const { cells, act, cov, events } = data;
  const n = cells.h.length;
  const ix = new Map(cells.h.map((h, i) => [h, i]));
  const m = { mode: 'typical', index: 0, hide: true, w: { ...DEFAULT_W }, t0: Date.now(), fx: { weather: false, events: false }, weather: null, ver: 0, rv: 0 };
  const subs = [];
  let memo = null;
  let rmemo = null;

  const nowWh = () => parisWeekHour(m.t0);
  const whAt = (i) => (m.mode === 'typical' ? i : (nowWh() + i) % 168);
  const timeAt = (i) => Math.floor(m.t0 / HOUR) * HOUR + i * HOUR;
  const touch = (structural = true) => { m.ver += 1; if (structural) m.rv += 1; memo = null; subs.forEach((f) => f()); };

  function fuse(k, wh) {
    let a = 0; let wc = 0; let ws = 0;
    for (const s of SRC) {
      const w = m.w[s]; const c = w * cov[s][k];
      a += c * act[s][k * 168 + wh]; wc += c; ws += w;
    }
    return { A: wc > 0 ? a / wc : 50, conf: ws > 0 ? wc / ws : 0 };
  }

  function weatherAt(i) {
    const w = m.weather;
    if (m.mode !== 'real' || !m.fx.weather || !w) return [0, 0];
    const k = Math.round((timeAt(i) - w.start) / HOUR);
    if (k < 0 || k >= w.temp.length) return [0, 0];
    return [clamp(w.precip[k] / 2, 0, 1), clamp((8 - w.temp[k]) / 10, 0, 1)];
  }

  function activeEvents(i) {
    if (m.mode !== 'real' || !m.fx.events) return [];
    const t = timeAt(i);
    return events.filter((e) => Date.parse(e.s) <= t && t < Date.parse(e.e));
  }

  function near(k, e) {
    const dx = (e.lon - cells.lon[k]) * M_PER_DEG * Math.cos(((e.lat + cells.lat[k]) / 2) * Math.PI / 180);
    const dy = (e.lat - cells.lat[k]) * M_PER_DEG;
    return Math.hypot(dx, dy) <= 300;
  }

  function cell(k, wh, r, c, evs) {
    const f = fuse(k, wh);
    let A = f.A;
    if (r > 0 || c > 0) A *= 1 - cells.outdoor[k] * (0.35 * r + 0.2 * c);
    for (const e of evs) if (near(k, e)) A = Math.min(100, A + 35);
    return { cold: 100 - A, conf: f.conf, ok: f.conf >= 0.4 - 1e-6 && !(m.hide && cells.isolated[k]) };
  }

  function frame(i = m.index) {
    if (i === m.index && memo && memo.ver === m.ver) return memo.f;
    const wh = whAt(i); const [r, c] = weatherAt(i); const evs = activeEvents(i);
    const cold = new Float64Array(n); const conf = new Float64Array(n); const ok = new Uint8Array(n);
    for (let k = 0; k < n; k++) {
      const x = cell(k, wh, r, c, evs);
      cold[k] = x.cold; conf[k] = x.conf; ok[k] = x.ok ? 1 : 0;
    }
    const f = { cold, conf, ok };
    if (i === m.index) memo = { ver: m.ver, f };
    return f;
  }

  const mean = (f) => {
    let s = 0; let c = 0;
    for (let k = 0; k < n; k++) if (f.ok[k]) { s += f.cold[k]; c += 1; }
    return c ? s / c : 0;
  };

  return {
    n, ix, state: m,
    subscribe: (f) => subs.push(f),
    wh: () => whAt(m.index),
    clock: () => clockLabel(whAt(m.index)),
    setIndex(i) { m.index = ((Math.round(i) % 168) + 168) % 168; touch(false); },
    setMode(mode) { m.mode = mode === 'real' ? 'real' : 'typical'; this.now(); },
    now() { m.t0 = Date.now(); m.index = m.mode === 'typical' ? parisWeekHour(m.t0) : 0; touch(); },
    setHide(b) { m.hide = !!b; touch(); },
    setWeights(w) { for (const s of SRC) if (w[s] !== undefined) m.w[s] = clamp(Number(w[s]), 0, 1); touch(); },
    setFeatures(fx) { Object.assign(m.fx, fx); touch(); },
    setWeather(w) { m.weather = w; touch(); },
    frame,
    activeEvents: () => activeEvents(m.index),
    weatherNow() {
      const w = m.weather;
      if (m.mode !== 'real' || !m.fx.weather || !w) return null;
      const k = Math.round((timeAt(m.index) - w.start) / HOUR);
      return k >= 0 && k < w.temp.length ? { temp: w.temp[k], precip: w.precip[k] } : null;
    },
    meanCold: () => mean(frame()),
    visible() { const f = frame(); let c = 0; for (let k = 0; k < n; k++) if (f.ok[k] && f.cold[k] >= 55) c += 1; return c; },
    topCold(count) {
      const f = frame(); const out = [];
      for (let k = 0; k < n; k++) if (f.ok[k]) out.push({ h: cells.h[k], cold: f.cold[k], conf: f.conf[k], iso: cells.isolated[k], arr: cells.arr[k], k });
      return out.sort((a, b) => b.cold - a.cold).slice(0, count);
    },
    coldOf(h) {
      const k = ix.get(h);
      if (k === undefined) return null;
      const [r, c] = weatherAt(m.index);
      return cell(k, whAt(m.index), r, c, activeEvents(m.index)).cold;
    },
    ribbon() {
      if (rmemo && rmemo.rv === m.rv) return rmemo.v;
      const v = [];
      for (let i = 0; i < 168; i++) v.push(mean(frame(i)));
      rmemo = { rv: m.rv, v };
      return v;
    },
  };
}