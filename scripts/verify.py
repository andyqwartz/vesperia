#!/usr/bin/env python3
"""Gate Vesperia — FICHIER FOURNI (règle R2) : ne jamais le modifier.

Usage :
  python3 scripts/verify.py N            gate de la phase N (0 à 8) ; code de sortie 0 si GATE N: PASS
  python3 scripts/verify.py --validate DIR [--mode fixture|real]   valide les JSON de DIR (meta, cells, activity, events)
  python3 scripts/verify.py --guard-init  enregistre l'empreinte des fichiers protégés (appelé par bootstrap.sh)

Bibliothèque standard uniquement. Quand le gate passe, il écrit lui-même la ligne
`PHASE N OK date hash` dans memory-bank/progress.md.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / ".venv" / "bin" / "python"
SOURCES = ["road", "bike", "rail", "poi"]
LABELS = {"road": "VOIRIE", "bike": "VÉLO", "rail": "MÉTRO", "poi": "COMMERCES"}
WEIGHTS = {"road": 0.30, "bike": 0.15, "rail": 0.30, "poi": 0.25}
PROTECTED = [
    "scripts/verify.py", "scripts/smoke.mjs", "scripts/brief.sh", "pipeline/tests/test_golden.py",
    "pipeline/vesperia/sources/poi_profiles.py", ".github/workflows/pages.yml", "pytest.ini",
]
GUARD = ROOT / ".git" / "vesperia-guard.sha256"
DEADLINE = time.time() + int(os.environ.get("VESPERIA_GATE_SECONDS", "270"))  # 270 s : marge sous le délai de 5 min de /goal gate ; plus long à la main
GATE = [None]  # numéro du gate en cours (renseigné par run_gate)
RESULTS = []  # (statut, nom, détail)
CHECKS = []   # (since, only, nom, fonction)


# ------------------------------------------------------------------ utilitaires

def remaining():
    return max(5, int(DEADLINE - time.time()))


def sh(cmd, timeout=120, cwd=None, env=None):
    timeout = min(timeout, remaining())
    try:
        p = subprocess.run(cmd, cwd=str(cwd or ROOT), capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"délai dépassé ({timeout}s)"
    except FileNotFoundError as e:
        return 127, str(e)


def tail(text, n=4):
    lines = [x for x in text.strip().splitlines() if x.strip()]
    return " | ".join(x.strip()[:160] for x in lines[-n:])


def check(since=0, only=None):
    def deco(fn):
        CHECKS.append((since, only, fn.__name__[2:].replace("_", " "), fn))
        return fn
    return deco


class Fail(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Fail(msg)


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        raise Fail(f"{path} illisible : {e}")


def venv_run(args, timeout=120, extra_env=None):
    need(VENV_PY.exists(), ".venv/bin/python absent (relance bootstrap.sh)")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "pipeline")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra_env or {})
    return sh([str(VENV_PY)] + args, timeout=timeout, env=env)


def git(*args, timeout=30):
    return sh(["git"] + list(args), timeout=timeout)


def repo_slug():
    rc, out = git("remote", "get-url", "origin")
    need(rc == 0, "pas de remote origin (gh repo create vesperia --public --source . --remote origin)")
    m = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?\s*$", out.strip())
    need(m and m.group(2) == "vesperia", f"origin doit pointer vers github.com/OWNER/vesperia (vu : {out.strip()})")
    return m.group(1), m.group(2)


# ------------------------------------------------------------------ validation des données

HEX_RE = re.compile(r"^89[0-9a-f]{13}$")
ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def parse_z(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validate_activity_rows(rows, n, label):
    need(isinstance(rows, list) and len(rows) == n, f"{label} : {n} lignes attendues")
    for r in rows:
        need(isinstance(r, list) and len(r) == 168, f"{label} : chaque ligne doit avoir 168 valeurs")
        for v in r:
            need(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100, f"{label} : entiers de 0 à 100 attendus (vu {v!r})")


def city_mean(rows, wh):
    return sum(r[wh] for r in rows) / len(rows)


def validate_data(d, mode=None):
    """Valide meta/cells/activity/events dans le dossier d. Renvoie la liste des messages d'erreur."""
    d = Path(d)
    errs = []
    try:
        meta = read_json(d / "meta.json")
        cells = read_json(d / "cells.json")
        act = read_json(d / "activity.json")
        events = read_json(d / "events.json")
    except Fail as e:
        return [str(e)]
    try:
        need(meta.get("version") == 1, "meta.version doit valoir 1")
        need(meta.get("mode") in ("fixture", "real"), "meta.mode doit valoir fixture ou real")
        if mode:
            need(meta["mode"] == mode, f"meta.mode doit valoir {mode} (vu {meta['mode']})")
        need(isinstance(meta.get("generated_at"), str) and ISO_Z.match(meta["generated_at"]), "meta.generated_at : ISO 8601 UTC terminé par Z")
        need(meta.get("h3_res") == 9, "meta.h3_res doit valoir 9")
        n = len(cells.get("h", []))
        need(900 <= n <= 1200, f"nombre de cellules {n} hors de 900..1200")
        need(meta.get("n_cells") == n, "meta.n_cells doit égaler len(cells.h)")
        srcs = meta.get("sources")
        need(isinstance(srcs, list) and [s.get("id") for s in srcs] == SOURCES, "meta.sources : ordre road, bike, rail, poi")
        for s in srcs:
            for k in ("id", "label", "weight", "n_inputs", "updated"):
                need(k in s, f"meta.sources[{s.get('id')}] sans clé {k}")
            need(s["label"] == LABELS[s["id"]], f"libellé de {s['id']} : {LABELS[s['id']]}")
            need(abs(s["weight"] - WEIGHTS[s["id"]]) < 1e-9, f"poids par défaut de {s['id']} : {WEIGHTS[s['id']]}")
            need(isinstance(s["n_inputs"], int) and s["n_inputs"] >= 0, "n_inputs entier positif")
        need(isinstance(meta.get("attribution"), list) and meta["attribution"] and all(isinstance(x, str) for x in meta["attribution"]), "meta.attribution : liste de chaînes non vide")
        # cells.json
        for k in ("h", "lat", "lon", "poly", "arr", "outdoor", "isolated", "confidence", "cov"):
            need(k in cells, f"cells.json sans clé {k}")
            if k != "cov":
                need(len(cells[k]) == n, f"cells.{k} : {n} éléments attendus")
        need(cells["h"] == sorted(cells["h"]) and len(set(cells["h"])) == n, "cells.h doit être trié et sans doublon")
        need(all(HEX_RE.match(h) for h in cells["h"]), "cells.h : identifiants H3 de niveau 9 (15 caractères hexadécimaux commençant par 89)")
        for i in range(n):
            lat, lon = cells["lat"][i], cells["lon"][i]
            need(is_num(lat) and 48.80 <= lat <= 48.91 and is_num(lon) and 2.21 <= lon <= 2.48, f"cellule {i} hors de Paris : {lat},{lon}")
            poly = cells["poly"][i]
            need(len(poly) == 7 and poly[0] == poly[-1], f"cellule {i} : anneau de 7 points fermé attendu")
            for p in poly:
                need(len(p) == 2 and abs(p[0] - lon) < 0.01 and abs(p[1] - lat) < 0.01, f"cellule {i} : points [lon, lat] attendus près du centre")
            need(isinstance(cells["arr"][i], int) and 0 <= cells["arr"][i] <= 20, "arr : entier de 0 à 20")
            need(is_num(cells["outdoor"][i]) and 0 <= cells["outdoor"][i] <= 1, "outdoor : de 0 à 1")
            need(cells["isolated"][i] in (0, 1), "isolated : 0 ou 1")
            need(is_num(cells["confidence"][i]) and 0 <= cells["confidence"][i] <= 1, "confidence : de 0 à 1")
        need(isinstance(cells["cov"], dict) and sorted(cells["cov"]) == sorted(SOURCES), "cells.cov : clés road, bike, rail, poi")
        for s in SOURCES:
            need(len(cells["cov"][s]) == n and all(is_num(v) and 0 <= v <= 1 for v in cells["cov"][s]), f"cells.cov.{s} : {n} valeurs de 0 à 1")
        wsum = sum(WEIGHTS.values())
        for i in range(n):
            exp = sum(WEIGHTS[s] * cells["cov"][s][i] for s in SOURCES) / wsum
            need(abs(cells["confidence"][i] - exp) <= 0.011, f"confidence de la cellule {i} incohérente avec la formule (attendu {exp:.3f}, vu {cells['confidence'][i]})")
        need(sum(cells["arr"]) > 0, "arr : aucun arrondissement renseigné")
        need(sum(cells["isolated"]) < n, "isolated : toutes les cellules sont isolées")
        # activity.json
        need(act.get("sources") == SOURCES, "activity.sources : road, bike, rail, poi")
        need(sorted(act.get("data", {})) == sorted(SOURCES), "activity.data : clés road, bike, rail, poi")
        for s in SOURCES:
            validate_activity_rows(act["data"][s], n, f"activity.{s}")
            rows = act["data"][s]
            night, day = city_mean(rows, 27), city_mean(rows, 35)  # mardi 03h, mardi 11h
            need(day > night + 3, f"source {s} : l'activité du mardi 11h ({day:.1f}) doit dépasser celle du mardi 3h ({night:.1f}) de plus de 3")
            need(max(max(r) for r in rows) >= 60, f"source {s} : activité maximale trop faible (< 60)")
        # events.json
        need(isinstance(events, list) and len(events) <= 5000, "events.json : liste de 5000 éléments au plus")
        gen = parse_z(meta["generated_at"])
        for e in events:
            for k in ("t", "lat", "lon", "s", "e"):
                need(k in e, f"événement sans clé {k}")
            need(ISO_Z.match(e["s"]) and ISO_Z.match(e["e"]) and parse_z(e["s"]) < parse_z(e["e"]), "événement : s < e en ISO UTC")
            need(is_num(e["lat"]) and 48.7 <= e["lat"] <= 49.0 and is_num(e["lon"]) and 2.1 <= e["lon"] <= 2.6, "événement hors de la région parisienne")
        if meta["mode"] == "fixture":
            need(len(events) >= 20, "fixture : au moins 20 événements")
            near = [e for e in events if gen - datetime.timedelta(days=2) <= parse_z(e["s"]) <= gen + datetime.timedelta(days=21)]
            need(len(near) >= 20, "fixture : au moins 20 événements dans la fenêtre generated_at -2 j / +21 j")
        else:
            need(len(events) >= 10, "real : au moins 10 événements")
        size = sum((d / f).stat().st_size for f in ("meta.json", "cells.json", "activity.json", "events.json"))
        need(size < 12 * 1024 * 1024, f"taille totale {size / 1e6:.1f} Mo ≥ 12 Mo")
        if meta["mode"] == "real":
            thr = {"poi": 10000, "road": 800, "bike": 20, "rail": 100}
            covthr = {"road": (0.5), "bike": (0.15), "rail": (0.4)}
            for s in srcs:
                need(s["n_inputs"] >= thr[s["id"]], f"real : n_inputs de {s['id']} = {s['n_inputs']} < {thr[s['id']]}")
            for s, t in covthr.items():
                frac = sum(1 for v in cells["cov"][s] if v > 0.3) / n
                need(frac >= t, f"real : couverture {s} trop faible ({frac:.2f} < {t})")
            need(min(cells["cov"]["poi"]) >= 0.999, "real : cov.poi doit valoir 1.0 partout")
    except Fail as e:
        errs.append(str(e))
    except Exception as e:  # structure inattendue
        errs.append(f"structure invalide ({type(e).__name__}: {e})")
    return errs


def validate_source(path, sid, ncells=None):
    d = read_json(path)
    for k in ("id", "label", "weight", "n_inputs", "cov", "data"):
        need(k in d, f"{Path(path).name} sans clé {k}")
    need(d["id"] == sid and d["label"] == LABELS[sid], f"id/label de {sid} : {LABELS[sid]}")
    need(abs(d["weight"] - WEIGHTS[sid]) < 1e-9, f"weight de {sid} : {WEIGHTS[sid]}")
    n = len(d["cov"])
    need(900 <= n <= 1200, f"{sid} : nombre de cellules {n} hors de 900..1200")
    if ncells:
        need(n == ncells, f"{sid} : {n} cellules au lieu de {ncells} (ordre : sorted(paris_cells(9)))")
    need(all(is_num(v) and 0 <= v <= 1 for v in d["cov"]), f"{sid} : cov de 0 à 1")
    validate_activity_rows(d["data"], n, sid)
    night, day = city_mean(d["data"], 27), city_mean(d["data"], 35)
    need(day > night + 3, f"{sid} : activité du mardi 11h ({day:.1f}) ≤ mardi 3h ({night:.1f}) + 3")
    need(max(max(r) for r in d["data"]) >= 90, f"{sid} : maximum de l'activité < 90 (normalisation to_percent à revoir)")
    thr = {"poi": 10000, "road": 800, "bike": 20, "rail": 100}
    need(d["n_inputs"] >= thr[sid], f"{sid} : n_inputs = {d['n_inputs']} < {thr[sid]}")
    covthr = {"road": 0.5, "bike": 0.15, "rail": 0.4}
    if sid in covthr:
        frac = sum(1 for v in d["cov"] if v > 0.3) / n
        need(frac >= covthr[sid], f"{sid} : couverture {frac:.2f} < {covthr[sid]}")
    if sid == "poi":
        need(min(d["cov"]) >= 0.999, "poi : cov doit valoir 1.0 partout")
        ex = d.get("extra") or {}
        need(len(ex.get("isolated", [])) == n and set(ex["isolated"]) <= {0, 1}, "poi.extra.isolated : N valeurs 0/1")
        need(len(ex.get("outdoor", [])) == n and all(0 <= v <= 1 for v in ex["outdoor"]), "poi.extra.outdoor : N valeurs de 0 à 1")
    return d


# Points de repère pour les tests de bon sens : (lat, lon)
CHATELET = (48.8620, 2.3467)
VINCENNES = (48.8288, 2.4350)
BOULOGNE = (48.8625, 2.2495)


def cell_indexes(points):
    code = (
        "import json,sys,h3\n"
        "from vesperia.grid import paris_cells\n"
        "c=sorted(paris_cells(9));ix={h:i for i,h in enumerate(c)}\n"
        "pts=json.loads(sys.argv[1])\n"
        "print(json.dumps({'n':len(c),'idx':[ix.get(h3.latlng_to_cell(a,b,9),-1) for a,b in pts]}))\n"
    )
    rc, out = venv_run(["-c", code, json.dumps(points)], timeout=60)
    need(rc == 0, "grille H3 inutilisable : " + tail(out))
    return json.loads(out.strip().splitlines()[-1])


def run_pipeline(args, out_dir, timeout=200):
    rc, out = venv_run([str(ROOT / "pipeline" / "run.py")] + args + ["--out", str(out_dir)], timeout=timeout)
    need(rc == 0, "pipeline/run.py " + " ".join(args) + " a échoué : " + tail(out, 5))


# ------------------------------------------------------------------ contrôles

TOOLS_MIN = {"git": None, "gh": None, "node": None}


@check(0, 0)
def c_outils_et_versions():
    for t in TOOLS_MIN:
        need(shutil.which(t), f"outil absent : {t}")
    need(sys.version_info >= (3, 8), "python3 trop ancien")
    rc, out = sh(["node", "--version"])
    need(rc == 0 and int(out.strip().lstrip("v").split(".")[0]) >= 20, f"Node 20 ou plus requis (vu {out.strip()})")
    rc, out = sh(["gh", "auth", "status"], timeout=20)
    need(rc == 0, "gh non authentifié : gh auth login")


@check(0, 0)
def c_environnement_python():
    rc, out = venv_run(["-c", "import numpy, pandas, h3, requests, pytest; print(h3.__version__)"])
    need(rc == 0, "imports numpy/pandas/h3/requests/pytest impossibles dans .venv : " + tail(out))


@check(0, 0)
def c_requirements_epingles():
    p = ROOT / "pipeline" / "requirements.txt"
    need(p.exists(), "pipeline/requirements.txt absent")
    lines = [x.strip() for x in p.read_text().splitlines() if x.strip() and not x.startswith("#")]
    need(lines and all("==" in x for x in lines), "chaque ligne de requirements.txt doit être épinglée avec ==")
    names = {x.split("==")[0].lower() for x in lines}
    need({"numpy", "pandas", "h3", "requests", "pytest"} <= names, "requirements.txt doit contenir numpy, pandas, h3, requests, pytest")


@check(0, 0)
def c_dependances_node():
    pj = read_json(ROOT / "package.json")
    v = pj.get("devDependencies", {}).get("playwright", "")
    need(re.fullmatch(r"\d+\.\d+\.\d+", v), "package.json : playwright doit être épinglé en x.y.z exact (R4)")
    need((ROOT / "package-lock.json").exists(), "package-lock.json absent : lance npm install, puis commite-le")


@check(0, 0)
def c_gitignore_et_memory_bank():
    gi = (ROOT / ".gitignore").read_text() if (ROOT / ".gitignore").exists() else ""
    for e in ("memory-bank/", ".venv/", "node_modules/", "pipeline/cache/", "site/data/", "__pycache__/"):
        need(any(l.strip() == e for l in gi.splitlines()), f".gitignore doit contenir la ligne {e}")
    mb = ROOT / "memory-bank"
    for f in ("projectbrief.md", "productContext.md", "systemPatterns.md", "techContext.md", "activeContext.md", "progress.md"):
        need((mb / f).exists() and (mb / f).stat().st_size >= 400, f"memory-bank/{f} absent ou trop court (< 400 octets)")
    rc, _ = git("check-ignore", "-q", "memory-bank/progress.md")
    need(rc == 0, "memory-bank/ doit être ignoré par git")
    rc, out = git("ls-files", "memory-bank")
    need(rc == 0 and not out.strip(), "des fichiers de memory-bank/ sont suivis par git (git rm -r --cached memory-bank)")


@check(0, 0)
def c_readme():
    p = ROOT / "README.md"
    need(p.exists() and p.stat().st_size >= 300 and "vesperia" in p.read_text().lower(), "README.md absent, trop court ou sans le mot Vesperia")


@check(0, 0)
def c_pages_active_en_mode_workflow():
    owner, repo = repo_slug()
    rc, out = sh(["gh", "api", f"repos/{owner}/{repo}/pages", "--jq", ".build_type"], timeout=30)
    need(rc == 0 and "workflow" in out, f"GitHub Pages inactif ou pas en mode workflow : gh api -X POST repos/{owner}/{repo}/pages -f build_type=workflow")


@check(0)
def c_fichiers_proteges_intacts():
    need(GUARD.exists(), "empreintes absentes (.git/vesperia-guard.sha256) : relance bootstrap.sh")
    expected = {}
    for line in GUARD.read_text().splitlines():
        if line.strip():
            h, p = line.split("  ", 1)
            expected[p] = h
    bad = []
    for p in PROTECTED:
        f = ROOT / p
        if not f.exists():
            bad.append(f"{p} (absent)")
        elif hashlib.sha256(f.read_bytes()).hexdigest() != expected.get(p):
            bad.append(f"{p} (modifié)")
    need(not bad, "fichiers protégés (R2) : " + ", ".join(bad))


@check(0)
def c_git_propre_et_pousse():
    repo_slug()
    rc, out = git("rev-parse", "--abbrev-ref", "HEAD")
    need(out.strip() == "main", f"la branche doit s'appeler main (vue : {out.strip()})")
    rc, out = git("status", "--porcelain")
    need(not out.strip(), "arbre git non propre : git add -A && git commit puis git push — " + tail(out, 3))
    rc, local = git("rev-parse", "HEAD")
    rc2, remote = git("ls-remote", "origin", "HEAD", timeout=30)
    need(rc2 == 0 and remote.split() and remote.split()[0] == local.strip(), "HEAD n'est pas poussé sur origin (git push)")


def source_files(globs):
    out = []
    for g in globs:
        out += [p for p in ROOT.glob(g) if p.is_file()]
    return sorted(set(out))


@check(1)
def c_taille_et_absence_de_stubs():
    prot = {str(ROOT / p) for p in PROTECTED}
    bad = []
    for p in source_files(["pipeline/**/*.py", "site/**/*.js", "site/**/*.css"]):
        if str(p) in prot or "/cache/" in str(p):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        n = len(text.splitlines())
        limit = 300 if p.suffix == ".py" else 400
        if n > limit:
            bad.append(f"{p.relative_to(ROOT)} : {n} lignes > {limit}")
        if re.search(r"NotImplementedError|#\s*TODO|//\s*TODO|\bFIXME\b", text):
            bad.append(f"{p.relative_to(ROOT)} : stub (TODO/NotImplementedError)")
    need(not bad, "; ".join(bad[:5]))


@check(1)
def c_phase1_fichiers_et_arrondissements():
    for f in ("pipeline/run.py", "pipeline/make_fixture.py", "pipeline/vesperia/timeidx.py", "pipeline/vesperia/grid.py", "pipeline/MODE"):
        need((ROOT / f).exists(), f"fichier absent : {f}")
    need((ROOT / "pipeline/MODE").read_text().strip() in ("fixture", "real"), "pipeline/MODE doit contenir fixture ou real")
    g = read_json(ROOT / "pipeline/data/arrondissements.geojson")
    need(g.get("type") == "FeatureCollection" and len(g.get("features", [])) == 20, "arrondissements.geojson : FeatureCollection de 20 entités")
    try:
        nums = sorted(int(f["properties"]["arr"]) for f in g["features"])
    except Exception:
        nums = []
    need(nums == list(range(1, 21)), "arrondissements.geojson : chaque entité doit porter properties.arr (entier), de 1 à 20 sans doublon")
    need(all(f["geometry"]["type"] in ("Polygon", "MultiPolygon") for f in g["features"]), "arrondissements.geojson : géométries Polygon ou MultiPolygon attendues")


@check(1)
def c_tests_dores_phase1():
    rc, out = venv_run(["-m", "pytest", "-m", "phase1"], timeout=100)
    need(rc == 0, "pytest -m phase1 : " + tail(out))


@check(1)
def c_fixture_conforme_au_contrat():
    with tempfile.TemporaryDirectory() as t:
        run_pipeline(["--mode", "fixture"], t, timeout=120)
        errs = validate_data(t, "fixture")
        need(not errs, errs[0] if errs else "")


@check(2)
def c_site_statique_et_epingles():
    for f in ("index.html", "css/style.css", "js/app.js", "js/data.js", "js/state.js", "js/map.js", "js/hud.js", "js/basemap.js"):
        need((ROOT / "site" / f).exists(), f"site/{f} absent")
    idx = (ROOT / "site/index.html").read_text(encoding="utf-8")
    need("maplibre-gl@5.24.0" in idx and "deck.gl@9.3.3" in idx, "index.html doit charger maplibre-gl@5.24.0 et deck.gl@9.3.3 (CDN épinglés)")
    allsrc = ""
    for p in source_files(["site/*.html", "site/js/*.js", "site/css/*.css"]):
        t = p.read_text(encoding="utf-8")
        allsrc += t
        bad = re.findall(r"""(?:src|href)\s*=\s*["']/(?!/)|url\(\s*["']?/(?!/)|fetch\(\s*["'`]/(?!/)|import\s*\(?\s*["']/(?!/)|from\s+["']/(?!/)""", t)
        if bad:
            raise Fail(f"{p.relative_to(ROOT)} : URL absolue interdite par R6 ({bad[0]!r})")
    need("@latest" not in allsrc, "version @latest interdite (R4)")
    need("openfreemap" in allsrc.lower(), "basemap.js doit utiliser le style OpenFreeMap")


def ensure_fixture_in_site():
    run_pipeline(["--mode", "fixture"], ROOT / "site" / "data", timeout=120)


def run_smoke(extra=None, timeout=215):
    ensure_fixture_in_site()
    rc, out = sh(["node", "scripts/smoke.mjs", "--site", "site", "--base", "/vesperia/", "--timeout", "200"] + (extra or []), timeout=timeout)
    need(rc == 0, "smoke : " + tail(out, 5))


@check(2)
def c_test_de_fumee_du_site():
    # Le test de fumée est lent (rendu logiciel) : le gate ne le rejoue que pour la phase 2. Ensuite, chaque push le rejoue en CI
    # (pages.yml), la phase 7 l'élargit, et la phase 8 le lance sur le site publié.
    if GATE[0] == 2:
        run_smoke()


def wait_deploy(expect_mode, wait=170):
    owner, repo = repo_slug()
    rc, head = git("rev-parse", "HEAD")
    head = head.strip()
    t0 = time.time()
    state = "aucun run trouvé pour HEAD"
    while True:
        rc, out = sh(["gh", "run", "list", "--workflow", "pages.yml", "--limit", "10", "--json", "headSha,status,conclusion"], timeout=30)
        runs = json.loads(out) if rc == 0 and out.strip().startswith("[") else []
        mine = [r for r in runs if r.get("headSha") == head]
        if mine:
            r = mine[0]
            if r["status"] == "completed":
                need(r["conclusion"] == "success", f"le run CI de HEAD a échoué ({r['conclusion']}) : gh run view --log-failed")
                break
            state = f"run CI en cours ({r['status']})"
        if time.time() - t0 > wait or remaining() < 20:
            raise Fail(f"{state} — attends 3 minutes (sleep 180) puis relance le gate")
        time.sleep(15)
    base = f"https://{owner}.github.io/{repo}/"
    last = ""
    for _ in range(8):
        try:
            with urllib.request.urlopen(base + "data/meta.json", timeout=20) as r:
                meta = json.loads(r.read().decode("utf-8"))
            with urllib.request.urlopen(base, timeout=20) as r:
                need(r.status == 200, "page d'accueil non servie")
            if expect_mode:
                need(meta.get("mode") == expect_mode, f"le site déployé est en mode {meta.get('mode')} (attendu {expect_mode})")
                if expect_mode == "real":
                    age = (datetime.datetime.now(datetime.timezone.utc) - parse_z(meta["generated_at"])).days
                    need(age <= 10, f"données déployées vieilles de {age} jours")
            return
        except Fail:
            raise
        except Exception as e:
            last = str(e)
            time.sleep(8)
    raise Fail("site déployé injoignable : " + last)


@check(2, 2)
def c_deploiement_pages_fixture():
    wait_deploy(None)


@check(3)
def c_phase3_tests_dores():
    rc, out = venv_run(["-m", "pytest", "-m", "phase1 or phase3"], timeout=100)
    need(rc == 0, "pytest phase1+phase3 : " + tail(out))


def check_source(sid, extra_checks=None):
    with tempfile.TemporaryDirectory() as t:
        run_pipeline(["--mode", "real", "--only", sid, "--cache-only"], t, timeout=200)
        path = Path(t) / f"src_{sid}.json"
        need(path.exists(), f"src_{sid}.json non écrit")
        info = cell_indexes([CHATELET, VINCENNES, BOULOGNE])
        need(min(info["idx"]) >= 0, "points de repère hors grille")
        d = validate_source(path, sid, info["n"])
        if extra_checks:
            extra_checks(d, info["idx"])


@check(3, 3)
def c_source_commerces_osm():
    def hub(d, idx):
        c, v, b = idx
        wh = 35
        need(d["data"][c][wh] > d["data"][v][wh] and d["data"][c][wh] > d["data"][b][wh], "poi : Châtelet doit être plus actif que les bois (mardi 11h)")
        need(sum(d["extra"]["isolated"]) / len(d["extra"]["isolated"]) < 0.6, "poi : plus de 60 % de cellules isolées, suspect")
        need(max(d["extra"]["outdoor"]) > 0.3, "poi : indicateur de plein air nul partout")
    check_source("poi", hub)


@check(4)
def c_phase4_tests_dores():
    rc, out = venv_run(["-m", "pytest", "-m", "phase1 or phase3 or phase4"], timeout=100)
    need(rc == 0, "pytest phases 1, 3, 4 : " + tail(out))


@check(4, 4)
def c_sources_voirie_et_velo():
    check_source("road")
    check_source("bike")


@check(5, 5)
def c_source_metro():
    def hub(d, idx):
        c, v, b = idx
        need(d["data"][c][35] > d["data"][v][35], "rail : Châtelet doit dépasser le bois de Vincennes (mardi 11h)")
        need(city_mean(d["data"], 27) < 0.5 * city_mean(d["data"], 35), "rail : le métro doit être quasi vide la nuit (mardi 3h < moitié de 11h)")
    check_source("rail", hub)


@check(5)
def c_phase5_tests_dores():
    rc, out = venv_run(["-m", "pytest", "-m", "phase1 or phase3 or phase4 or phase5"], timeout=100)
    need(rc == 0, "pytest phases 1, 3, 4, 5 : " + tail(out))


@check(5, 5)
def c_assemblage_reel_hors_ligne():
    with tempfile.TemporaryDirectory() as t:
        run_pipeline(["--mode", "real", "--cache-only"], t, timeout=240)
        errs = validate_data(t, "real")
        need(not errs, errs[0] if errs else "")


@check(6, 6)
def c_mode_reel_en_ci():
    need((ROOT / "pipeline/MODE").read_text().strip() == "real", "pipeline/MODE doit contenir real")
    wait_deploy("real")


@check(7)
def c_phase7_fonctions_vivantes():
    for f in ("js/weather.js", "js/audio.js"):
        need((ROOT / "site" / f).exists(), f"site/{f} absent")
    need('id="listen"' in (ROOT / "site/index.html").read_text(encoding="utf-8"), 'index.html doit contenir id="listen"')
    if GATE[0] == 7:
        run_smoke(["--require", "weather,events,listen"])


@check(7, 7)
def c_deploiement_reel_phase7():
    wait_deploy("real")


@check(8, 8)
def c_audit_final():
    owner, repo = repo_slug()
    rc, out = sh(["gh", "repo", "view", f"{owner}/{repo}", "--json", "visibility", "--jq", ".visibility"], timeout=30)
    need(rc == 0 and out.strip().upper() == "PUBLIC", "le dépôt doit être public pour GitHub Pages")
    prog = (ROOT / "memory-bank/progress.md").read_text()
    for n in range(8):
        need(re.search(rf"^PHASE {n} OK \d{{4}}-\d{{2}}-\d{{2}} [0-9a-f]{{7,}}", prog, re.M), f"progress.md : ligne PHASE {n} OK absente (relance le gate {n})")
    blob = ""
    for p in source_files(["site/*.html", "site/js/*.js", "README.md"]):
        blob += p.read_text(encoding="utf-8")
    for name in ("OpenStreetMap", "Open-Meteo", "Île-de-France Mobilités", "Ville de Paris", "OpenFreeMap"):
        need(name in blob, f"attribution manquante dans le site ou le README : {name}")
    need("a priori statistique" in blob.lower(), "le site ou le README doit préciser que l'indice est un a priori statistique")
    for p in source_files(["pipeline/**/*.py", "site/**/*.js", "site/*.html", "README.md", ".github/workflows/*.yml"]):
        need("sk-or-" not in p.read_text(encoding="utf-8", errors="replace"), f"clé OpenRouter trouvée dans {p.relative_to(ROOT)}")
    readme = (ROOT / "README.md").read_text().lower()
    for kw in ("usage", "sources", "limites"):
        need(kw in readme, f"README.md : section « {kw} » absente")
    owner, repo = repo_slug()
    rc, out = sh(["node", "scripts/smoke.mjs", "--url", f"https://{owner}.github.io/{repo}/", "--require", "weather,events,listen", "--live-basemap", "--timeout", "200"], timeout=215)
    need(rc == 0, "smoke sur le site déployé : " + tail(out, 5))


# ------------------------------------------------------------------ exécution

def guard_init():
    lines = []
    for p in PROTECTED:
        f = ROOT / p
        if not f.exists():
            print(f"[FAIL] fichier protégé absent : {p}")
            return 1
        lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {p}")
    GUARD.parent.mkdir(parents=True, exist_ok=True)
    GUARD.write_text("\n".join(lines) + "\n")
    print(f"[OK] {len(lines)} empreintes écrites dans .git/vesperia-guard.sha256")
    return 0


def stamp_progress(n):
    mb = ROOT / "memory-bank" / "progress.md"
    if not mb.exists():
        return
    rc, h = git("rev-parse", "--short", "HEAD")
    line = f"PHASE {n} OK {datetime.date.today().isoformat()} {h.strip()}"
    cur = mb.read_text()
    if line not in cur:
        mb.write_text(cur.rstrip("\n") + "\n" + line + "\n")


def run_gate(n):
    GATE[0] = n
    print(f"VERIFY phase {n} — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    fails = 0
    total = 0
    for since, only, name, fn in CHECKS:
        if since > n or (only is not None and only != n):
            continue
        total += 1
        t0 = time.time()
        try:
            if remaining() <= 6:
                raise Fail("temps du gate épuisé : relance-le une fois ; si le message revient, applique la règle R11")
            fn()
            print(f"[OK]   {name} ({time.time() - t0:.0f}s)")
        except Fail as e:
            fails += 1
            print(f"[FAIL] {name} — {str(e)[:420]}")
        except Exception as e:
            fails += 1
            print(f"[FAIL] {name} — erreur inattendue du contrôle : {type(e).__name__}: {str(e)[:200]}")
    if fails:
        print(f"GATE {n}: FAIL ({fails} échec(s) sur {total})")
        return 1
    stamp_progress(n)
    print(f"GATE {n}: PASS ({total} contrôles)")
    return 0


def main(argv):
    if len(argv) >= 2 and argv[1] == "--guard-init":
        return guard_init()
    if len(argv) >= 3 and argv[1] == "--validate":
        mode = argv[argv.index("--mode") + 1] if "--mode" in argv else None
        errs = validate_data(argv[2], mode)
        for e in errs:
            print("[FAIL]", e)
        print("VALIDATE:", "FAIL" if errs else "PASS")
        return 1 if errs else 0
    if len(argv) == 2 and argv[1].isdigit() and 0 <= int(argv[1]) <= 8:
        return run_gate(int(argv[1]))
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))