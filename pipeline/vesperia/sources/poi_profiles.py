"""Profils hebdomadaires d'activité par type d'établissement OSM.

FICHIER FOURNI (règle R2) : ne jamais le modifier.
Ces profils sont une HEURISTIQUE assumée (pas des horaires réels). Le module ne fait
aucune entrée-sortie : il classe des tags OSM, fabrique les requêtes Overpass et
extrait des points des éléments JSON renvoyés par Overpass.

Indice de semaine : wh = jour (lundi = 0) * 24 + heure, de 0 à 167.
"""

HOURS = 168
# Emprise de Paris : (sud, ouest, nord, est), en degrés.
BBOX = (48.815, 2.223, 48.903, 2.470)
ISOLATION_RADIUS_M = 250
OUTDOOR_RADIUS_M = 250

_DAYTYPE = ("mon_thu", "mon_thu", "mon_thu", "mon_thu", "fri", "sat", "sun")

# Segments (heure_début, heure_fin, niveau) par type de jour. Une heure_fin > 24
# déborde sur le lendemain (le niveau s'applique alors aux premières heures du jour suivant).
_SPECS = {
    "food": {
        "base": 0.02,
        "mon_thu": [(7, 10, 0.35), (10, 12, 0.30), (12, 15, 0.95), (15, 18, 0.35), (18, 23, 0.85), (23, 24, 0.20)],
        "fri": [(7, 10, 0.35), (10, 12, 0.30), (12, 15, 0.95), (15, 18, 0.40), (18, 24, 0.90), (24, 26, 0.25)],
        "sat": [(9, 12, 0.40), (12, 15, 0.90), (15, 18, 0.45), (18, 24, 1.00), (24, 26, 0.30)],
        "sun": [(9, 12, 0.45), (12, 15, 0.90), (15, 18, 0.45), (18, 22, 0.60)],
    },
    "night": {
        "base": 0.0,
        "mon_thu": [(17, 20, 0.35), (20, 24, 0.70), (24, 26, 0.30)],
        "fri": [(17, 20, 0.45), (20, 24, 1.00), (24, 28, 0.85)],
        "sat": [(17, 20, 0.45), (20, 24, 1.00), (24, 29, 0.90)],
        "sun": [(16, 20, 0.40), (20, 23, 0.45)],
    },
    "retail": {
        "base": 0.0,
        "mon_thu": [(10, 12, 0.45), (12, 14, 0.55), (14, 19, 0.80), (19, 20, 0.40)],
        "fri": [(10, 12, 0.50), (12, 14, 0.60), (14, 19, 0.85), (19, 20, 0.45)],
        "sat": [(10, 12, 0.60), (12, 19, 1.00), (19, 20, 0.50)],
        "sun": [(11, 13, 0.35), (13, 18, 0.45)],
    },
    "grocery": {
        "base": 0.0,
        "mon_thu": [(7, 9, 0.50), (9, 12, 0.60), (12, 14, 0.55), (14, 17, 0.55), (17, 20, 0.90), (20, 22, 0.45)],
        "fri": [(7, 9, 0.50), (9, 12, 0.60), (12, 14, 0.55), (14, 17, 0.60), (17, 20, 1.00), (20, 22, 0.50)],
        "sat": [(8, 12, 0.90), (12, 19, 1.00), (19, 21, 0.50)],
        "sun": [(8, 13, 0.75), (13, 19, 0.15)],
    },
    "office": {
        "base": 0.02,
        "mon_thu": [(8, 9, 0.45), (9, 12, 1.00), (12, 14, 0.55), (14, 18, 1.00), (18, 20, 0.40)],
        "fri": [(8, 9, 0.40), (9, 12, 0.95), (12, 14, 0.50), (14, 17, 0.85), (17, 19, 0.25)],
        "sat": [(10, 13, 0.06)],
        "sun": [],
    },
    "school": {
        "base": 0.0,
        "mon_thu": [(8, 9, 0.70), (9, 12, 1.00), (12, 14, 0.50), (14, 17, 1.00), (17, 19, 0.35)],
        "fri": [(8, 9, 0.70), (9, 12, 1.00), (12, 14, 0.50), (14, 17, 0.90), (17, 19, 0.25)],
        "sat": [(8, 12, 0.15)],
        "sun": [],
    },
    "culture": {
        "base": 0.0,
        "mon_thu": [(10, 12, 0.30), (12, 14, 0.40), (14, 18, 0.60), (18, 20, 0.55), (20, 23, 0.70), (23, 24, 0.15)],
        "fri": [(10, 12, 0.30), (12, 14, 0.40), (14, 18, 0.65), (18, 20, 0.60), (20, 24, 0.85)],
        "sat": [(10, 12, 0.45), (12, 18, 0.90), (18, 20, 0.70), (20, 24, 1.00)],
        "sun": [(10, 12, 0.45), (12, 18, 0.85), (18, 20, 0.55), (20, 23, 0.45)],
    },
    "lodging": {
        "base": 0.50,
        "mon_thu": [(6, 10, 0.70), (10, 17, 0.45), (17, 24, 0.75)],
        "fri": [(6, 10, 0.70), (10, 17, 0.45), (17, 24, 0.80)],
        "sat": [(6, 10, 0.70), (10, 17, 0.45), (17, 24, 0.80)],
        "sun": [(6, 10, 0.70), (10, 17, 0.45), (17, 24, 0.70)],
    },
    "health": {
        "base": 0.0,
        "mon_thu": [(8, 12, 0.90), (12, 14, 0.40), (14, 19, 0.90), (19, 20, 0.25)],
        "fri": [(8, 12, 0.90), (12, 14, 0.40), (14, 19, 0.85), (19, 20, 0.25)],
        "sat": [(9, 12, 0.50), (12, 14, 0.20)],
        "sun": [(10, 12, 0.08)],
    },
    "hospital": {
        "base": 0.60,
        "mon_thu": [(7, 20, 1.00)],
        "fri": [(7, 20, 1.00)],
        "sat": [(7, 20, 0.85)],
        "sun": [(7, 20, 0.85)],
    },
    "worship": {
        "base": 0.0,
        "mon_thu": [(9, 12, 0.12), (17, 19, 0.12)],
        "fri": [(9, 12, 0.12), (12, 14, 0.45), (17, 19, 0.15)],
        "sat": [(9, 12, 0.10), (17, 19, 0.18)],
        "sun": [(9, 13, 1.00), (17, 19, 0.35)],
    },
    "sport": {
        "base": 0.0,
        "mon_thu": [(6, 9, 0.55), (9, 12, 0.35), (12, 14, 0.60), (14, 17, 0.35), (17, 22, 1.00)],
        "fri": [(6, 9, 0.55), (9, 12, 0.35), (12, 14, 0.60), (14, 17, 0.35), (17, 21, 0.80)],
        "sat": [(9, 18, 0.85)],
        "sun": [(9, 18, 0.70)],
    },
}

KINDS = tuple(_SPECS)

# Importance relative d'un établissement de chaque type (nombre de personnes brassées, grossièrement).
KIND_WEIGHT = {
    "food": 1.0, "night": 0.9, "retail": 0.8, "grocery": 1.2, "office": 2.0, "school": 4.0,
    "culture": 3.0, "lodging": 1.5, "health": 1.5, "hospital": 12.0, "worship": 1.5, "sport": 2.0,
}


def _build(kind):
    spec = _SPECS[kind]
    arr = [float(spec["base"])] * HOURS
    for d in range(7):
        for (s, e, level) in spec[_DAYTYPE[d]]:
            for h in range(s, e):
                i = (d * 24 + h) % HOURS
                if level > arr[i]:
                    arr[i] = float(level)
    return [round(v, 3) for v in arr]


# Profils unitaires (valeurs de 0 à 1, 168 éléments) par type.
PROFILES = {k: _build(k) for k in KINDS}

_AMENITY_KIND = {
    "restaurant": "food", "fast_food": "food", "cafe": "food", "ice_cream": "food", "food_court": "food",
    "bar": "night", "pub": "night", "nightclub": "night", "biergarten": "night", "casino": "night", "stripclub": "night",
    "cinema": "culture", "theatre": "culture", "arts_centre": "culture", "library": "culture",
    "community_centre": "culture", "events_venue": "culture",
    "school": "school", "kindergarten": "school", "college": "school", "university": "school",
    "language_school": "school", "music_school": "school",
    "hospital": "hospital",
    "clinic": "health", "doctors": "health", "dentist": "health", "pharmacy": "health", "veterinary": "health",
    "bank": "office", "townhall": "office", "courthouse": "office", "post_office": "office", "coworking_space": "office",
    "place_of_worship": "worship",
    "marketplace": "retail",
}
_GROCERY_SHOPS = {
    "supermarket", "convenience", "greengrocer", "butcher", "bakery", "deli", "alcohol", "wine", "cheese",
    "seafood", "pastry", "organic", "beverages", "chocolate", "farm",
}
_LODGING = {"hotel", "hostel", "guest_house", "apartment", "motel"}
_TOURISM_CULTURE = {"museum", "gallery", "attraction", "theme_park", "zoo", "aquarium"}
_LEISURE_SPORT = {"fitness_centre", "sports_centre", "swimming_pool", "sports_hall"}


def _alt(values):
    return "|".join(sorted(values))


_AMENITY_REGEX = _alt(_AMENITY_KIND)
_TOURISM_REGEX = _alt(_LODGING | _TOURISM_CULTURE)
_LEISURE_REGEX = _alt(_LEISURE_SPORT)


def classify(tags):
    """Renvoie le type (voir KINDS) d'un établissement d'après ses tags OSM, ou None."""
    if not tags:
        return None
    amenity = tags.get("amenity")
    if amenity in _AMENITY_KIND:
        return _AMENITY_KIND[amenity]
    shop = tags.get("shop")
    if shop and shop not in ("vacant", "no"):
        return "grocery" if shop in _GROCERY_SHOPS else "retail"
    office = tags.get("office")
    if office and office != "no":
        return "office"
    tourism = tags.get("tourism")
    if tourism in _LODGING:
        return "lodging"
    if tourism in _TOURISM_CULTURE:
        return "culture"
    if tags.get("leisure") in _LEISURE_SPORT:
        return "sport"
    return None


def weekly(kind):
    """Profil unitaire (liste de 168 flottants) d'un type."""
    return list(PROFILES[kind])


def poi_vector(tags):
    """Profil pondéré (168 flottants = profil unitaire * KIND_WEIGHT) pour des tags OSM, ou None."""
    kind = classify(tags)
    if kind is None:
        return None
    w = KIND_WEIGHT[kind]
    return [round(v * w, 4) for v in PROFILES[kind]]


def is_transit(tags):
    """Vrai pour un arrêt ou une station de transport (sert à l'indicateur d'isolement)."""
    if not tags:
        return False
    return (
        tags.get("highway") == "bus_stop"
        or tags.get("railway") in ("station", "subway_entrance", "tram_stop", "halt")
        or tags.get("amenity") == "bus_station"
        or tags.get("public_transport") in ("platform", "station")
    )


def is_outdoor(tags):
    """Vrai pour un parc, jardin, aire de jeux, plan d'eau, cimetière ou espace vert (indicateur plein air)."""
    if not tags:
        return False
    return (
        tags.get("leisure") in ("park", "garden", "playground", "dog_park")
        or tags.get("natural") == "water"
        or tags.get("landuse") in ("recreation_ground", "village_green", "cemetery")
    )


def overpass_poi_query(bbox=BBOX, timeout=240):
    """Requête Overpass QL des établissements (JSON, centre des ways et relations, tags)."""
    s, w, n, e = bbox
    b = f"({s},{w},{n},{e})"
    return (
        f"[out:json][timeout:{timeout}];("
        f'nwr["amenity"~"^({_AMENITY_REGEX})$"]{b};'
        f'nwr["shop"]["shop"!~"^(vacant|no)$"]{b};'
        f'nwr["office"]["office"!="no"]{b};'
        f'nwr["tourism"~"^({_TOURISM_REGEX})$"]{b};'
        f'nwr["leisure"~"^({_LEISURE_REGEX})$"]{b};'
        ");out center tags;"
    )


def overpass_transit_query(bbox=BBOX, timeout=240):
    """Requête Overpass QL des arrêts et stations de transport (centres)."""
    s, w, n, e = bbox
    b = f"({s},{w},{n},{e})"
    return (
        f"[out:json][timeout:{timeout}];("
        f'nwr["highway"="bus_stop"]{b};'
        f'nwr["railway"~"^(station|subway_entrance|tram_stop|halt)$"]{b};'
        f'nwr["amenity"="bus_station"]{b};'
        f'nwr["public_transport"~"^(platform|station)$"]{b};'
        ");out center tags;"
    )


def overpass_outdoor_query(bbox=BBOX, timeout=240):
    """Requête Overpass QL des espaces de plein air, avec la géométrie (sommets des contours)."""
    s, w, n, e = bbox
    b = f"({s},{w},{n},{e})"
    return (
        f"[out:json][timeout:{timeout}];("
        f'nwr["leisure"~"^(park|garden|playground|dog_park)$"]{b};'
        f'nwr["natural"="water"]{b};'
        f'nwr["landuse"~"^(recreation_ground|village_green|cemetery)$"]{b};'
        ");out geom tags;"
    )


def element_point(el):
    """Point (lat, lon) d'un élément Overpass : nœud (lat, lon) ou centre (center). None si absent."""
    if "lat" in el and "lon" in el:
        return (float(el["lat"]), float(el["lon"]))
    c = el.get("center")
    if c and "lat" in c and "lon" in c:
        return (float(c["lat"]), float(c["lon"]))
    return None


def element_points(el):
    """Tous les points (lat, lon) d'un élément Overpass : point, centre, sommets de geometry et des membres."""
    pts = []
    p = element_point(el)
    if p:
        pts.append(p)
    for g in el.get("geometry") or []:
        if g and "lat" in g and "lon" in g:
            pts.append((float(g["lat"]), float(g["lon"])))
    for m in el.get("members") or []:
        for g in m.get("geometry") or []:
            if g and "lat" in g and "lon" in g:
                pts.append((float(g["lat"]), float(g["lon"])))
    return pts
