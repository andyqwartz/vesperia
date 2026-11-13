"""Accès réseau et cache disque (règle R8 : tout appel réseau du pipeline passe par ce module)."""
import datetime as dt
import json
import os
import subprocess
import time
from functools import lru_cache
from pathlib import Path

import requests

MIRRORS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
MAX_OSM_AGE_DAYS = 14
DELAYS = (5, 15, 45)


@lru_cache(maxsize=1)
def headers():
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    if not owner:
        try:
            r = subprocess.run(["gh", "repo", "view", "--json", "owner", "--jq", ".owner.login"],
                               capture_output=True, text=True, timeout=20)
            owner = r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            owner = ""
    return {"User-Agent": f"vesperia/1.0 (+https://github.com/{owner or 'OWNER'}/vesperia)"}


def get(url, params=None, timeout=120):
    """GET avec trois essais (attentes de 5 puis 15 s). Renvoie la réponse (statut 200) ou lève RuntimeError."""
    last = "aucune réponse"
    for i, wait in enumerate(DELAYS):
        try:
            r = requests.get(url, params=params, headers=headers(), timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code} {r.text[:200]}"
        except requests.RequestException as e:
            last = str(e)[:200]
        if i < len(DELAYS) - 1:
            time.sleep(wait)
    raise RuntimeError(f"{url} : {last}")


def _osm_age_days(base):
    try:
        t = dt.datetime.strptime(base, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return 0.0
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 86400.0


def overpass(query):
    """Exécute une requête Overpass QL : trois tours (attentes de 5 puis 15 s) sur les deux miroirs, dans l'ordre.
    Rejette les réponses incomplètes, vides ou dont les données OSM ont plus de 14 jours."""
    last = "aucune réponse"
    for i, wait in enumerate(DELAYS):
        for url in MIRRORS:
            try:
                r = requests.post(url, data={"data": query}, headers=headers(), timeout=330)
                if r.status_code != 200:
                    last = f"{url} : HTTP {r.status_code} {r.text[:120]}"
                    continue
                d = r.json()
            except (requests.RequestException, ValueError) as e:
                last = f"{url} : {str(e)[:160]}"
                continue
            if d.get("remark"):
                last = f"{url} : remarque Overpass : {str(d['remark'])[:160]}"
                continue
            base = (d.get("osm3s") or {}).get("timestamp_osm_base", "")
            if _osm_age_days(base) > MAX_OSM_AGE_DAYS:
                last = f"{url} : données OSM vieilles de plus de {MAX_OSM_AGE_DAYS} jours ({base})"
                continue
            if not d.get("elements"):
                last = f"{url} : aucun élément"
                continue
            return d
        if i < len(DELAYS) - 1:
            time.sleep(wait)
    raise RuntimeError("Overpass a échoué : " + last)


def cached_json(path, producer, cache_only, reuse_days=2.0):
    """Lit path si cache_only (erreur claire s'il manque). Sinon réutilise un cache récent, ou appelle producer() et l'écrit."""
    path = Path(path)
    if cache_only:
        if not path.exists():
            raise SystemExit(f"cache absent : {path.name}. Lance d'abord la commande sans --cache-only.")
        return json.loads(path.read_text(encoding="utf-8"))
    if path.exists() and (time.time() - path.stat().st_mtime) / 86400.0 <= reuse_days:
        return json.loads(path.read_text(encoding="utf-8"))
    obj = producer()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return obj
