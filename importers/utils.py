"""Utilitaires partagés par les management commands d'import (importers/management/commands/).

Les exports Excel sources présentent des incohérences connues (documentées dans le
plan) : accents abîmés dans certains en-têtes de colonnes (penalit?TTC), dates tantôt
en datetime réel tantôt en numéro de série Excel, identifiants client avec ou sans
zéro de tête. Ces helpers centralisent la tolérance à ces incohérences plutôt que de
la dupliquer dans chaque commande.
"""

import re
import unicodedata
from datetime import date, datetime

import pandas as pd
from django.conf import settings

# settings.BASE_DIR = .../DCB ONLINE/dashboard_app -> son parent est DCB ONLINE,
# qui contient data/ et informations clients/.
DCB_ONLINE_DIR = settings.BASE_DIR.parent
DATA_DIR = DCB_ONLINE_DIR / "data"
INFO_CLIENTS_DIR = DCB_ONLINE_DIR / "informations clients"


def _ascii_fold(value):
    value = unicodedata.normalize("NFKD", str(value))
    return "".join(c for c in value if not unicodedata.combining(c)).lower()


def find_column(df, *parts):
    """Retourne le nom de colonne contenant tous les `parts` (insensible accents/casse).

    Utile quand l'en-tête source a un accent corrompu (ex: 'penalit�TTC' pour
    'pénalitéTTC') : on matche sur les fragments ASCII stables plutôt que sur le nom
    exact, dont l'octet abîmé n'est pas reproductible de façon fiable dans le code.
    """
    folded_parts = [_ascii_fold(p) for p in parts]
    for col in df.columns:
        folded_col = _ascii_fold(col)
        if all(p in folded_col for p in folded_parts):
            return col
    raise KeyError(f"Aucune colonne ne correspond à {parts} parmi {list(df.columns)}")


def periode_annee_mois(value):
    """Convertit un Periode au format YYYYMM (int/str, ex: 202401) en (annee, mois)."""
    s = str(int(value))
    return int(s[:4]), int(s[4:6])


def get_or_create_periode_cache(cache, value):
    """get_or_create Periode en s'appuyant sur un cache {(annee,mois): Periode} fourni
    par l'appelant, pour éviter une requête SQL par ligne lors d'un import volumineux."""
    from core.models import Periode

    annee, mois = periode_annee_mois(value)
    key = (annee, mois)
    if key not in cache:
        cache[key], _ = Periode.objects.get_or_create(annee=annee, mois=mois)
    return cache[key]


def parse_date_flexible(value):
    """Parse une date qui peut être : NaT/None, datetime/Timestamp, numéro de série
    Excel (observé dans V_Fait_Raccord_Dash_DCB.Date_Periode), ou chaîne DD/MM/YYYY
    (observé dans V_PNEX_HT.date_paiement et al.)."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.date() if isinstance(value, datetime) else value
    if isinstance(value, (int, float)):
        # Numéro de série Excel (jours depuis 1899-12-30).
        return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(value))).date()
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    parsed = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return parsed.date() if not pd.isna(parsed) else None


def coerce_id_str(value):
    """Normalise une cellule identifiant (IDABON, Ref_Contrat...) en str propre.

    Ces colonnes sont parfois dtype=object (mélange numérique/texte, ex: IDABON
    "24D07701" observé dans V_PNEX_HT à côté de valeurs purement numériques stockées
    en float à cause de NaN ailleurs dans la colonne). Un simple str(value) sur un
    float numérique donnerait "3301903.0" ; on retire ce ".0" quand c'est un entier.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def format_identifiant_8(value):
    """Met un identifiant (IDABON ou REFRACCORD) à sa forme canonique de la base de
    facturation : 8 chiffres numériques. La source stocke ces deux colonnes comme
    des NOMBRES, ce qui fait perdre le zéro de tête des identifiants commençant par
    0 (02248501 devient 2248501, même bug vérifié sur REFRACCORD : 19 533 cellules
    int / 467 str sur un échantillon de 20 000 lignes de V_Fait_Fact_HT_DCB.xlsx,
    soit exactement la même signature que IDABON) ; on le rétablit ici car ce zéro
    est significatif (demande utilisateur). Une éventuelle lettre de sous-site est
    conservée (le champ reste alphanumérique) :
    - "2248501"  -> "02248501"   (7 chiffres -> 8)
    - "23A00207" -> "023A00207"  (7 chiffres + lettre -> 8 chiffres + lettre)
    - "26127001" -> "26127001"   (déjà 8 chiffres, inchangé)
    Retourne la valeur vide (None/"") telle quelle."""
    s = coerce_id_str(value)
    if not s:
        return s
    s = s.strip().upper()
    nb_chiffres = sum(c.isdigit() for c in s)
    if 0 < nb_chiffres < 8:
        s = "0" * (8 - nb_chiffres) + s
    return s


# Alias explicites par usage (même règle de formatage) : gardés séparés dans les
# imports pour que chaque appel se lise clairement ("je formate un IDABON" /
# "je formate une référence raccordement"), sans dupliquer la logique.
format_idabon = format_identifiant_8
format_refraccord = format_identifiant_8


def clean_mojibake(value):
    """Heuristique de nettoyage pour les valeurs texte des exports sources : l'octet
    accentué perdu à l'export est systématiquement remplacé par U+FFFD, et dans tous
    les cas observés (Délai, Exécutée, Activité, Qualité...) la lettre d'origine est
    un 'é', donc on le restitue tel quel plutôt que de garder le caractère de
    remplacement illisible. Imparfait mais largement suffisant pour l'affichage V1."""
    if value is None:
        return value
    return str(value).replace("�", "é")


def normalize_identifiant(value):
    """Normalise un identifiant client (IDABON ou IDENTIFIANT) pour comparaison :
    ne garde que les caractères alphanumériques et retire les zéros de tête
    (ex: '02113310' == '2113310').

    Conserve les lettres : 145 Client.idabon réels intègrent un code de sous-site
    alphabétique (ex: '23A00207', '23B00207', '23C00207'...) qui distingue de vraies
    sociétés différentes installées sur le même groupe ('23A00207' = TBT NOUVELLE
    GERANCE, '02300207' = SE2I SARL : deux clients distincts, vérifié). Une version
    antérieure de cette fonction ne gardait que les chiffres et fusionnait ces deux
    identifiants en une seule clé, provoquant un mauvais routage de données
    d'enrichissement entre sociétés homonymes par hasard de normalisation."""
    alnum = re.sub(r"[^0-9A-Za-z]", "", str(value)).upper()
    return alnum.lstrip("0") or "0"


def split_dr_code(value):
    """Découpe un champ DR concaténé du type '03-DRYOP' -> ('03', 'DRYOP').
    Retourne (None, str(value)) si pas de tiret (cas où DR est déjà juste le libellé)."""
    s = str(value).strip()
    if "-" in s:
        prefix, libelle = s.split("-", 1)
        return prefix, libelle
    return None, s
