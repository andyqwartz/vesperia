"""Source VOIRIE : débit horaire moyen des capteurs permanents de la Ville de Paris, lissé sur la grille."""
from datetime import timedelta, timezone
from pathlib import Path

import numpy as np

from vesperia.assemble import LABELS, WEIGHTS
from vesperia.kernel import spread_average
from vesperia.normalize import to_percent
from vesperia.sources import net, ods

DATASET = "comptages-routiers-permanents"
# ADAPTER : noms de champs, à ne modifier que pour refléter le schéma observé à l'étape R5 de la phase 4.
F_ID, F_TIME, F_FLOW, F_POINT = "iu_ac", "t_1h", "q", "geo_point_2d"
PERIOD_END = True  # t_1h est l'heure de FIN de la période (notice officielle)
WINDOW_DAYS = 14
SIGMA_M = 300.0


def fetch():
    newest = ods.latest(ods.PARIS_BASE, DATASET, F_TIME)
    day0 = (newest - timedelta(days=WINDOW_DAYS)).date().isoformat()
    rows = ods.export_json(ods.PARIS_BASE, DATASET, [F_ID, F_TIME, F_FLOW, F_POINT], where=f"{F_TIME} >= date'{day0}'")
    sensors = ods.week_profiles(rows, F_ID, F_TIME, F_FLOW, F_POINT, PERIOD_END)
    return {"newest": newest.isoformat(), "n_rows": len(rows), "sensors": sensors}


def build(cells, centers, cache, cache_only):
    prof = net.cached_json(Path(cache) / "road_profiles.json", fetch, cache_only)
    sensors = prof["sensors"]
    if not sensors:
        raise SystemExit("road : aucun capteur exploitable (vérifie les champs ADAPTER en tête de road.py)")
    pts = [(s["lat"], s["lon"]) for s in sensors]
    field, cov = spread_average(centers, pts, np.array([s["v"] for s in sensors]), SIGMA_M)
    data = to_percent(field, 99.0, mask=cov > 0.3)
    stamp = ods.parse_ts(prof["newest"]).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": "road", "label": LABELS["road"], "weight": WEIGHTS["road"], "n_inputs": len(sensors),
            "cov": [float(c) for c in cov], "data": data.tolist(), "updated": stamp}
