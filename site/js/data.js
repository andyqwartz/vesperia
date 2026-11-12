// data.js — chargement des quatre fichiers de données (chemins relatifs, règle R6).
const SRC = ['road', 'bike', 'rail', 'poi'];

async function getJson(name) {
  const r = await fetch(`data/${name}.json`, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`data/${name}.json : HTTP ${r.status}`);
  return r.json();
}

export async function loadData() {
  const [meta, cells, activity, events] = await Promise.all(['meta', 'cells', 'activity', 'events'].map(getJson));
  const n = cells.h.length;
  const act = {};
  for (const s of activity.sources) {
    const a = new Uint8Array(n * 168);
    activity.data[s].forEach((row, i) => a.set(row, i * 168));
    act[s] = a;
  }
  const cov = {};
  for (const s of SRC) cov[s] = Float32Array.from(cells.cov[s]);
  return { meta, cells, act, cov, events };
}