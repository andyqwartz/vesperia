"""Jeu de données synthétique déterministe (mode fixture), au même format que le mode réel."""
import datetime as dt
import math

import numpy as np

from vesperia.assemble import LABELS, ORDER, WEIGHTS, assemble
from vesperia.grid import cell_center, paris_cells

C0 = (48.8606, 2.3470)
K = math.pi / 180 * 6371000.0
EXPO = {"road": 0.5, "bike": 0.8, "rail": 1.2, "poi": 1.0}
BOIS = [((48.862, 2.250), 1600.0), ((48.829, 2.435), 1500.0)]
H = np.arange(24)


def _g(m, s):
    return np.exp(-0.5 * ((H - m) / s) ** 2)


def _week(kind):
    wd, sa, su = {
        "road": (0.10 + 0.5 * _g(8.5, 2) + 0.6 * _g(17.5, 2.5) + 0.35 * _g(13, 4), 0.10 + 0.5 * _g(14, 4.5), 0.08 + 0.4 * _g(15, 4)),
        "bike": (0.04 + 0.5 * _g(8.5, 1.6) + 0.6 * _g(18, 2) + 0.2 * _g(13, 3), 0.04 + 0.5 * _g(15, 3.5), 0.03 + 0.5 * _g(15, 3.5)),
        "rail": (0.03 + _g(8.5, 1.5) + _g(18, 2) + 0.45 * _g(13, 3.5), 0.03 + 0.6 * _g(16, 4.5), 0.03 + 0.5 * _g(16, 4)),
        "poi": (0.04 + 0.9 * _g(13, 4.5) + 0.3 * _g(20, 2), 0.05 + 0.9 * _g(15, 4.5) + 0.4 * _g(22, 2), 0.04 + 0.6 * _g(14, 4)),
    }[kind]
    return np.concatenate([wd] * 5 + [sa, su])


def _dist(lat, lon, p):
    return np.hypot((lon - p[1]) * K * math.cos(math.radians(p[0])), (lat - p[0]) * K)


def _iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def build(out_dir):
    rng = np.random.default_rng(20261112)
    cells = paris_cells(9)
    n = len(cells)
    ctr = np.array([cell_center(c) for c in cells])
    lat, lon = ctr[:, 0], ctr[:, 1]
    d = _dist(lat, lon, C0)
    u = np.exp(-d / 4500.0)
    cov = {"road": np.clip(1.15 - d / 10000, 0.3, 1), "bike": np.clip(1.1 - d / 6000, 0, 1),
           "rail": np.clip(1.2 - d / 7000, 0.05, 1), "poi": np.ones(n)}
    sources = []
    for s in ORDER:
        raw = (u ** EXPO[s])[:, None] * _week(s)[None, :] * rng.lognormal(0.0, 0.25, (n, 168))
        data = np.rint(100 * np.minimum(1.0, raw / np.percentile(raw, 99.0))).astype(int)
        sources.append({"id": s, "label": LABELS[s], "weight": WEIGHTS[s], "n_inputs": 1000,
                        "cov": cov[s].tolist(), "data": data.tolist()})
    parks = [(C0[0] + rng.uniform(-0.04, 0.04), C0[1] + rng.uniform(-0.06, 0.06)) for _ in range(12)]
    count = sum((_dist(lat, lon, p) <= 450).astype(int) for p in parks)
    count = count + sum(3 * (_dist(lat, lon, b) <= r).astype(int) for b, r in BOIS)
    isolated = ((d > 7500) | (rng.random(n) < 0.03)).astype(int)
    sources[-1]["extra"] = {"outdoor": np.minimum(1.0, count / 3.0).tolist(), "isolated": isolated.tolist()}
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    events = []
    for i in range(60):
        k = int(rng.integers(n))
        st = now + dt.timedelta(hours=float(rng.uniform(-24, 20 * 24)))
        events.append({"t": f"Événement de démonstration {i + 1}", "lat": round(float(lat[k]), 5),
                       "lon": round(float(lon[k]), 5), "s": _iso(st), "e": _iso(st + dt.timedelta(hours=3))})
    assemble(sources, events, cells, out_dir, "fixture")