import numpy as np


def to_percent(x, q=99.0, mask=None):
    x = np.asarray(x, dtype=float)
    sel = x if mask is None else x[np.asarray(mask, dtype=bool)]
    if sel.size == 0:
        return np.zeros(x.shape, dtype=int)
    p = float(np.percentile(sel, q))
    if p <= 0:
        return np.zeros(x.shape, dtype=int)
    return np.rint(100.0 * np.minimum(1.0, x / p)).astype(int)
