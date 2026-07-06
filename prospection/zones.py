"""Correspondance quartier/zone de prospection (colonne libre ImmeubleProspecte.
zone_prospection) -> code Direction Régionale CIE, pour permettre la répartition
géographique des immeubles PAR DR (demande utilisateur, cf. cartographie) faute de
coordonnées précises. Établie par recherche (limites administratives des communes
du District Autonome d'Abidjan, quartiers rattachés à chaque commune) : DRAS
(Treichville, Marcory, Koumassi, Port-Bouët), DRAN (Plateau, Cocody, Adjamé,
Attécoubé, Bingerville), DRYOP (Yopougon), DRABO (Abobo, Anyama).

Les clés sont volontairement normalisées (majuscules, espaces simples) pour être
tolérantes aux variantes de saisie du fichier terrain (accents, parenthèses)."""

import re

ZONE_VERS_DR = {
    "FAYA": "DRABO",
    "DJROGOBITE": "DRABO",
    "DJIBI": "DRABO",
    "AKOUEDO": "DRAN",
    "COCODY": "DRAN",
    "PLATEAU": "DRAN",
    "MARCORY": "DRAS",
    "TREICHVILLE": "DRAS",
    "RIV. PALMERAIE": "DRAN",
    "RIVIERE PALMERAIE": "DRAN",
    "M'BADON": "DRYOP",
    "MBADON": "DRYOP",
    "2 PLATEAUX VALLONS": "DRAN",
    "DEUX PLATEAUX VALLONS": "DRAN",
    "ANGRE": "DRAN",
    "ZONE 4": "DRAS",
    "GRAND-BASSAM": "DRBC",
    "GRAND BASSAM": "DRBC",
    "RIV. BONOUMIN": "DRAN",
    "RIVIERE BONOUMIN": "DRAN",
    "BIETRY": "DRAS",
    "ABATTA": "DRAN",
    "MPOUTO": "DRAN",
    "ATTOBAN": "DRAN",
    "PORT-BOUET": "DRAS",
    "PORT BOUET": "DRAS",
    "RIVIERA": "DRAN",
    "ADJAME": "DRAN",
    "ATTECOUBE": "DRAN",
    "KOUMASSI": "DRAS",
    "VRIDI": "DRAS",
    "YOPOUGON": "DRYOP",
    "ABOBO": "DRABO",
    "ANYAMA": "DRABO",
    "BINGERVILLE": "DRAN",
    "SONGON": "DRYOP",
}


def _normaliser(zone):
    """Retire accents/ponctuation de base pour matcher les variantes de saisie
    (ex: 'RIV. PALMERAIE' et 'Riv Palmeraie' doivent matcher la même clé)."""
    z = zone.upper().strip()
    z = z.split("(")[0].strip()  # "COCODY ( DANGA, ...)" -> "COCODY"
    z = re.sub(r"[ÉÈÊË]", "E", z)
    z = re.sub(r"[ÀÂ]", "A", z)
    z = re.sub(r"\s+", " ", z)
    return z


def dr_code_pour_zone(zone_prospection):
    """Retourne le code DR correspondant à une zone de prospection (texte libre),
    ou None si aucune correspondance connue. Recherche par correspondance exacte
    puis par inclusion (la clé du dictionnaire apparaît dans la zone normalisée),
    pour tolérer les suffixes ("MARCORY - RÉSIDENTIEL" -> "MARCORY")."""
    if not zone_prospection:
        return None
    z = _normaliser(zone_prospection)
    if z in ZONE_VERS_DR:
        return ZONE_VERS_DR[z]
    for cle, code in ZONE_VERS_DR.items():
        if cle in z:
            return code
    return None
