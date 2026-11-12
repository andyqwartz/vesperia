"""Fusion des sources et écriture des fichiers de données (contrat §2.4 et §2.5)."""
import datetime as dt
import json
from pathlib import Path

import numpy as np

from vesperia.grid import cell_arr, cell_center, cell_polygon

ORDER = ["road", "bike", "rail", "poi"]
WEIGHTS = {"road": 0.30, "bike": 0.15, "rail": 0.30, "poi": 0.25}
LABELS = {"road": "VOIRIE", "bike": "VÉLO", "rail": "MÉTRO", "poi": "COMMERCES"}
ATTRIBUTION = [
    "Ville de Paris — Open Data (ODbL)",
    "Île-de-France Mobilités — Open Data",
    "© contributeurs OpenStreetMap (ODbL)",
    "Open-Meteo.com (CC BY 4.0)",
    "OpenFreeMap",
]


def fuse(act, cov, w):
    """act (S,N,168), cov (S,N), w (S,) -> (A (N,168), conf (N,))."""
    act = np.asarray(act, dtype=float)
    cov = np.asarray(cov, dtype=float)
    w = np.asarray(w, dtype=float)
    wc = w[:, None] * cov
    den = wc.sum(axis=0)
    num = (wc[:, :, None] * act).sum(axis=0)
    a = np.full(num.shape, 50.0)
    ok = den > 0
    a[ok] = num[ok] / den[ok][:, None]
    conf = den / w.sum() if w.sum() > 0 else np.zeros(den.shape)
    return a, conf


def _now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def assemble(sources, events, cells, out_dir, mode):
    by = {s["id"]: s for s in sources}
    if sorted(by) != sorted(ORDER):
        raise ValueError("assemble attend exactement les sources road, bike, rail, poi")
    n = len(cells)
    for s in ORDER:
        if len(by[s]["cov"]) != n or len(by[s]["data"]) != n:
            raise ValueError(f"la source {s} n'a pas {n} lignes")
    arr = cell_arr(9)
    centers = [cell_center(c) for c in cells]
    extra = by["poi"].get("extra") or {}
    cov = {s: np.round(np.asarray(by[s]["cov"], dtype=float), 2) for s in ORDER}
    w = np.array([WEIGHTS[s] for s in ORDER])
    _, conf = fuse(np.zeros((4, n, 168)), np.stack([cov[s] for s in ORDER]), w)
    out = {
        "h": list(cells),
        "lat": [round(float(c[0]), 5) for c in centers],
        "lon": [round(float(c[1]), 5) for c in centers],
        "poly": [[[round(p[0], 5), round(p[1], 5)] for p in cell_polygon(c)] for c in cells],
        "arr": [int(arr.get(c, 0)) for c in cells],
        "outdoor": [round(float(x), 2) for x in extra.get("outdoor", [0.0] * n)],
        "isolated": [int(x) for x in extra.get("isolated", [0] * n)],
        "confidence": [round(float(x), 2) for x in conf],
        "cov": {s: [float(x) for x in cov[s]] for s in ORDER},
    }
    stamp = _now()
    meta = {
        "version": 1, "mode": mode, "generated_at": stamp, "h3_res": 9, "n_cells": n,
        "sources": [{"id": s, "label": LABELS[s], "weight": WEIGHTS[s], "n_inputs": int(by[s]["n_inputs"]),
                     "updated": by[s].get("updated", stamp)} for s in ORDER],
        "attribution": ATTRIBUTION,
    }
    act = {"sources": ORDER, "data": {s: np.asarray(by[s]["data"]).astype(int).tolist() for s in ORDER}}
    ev = sorted(events, key=lambda e: e["s"])[:5000]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, obj in (("meta", meta), ("cells", out), ("activity", act), ("events", ev)):
        _dump(out_dir / f"{name}.json", obj)