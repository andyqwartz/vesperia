#!/usr/bin/env bash
# Amorçage Vesperia — FICHIER FOURNI. À lancer une seule fois depuis le dossier VESPERIA :
#   cd /Users/andy/Documents/VESPERIA && bash bootstrap.sh
# Relançable sans danger. BOOTSTRAP_OFFLINE=1 saute les étapes réseau (tests uniquement).
set -euo pipefail
cd "$(dirname "$0")"
OFFLINE="${BOOTSTRAP_OFFLINE:-0}"
die() { printf 'ERREUR : %s\n' "$*" >&2; exit 1; }
say() { printf '• %s\n' "$*"; }

# 1. Fichiers fournis : déposés à côté de ce script, rangés ici à leur place définitive.
place() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [ -f "$src" ]; then mv -f "$src" "$dest"
  elif [ ! -f "$dest" ]; then die "fichier manquant : $src (dépose-le à côté de bootstrap.sh)"; fi
}
mkdir -p memory-bank scripts pipeline/data pipeline/cache pipeline/tests pipeline/vesperia/sources site/css site/js .github/workflows
place verify.py scripts/verify.py
place smoke.mjs scripts/smoke.mjs
place test_golden.py pipeline/tests/test_golden.py
place pages.yml .github/workflows/pages.yml
place poi_profiles.py pipeline/vesperia/sources/poi_profiles.py
[ -f BRIEF.md ] || die "BRIEF.md manquant : exporte le document Google Docs / Claude en Markdown sous ce nom, dans ce dossier"
say "fichiers fournis rangés"

# 2. Outils.
for t in git node npm; do command -v "$t" >/dev/null 2>&1 || die "outil absent : $t"; done
if [ "$OFFLINE" != "1" ]; then
  command -v gh >/dev/null 2>&1 || die "outil absent : gh (https://cli.github.com)"
  gh auth status >/dev/null 2>&1 || die "gh n'est pas authentifié : lance gh auth login (droits repo et workflow)"
fi
[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 20 ] || die "Node 20 ou plus requis"
PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then PY="$c"; break; fi
done
[ -n "$PY" ] || die "Python 3.11 ou plus requis"
say "outils : $PY, node $(node -v), $(git --version)"

# 3. Dépôt git local.
[ -d .git ] || git init -q -b main
git symbolic-ref HEAD refs/heads/main >/dev/null 2>&1 || true
git config user.name >/dev/null 2>&1 || git config user.name "Vesperia"
git config user.email >/dev/null 2>&1 || git config user.email "vesperia@users.noreply.github.com"

# 4. Fichiers de configuration (écrasés à chaque lancement, sans surprise).
cat > .gitignore <<'EOF'
memory-bank/
BRIEF.md
.venv/
node_modules/
pipeline/cache/
site/data/
__pycache__/
*.pyc
.DS_Store
EOF
cat > pytest.ini <<'EOF'
[pytest]
testpaths = pipeline/tests
pythonpath = pipeline
markers =
    phase1: contrats du temps et de la grille H3
    phase3: noyaux, normalisation, profils de commerces
    phase4: lecture des données ouvertes (profils hebdomadaires)
    phase5: fusion et assemblage
addopts = -q -p no:cacheprovider
EOF
cat > package.json <<'EOF'
{
  "name": "vesperia",
  "version": "1.0.0",
  "private": true,
  "description": "Atlas des points froids de Paris",
  "scripts": { "smoke": "node scripts/smoke.mjs --site site --base /vesperia/" },
  "devDependencies": { "playwright": "1.63.0" }
}
EOF
[ -f pipeline/MODE ] || printf 'fixture\n' > pipeline/MODE
: > pipeline/vesperia/__init__.py
: > pipeline/vesperia/sources/__init__.py

cat > scripts/brief.sh <<'EOF'
#!/usr/bin/env bash
# Affiche les règles, les contrats et la section de la phase demandée : bash scripts/brief.sh N  (N de 0 à 8, ou annexes)
set -euo pipefail
cd "$(dirname "$0")/.."
N="${1:?usage : bash scripts/brief.sh N  (0 à 8, ou annexes)}"
awk -v n="$N" '
/^```/ { fence = !fence }
!fence && /^## / {
  show = 0
  if ($0 ~ /^## 1\\?\./ || $0 ~ /^## 2\\?\./) show = 1
  if (n == "annexes" && $0 ~ /^## ANNEXES/) show = 1
  if ($0 ~ ("^## PHASE " n "([^0-9]|$)")) show = 1
}
show { print }
' BRIEF.md
EOF
chmod +x scripts/brief.sh
say "configuration écrite"

# 5. Contrôle de l'export BRIEF.md.
[ "$(grep -Ec '^## PHASE [0-8]' BRIEF.md)" = "9" ] || die "BRIEF.md doit contenir 9 titres « ## PHASE 0 » à « ## PHASE 8 » : refais l'export Markdown du document"
grep -Eq '^## 1\\?\. ' BRIEF.md || die "BRIEF.md : titre « ## 1. Règles » introuvable (export Markdown incorrect)"
grep -Eq '^## 2\\?\. Contrats' BRIEF.md || die "BRIEF.md : titre « ## 2. Contrats » introuvable (export Markdown incorrect)"
bash scripts/brief.sh 0 | grep -q 'PHASE 0' || die "scripts/brief.sh n'extrait pas la phase 0"

# 6. Environnement Python et Node.
if [ ! -x .venv/bin/python ]; then "$PY" -m venv .venv; fi
if [ "$OFFLINE" != "1" ]; then
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q numpy pandas h3 requests pytest tzdata
  .venv/bin/python -c 'import h3, sys; sys.exit(0 if h3.__version__.split(".")[0] == "4" else 1)' || die "h3 version 4 requise"
  .venv/bin/python -m pip freeze > pipeline/requirements.txt
  npm install --no-audit --no-fund --silent
  npx --yes playwright install chromium >/dev/null
  say "environnements prêts ($(wc -l < pipeline/requirements.txt | tr -d ' ') paquets Python épinglés)"
else
  say "mode hors ligne : installations sautées"
fi

# 7. Memory bank locale (jamais commitée).
mb() { [ -s "memory-bank/$1" ] && return 0; cat > "memory-bank/$1"; }
mb projectbrief.md <<'EOF'
# Vesperia — brief du projet

Vesperia est un atlas dynamique des points froids de Paris : pour chaque cellule H3 de niveau 9 et chacune des 168 heures d'une semaine type, un indice de froid F de 0 à 100 (100 = vide complet), calculé à partir de données ouvertes agrégées uniquement (voirie, vélo, métro, commerces OpenStreetMap).

Livrable : un site statique servi par GitHub Pages sous /vesperia/, reconstruit chaque lundi par GitHub Actions, avec une interface sombre NÉGATIF où seuls les vides s'allument.

Source de vérité : BRIEF.md à la racine (règles R1 à R15, contrats section 2, une section par phase). En cas de doute, relire la section voulue avec : bash scripts/brief.sh N.

Hors périmètre définitif : toute donnée sur des personnes, tout capteur, tout sous-sol (règle R12). L'indice est un a priori statistique, pas une observation.

Critère de succès : python3 scripts/verify.py 8 affiche GATE 8: PASS et le site déployé passe le test de fumée.
EOF
mb productContext.md <<'EOF'
# Vesperia — contexte produit

Utilisateur : Andy, qui explore la ville par le vide plutôt que par l'affluence. L'atlas répond à la question « où et quand Paris est-il le plus calme ? » et montre aussi la confiance qu'on peut accorder à chaque cellule.

Expérience visée : une carte noire où les vides s'allument en colonnes bleu glacé, une horloge géante, un ruban de la semaine de 168 barres, un classement des dix points les plus froids, quatre curseurs de pondération des sources et un interrupteur qui masque les zones isolées.

Deux modes : TYPIQUE (semaine type du lundi au dimanche) et RÉEL (les 168 heures à venir, avec météo Open-Meteo et événements Que faire à Paris, appliqués par le site seulement, étiquetés comme heuristiques).

Honnêteté : le site affiche ses sources et précise que l'indice est un a priori statistique. Tout texte visible est en français. Un seul thème, sombre.

Ce que le produit ne fait pas : localiser des personnes, deviner des présences, utiliser des données individuelles.
EOF
mb systemPatterns.md <<'EOF'
# Vesperia — architecture et motifs

Deux mondes reliés par des fichiers JSON : le pipeline Python (pipeline/) écrit meta.json, cells.json, activity.json et events.json dans site/data/ ; le site JavaScript (site/) ne lit rien d'autre. Aucun serveur, aucun build côté site.

Ordre des cellules partout : sorted(paris_cells(9)). Tous les tableaux sont alignés sur cet ordre.

Chaque source (poi, road, bike, rail) produit {id, label, weight, n_inputs, cov, data} via un noyau gaussien tronqué à 3 sigma (spread_average ou spread_sum) puis une normalisation to_percent. assemble.py fusionne : A = somme(w cov a) / somme(w cov), F = 100 - A, confiance = somme(w cov) / somme(w).

Deux modes de données : fixture (jeu synthétique déterministe, graine 20261112) et real. Le fichier pipeline/MODE choisit celui que la CI construit.

Garde-fous : scripts/verify.py (le vrai juge), scripts/smoke.mjs (navigateur), test_golden.py (contrats), fichiers protégés par empreinte SHA-256 dans .git/vesperia-guard.sha256.
EOF
mb techContext.md <<'EOF'
# Vesperia — contexte technique

Pile : Python 3.11+ dans .venv (numpy, pandas, h3 v4, requests, pytest, tzdata), Node 20+ pour Playwright seulement, MapLibre GL JS 5.24.0 et deck.gl 9.3.3 en CDN jsdelivr, fond de carte OpenFreeMap (style liberty), météo Open-Meteo, hébergement GitHub Pages par workflow.

Commandes : .venv/bin/python -m pytest -m phase1 ; .venv/bin/python pipeline/run.py --mode fixture --out site/data ; node scripts/smoke.mjs --site site --base /vesperia/ ; python3 scripts/verify.py N.

Réseau (R8) : 2 requêtes par seconde au plus, User-Agent vesperia/1.0, cache dans pipeline/cache, rejeu possible avec --cache-only.

## Schémas observés

(À remplir selon la règle R5 : pour chaque API, trois enregistrements réels, noms de champs et un exemple de valeur. Aucun champ ne doit être deviné.)

## Modèle et quotas

Modèle Hermes : voir ~/.hermes/config.yaml. Quota gratuit OpenRouter : 20 requêtes par minute, 50 par jour sous 10 crédits achetés, 1000 par jour au-delà.
EOF
mb activeContext.md <<'EOF'
# Vesperia — contexte actif

Phase en cours : 0 (amorçage).

Dernière action : bootstrap.sh terminé, fichiers fournis rangés, environnement Python prêt, memory bank créée, empreintes des fichiers protégés enregistrées.

Prochaine action : lire BRIEF.md avec bash scripts/brief.sh 0, puis exécuter la section PHASE 0 : créer le dépôt GitHub public, pousser, activer Pages en mode workflow, écrire README.md.

Blocages ouverts : aucun.

Ambiguïtés rencontrées et lecture retenue (règle R15) : aucune pour l'instant.

Rappel : en cas de même erreur deux fois de suite, écrire ici la commande, l'erreur complète et deux hypothèses, puis s'arrêter (règle R11).
EOF
mb progress.md <<'EOF'
# Vesperia — progression

Journal des phases. Une ligne PHASE N OK AAAA-MM-JJ HASH est ajoutée automatiquement par scripts/verify.py quand le gate N est vert ; ne jamais l'écrire à la main.

Phases : 0 amorçage ; 1 contrat de données et fixture ; 2 interface NÉGATIF et déploiement ; 3 fondations du pipeline et source commerces ; 4 voirie et vélo ; 5 métro, événements, assemblage ; 6 données réelles en CI ; 7 interface vivante ; 8 audit final.

Historique :
- bootstrap.sh exécuté, aucune phase terminée.
EOF
say "memory bank prête"

# 8. Empreintes des fichiers protégés (le gate vérifie qu'ils n'ont pas bougé).
python3 scripts/verify.py --guard-init
printf '\nAMORCAGE OK\n'
