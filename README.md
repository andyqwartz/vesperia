# Vesperia

*Contre-carte des silences urbains · Paris.*

Atlas dynamique des points froids de Paris : les zones et les heures où la ville est statistiquement la moins active, calculées sur une grille hexagonale H3 de résolution 9 (environ 1 100 cellules couvrant Paris intra-muros et les deux bois) à partir de données ouvertes agrégées. Carte en ligne : https://andyqwartz.github.io/vesperia/

L'indice est un a priori statistique : il décrit le profil moyen de la ville pour chacune des 168 heures d'une semaine, jamais ce qui se passe réellement dans une rue à un instant donné. Il ne voit aucune personne : aucune donnée personnelle, aucun signal de téléphone, de Wi-Fi, de Bluetooth, de réseau social ou de caméra n'entre dans le calcul, et rien ne concerne le sous-sol.

## Fondement

La cartographie officielle est un acte de pouvoir et de simplification. Elle montre ce que l'autorité juge pertinent, les axes de circulation, les points d'intérêt économique, les structures de contrôle, et elle invisibilise des pans entiers de la réalité vécue : les flux humains non normés, les espaces interstitiels, les temporalités marginales. Vesperia prend le chemin inverse : une cartographie dynamique des vides métropolitains, de ces moments où la pression normative de la ville se relâche.

La démarche hérite de la psychogéographie situationniste et des artistes qui arpentent les marges et les non-lieux, hybridée avec l'analyse de données ouvertes. Ce ne sont pas des ruines ou des lieux abandonnés connus que l'atlas désigne, mais des vides dynamiques, qui se déplacent avec l'heure, le jour, la météo. Chercher le point froid, c'est résister à l'injonction de visibilité et d'activité permanente.

L'hypothèse va plus loin : ces vides ne sont peut-être pas déserts. Ils pourraient être recherchés, habités même fugitivement, par d'autres qui partagent la même sensibilité, quête de retrait, d'observation, de silence, de liberté interstitielle. Vesperia est une tentative d'ingénierie de la sérendipité : se rendre là où la ville se tait, et laisser advenir la possibilité d'une rencontre incidente.

La posture est celle de l'observateur flottant : ne pas chercher activement, être prêt à percevoir, attentif aux ambiances sonores et lumineuses, aux traces ténues d'une activité passée. La rencontre est une possibilité, jamais une garantie ; le vide effectivement vide est un résultat à part entière. Vers une herméneutique des silences urbains.

## Usage

La grande horloge donne l'heure affichée. La frise du bas représente la semaine : clique dessus ou fais-la glisser pour choisir l'heure, ou utilise les flèches du clavier (gauche et droite : une heure ; haut et bas : un jour). LECTURE fait défiler la semaine, MAINTENANT revient à l'heure courante de Paris. TYPIQUE affiche le profil moyen ; RÉEL y ajoute la météo prévue (la pluie et le froid refroidissent les lieux de plein air) et les événements en cours (ils réchauffent leurs environs).

Sur la carte, chaque point froid de l'heure s'allume (mode sombre) ou se creuse à l'encre (mode clair, bouton CLAIR / SOMBRE). À droite, les fenêtres de silence : les lieux froids maintenant, classés par la durée de leur silence à venir ; un clic centre la carte dessus. DÉRIVE en tire une au sort. CARTE OFFICIELLE fait réapparaître en or les axes et repères de la carte ordinaire. À gauche, les curseurs règlent le poids de chacune des quatre mesures d'activité (voirie, vélo, métro, commerces) ; RÉGLAGES en détaille les données. La case MASQUER LES ZONES ISOLÉES retire les cellules sans arrêt de transport à moins de 250 m. ÉCOUTE active un drone sonore qui s'éclaircit et s'amplifie quand la ville est froide ; il ne démarre jamais sans clic. Le bouton ⓘ ouvre le fondement du projet. Raccourcis : D dérive, O carte officielle, R réglages, T thème, I fondement, Échap ferme.

Pour lancer le site chez toi :

    python3 -m venv .venv
    .venv/bin/pip install -r pipeline/requirements.txt
    .venv/bin/python pipeline/run.py --mode fixture --out site/data
    python3 -m http.server --directory site 8000

puis ouvre http://localhost:8000/. Le mode fixture produit un jeu synthétique de démonstration ; pour les données réelles, remplace fixture par real (quelques minutes et du réseau). Le fichier pipeline/MODE contient le mode utilisé par le déploiement automatique, qui reconstruit les données chaque lundi à 03:17 UTC ; les téléchargements de moins de deux jours sont réutilisés entre deux déploiements.

## Sources et licences

| Source | Usage | Licence |
|---|---|---|
| Ville de Paris — Open Data | comptages routiers permanents, compteurs vélo, événements Que faire à Paris | licence indiquée sur la fiche de chaque jeu (ODbL en général) |
| Île-de-France Mobilités — Open Data | profils horaires de validation sur le réseau ferré | licence indiquée sur la fiche du jeu |
| © contributeurs OpenStreetMap | commerces et accès au réseau ferré, via l'API Overpass | ODbL |
| Open-Meteo.com | prévision horaire de température et de pluie, appelée depuis le navigateur | CC BY 4.0 |
| OpenFreeMap | fond de carte, style liberty recoloré | gratuit, sans clé ; données OpenStreetMap, ODbL |
| MapLibre GL JS et deck.gl | rendu de la carte, chargés depuis le CDN jsDelivr | BSD-3 et MIT |
| Instrument Serif et JetBrains Mono | typographies, chargées depuis le CDN jsDelivr (Fontsource) | SIL Open Font License |

## Limites

L'indice est un a priori statistique, pas une mesure : il ne dit pas qu'une rue est vide à un instant donné, seulement qu'elle l'est typiquement à cette heure de la semaine.

Les capteurs routiers et vélo sont en nombre limité ; leur effet est étalé sur la grille par un noyau gaussien (300 m et 500 m), et les zones sans capteur proche reçoivent une confiance faible, ce qui les exclut du classement.

La source MÉTRO est la densité des accès au réseau ferré (OpenStreetMap) multipliée par le profil horaire moyen de tout le réseau (Île-de-France Mobilités) : elle ne reflète pas les validations de chaque station, et une station de bureaux a le même rythme qu'une station de sorties nocturnes.

Les horaires des commerces viennent d'OpenStreetMap, incomplets par endroits ; à défaut, un profil par type de lieu est appliqué.

Les événements se limitent aux manifestations de 72 heures au plus du jeu Que faire à Paris, et leur effet est un simple rayon de 300 m. La météo ne joue qu'en mode RÉEL, sur huit jours de prévision, et seulement sur les lieux de plein air.

Si le fond OpenFreeMap est injoignable, la carte s'affiche sur un fond uni. Si un jeu de données source change de format, la reconstruction hebdomadaire échoue et le site garde les dernières données publiées.
