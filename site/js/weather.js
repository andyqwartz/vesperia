// weather.js — prévision horaire Open-Meteo (Phase 7). Heures en GMT, 8 jours : couvre les 168 heures à venir.
const URL = 'https://api.open-meteo.com/v1/forecast?latitude=48.8566&longitude=2.3522&hourly=temperature_2m,precipitation&forecast_days=8&timezone=GMT';

export async function loadWeather() {
  const r = await fetch(URL);
  if (!r.ok) throw new Error(`Open-Meteo : HTTP ${r.status}`);
  const j = await r.json();
  const h = j.hourly;
  return {
    start: Date.parse(`${h.time[0]}:00Z`),
    temp: h.temperature_2m.map((x) => (x === null ? 8 : x)),
    precip: h.precipitation.map((x) => (x === null ? 0 : x)),
  };
}
