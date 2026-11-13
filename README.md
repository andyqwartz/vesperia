# Vesperia

*Contre-carte des silences urbains · Paris.*

## Fondement

Une carte officielle n'est jamais neutre : elle montre ce que l'autorité juge utile (axes de circulation, commerces, monuments, équipements) et laisse dans l'ombre le reste de la ville vécue, ses interstices, ses heures creuses, ses usages sans nom. Vesperia prend le parti inverse. Elle n'éclaire pas l'activité, elle éclaire son absence : les lieux et les moments où la pression de la ville se relâche.

La démarche vient de la psychogéographie et de la dérive situationniste, augmentée par les données ouvertes. Plutôt que d'errer au hasard ou de visiter des ruines connues, Vesperia prédit des vides qui bougent avec l'heure, le jour et la météo, puis laisse le hasard choisir : une dérive tirée au sort parmi les fenêtres de silence les plus longues. Chercher le point froid, c'est refuser l'injonction à être visible et actif en permanence ; c'est aussi tenter une forme d'ingénierie de la sérendipité.

La posture proposée est celle de l'observateur flottant : ne pas chercher, être prêt à percevoir. Noter les sons, la lumière, les traces, ce qu'on ressent. Un vide effectivement vide est un résultat à part entière.

### Ce que Vesperia s'interdit

- Observer, identifier, suivre ou deviner des personnes. L'atlas ne connaît que des cellules et des heures, jamais des individus.
- Toute collecte de signaux personnels : Wi-Fi, Bluetooth, réseaux sociaux, caméras.
- Le sous-sol et les lieux d'accès interdit.
- Tout usage de surveillance. Observer sans surveiller, ne rien perturber, ne laisser aucune trace.

## L'interface

La ville est éteinte ; seuls les vides s'allument. Une horloge écrite en toutes lettres, une semaine de 168 heures à parcourir, les fenêtres de silence qui tiennent le plus longtemps à partir de l'heure choisie, un bouton DÉRIVE qui en tire une au sort, et la carte officielle qu'on peut faire réapparaître pour mesurer l'écart entre ce qu'elle montre et ce que Vesperia montre.

## Usage

Le site s'ouvre sur https://andyqwartz.github.io/vesperia/. Lancez l'index de froid avec `.venv/bin/python pipeline/run.py --mode fixture --out site/data` puis `node scripts/smoke.mjs --site site --base /vesperia/`.

## Sources

- Ville de Paris (Open Data, ODbL)
- Île-de-France Mobilités (Open Data)
- Contributeurs OpenStreetMap (ODbL)
- Open-Meteo (CC BY 4.0)
- OpenFreeMap

## Limites

L'indice est un a priori statistique construit à partir de données ouvertes agrégées ; il ne voit aucune personne. Il dit où l'activité est probablement faible, pas où il n'y a personne, ni qu'un lieu est sûr. La rencontre, le silence ou la dérive restent des possibilités, jamais des garanties.
