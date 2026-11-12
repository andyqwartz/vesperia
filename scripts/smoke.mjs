#!/usr/bin/env node
// Test de fumée Vesperia — FICHIER FOURNI (règle R2) : ne jamais le modifier.
// Usage : node scripts/smoke.mjs --site site --base /vesperia/ [--require weather,events,listen] [--live-basemap] [--timeout 420]
//         node scripts/smoke.mjs --url https://OWNER.github.io/vesperia/ [--require ...]
// Le rendu WebGL logiciel (SwiftShader) est lent : les pages sont ouvertes avec devicePixelRatio 0,5 (4 fois moins de pixels
// à dessiner, mise en page inchangée). Variables : SMOKE_SCALE (défaut 0.5), SMOKE_TIMEOUT_S (défaut 420).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const argv = process.argv.slice(2);
const opt = (n, d) => { const i = argv.indexOf('--' + n); if (i < 0) return d; const v = argv[i + 1]; return v && !v.startsWith('--') ? v : true; };
const SITE = path.resolve(String(opt('site', 'site')));
const URL_ARG = opt('url', null);
const REQUIRE = String(opt('require', '')).split(',').filter(Boolean);
const LIVE = !!opt('live-basemap', false);
const LIMIT_S = Number(opt('timeout', process.env.SMOKE_TIMEOUT_S || 420)) || 420;
const SCALE = Number(process.env.SMOKE_SCALE || 0.5) || 0.5;
const T0 = Date.now();
const secs = (t) => ((Date.now() - t) / 1000).toFixed(1) + 's';
const NOW = new Date('2026-11-10T10:00:00Z'); // mardi 11 h à Paris
const DAYS = ['LUN', 'MAR', 'MER', 'JEU', 'VEN', 'SAM', 'DIM'];
const IDS = ['map', 'clock', 'ribbon', 'top', 'weights', 'toggle-isolated', 'btn-mode', 'btn-now', 'btn-play', 'sources-link', 'sources'];

let pw = null;
for (const load of [() => import('playwright'), async () => createRequire(path.join(process.cwd(), 'x.js'))('playwright'),
  async () => createRequire(path.join(process.env.SMOKE_PLAYWRIGHT_DIR || '/nonexistent', 'x.js'))('playwright')]) {
  try { pw = await load(); break; } catch { /* essai suivant */ }
}
if (!pw) { console.log('[FAIL] playwright introuvable (npm ci)'); console.log('SMOKE: FAIL'); process.exit(1); }
const chromium = pw.chromium || pw.default.chromium;

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.geojson': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2', '.txt': 'text/plain' };
let BASE = '/vesperia/';
let ORIGIN = '';
let server = null;
if (URL_ARG) {
  const u = new URL(String(URL_ARG));
  ORIGIN = u.origin; BASE = u.pathname.endsWith('/') ? u.pathname : u.pathname + '/';
} else {
  BASE = String(opt('base', '/vesperia/'));
  server = http.createServer((req, rsp) => {
    const u = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (!u.startsWith(BASE)) { rsp.writeHead(404); return rsp.end('hors du sous-chemin ' + BASE); }
    let rel = u.slice(BASE.length) || 'index.html';
    if (rel.endsWith('/')) rel += 'index.html';
    const f = path.join(SITE, rel);
    if (!f.startsWith(SITE + path.sep) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { rsp.writeHead(404); return rsp.end('absent'); }
    rsp.writeHead(200, { 'content-type': MIME[path.extname(f)] || 'application/octet-stream', 'cache-control': 'no-store' });
    fs.createReadStream(f).pipe(rsp);
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  ORIGIN = 'http://127.0.0.1:' + server.address().port;
}
const PAGE_URL = ORIGIN + BASE;

const FORECAST = (() => {
  const time = []; const t = []; const p = [];
  for (let i = 0; i < 168; i++) {
    const d = new Date(Date.UTC(2026, 10, 10, i, 0));
    time.push(d.toISOString().slice(0, 13) + ':00'); t.push(2); p.push(3);
  }
  return { latitude: 48.86, longitude: 2.35, timezone: 'Europe/Paris', hourly: { time, temperature_2m: t, precipitation: p } };
})();

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl'] });
let PRELOAD = null;
if (process.env.SMOKE_PRELOAD) PRELOAD = (await import(pathToFileURL(path.resolve(process.env.SMOKE_PRELOAD)).href)).default;

const results = [];
const open = [];
async function openPage(o = {}) {
  const t0 = Date.now();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: SCALE, locale: 'fr-FR', timezoneId: 'Europe/Paris', reducedMotion: o.reduced ? 'reduce' : 'no-preference' });
  open.push(ctx);
  ctx.setDefaultTimeout(15000);
  if (PRELOAD) await PRELOAD(ctx);
  const page = await ctx.newPage();
  page.errs = [];
  page.on('pageerror', (e) => page.errs.push('erreur JS : ' + e.message));
  page.on('response', (r) => { if (r.url().startsWith(ORIGIN) && r.status() >= 400) page.errs.push(`HTTP ${r.status()} ${r.url()}`); });
  await page.clock.setFixedTime(NOW);
  if (!LIVE) await page.route(/tiles\.openfreemap\.org/, (r) => r.abort());
  await page.route(/api\.open-meteo\.com/, (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(FORECAST) }));
  if (o.events !== undefined) await page.route('**/data/events.json', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(o.events) }));
  await page.goto(PAGE_URL, { waitUntil: 'load', timeout: 45000 });
  await page.waitForFunction(() => window.__VESPERIA__ && window.__VESPERIA__.ready === true, null, { timeout: 45000 });
  console.log('       (page ouverte en ' + secs(t0) + ')');
  return page;
}
const api = (page, name, ...args) => page.evaluate(([n, a]) => { const v = window.__VESPERIA__; return typeof v[n] === 'function' ? v[n](...a) : v[n]; }, [name, args]);
const text = (page, sel) => page.locator(sel).first().innerText();
const ok = (c, m) => { if (!c) throw new Error(m); };
let current = 'démarrage';
async function check(name, fn) {
  current = name;
  const t0 = Date.now();
  try { await fn(); results.push(true); console.log('[OK]   ' + name + ' (' + secs(t0) + ')'); }
  catch (e) { results.push(false); console.log('[FAIL] ' + name + ' — ' + String(e.message).split('\n')[0].slice(0, 300) + ' (' + secs(t0) + ')'); }
}
const getJson = async (rel) => (await fetch(PAGE_URL + rel, { cache: 'no-store' })).json();
const metersBetween = (a, b) => { const k = Math.PI / 180 * 6371000; return Math.hypot((a[1] - b[1]) * k * Math.cos((a[0] + b[0]) / 2 * Math.PI / 180), (a[0] - b[0]) * k); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitWeather(p) { for (let i = 0; i < 40 && (await api(p, 'weatherLoaded')) === false; i++) await sleep(250); }
const killer = setTimeout(() => { console.log('[FAIL] délai global de ' + LIMIT_S + ' s dépassé pendant : ' + current); console.log('SMOKE: FAIL'); process.exit(1); }, LIMIT_S * 1000);

let page = null;
let cells = null; let meta = null;
await check('chargement : API prête, aucune erreur JS', async () => {
  cells = await getJson('data/cells.json'); meta = await getJson('data/meta.json');
  page = await openPage();
  ok(page.errs.length === 0, page.errs[0]);
});
if (!page) { console.log('SMOKE: FAIL (la page ne se charge pas)'); await browser.close(); if (server) server.close(); process.exit(1); }

await check('cellules : nombre égal à cells.json, entre 900 et 1200', async () => {
  const n = await api(page, 'cells');
  ok(n === cells.h.length && n >= 900 && n <= 1200, `cells=${n}, cells.json=${cells.h.length}`);
});
await check('identifiants DOM imposés présents', async () => {
  for (const id of IDS) ok(await page.locator('#' + id).count() === 1, `#${id} manquant`);
  ok(await page.locator('#map canvas').count() >= 1, 'aucun canvas dans #map');
});
await check('ruban : 168 barres [data-i]', async () => {
  const n = await page.locator('#ribbon [data-i]').count();
  ok(n === 168, `${n} barres`);
});
await check(LIVE ? 'fond de carte : style OpenFreeMap recoloré' : 'fond de carte : repli sans réseau', async () => {
  const b = await api(page, 'basemap');
  ok(b === (LIVE ? 'styled' : 'fallback'), `basemap()=${b}`);
});
await check('horloge initiale : mode typique, mardi 11 h, format « MAR 11:00 »', async () => {
  ok(await api(page, 'mode') === 'typical', 'mode initial différent de typical');
  ok(await api(page, 'index') === 35, `index initial ${await api(page, 'index')} au lieu de 35`);
  const c = (await text(page, '#clock')).replace(/\s+/g, ' ').trim();
  ok(c === 'MAR 11:00', `horloge « ${c} »`);
});
await check('setIndex met l\'horloge à jour (63 → MER 15:00)', async () => {
  await api(page, 'setIndex', 63);
  ok(await api(page, 'index') === 63, 'index non pris en compte');
  const c = (await text(page, '#clock')).replace(/\s+/g, ' ').trim();
  ok(c === 'MER 15:00', `horloge « ${c} »`);
});
await check('clavier : ← → 1 heure, ↑ ↓ 1 jour, retour à la ligne de la semaine', async () => {
  await api(page, 'setIndex', 63);
  await page.keyboard.press('ArrowRight'); ok(await api(page, 'index') === 64, '→ ne donne pas 64');
  await page.keyboard.press('ArrowLeft'); ok(await api(page, 'index') === 63, '← ne ramène pas à 63');
  await page.keyboard.press('ArrowUp'); ok(await api(page, 'index') === 87, '↑ ne donne pas 87');
  await page.keyboard.press('ArrowDown'); ok(await api(page, 'index') === 63, '↓ ne ramène pas à 63');
  await api(page, 'setIndex', 167); await page.keyboard.press('ArrowRight'); ok(await api(page, 'index') === 0, '→ après 167 doit donner 0');
  await page.keyboard.press('ArrowLeft'); ok(await api(page, 'index') === 167, '← après 0 doit donner 167');
});
await check('souris : un clic sur une barre du ruban fixe l\'index', async () => {
  await page.locator('#ribbon [data-i="100"]').click();
  ok(await api(page, 'index') === 100, `index ${await api(page, 'index')} après clic sur la barre 100`);
});
await check('froid : la nuit (mar 03 h) est plus froide que le jour (mar 11 h)', async () => {
  await api(page, 'setIndex', 35); const d = await api(page, 'meanCold'); const vd = await api(page, 'visible');
  await api(page, 'setIndex', 27); const n = await api(page, 'meanCold'); const vn = await api(page, 'visible');
  ok(Number.isFinite(d) && Number.isFinite(n) && d >= 0 && n <= 100, `meanCold ${d} / ${n}`);
  ok(n > d + 3, `froid de nuit ${n.toFixed(1)} ≤ froid de jour ${d.toFixed(1)} + 3`);
  ok(vn > vd, `cellules visibles : nuit ${vn} ≤ jour ${vd}`);
});
await check('top 10 : trié, confiance ≥ 0,40, aucune cellule isolée, 10 lignes dans #top', async () => {
  await api(page, 'setIndex', 27);
  const t = await api(page, 'topCold', 10);
  ok(t.length === 10, `${t.length} entrées`);
  for (let i = 0; i < t.length; i++) {
    const r = t[i];
    ok(typeof r.h === 'string' && r.cold >= 0 && r.cold <= 100 && r.conf >= 0.4 && r.iso === 0 && Number.isInteger(r.arr) && r.arr >= 0 && r.arr <= 20, `entrée ${i} invalide : ${JSON.stringify(r)}`);
    if (i) ok(t[i - 1].cold >= r.cold, 'tri non décroissant');
  }
  ok(await page.locator('#top li').count() === 10, '#top doit contenir 10 éléments li');
  ok(await api(page, 'coldOf', t[0].h) === t[0].cold, 'coldOf(h) incohérent avec topCold');
  await page.locator('#top li').first().click();
});
await check('interrupteur d\'isolement : actif par défaut, API et case synchronisées', async () => {
  ok(await page.locator('#toggle-isolated').isChecked(), 'la case #toggle-isolated doit être cochée par défaut');
  const before = (await api(page, 'topCold', 5000)).length;
  await page.locator('#toggle-isolated').uncheck();
  const after = (await api(page, 'topCold', 5000)).length;
  ok(after > before, `masquer les isolés : ${before} cellules, sans masque : ${after}`);
  await api(page, 'setHideIsolated', true);
  ok(await page.locator('#toggle-isolated').isChecked(), 'la case ne suit pas setHideIsolated(true)');
  ok((await api(page, 'topCold', 5000)).length === before, 'le filtre ne revient pas à son état initial');
});
await check('poids : 4 curseurs 0-100 synchronisés avec setWeights', async () => {
  const sl = page.locator('#weights input[type=range]');
  ok(await sl.count() === 4, `${await sl.count()} curseurs au lieu de 4`);
  const def = { road: 30, bike: 15, rail: 30, poi: 25 };
  for (const k of Object.keys(def)) ok(Number(await page.locator(`#weights input[data-src=${k}]`).inputValue()) === def[k], `valeur par défaut du curseur ${k}`);
  await api(page, 'setIndex', 27);
  const ref = JSON.stringify(await api(page, 'topCold', 10));
  await api(page, 'setWeights', { road: 0, bike: 0, rail: 0, poi: 1 });
  ok(Number(await page.locator('#weights input[data-src=poi]').inputValue()) === 100, 'le curseur poi doit afficher 100 après setWeights({poi:1})');
  ok(JSON.stringify(await api(page, 'topCold', 10)) !== ref, 'changer les poids ne change pas le classement');
  await api(page, 'setWeights', { road: 0, bike: 0, rail: 0, poi: 0 });
  ok((await api(page, 'topCold', 10)).length === 0 && await api(page, 'meanCold') === 0, 'poids tous nuls : topCold doit être vide et meanCold valoir 0');
  await api(page, 'setWeights', { road: 0.3, bike: 0.15, rail: 0.3, poi: 0.25 });
  ok(JSON.stringify(await api(page, 'topCold', 10)) === ref, 'les poids par défaut ne restituent pas le classement initial');
  await page.locator('#weights input[data-src=road]').evaluate((el) => { el.value = '0'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  ok(JSON.stringify(await api(page, 'topCold', 10)) !== ref, 'déplacer un curseur ne change pas le classement');
  await api(page, 'setWeights', { road: 0.3 });
});
await check('bascule TYPIQUE / RÉEL et bouton MAINTENANT', async () => {
  await page.locator('#btn-now').click();
  ok(await api(page, 'index') === 35, 'MAINTENANT (typique) doit donner 35');
  await page.locator('#btn-mode').click();
  ok(await api(page, 'mode') === 'real', 'la bascule ne passe pas en real');
  ok(/RÉEL/.test(await text(page, '#btn-mode')), 'le bouton doit afficher RÉEL');
  await page.locator('#btn-now').click();
  ok(await api(page, 'index') === 0, 'MAINTENANT (réel) doit donner 0');
  const c = (await text(page, '#clock')).replace(/\s+/g, ' ').trim();
  ok(c === 'MAR 11:00', `horloge en mode réel « ${c} »`);
  await page.locator('#btn-mode').click();
  ok(await api(page, 'mode') === 'typical' && /TYPIQUE/.test(await text(page, '#btn-mode')), 'retour au mode typique');
  await page.locator('#btn-now').click();
  ok(await api(page, 'index') === 35, 'MAINTENANT après retour en typique');
});
await check('lecture : avance d\'une heure environ toutes les 350 ms, pause au second clic', async () => {
  await api(page, 'setIndex', 0);
  await page.locator('#btn-play').click(); await sleep(1700);
  const a = await api(page, 'index'); ok(a >= 2 && a <= 9, `index ${a} après 1,7 s de lecture`);
  await page.locator('#btn-play').click(); const b = await api(page, 'index'); await sleep(900);
  ok(await api(page, 'index') === b, 'la lecture continue après le second clic');
});
await check('liste SOURCES : le panneau affiche tous les crédits de meta.json', async () => {
  await page.locator('#sources-link').click();
  ok(await page.locator('#sources').isVisible(), '#sources invisible après clic sur #sources-link');
  const t = await text(page, '#sources');
  for (const a of meta.attribution) ok(t.includes(a), `crédit absent du panneau : ${a}`);
});
await check('aucune requête en erreur ni erreur JS pendant tout le parcours', async () => {
  ok(page.errs.length === 0, page.errs.slice(0, 2).join(' ; '));
});

await check('mouvement réduit : ni lecture automatique ni transitions', async () => {
  const p = await openPage({ reduced: true });
  ok(await p.evaluate(() => document.documentElement.dataset.motion) === 'reduced', 'html[data-motion] doit valoir reduced');
  const i0 = await api(p, 'index'); await sleep(1200);
  ok(await api(p, 'index') === i0, 'l\'index bouge sans action de l\'utilisateur');
  ok(p.errs.length === 0, p.errs[0]);
});

if (REQUIRE.includes('weather') || REQUIRE.includes('events')) {
  await check('fonctions vivantes déclarées dans __VESPERIA__.features', async () => {
    const f = await api(page, 'features');
    for (const r of REQUIRE) ok(Array.isArray(f) && f.includes(r), `features ne contient pas ${r}`);
  });
}
if (REQUIRE.includes('weather')) {
  await check('météo : en mode réel, pluie et froid refroidissent les cellules de plein air', async () => {
    const p = await openPage({ events: [] });
    await api(p, 'setIndex', 35);
    const hs = (await api(p, 'topCold', 5000)).map((r) => r.h);
    const typ = {}; for (const h of hs) typ[h] = await api(p, 'coldOf', h);
    await api(p, 'setMode', 'real'); await api(p, 'setIndex', 0);
    await waitWeather(p);
    ok(await api(p, 'weatherLoaded') === true, 'la prévision Open-Meteo n\'est jamais chargée');
    let up = 0;
    for (const h of hs) {
      const r = await api(p, 'coldOf', h);
      ok(r >= typ[h] - 0.01, `la météo a réchauffé la cellule ${h} (${typ[h]} → ${r})`);
      if (r > typ[h] + 0.5) up++;
    }
    ok(up >= 5, `seulement ${up} cellules refroidies par la météo (au moins 5 attendues)`);
    ok(p.errs.length === 0, p.errs[0]);
  });
}
if (REQUIRE.includes('events')) {
  await check('événements : un événement actif réchauffe les cellules à 300 m, pas les autres', async () => {
    const probe = await openPage({ events: [] });
    await api(probe, 'setMode', 'real'); await api(probe, 'setIndex', 0);
    await waitWeather(probe);
    const top = (await api(probe, 'topCold', 5000));
    const target = top[0].h; const far = top.find((r) => metersBetween([cells.lat[cells.h.indexOf(r.h)], cells.lon[cells.h.indexOf(r.h)]], [cells.lat[cells.h.indexOf(target)], cells.lon[cells.h.indexOf(target)]]) > 2000).h;
    const before = await api(probe, 'coldOf', target); const farBefore = await api(probe, 'coldOf', far);
    const k = cells.h.indexOf(target);
    const ev = [{ t: 'Événement de test', lat: cells.lat[k], lon: cells.lon[k], s: '2026-11-10T09:00:00Z', e: '2026-11-10T12:00:00Z' }];
    const p = await openPage({ events: ev });
    await api(p, 'setMode', 'real'); await api(p, 'setIndex', 0);
    await waitWeather(p);
    const after = await api(p, 'coldOf', target); const farAfter = await api(p, 'coldOf', far);
    ok(Math.abs((before - after) - 35) <= 1.5, `froid ${before} → ${after} : écart attendu 35 (±1,5)`);
    ok(Math.abs(farBefore - farAfter) <= 0.01, 'une cellule à plus de 2 km a été modifiée par l\'événement');
    await api(p, 'setIndex', 12); await api(probe, 'setIndex', 12);
    ok(Math.abs((await api(p, 'coldOf', target)) - (await api(probe, 'coldOf', target))) <= 0.01, 'un événement terminé modifie encore la cellule');
    ok(p.errs.length === 0, p.errs[0]);
  });
}
if (REQUIRE.includes('listen')) {
  await check('écoute : #listen démarre et coupe le drone, niveau lié au froid', async () => {
    const p = await openPage();
    ok(await p.locator('#listen').count() === 1, '#listen manquant');
    ok((await api(p, 'audio')).state === 'off', 'audio.state doit valoir off avant tout clic');
    await p.locator('#listen').click();
    for (let i = 0; i < 20 && (await api(p, 'audio')).state !== 'on'; i++) await sleep(150);
    ok((await api(p, 'audio')).state === 'on', 'audio.state ne passe pas à on après le clic');
    await api(p, 'setIndex', 35); await sleep(300); const day = (await api(p, 'audio')).level;
    await api(p, 'setIndex', 27); await sleep(300); const night = (await api(p, 'audio')).level;
    ok(Number.isFinite(day) && Number.isFinite(night) && night > day, `audio.level nuit ${night} ≤ jour ${day}`);
    await p.locator('#listen').click();
    for (let i = 0; i < 20 && (await api(p, 'audio')).state !== 'off'; i++) await sleep(150);
    ok((await api(p, 'audio')).state === 'off', 'le second clic doit couper le son');
    ok(p.errs.length === 0, p.errs[0]);
  });
}

clearTimeout(killer);
for (const c of open) await c.close().catch(() => {});
await browser.close();
if (server) server.close();
const bad = results.filter((x) => !x).length;
console.log(`SMOKE: ${bad ? 'FAIL' : 'PASS'} (${results.length - bad}/${results.length}) en ${secs(T0)}`);
process.exit(bad ? 1 : 0);
