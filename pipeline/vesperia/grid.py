"""Grille H3 de Paris intra-muros (contrat §2.6)."""
import json
import math
from functools import lru_cache
from pathlib import Path

import h3

ARR_FILE = Path(__file__).resolve().parents[1] / "data" / "arrondissements.geojson"


@lru_cache(maxsize=1)
def _features():
    return json.loads(ARR_FILE.read_text(encoding="utf-8"))["features"]


def _polys(geom):
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


def _in_ring(lat, lon, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _in_geometry(lat, lon, geom):
    for rings in _polys(geom):
        if _in_ring(lat, lon, rings[0]) and not any(_in_ring(lat, lon, h) for h in rings[1:]):
            return True
    return False


def _nearest(lat, lon):
    best, best_d = 1, float("inf")
    for f in _features():
        ring = _polys(f["geometry"])[0][0]
        cy = sum(p[1] for p in ring) / len(ring)
        cx = sum(p[0] for p in ring) / len(ring)
        d = (cy - lat) ** 2 + ((cx - lon) * math.cos(math.radians(lat))) ** 2
        if d < best_d:
            best, best_d = int(f["properties"]["arr"]), d
    return best


@lru_cache(maxsize=4)
def _cells(res):
    cells = set()
    for f in _features():
        cells |= set(h3.geo_to_cells(f["geometry"], res))
    return sorted(cells)


def paris_cells(res=9):
    return list(_cells(res))


def cell_center(cell):
    lat, lon = h3.cell_to_latlng(cell)
    return lat, lon


def cell_polygon(cell):
    ring = [[lon, lat] for lat, lon in h3.cell_to_boundary(cell)]
    ring.append(list(ring[0]))
    return ring


@lru_cache(maxsize=4)
def _arr(res):
    out = {}
    for c in _cells(res):
        lat, lon = cell_center(c)
        arr = 0
        for f in _features():
            if _in_geometry(lat, lon, f["geometry"]):
                arr = int(f["properties"]["arr"])
                break
        out[c] = arr or _nearest(lat, lon)
    return out


def cell_arr(res=9):
    return dict(_arr(res))