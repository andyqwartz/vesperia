"""Télécharge les 20 arrondissements (Paris Open Data) et écrit pipeline/data/arrondissements.geojson."""
import json
import subprocess
from pathlib import Path

import requests

URL = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/arrondissements/exports/geojson"
OUT = Path(__file__).resolve().parent / "data" / "arrondissements.geojson"


def owner():
    r = subprocess.run(["gh", "api", "user", "-q", ".login"], capture_output=True, text=True)
    return r.stdout.strip() or "OWNER"


def number(props):
    for key in ("c_ar", "c_arinsee"):
        if props.get(key) is not None:
            v = int(props[key])
            return v - 75100 if v > 100 else v
    raise SystemExit("ni c_ar ni c_arinsee dans " + json.dumps(props, ensure_ascii=False)[:400])


def main():
    headers = {"User-Agent": f"vesperia/1.0 (+https://github.com/{owner()}/vesperia)"}
    r = requests.get(URL, headers=headers, timeout=60)
    r.raise_for_status()
    src = r.json()["features"]
    for f in src[:3]:
        print(json.dumps(f["properties"], ensure_ascii=False)[:300])
    feats = [{"type": "Feature", "properties": {"arr": number(f["properties"])}, "geometry": f["geometry"]} for f in src]
    feats.sort(key=lambda f: f["properties"]["arr"])
    if [f["properties"]["arr"] for f in feats] != list(range(1, 21)):
        raise SystemExit("il faut 20 arrondissements numérotés de 1 à 20")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False), encoding="utf-8")
    print("écrit", OUT, len(feats), "entités")


if __name__ == "__main__":
    main()