"""Opérateurs de lissage spatial à noyau gaussien tronqué à 3 sigma."""
import numpy as np

R = 6371000.0


def _kernel(centers, points, sigma_m):
    c = np.asarray(centers, dtype=float)[:, None, :]
    p = np.asarray(points, dtype=float)[None, :, :]
    lat0 = np.radians((c[..., 0] + p[..., 0]) / 2.0)
    dx = np.radians(p[..., 1] - c[..., 1]) * R * np.cos(lat0)
    dy = np.radians(p[..., 0] - c[..., 0]) * R
    d = np.hypot(dx, dy)
    k = np.exp(-(d ** 2) / (2.0 * sigma_m ** 2))
    k[d > 3.0 * sigma_m] = 0.0
    return k


def _chunks(n, m, budget=4_000_000):
    step = max(1, budget // max(1, m))
    for a in range(0, n, step):
        yield a, min(n, a + step)


def _spread(centers, points, values, sigma_m, average):
    centers = np.asarray(centers, dtype=float)
    n = len(centers)
    values = np.asarray(values, dtype=float)
    width = values.shape[1] if values.ndim == 2 else 168
    field = np.zeros((n, width))
    cov = np.zeros(n)
    if len(points) == 0:
        return field, cov
    points = np.asarray(points, dtype=float)
    for a, b in _chunks(n, len(points)):
        k = _kernel(centers[a:b], points, sigma_m)
        s = k.sum(axis=1)
        acc = k @ values
        if average:
            ok = s > 0
            acc[ok] = acc[ok] / s[ok][:, None]
            acc[~ok] = 0.0
        field[a:b] = acc
        cov[a:b] = np.minimum(1.0, s)
    return field, cov


def spread_average(centers, points, values, sigma_m):
    return _spread(centers, points, values, sigma_m, True)


def spread_sum(centers, points, values, sigma_m):
    return _spread(centers, points, values, sigma_m, False)
