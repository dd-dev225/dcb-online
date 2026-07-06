"""Rapprochement entre les départs HTA d'INCIBCC/MANTBCC et le référentiel
ZI_Departures_SS.xlsx (reseau.models.DepartZoneIndustrielle) : les deux sources
nomment le même départ différemment ("1DEPART CHOCOLATIER" côté INCIBCC,
"Départ 15KV CHOCOLATIER" côté référentiel) et le même poste source aussi
("YOPOUGON2" sans espace côté INCIBCC, "YOPOUGON 2" avec espace côté
référentiel). On normalise donc les deux côtés vers le même nom de site nu
(majuscules, sans accent, sans préfixe "<n>DEPART"/"Départ <n>KV", sans espace)
avant de les comparer."""

import re
import unicodedata

from .models import DepartZoneIndustrielle

_PREFIXE_DEPART = re.compile(r"^\d*\s*DEPART\s*(?:\d*KV)?\s*")


def normaliser_site(texte):
    """"1DEPART CHOCOLATIER" et "Départ 15KV CHOCOLATIER" -> "CHOCOLATIER".
    "YOPOUGON 2" et "YOPOUGON2" -> "YOPOUGON2"."""
    sans_accent = unicodedata.normalize("NFKD", str(texte))
    sans_accent = "".join(c for c in sans_accent if not unicodedata.combining(c))
    majuscule = sans_accent.upper()
    sans_prefixe = _PREFIXE_DEPART.sub("", majuscule)
    return re.sub(r"\s+", "", sans_prefixe)


def construire_zone_par_depart():
    """Retourne {(poste_normalise, nom_depart_normalise): ZoneIndustrielle}."""
    return {
        (normaliser_site(d.poste_source), normaliser_site(d.nom_depart)): d.zone
        for d in DepartZoneIndustrielle.objects.select_related("zone")
    }
