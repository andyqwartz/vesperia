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
