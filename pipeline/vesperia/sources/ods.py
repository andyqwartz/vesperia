"""Outils communs aux jeux de données Opendatasoft (Paris Open Data, Île-de-France Mobilités) et profils hebdomadaires."""
import datetime as dt
import warnings

import numpy as np

from vesperia.sources import net
from vesperia.timeidx import PARIS, week_hour, week_hour_from_period_end

PARIS_BASE = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets"
IDFM_BASE = "https://data.iledefrance-mobilites.fr/api/explore/v2.1/catalog/datasets"


def parse_ts(value):
    """Texte ISO (avec ou sans fuseau) -> datetime avec fuseau. Sans fuseau, l'heure est supposée locale (Europe/Paris)."""
    t = dt.datetime.fromisoformat(str(value).strip().replace(" ", "T"))
    return t.replace(tzinfo=PARIS) if t.tzinfo is None else t


def point_of(v):
    """Position (lat, lon) depuis {"lat": .., "lon": ..} ou depuis le texte "lat, lon" ; None sinon."""
    try:
        if isinstance(v, dict):
            return float(v["lat"]), float(v["lon"])
        if isinstance(v, str) and "," in v:
            a, b = v.split(",", 1)
            return float(a), float(b)
    except (KeyError, ValueError, TypeError):
        pass
    return None


def latest(base, dataset, field):
    """Valeur la plus récente (datetime) du champ date field d'un jeu de données."""
    r = net.get(f"{base}/{dataset}/records", params={"select": field, "order_by": f"{field} desc", "limit": 1})
    res = r.json().get("results") or []
    if not res or res[0].get(field) is None:
        keys = sorted(res[0]) if res else "aucun résultat"
        raise RuntimeError(f"{dataset} : champ {field} introuvable ; clés observées : {keys}")
    return parse_ts(res[0][field])


def export_json(base, dataset, select, where=None, timeout=900):
    """Export complet (liste d'objets) des champs select, filtré par where (langage de requête Opendatasoft)."""
    params = {"select": ",".join(select), "limit": -1}
    if where:
        params["where"] = where
    data = net.get(f"{base}/{dataset}/exports/json", params=params, timeout=timeout).json()
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"{dataset} : export vide ou inattendu ({type(data).__name__})")
    return data


def fill_week(v):
    """Remplace les NaN d'une semaine de 168 valeurs par la moyenne de la même heure sur les autres jours, sinon par la moyenne globale."""
    v = np.asarray(v, dtype=float).copy()
    bad = np.isnan(v)
    if not bad.any():
        return v
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        by_hour = np.nanmean(v.reshape(7, 24), axis=0)
        overall = np.nanmean(v)
    by_hour = np.where(np.isnan(by_hour), overall, by_hour)
    for i in np.nonzero(bad)[0]:
        v[i] = by_hour[i % 24]
    return v


def week_profiles(rows, id_key, time_key, value_key, point_key, period_end, min_hours=100):
    """Profil moyen par heure de la semaine et par capteur : liste triée de {id, lat, lon, v (168 valeurs)}.
    Écarte les capteurs sans position, ceux qui couvrent moins de min_hours heures de la semaine et ceux toujours à zéro."""
    to_wh = week_hour_from_period_end if period_end else week_hour
    acc = {}
    for r in rows:
        sid, t, x, p = r.get(id_key), r.get(time_key), r.get(value_key), point_of(r.get(point_key))
        if sid is None or t is None or x is None or p is None:
            continue
        try:
            wh, x = to_wh(parse_ts(t)), float(x)
        except (ValueError, TypeError):
            continue
        if x < 0:
            continue
        s = acc.setdefault(sid, {"p": p, "sum": np.zeros(168), "n": np.zeros(168)})
        s["sum"][wh] += x
        s["n"][wh] += 1
    out = []
    for sid, s in acc.items():
        ok = s["n"] > 0
        if ok.sum() < min_hours:
            continue
        v = np.full(168, np.nan)
        v[ok] = s["sum"][ok] / s["n"][ok]
        v = fill_week(v)
        if v.max() <= 0:
            continue
        out.append({"id": str(sid), "lat": s["p"][0], "lon": s["p"][1], "v": [round(float(x), 2) for x in v]})
    return sorted(out, key=lambda d: d["id"])
