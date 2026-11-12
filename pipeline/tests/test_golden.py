"""Tests dorés de Vesperia.

FICHIER FOURNI (règle R2) : ne jamais le modifier. Chaque test vérifie un contrat du BRIEF (§2).
Les marqueurs phase1, phase3, phase4 et phase5 sont déclarés dans pytest.ini ; le gate de chaque phase
lance les marqueurs qui la concernent.
"""
import datetime as dt
import math
import pathlib
from zoneinfo import ZoneInfo

import numpy as np
import pytest

PARIS = ZoneInfo("Europe/Paris")
UTC = dt.timezone.utc
ROOT = pathlib.Path(__file__).resolve().parents[2]
ARR_FILE = ROOT / "pipeline" / "data" / "arrondissements.geojson"
R_EARTH = 6371000.0
M_PER_DEG_LAT = math.radians(1.0) * R_EARTH

# ---------------------------------------------------------------- phase 1 : temps


@pytest.mark.phase1
def test_week_hour_monday_midnight():
    from vesperia.timeidx import week_hour
    assert week_hour(dt.datetime(2026, 11, 9, 0, 0, tzinfo=PARIS)) == 0


@pytest.mark.phase1
def test_week_hour_sunday_last_hour():
    from vesperia.timeidx import week_hour
    assert week_hour(dt.datetime(2026, 11, 15, 23, 0, tzinfo=PARIS)) == 167


@pytest.mark.phase1
def test_week_hour_wednesday_afternoon_and_type():
    from vesperia.timeidx import week_hour
    out = week_hour(dt.datetime(2026, 11, 11, 15, 30, tzinfo=PARIS))
    assert out == 63
    assert isinstance(out, int)


@pytest.mark.phase1
def test_week_hour_converts_utc_to_paris_winter():
    from vesperia.timeidx import week_hour
    # 23h30 UTC le lundi = 00h30 le mardi à Paris (UTC+1) -> 24
    assert week_hour(dt.datetime(2026, 11, 9, 23, 30, tzinfo=UTC)) == 24


@pytest.mark.phase1
def test_week_hour_converts_utc_to_paris_summer():
    from vesperia.timeidx import week_hour
    # 22h30 UTC le mardi 14 juillet = 00h30 le mercredi 15 à Paris (UTC+2) -> 48
    assert week_hour(dt.datetime(2026, 7, 14, 22, 30, tzinfo=UTC)) == 48


@pytest.mark.phase1
def test_week_hour_after_spring_change():
    from vesperia.timeidx import week_hour
    assert week_hour(dt.datetime(2026, 3, 29, 12, 0, tzinfo=PARIS)) == 6 * 24 + 12


@pytest.mark.phase1
def test_week_hour_naive_raises():
    from vesperia.timeidx import week_hour
    with pytest.raises(ValueError):
        week_hour(dt.datetime(2026, 11, 9, 12, 0))


@pytest.mark.phase1
def test_period_end_shifts_one_hour_back():
    from vesperia.timeidx import week_hour_from_period_end
    assert week_hour_from_period_end(dt.datetime(2026, 11, 10, 0, 0, tzinfo=PARIS)) == 23
    assert week_hour_from_period_end(dt.datetime(2026, 11, 9, 1, 0, tzinfo=PARIS)) == 0


@pytest.mark.phase1
def test_period_end_wraps_to_sunday():
    from vesperia.timeidx import week_hour_from_period_end
    assert week_hour_from_period_end(dt.datetime(2026, 11, 9, 0, 0, tzinfo=PARIS)) == 167


@pytest.mark.phase1
def test_period_end_across_spring_change():
    from vesperia.timeidx import week_hour_from_period_end
    # 03h00 CEST le 29 mars = 01h00 UTC ; une heure avant = 00h00 UTC = 01h00 CET -> dimanche 01h
    assert week_hour_from_period_end(dt.datetime(2026, 3, 29, 3, 0, tzinfo=PARIS)) == 6 * 24 + 1


@pytest.mark.phase1
def test_period_end_naive_raises():
    from vesperia.timeidx import week_hour_from_period_end
    with pytest.raises(ValueError):
        week_hour_from_period_end(dt.datetime(2026, 11, 9, 12, 0))


# ---------------------------------------------------------------- phase 1 : grille H3


@pytest.mark.phase1
def test_cell_center_and_polygon():
    import h3
    from vesperia.grid import cell_center, cell_polygon
    cell = h3.latlng_to_cell(48.8566, 2.3522, 9)
    lat, lon = cell_center(cell)
    assert abs(lat - 48.8566) < 0.003 and abs(lon - 2.3522) < 0.004
    poly = cell_polygon(cell)
    assert len(poly) == 7
    assert list(poly[0]) == list(poly[-1])
    for p in poly:
        assert 2.34 < p[0] < 2.37 and 48.85 < p[1] < 48.87, "ordre attendu : [lon, lat]"
    lons = [p[0] for p in poly]
    lats = [p[1] for p in poly]
    assert min(lons) < lon < max(lons) and min(lats) < lat < max(lats)


@pytest.mark.phase1
@pytest.mark.skipif(not ARR_FILE.exists(), reason="pipeline/data/arrondissements.geojson absent")
def test_paris_cells_membership():
    import h3
    from vesperia.grid import paris_cells
    cells = paris_cells(9)
    assert cells == sorted(cells)
    assert len(cells) == len(set(cells))
    assert 900 <= len(cells) <= 1200
    assert cells == paris_cells(9)
    inside = [(48.8530, 2.3499), (48.8625, 2.2495), (48.8288, 2.4350), (48.8867, 2.3431), (48.8443, 2.3744)]
    outside = [(48.8920, 2.2362), (48.9245, 2.3601), (48.8610, 2.4430), (48.8354, 2.2400)]
    s = set(cells)
    for lat, lon in inside:
        assert h3.latlng_to_cell(lat, lon, 9) in s, f"devrait être dans Paris : {lat},{lon}"
    for lat, lon in outside:
        assert h3.latlng_to_cell(lat, lon, 9) not in s, f"devrait être hors Paris : {lat},{lon}"


@pytest.mark.phase1
@pytest.mark.skipif(not ARR_FILE.exists(), reason="pipeline/data/arrondissements.geojson absent")
def test_cell_arr_mapping():
    import h3
    from vesperia.grid import cell_arr, paris_cells
    m = cell_arr(9)
    assert set(m) == set(paris_cells(9))
    assert all(isinstance(v, int) and 1 <= v <= 20 for v in m.values())
    expected = {(48.8584, 2.2945): 7, (48.8867, 2.3431): 18, (48.8443, 2.3744): 12,
                (48.8288, 2.4350): 12, (48.8625, 2.2495): 16}
    for (lat, lon), arr in expected.items():
        assert m[h3.latlng_to_cell(lat, lon, 9)] == arr, f"arrondissement attendu {arr} en {lat},{lon}"


# ---------------------------------------------------------------- phase 3 : noyaux


def _k(d, sigma):
    return math.exp(-(d ** 2) / (2.0 * sigma ** 2)) if d <= 3.0 * sigma else 0.0


C0 = (48.85, 2.35)


def _north(meters):
    return (C0[0] + meters / M_PER_DEG_LAT, C0[1])


@pytest.mark.phase3
def test_kernel_known_offset():
    from vesperia.kernel import spread_average, spread_sum
    d = math.radians(0.001) * R_EARTH
    pt = (C0[0] + 0.001, C0[1])
    vals = np.full((1, 168), 10.0)
    f_sum, c_sum = spread_sum([C0], [pt], vals, 100.0)
    f_avg, c_avg = spread_average([C0], [pt], vals, 100.0)
    k = _k(d, 100.0)
    assert c_sum[0] == pytest.approx(k, rel=1e-9)
    assert c_avg[0] == pytest.approx(k, rel=1e-9)
    assert f_sum[0, 0] == pytest.approx(10.0 * k, rel=1e-9)
    assert f_avg[0, 0] == pytest.approx(10.0, rel=1e-9)


@pytest.mark.phase3
def test_kernel_longitude_uses_cosine_of_mean_latitude():
    from vesperia.kernel import spread_sum
    pt = (C0[0], C0[1] + 0.002)
    d = math.radians(0.002) * R_EARTH * math.cos(math.radians(C0[0]))
    f, c = spread_sum([C0], [pt], np.ones((1, 168)), 150.0)
    assert c[0] == pytest.approx(_k(d, 150.0), rel=1e-9)


@pytest.mark.phase3
def test_kernel_truncated_at_three_sigma():
    from vesperia.kernel import spread_average, spread_sum
    vals = np.full((1, 168), 7.0)
    for op in (spread_sum, spread_average):
        f_out, c_out = op([C0], [_north(301.0)], vals, 100.0)
        assert c_out[0] == 0.0 and np.all(f_out == 0.0)
        f_in, c_in = op([C0], [_north(299.0)], vals, 100.0)
        assert c_in[0] > 0.0 and np.all(f_in > 0.0)


@pytest.mark.phase3
def test_kernel_two_points_weights():
    from vesperia.kernel import spread_average, spread_sum
    pts = [C0, _north(100.0)]
    vals = np.vstack([np.full(168, 10.0), np.full(168, 50.0)])
    k2 = math.exp(-0.5)
    f_sum, c_sum = spread_sum([C0], pts, vals, 100.0)
    f_avg, c_avg = spread_average([C0], pts, vals, 100.0)
    assert f_sum[0, 5] == pytest.approx(10.0 + 50.0 * k2, rel=1e-9)
    assert f_avg[0, 5] == pytest.approx((10.0 + 50.0 * k2) / (1.0 + k2), rel=1e-9)
    assert c_sum[0] == pytest.approx(1.0) and c_avg[0] == pytest.approx(1.0)


@pytest.mark.phase3
def test_kernel_coverage_is_clipped_at_one():
    from vesperia.kernel import spread_average, spread_sum
    pts = [C0, C0, C0]
    vals = np.full((3, 168), 4.0)
    f_sum, c_sum = spread_sum([C0], pts, vals, 100.0)
    f_avg, c_avg = spread_average([C0], pts, vals, 100.0)
    assert c_sum[0] == 1.0 and c_avg[0] == 1.0
    assert f_sum[0, 0] == pytest.approx(12.0)
    assert f_avg[0, 0] == pytest.approx(4.0)


@pytest.mark.phase3
def test_kernel_shapes_columns_and_no_nan():
    from vesperia.kernel import spread_average, spread_sum
    rng = np.random.default_rng(1)
    centers = np.column_stack([48.85 + rng.random(5) * 0.01, 2.35 + rng.random(5) * 0.01])
    points = np.column_stack([48.85 + rng.random(7) * 0.01, 2.35 + rng.random(7) * 0.01])
    vals = np.tile(np.arange(168, dtype=float), (7, 1))
    for op in (spread_sum, spread_average):
        f, c = op(centers, points, vals, 500.0)
        assert f.shape == (5, 168) and c.shape == (5,)
        assert not np.isnan(f).any() and not np.isnan(c).any()
    f, c = spread_average(centers, points, vals, 500.0)
    assert f[0, 100] == pytest.approx(100.0, rel=1e-9)


@pytest.mark.phase3
def test_kernel_far_cells_are_zero_not_nan_and_empty_points():
    from vesperia.kernel import spread_average, spread_sum
    far = (49.5, 2.35)
    vals = np.ones((1, 168))
    for op in (spread_sum, spread_average):
        f, c = op([far], [C0], vals, 300.0)
        assert c[0] == 0.0 and np.all(f == 0.0)
        f0, c0 = op([C0, far], np.zeros((0, 2)), np.zeros((0, 168)), 300.0)
        assert f0.shape == (2, 168) and np.all(f0 == 0.0) and np.all(c0 == 0.0)


# ---------------------------------------------------------------- phase 3 : normalisation


@pytest.mark.phase3
def test_to_percent_basic_and_dtype():
    from vesperia.normalize import to_percent
    out = to_percent(np.array([0.0, 50.0, 100.0, 200.0]))
    assert out.tolist() == [0, 25, 51, 100]
    assert np.issubdtype(out.dtype, np.integer)


@pytest.mark.phase3
def test_to_percent_mask_excludes_outliers_from_percentile():
    from vesperia.normalize import to_percent
    x = np.array([0.0, 50.0, 100.0, 10000.0])
    out = to_percent(x, mask=np.array([True, True, True, False]))
    assert out.tolist() == [0, 51, 100, 100]


@pytest.mark.phase3
def test_to_percent_zero_and_2d_rows_mask():
    from vesperia.normalize import to_percent
    assert to_percent(np.zeros((3, 4))).tolist() == [[0] * 4] * 3
    x = np.vstack([np.full(168, 10.0), np.full(168, 20.0), np.full(168, 9999.0)])
    out = to_percent(x, mask=np.array([True, True, False]))
    assert out.shape == (3, 168)
    assert out[2].min() == 100
    assert 0 < out[0, 0] < 100


# ---------------------------------------------------------------- phase 3 : profils OSM


@pytest.mark.phase3
def test_poi_profiles_shape_and_ranges():
    from vesperia.sources import poi_profiles as pp
    assert len(pp.KINDS) == 12
    for kind in pp.KINDS:
        prof = pp.weekly(kind)
        assert len(prof) == 168, kind
        assert min(prof) >= 0.0 and max(prof) <= 1.0, kind
    assert set(pp.KIND_WEIGHT) == set(pp.KINDS)


@pytest.mark.phase3
def test_poi_profiles_expected_rhythms():
    from vesperia.sources import poi_profiles as pp
    P = pp.PROFILES

    def at(kind, day, hour):
        return P[kind][day * 24 + hour]

    assert at("office", 1, 11) >= 0.8 and at("office", 6, 11) <= 0.1 and at("office", 1, 3) <= 0.05
    assert at("night", 4, 22) > at("night", 1, 22) > at("night", 1, 4)
    assert at("night", 5, 1) >= 0.5
    assert at("worship", 6, 10) > 3 * at("worship", 1, 10)
    assert at("hospital", 1, 3) >= 0.4
    assert at("food", 1, 13) > at("food", 1, 4)
    assert at("school", 5, 15) < at("school", 2, 15)
    assert at("lodging", 2, 3) >= 0.4


@pytest.mark.phase3
def test_poi_classify_and_vector():
    from vesperia.sources import poi_profiles as pp
    assert pp.classify({"amenity": "cafe"}) == "food"
    assert pp.classify({"amenity": "bar"}) == "night"
    assert pp.classify({"shop": "bakery"}) == "grocery"
    assert pp.classify({"shop": "clothes"}) == "retail"
    assert pp.classify({"shop": "vacant"}) is None
    assert pp.classify({"office": "company"}) == "office"
    assert pp.classify({"tourism": "hotel"}) == "lodging"
    assert pp.classify({"tourism": "museum"}) == "culture"
    assert pp.classify({"leisure": "swimming_pool"}) == "sport"
    assert pp.classify({"amenity": "hospital"}) == "hospital"
    assert pp.classify({"amenity": "bench"}) is None
    assert pp.classify({}) is None and pp.classify(None) is None
    vec = pp.poi_vector({"amenity": "hospital"})
    assert len(vec) == 168 and max(vec) == pytest.approx(12.0)
    assert pp.poi_vector({"amenity": "bench"}) is None


@pytest.mark.phase3
def test_poi_transit_outdoor_and_queries():
    from vesperia.sources import poi_profiles as pp
    assert pp.is_transit({"highway": "bus_stop"}) and pp.is_transit({"railway": "subway_entrance"})
    assert not pp.is_transit({"highway": "residential"})
    assert pp.is_outdoor({"leisure": "park"}) and pp.is_outdoor({"natural": "water"})
    assert not pp.is_outdoor({"leisure": "pitch"})
    for q in (pp.overpass_poi_query(), pp.overpass_transit_query(), pp.overpass_outdoor_query()):
        assert q.startswith("[out:json]") and q.endswith(";")
        assert "48.815" in q and "2.47" in q
    assert "out center tags" in pp.overpass_poi_query()
    assert "out geom" in pp.overpass_outdoor_query()
    assert pp.element_point({"lat": 48.8, "lon": 2.3}) == (48.8, 2.3)
    assert pp.element_point({"center": {"lat": 48.9, "lon": 2.4}}) == (48.9, 2.4)
    assert pp.element_point({"type": "relation"}) is None
    pts = pp.element_points({"geometry": [{"lat": 1, "lon": 2}], "members": [{"geometry": [{"lat": 3, "lon": 4}]}],
                             "center": {"lat": 5, "lon": 6}})
    assert sorted(pts) == [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]


# ---------------------------------------------------------------- phase 3 : source commerces (fonctions pures)


def _east(meters, lat=48.85):
    return meters / (M_PER_DEG_LAT * math.cos(math.radians(lat)))


def _square(c, half_m):
    dla, dlo = half_m / M_PER_DEG_LAT, _east(half_m, c[0])
    ring = [(c[0] - dla, c[1] - dlo), (c[0] - dla, c[1] + dlo), (c[0] + dla, c[1] + dlo), (c[0] + dla, c[1] - dlo),
            (c[0] - dla, c[1] - dlo)]
    return [{"lat": a, "lon": b} for a, b in ring]


@pytest.mark.phase3
def test_inside_polygon_square():
    from vesperia.sources.poi import inside_polygon
    ring = np.array([(p["lat"], p["lon"]) for p in _square(C0, 100.0)])
    lat = [C0[0], C0[0] + 50 / M_PER_DEG_LAT, C0[0] + 150 / M_PER_DEG_LAT, C0[0]]
    lon = [C0[1], C0[1], C0[1], C0[1] + _east(150.0)]
    assert inside_polygon(lat, lon, ring).tolist() == [True, True, False, False]


@pytest.mark.phase3
def test_poi_points_keep_only_known_places_with_a_position():
    from vesperia.sources.poi import poi_points
    els = [
        {"type": "node", "lat": 48.85, "lon": 2.35, "tags": {"amenity": "restaurant"}},
        {"type": "way", "center": {"lat": 48.86, "lon": 2.36}, "tags": {"shop": "bakery"}},
        {"type": "node", "lat": 48.85, "lon": 2.35, "tags": {"highway": "bus_stop"}},
        {"type": "node", "lat": 48.85, "lon": 2.35},
        {"type": "relation", "tags": {"amenity": "cafe"}},
    ]
    pts, vecs = poi_points(els)
    assert pts == [(48.85, 2.35), (48.86, 2.36)]
    assert len(vecs) == 2 and all(len(v) == 168 for v in vecs)


@pytest.mark.phase3
def test_isolation_uses_the_250_m_radius():
    from vesperia.sources.poi import isolation
    near = (C0[0] + 200 / M_PER_DEG_LAT, C0[1])
    far = (C0[0] + 300 / M_PER_DEG_LAT, C0[1])
    assert isolation([C0], [near]).tolist() == [0]
    assert isolation([C0], [far]).tolist() == [1]
    assert isolation([C0, C0], []).tolist() == [1, 1]


@pytest.mark.phase3
def test_outdoor_levels_inside_near_and_far():
    from vesperia.sources.poi import outdoor_levels
    park = {"type": "way", "geometry": _square(C0, 100.0), "tags": {"leisure": "park"}}
    near_c = (C0[0] + 200 / M_PER_DEG_LAT, C0[1])
    far_c = (C0[0] + 900 / M_PER_DEG_LAT, C0[1])
    out = outdoor_levels([C0, near_c, far_c], [park])
    assert out.tolist() == [1.0, 0.5, 0.0]
    rel = {"type": "relation", "members": [{"role": "outer", "geometry": _square(C0, 100.0)}], "tags": {"leisure": "park"}}
    assert outdoor_levels([C0], [rel]).tolist() == [1.0]
    assert outdoor_levels([C0], []).tolist() == [0.0]


# ---------------------------------------------------------------- phase 4 : lecture des données ouvertes


MON = dt.datetime(2026, 11, 9, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=1)))  # lundi, heure de Paris en novembre


def _stamps(skip=0):
    return [(MON + dt.timedelta(hours=i)).isoformat() for i in range(skip, 168)]


def _rows(stamps, sid="a", value=None, point=True):
    return [{"id": sid, "t": t, "q": (float(i) if value is None else value), "p": ({"lat": 48.85, "lon": 2.35} if point else None)}
            for i, t in enumerate(stamps)]


@pytest.mark.phase4
def test_point_of_accepts_object_and_text():
    from vesperia.sources.ods import point_of
    assert point_of({"lon": 2.35, "lat": 48.85}) == (48.85, 2.35)
    assert point_of("48.85, 2.35") == (48.85, 2.35)
    assert point_of(None) is None and point_of("pas un point") is None and point_of({"lat": 1}) is None


@pytest.mark.phase4
def test_parse_ts_with_and_without_zone():
    from vesperia.sources.ods import parse_ts
    assert parse_ts("2026-11-10T09:00:00+00:00").utcoffset() == dt.timedelta(0)
    assert parse_ts("2026-07-10T09:00:00Z").utcoffset() == dt.timedelta(0)
    assert parse_ts("2026-11-10 09:00:00").utcoffset() == dt.timedelta(hours=1)
    assert parse_ts("2026-07-10T09:00:00").utcoffset() == dt.timedelta(hours=2)


@pytest.mark.phase4
def test_week_profiles_period_start_and_period_end():
    from vesperia.sources.ods import week_profiles
    rows = _rows(_stamps())
    start = week_profiles(rows, "id", "t", "q", "p", False)
    assert len(start) == 1 and start[0]["id"] == "a" and len(start[0]["v"]) == 168
    assert start[0]["lat"] == 48.85 and start[0]["lon"] == 2.35
    assert start[0]["v"][0] == 0.0 and start[0]["v"][10] == 10.0 and start[0]["v"][167] == 167.0
    end = week_profiles(rows, "id", "t", "q", "p", True)
    assert end[0]["v"][0] == 1.0 and end[0]["v"][10] == 11.0 and end[0]["v"][167] == 0.0


@pytest.mark.phase4
def test_week_profiles_drops_sparse_zero_and_unlocated_sensors():
    from vesperia.sources.ods import week_profiles
    rows = _rows(_stamps(), "ok", value=2.0)
    rows += _rows(_stamps()[:10], "sparse", value=2.0)
    rows += _rows(_stamps(), "zero", value=0.0)
    rows += _rows(_stamps(), "nopos", value=2.0, point=False)
    out = week_profiles(rows, "id", "t", "q", "p", False)
    assert [d["id"] for d in out] == ["ok"]


@pytest.mark.phase4
def test_fill_week_and_missing_hours():
    from vesperia.sources.ods import fill_week, week_profiles
    v = np.tile(np.arange(24.0), 7)
    v[24 + 5] = np.nan
    assert fill_week(v)[24 + 5] == pytest.approx(5.0)
    w = np.tile(np.arange(24.0), 7)
    w[3::24] = np.nan
    assert fill_week(w)[3] == pytest.approx(np.nanmean(w))
    rows = [{"id": "a", "t": t, "q": float(i % 24), "p": {"lat": 48.85, "lon": 2.35}}
            for i, t in enumerate(_stamps(), start=0)]
    rows = rows[18:]
    out = week_profiles(rows, "id", "t", "q", "p", False)
    assert out[0]["v"] == [float(i % 24) for i in range(168)]


# ---------------------------------------------------------------- phase 5 : métro et événements (fonctions pures)


@pytest.mark.phase5
def test_rail_pick_datasets_filters_by_title_and_keeps_order():
    from vesperia.sources.rail import pick_datasets
    payload = {"datasets": [
        {"datasetid": "surface", "metas": {"title": "Validations sur le réseau de surface : Profils horaires par jour type (1er trimestre)"}},
        {"datasetid": "ferre-b", "metas": {"title": "Validations sur le réseau ferré : Profils horaires par jour type (1er semestre 2026)"}},
        {"datasetid": "ferre-a", "metas": {"title": "Validations sur le réseau ferré : Nombre de validations par jour"}},
        {"datasetid": "ferre-c", "metas": {"title": "Validations sur le réseau ferré : Profils horaires par jour type (1er trimestre 2025)"}},
        {"metas": {"title": "Profils horaires ferré sans identifiant"}},
    ]}
    assert [i for i, _ in pick_datasets(payload)] == ["ferre-b", "ferre-c"]
    assert pick_datasets({}) == []


@pytest.mark.phase5
def test_rail_week_from_rows_maps_days_and_hours():
    from vesperia.sources.rail import week_from_rows
    rows = []
    for cat, base in (("JOHV", 10.0), ("SAHV", 5.0), ("DIJFP", 2.0), ("JOVS", 99.0)):
        for h in range(24):
            share = 0.0 if (cat == "JOHV" and h == 3) else base + h
            rows.append({"cat_jour": cat, "trnc_horr_60": f"{h}H-{(h + 1) % 24}H", "pourc_validations": share})
    week = week_from_rows(rows)
    assert len(week) == 168
    assert week[23] == 1.0 and week[4 * 24 + 23] == 1.0 and week[3] == 0.0
    assert week[5 * 24 + 23] == round(28.0 / 33.0, 4)
    assert week[6 * 24 + 0] == round(2.0 / 33.0, 4)
    with pytest.raises(RuntimeError, match="SAHV"):
        week_from_rows([r for r in rows if r["cat_jour"] == "JOHV"])


@pytest.mark.phase5
def test_rail_points_keep_only_rail_access():
    from vesperia.sources.rail import rail_points
    els = [
        {"lat": 48.85, "lon": 2.35, "tags": {"railway": "subway_entrance"}},
        {"center": {"lat": 48.86, "lon": 2.36}, "tags": {"railway": "station"}},
        {"lat": 48.8, "lon": 2.3, "tags": {"highway": "bus_stop"}},
        {"tags": {"railway": "station"}},
    ]
    assert rail_points(els) == [(48.85, 2.35), (48.86, 2.36)]


@pytest.mark.phase5
def test_events_from_rows_filters_and_converts():
    from vesperia.sources.events import events_from_rows
    ok = {"title": "Concert", "date_start": "2026-11-14T20:00:00+01:00", "date_end": "2026-11-14T23:00:00+01:00",
          "lat_lon": {"lat": 48.85, "lon": 2.35}}
    rows = [
        ok, dict(ok),
        {**ok, "title": "Expo longue", "date_end": "2026-12-30T23:00:00+01:00"},
        {**ok, "title": "Hors Paris", "lat_lon": {"lat": 45.0, "lon": 4.0}},
        {**ok, "title": "Sans lieu", "lat_lon": None},
        {**ok, "title": "Fin avant debut", "date_end": "2026-11-14T19:00:00+01:00"},
    ]
    assert events_from_rows(rows) == [{"t": "Concert", "lat": 48.85, "lon": 2.35, "s": "2026-11-14T19:00:00Z", "e": "2026-11-14T22:00:00Z"}]


# ---------------------------------------------------------------- phase 5 : fusion


@pytest.mark.phase5
def test_fuse_formula():
    from vesperia.assemble import fuse
    act = np.zeros((2, 1, 168))
    act[0] = 80
    act[1] = 20
    cov = np.array([[1.0], [0.5]])
    a, conf = fuse(act, cov, np.array([0.3, 0.7]))
    assert a.shape == (1, 168) and conf.shape == (1,)
    assert a[0, 0] == pytest.approx((0.3 * 80 + 0.7 * 0.5 * 20) / 0.65, rel=1e-9)
    assert conf[0] == pytest.approx(0.65, rel=1e-9)


@pytest.mark.phase5
def test_fuse_zero_coverage_gives_fifty_and_zero_confidence():
    from vesperia.assemble import fuse
    act = np.full((2, 3, 168), 90.0)
    cov = np.zeros((2, 3))
    cov[0, 1] = 1.0
    a, conf = fuse(act, cov, np.array([0.5, 0.5]))
    assert np.all(a[0] == 50.0) and conf[0] == 0.0
    assert np.all(a[1] == 90.0) and conf[1] == pytest.approx(0.5)
