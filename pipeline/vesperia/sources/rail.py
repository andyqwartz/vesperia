"""Source MÉTRO : densité des accès au réseau ferré (OpenStreetMap) multipliée par le profil horaire moyen des validations (IDFM)."""
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from vesperia.assemble import LABELS, WEIGHTS
from vesperia.kernel import spread_sum
from vesperia.normalize import to_percent
from vesperia.sources import net, ods
from vesperia.sources.poi_profiles import element_point, overpass_transit_query

PORTALS = ["https://data.iledefrance.fr", "https://data.iledefrance-mobilites.fr"]
TERMS = ("profils horaires", "ferre")  # mots que doit contenir le titre du jeu de données (sans accents, en minuscules)
# ADAPTER : noms de champs et codes de jours, à ne modifier que pour refléter le schéma observé à l'étape R5 de la phase 5.
F_DAY, F_HOUR, F_SHARE = "cat_jour", "trnc_horr_60", "pourcentage_validations"
DAY_CAT = ["JOHV", "JOHV", "JOHV", "JOHV", "JOHV", "SAHV", "DIJFP"]  # lundi à dimanche
RAILWAY = {"station", "subway_entrance", "tram_stop", "halt"}
SIGMA_M = 400.0


def plain(text):
    return "".join(c for c in unicodedata.normalize("NFKD", str(text)) if not unicodedata.combining(c)).lower()


def pick_datasets(payload, terms=TERMS):
    """(identifiant, titre) des jeux de données dont le titre contient tous les mots, du plus récent au plus ancien."""
    out = []
    for d in payload.get("datasets") or []:
        title = (d.get("metas") or {}).get("title", "")
        if d.get("datasetid") and all(t in plain(title) for t in terms):
            out.append((d["datasetid"], title))
    return out


def week_from_rows(rows):
    """Profil moyen des 168 heures de la semaine, de 0 à 1, depuis des lignes (catégorie de jour, tranche « 15H-16H », part)."""
    acc = {}
    for r in rows:
        m = re.match(r"\s*(\d+)\s*H", str(r.get(F_HOUR, "")), re.I)
        try:
            share = float(r.get(F_SHARE))
        except (TypeError, ValueError):
            continue
        if not m or not 0 <= int(m.group(1)) <= 23:
            continue
        s = acc.setdefault((str(r.get(F_DAY, "")).strip().upper(), int(m.group(1))), [0.0, 0])
        s[0] += share
        s[1] += 1
    seen = sorted({k[0] for k in acc})
    week = []
    for d in range(7):
        for h in range(24):
            s = acc.get((DAY_CAT[d], h))
            week.append(s[0] / s[1] if s else 0.0)
    for cat in dict.fromkeys(DAY_CAT):
        if sum(1 for h in range(24) if (cat, h) in acc) < 15:
            raise RuntimeError(f"profil ferré : catégorie {cat} absente ou incomplète ; catégories observées : {seen}")
    top = max(week) or 1.0
    return [round(x / top, 4) for x in week]


def fetch_profile():
    last = "aucune réponse"
    for portal in PORTALS:
        try:
            r = net.get(f"{portal}/api/datasets/1.0/search/", params={"q": "profils horaires ferré", "rows": 50, "sort": "-modified"})
            found = pick_datasets(r.json())
        except (RuntimeError, ValueError) as e:
            last = str(e)[:200]
            continue
        if found:
            ident, title = found[0]
            rows = ods.export_json(f"{portal}/api/explore/v2.1/catalog/datasets", ident, [F_DAY, F_HOUR, F_SHARE])
            return {"dataset": ident, "title": title, "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "week": week_from_rows(rows)}
    raise RuntimeError("aucun jeu « profils horaires » du réseau ferré trouvé sur " + " ni ".join(PORTALS) + " ; dernière erreur : " + last)


def rail_points(elements):
    """Positions (lat, lon) des stations, entrées de métro, arrêts de tramway et haltes."""
    out = []
    for e in elements:
        if (e.get("tags") or {}).get("railway") in RAILWAY:
            p = element_point(e)
            if p:
                out.append(p)
    return out


def build(cells, centers, cache, cache_only):
    cache = Path(cache)
    prof = net.cached_json(cache / "rail_profile.json", fetch_profile, cache_only)
    transit = net.cached_json(cache / "overpass_transit.json", lambda: net.overpass(overpass_transit_query()), cache_only)
    pts = rail_points(transit["elements"])
    if not pts:
        raise SystemExit("rail : aucun accès au réseau ferré dans la réponse Overpass")
    density, cov = spread_sum(centers, pts, np.ones((len(pts), 1)), SIGMA_M)
    field = density @ np.asarray(prof["week"], dtype=float)[None, :]
    data = to_percent(field, 99.0)
    return {"id": "rail", "label": LABELS["rail"], "weight": WEIGHTS["rail"], "n_inputs": len(pts),
            "cov": [float(c) for c in cov], "data": data.tolist(), "updated": prof["fetched"]}
