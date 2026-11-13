"""Source COMMERCES : activité des établissements OSM, plus indicateurs plein air et isolement."""
import datetime as dt
import re
from pathlib import Path

import numpy as np

from vesperia.assemble import LABELS, WEIGHTS
from vesperia.kernel import spread_sum
from vesperia.normalize import to_percent
from vesperia.sources import net
from vesperia.sources.poi_profiles import (
    ISOLATION_RADIUS_M, OUTDOOR_RADIUS_M, element_point, element_points,
    overpass_outdoor_query, overpass_poi_query, overpass_transit_query, poi_vector,
)

SIGMA_M = 200.0
ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def poi_points(elements):
    """(points, vecteurs) : un point (lat, lon) et un profil de 168 valeurs par établissement reconnu."""
    pts, vecs = [], []
    for el in elements:
        v = poi_vector(el.get("tags"))
        p = element_point(el)
        if v is None or p is None:
            continue
        pts.append(p)
        vecs.append(v)
    return pts, vecs


def isolation(centers, transit_points):
    """1 si aucun arrêt de transport à moins de ISOLATION_RADIUS_M du centre de la cellule, sinon 0."""
    n = len(centers)
    if not transit_points:
        return np.ones(n, dtype=int)
    _, cov = spread_sum(centers, transit_points, np.zeros((len(transit_points), 1)), ISOLATION_RADIUS_M / 3.0)
    return (cov <= 0.0).astype(int)


def inside_polygon(lat, lon, ring):
    """Test du rayon (parité des croisements). lat, lon : tableaux de k points ; ring : tableau (m, 2) de (lat, lon)."""
    lat = np.asarray(lat, dtype=float)[:, None]
    lon = np.asarray(lon, dtype=float)[:, None]
    y1, x1 = ring[:-1, 0][None, :], ring[:-1, 1][None, :]
    y2, x2 = ring[1:, 0][None, :], ring[1:, 1][None, :]
    straddle = (y1 > lat) != (y2 > lat)
    dy = np.where(y2 == y1, 1.0, y2 - y1)
    xcross = x1 + (lat - y1) * (x2 - x1) / dy
    return (np.sum(straddle & (lon < xcross), axis=1) % 2) == 1


def rings_of(el):
    """Anneaux fermés (listes de (lat, lon)) d'un élément Overpass : sa géométrie, et ses membres de rôle outer."""
    rings = []
    parts = [el.get("geometry") or []]
    parts += [m.get("geometry") or [] for m in (el.get("members") or []) if m.get("role") == "outer"]
    for g in parts:
        pts = [(float(p["lat"]), float(p["lon"])) for p in g if p and "lat" in p and "lon" in p]
        if len(pts) >= 4 and pts[0] == pts[-1]:
            rings.append(pts)
    return rings


def outdoor_levels(centers, elements):
    """1.0 si le centre est dans un parc, jardin, plan d'eau ou cimetière ; 0.5 si un contour est à moins de OUTDOOR_RADIUS_M ; sinon 0."""
    c = np.asarray(centers, dtype=float)
    lat, lon = c[:, 0], c[:, 1]
    inside = np.zeros(len(c), dtype=bool)
    pts = []
    for el in elements:
        pts.extend(element_points(el))
        for ring in rings_of(el):
            a = np.asarray(ring, dtype=float)
            m = ((lat >= a[:, 0].min()) & (lat <= a[:, 0].max()) & (lon >= a[:, 1].min())
                 & (lon <= a[:, 1].max()) & ~inside)
            idx = np.nonzero(m)[0]
            if idx.size:
                inside[idx[inside_polygon(lat[idx], lon[idx], a)]] = True
    near = np.zeros(len(c), dtype=bool)
    if pts:
        _, cov = spread_sum(c, pts, np.zeros((len(pts), 1)), OUTDOOR_RADIUS_M / 3.0)
        near = cov > 0.0
    return np.where(inside, 1.0, np.where(near, 0.5, 0.0))


def build(cells, centers, cache, cache_only):
    cache = Path(cache)
    poi = net.cached_json(cache / "overpass_poi.json", lambda: net.overpass(overpass_poi_query()), cache_only)
    transit = net.cached_json(cache / "overpass_transit.json", lambda: net.overpass(overpass_transit_query()), cache_only)
    outdoor = net.cached_json(cache / "overpass_outdoor.json", lambda: net.overpass(overpass_outdoor_query()), cache_only)
    pts, vecs = poi_points(poi["elements"])
    if not pts:
        raise SystemExit("aucun établissement exploitable dans la réponse Overpass")
    field, _ = spread_sum(centers, pts, np.asarray(vecs, dtype=float), SIGMA_M)
    data = to_percent(field, 99.0)
    t_pts = [p for p in (element_point(e) for e in transit["elements"]) if p]
    stamp = (poi.get("osm3s") or {}).get("timestamp_osm_base", "")
    if not ISO_Z.match(stamp):
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": "poi", "label": LABELS["poi"], "weight": WEIGHTS["poi"], "n_inputs": len(pts),
        "cov": [1.0] * len(cells), "data": data.tolist(), "updated": stamp,
        "extra": {
            "outdoor": [round(float(x), 2) for x in outdoor_levels(centers, outdoor["elements"])],
            "isolated": [int(x) for x in isolation(centers, t_pts)],
        },
    }
