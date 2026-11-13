"""Événements « Que faire à Paris » : manifestations courtes (72 h au plus) autour de la date de génération."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vesperia.sources import net, ods

DATASET = "que-faire-a-paris-"
# ADAPTER : noms de champs, à ne modifier que pour refléter le schéma observé à l'étape R5 de la phase 5.
F_TITLE, F_START, F_END, F_POINT = "title", "date_start", "date_end", "lat_lon"
MAX_HOURS = 72
FMT = "%Y-%m-%dT%H:%M:%SZ"


def events_from_rows(rows):
    """Objets {t, lat, lon, s, e} (heures UTC) : position valide, début avant fin, durée de 72 h au plus, sans doublon."""
    seen, out = set(), []
    for r in rows:
        p = ods.point_of(r.get(F_POINT))
        if p is None or not (48.7 <= p[0] <= 49.0 and 2.1 <= p[1] <= 2.6):
            continue
        try:
            s = ods.parse_ts(r.get(F_START)).astimezone(timezone.utc)
            e = ods.parse_ts(r.get(F_END)).astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
        if not s < e or e - s > timedelta(hours=MAX_HOURS):
            continue
        ev = {"t": str(r.get(F_TITLE) or "")[:80], "lat": round(p[0], 5), "lon": round(p[1], 5), "s": s.strftime(FMT), "e": e.strftime(FMT)}
        key = (ev["t"], ev["s"], ev["e"], ev["lat"], ev["lon"])
        if key not in seen:
            seen.add(key)
            out.append(ev)
    out.sort(key=lambda x: (x["s"], x["t"]))
    return out[:5000]


def fetch():
    now = datetime.now(timezone.utc)
    lo, hi = (now - timedelta(days=1)).date().isoformat(), (now + timedelta(days=14)).date().isoformat()
    rows = ods.export_json(ods.PARIS_BASE, DATASET, [F_TITLE, F_START, F_END, F_POINT],
                           where=f"{F_END} >= date'{lo}' and {F_START} <= date'{hi}'")
    return {"fetched": now.strftime(FMT), "events": events_from_rows(rows)}


def build(cache, cache_only):
    return net.cached_json(Path(cache) / "events.json", fetch, cache_only)["events"]
