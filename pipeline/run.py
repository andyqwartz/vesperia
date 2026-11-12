"""Point d'entrée : python pipeline/run.py --mode fixture|real [--only poi,road,bike,rail] [--cache-only] --out DIR"""
import argparse
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vesperia.assemble import ORDER, assemble  # noqa: E402
from vesperia.grid import cell_center, paris_cells  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["fixture", "real"], required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--cache-only", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.mode == "fixture":
        from make_fixture import build
        build(out)
        return
    cache = HERE / "cache"
    cache.mkdir(exist_ok=True)
    cells = paris_cells(9)
    centers = [cell_center(c) for c in cells]
    ids = [x for x in a.only.split(",") if x] or ORDER
    built = []
    for sid in ids:
        mod = importlib.import_module(f"vesperia.sources.{sid}")
        src = mod.build(cells, centers, cache, a.cache_only)
        built.append(src)
        if a.only:
            (out / f"src_{sid}.json").write_text(json.dumps(src, ensure_ascii=False), encoding="utf-8")
    if a.only:
        return
    from vesperia.sources import events as ev
    assemble(built, ev.build(cache, a.cache_only), cells, out, "real")


if __name__ == "__main__":
    main()