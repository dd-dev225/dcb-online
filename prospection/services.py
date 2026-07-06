"""Parsing partagé entre la commande d'import historique
(importers/management/commands/import_prospection_guichet_unique.py, qui fait un
rafraîchissement complet depuis le fichier source d'origine) et l'import web
incrémental (prospection.views.importer_prospects, qui ajoute uniquement de
nouveaux prospects sans toucher à l'existant). Un seul endroit qui sait lire la
forme "ACTIONS_IMM" plutôt que deux parsers qui dérivent l'un de l'autre dans le
temps.

Tolère l'hétérogénéité documentée par l'utilisateur (variantes OUI/NON, typo
TERASSEMENT, valeurs ambiguës) plutôt que de rejeter une ligne entière. Tout texte
hors vocabulaire connu est conservé dans observations pour ne rien perdre
silencieusement.
"""

import re

import pandas as pd
from django.contrib.auth import get_user_model

from core.models import DirectionRegionale
from importers.utils import clean_mojibake, parse_date_flexible

from .models import DemarcheAdministrative, ImmeubleProspecte

User = get_user_model()

# Mapping (sous-chaîne du nom trouvée dans la colonne source, en majuscules) ->
# username du compte de test correspondant (cf. comptes.seed_users). Ordre de
# priorité explicite : certaines cellules combinent deux noms (ex. "Mme DIOMANDE
# / N'DJESSAN"). On retient le premier match de cette liste plutôt que de deviner
# une répartition. Pas de nom réel stocké en base, uniquement le compte rattaché.
COMMERCIAL_USERNAME_BY_SUBSTRING = [
    ("DIBY", "cadre_guichet_unique"),
    ("NDJESSAN", "cadre_charge_affaires_guichet"),
    ("N'DJESSAN", "cadre_charge_affaires_guichet"),
    ("SYLLA", "conseiller_grands_comptes_guichet"),
    ("BOGGA", "conseiller_grands_comptes_guichet_2"),
    ("BOGA", "conseiller_grands_comptes_guichet_2"),
    ("DIOMANDE", "conseiller_grands_comptes_guichet_3"),
    ("DIOMAND", "conseiller_grands_comptes_guichet_3"),
]

STADE_NORMALISE = {
    "TERASSEMENT": ImmeubleProspecte.TERRASSEMENT,
    "TERRASSEMENT": ImmeubleProspecte.TERRASSEMENT,
    "GROS OEUVRE": ImmeubleProspecte.GROS_OEUVRE,
    "FINITION": ImmeubleProspecte.FINITION,
}

TYPE_DEMANDE_NORMALISE = {
    "COMPTEUR CHANTIER": DemarcheAdministrative.COMPTEUR_CHANTIER,
    "CTR CHANTIER": DemarcheAdministrative.COMPTEUR_CHANTIER,
}

# Seule colonne strictement requise : toutes les autres sont lues via .get() avec
# un repli "" / None si absentes (cf. importer_depuis_dataframe). Un fichier plus
# pauvre que recensement_sdgu.xlsx (ex: sans MONTANT BRA PAYE) doit pouvoir
# s'importer quand même, seules les lignes sans nom de structure sont ignorées.
COLONNES_ATTENDUES = ["NOM DU CLIENT"]


def _clean_str(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return clean_mojibake(str(value)).strip()


def _clean_annee_ou_texte(value):
    """DATE DEBUT / DATE PREV. FIN ne sont pas des dates précises dans la source :
    le plus souvent juste une année brute (2025.0), parfois un mois textuel
    ("JANVIER", "DECEMBRE 2026"), rarement une vraie date complète. On normalise
    tout en texte plutôt que d'utiliser parse_date_flexible, qui interprète à tort
    une année brute comme un numéro de série Excel (bug réel observé : la valeur
    2025 devenait la date "1905-07-16", cf. historique du fichier).

    Quelques cellules contiennent malgré tout un véritable numéro de série Excel
    (ex: 46327 -> 2026-11-01) plutôt qu'une année brute. Les deux se distinguent
    sans ambiguïté par l'ordre de grandeur (une année est à 4 chiffres ~2000-2100,
    un numéro de série correspondant à cette période est >20000)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (int, float)) and value == int(value):
        nombre = int(value)
        if 1900 <= nombre <= 2100:
            return str(nombre)
        return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=nombre)).date().isoformat()
    return clean_mojibake(str(value)).strip()


def _parse_niveaux(type_batiment):
    m = re.search(r"R\s*\+?\s*(\d+)", type_batiment.upper())
    return int(m.group(1)) if m else None


def _parse_oui_non(value):
    v = _clean_str(value).upper()
    if v == "OUI":
        return True
    if v == "NON":
        return False
    return None  # valeur absente ou ambiguë (ex: "2027" observé une fois)


def _split_interlocuteur(value):
    v = _clean_str(value)
    if "/" in v:
        nom, fonction = v.split("/", 1)
        return nom.strip(), fonction.strip()
    return v, ""


def _resolve_commercial(value, cache):
    v = _clean_str(value).upper()
    if not v:
        return None
    if v in cache:
        return cache[v]
    commercial = None
    for substring, username in COMMERCIAL_USERNAME_BY_SUBSTRING:
        if substring in v:
            commercial = User.objects.filter(username=username).first()
            break
    cache[v] = commercial
    return commercial


def colonnes_manquantes(df):
    return [c for c in COLONNES_ATTENDUES if c not in df.columns]


def importer_depuis_dataframe(df, cree_par):
    """Crée un ImmeubleProspecte (+ DemarcheAdministrative CIE/SODECI) par ligne du
    DataFrame qui porte au moins une donnée exploitable. N'efface jamais rien,
    c'est à l'appelant de décider s'il veut un ajout pur (import web incrémental)
    ou un rafraîchissement complet (commande d'import, qui supprime ses propres
    anciennes lignes avant d'appeler cette fonction).

    Une ligne sans "NOM DU CLIENT" mais avec d'autres données (zone, type de
    bâtiment, contact...) n'est PAS ignorée : elle est importée avec un nom
    provisoire "(à compléter)", à corriger ensuite via la liste/modification.
    La jeter aurait perdu de vraies données de prospection pour la seule raison
    qu'une colonne n'avait pas été remplie sur le terrain. Seules les lignes
    entièrement vides sont ignorées. Retourne (nb_crees, nb_ignores_vides,
    nb_a_completer)."""
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]

    dr_par_code = {dr.code: dr for dr in DirectionRegionale.objects.all()}
    commercial_cache = {}

    nb_crees, nb_ignores_vides, nb_a_completer = 0, 0, 0
    for d in df.to_dict("records"):
        nom_structure = _clean_str(d.get("NOM DU CLIENT"))
        if not nom_structure:
            ligne_a_des_donnees = any(
                _clean_str(v) for k, v in d.items() if k not in ("N", "NOM DU CLIENT")
            )
            if not ligne_a_des_donnees:
                nb_ignores_vides += 1
                continue
            nom_structure = "(à compléter)"
            nb_a_completer += 1

        zone_prospection = _clean_str(d.get("ZONE DE PROSPECTION"))
        interlocuteur, fonction = _split_interlocuteur(d.get("INTERLOCUTEUR/FONCTION"))
        type_batiment = _clean_str(d.get("TYPE BATIMENT"))
        stade_brut = _clean_str(d.get("STADE D'AVANCEMENT")).upper()
        dr_code = _clean_str(d.get("DR")).upper()

        nb_appart = d.get("NOMBRES D'APPARTEMENTS/BUREAU")
        nb_appart = int(nb_appart) if pd.notna(nb_appart) else None

        montant_bra = d.get("MONTANT BRA PAYE")
        montant_bra = montant_bra if pd.notna(montant_bra) and isinstance(montant_bra, (int, float)) else None

        observations_brutes = [
            _clean_str(d.get("DETAILS CONS.")),
            _clean_str(d.get("DETAILS DEMANDE")),
            _clean_str(d.get("DETAILS DATE")),
            _clean_str(d.get("OBSERVATIONS")),
        ]
        observations = " | ".join(s for s in observations_brutes if s)

        ccgc_raw = _clean_str(d.get("SDGU CIE/SODECI COMMERCIAL"))
        immeuble = ImmeubleProspecte.objects.create(
            date_visite=parse_date_flexible(d.get("DATE")),
            nom_structure=nom_structure,
            constructeur=_clean_str(d.get("CONSTRUCTEUR")),
            interlocuteur=interlocuteur,
            fonction_interlocuteur=fonction,
            contact=_clean_str(d.get("CONTACTS")),
            email=_clean_str(d.get("EMAIL")),
            situation_geographique=_clean_str(d.get("SITUATION GEOGRAPHIQUE")),
            zone_prospection=zone_prospection,
            direction_regionale=dr_par_code.get(dr_code),
            nb_niveaux=_parse_niveaux(type_batiment) if type_batiment else None,
            nb_appartements_bureaux=nb_appart,
            stade_avancement=STADE_NORMALISE.get(stade_brut, ""),
            date_debut_travaux=_clean_annee_ou_texte(d.get("DATE DEBUT")),
            date_prev_fin_travaux=_clean_annee_ou_texte(d.get("DATE PREV. FIN")),
            delai_livraison=_clean_str(d.get("DELAI DE LIVRAISON")),
            poste_existant=_parse_oui_non(d.get("POSTE EXISTENT")),
            montant_bra_paye=montant_bra,
            observations=observations,
            ccgc_nom=ccgc_raw[:100],
            commercial=_resolve_commercial(ccgc_raw, commercial_cache),
            cree_par=cree_par,
        )

        type_demande_brut = _clean_str(d.get("TYPE DEMANDE")).upper()
        type_demande = TYPE_DEMANDE_NORMALISE.get(type_demande_brut, "")

        demande_cie = _parse_oui_non(d.get("DEMANDE CIE"))
        if demande_cie is not None:
            DemarcheAdministrative.objects.create(
                immeuble=immeuble,
                organisme=DemarcheAdministrative.CIE,
                demande_initiee=demande_cie,
                type_demande=type_demande,
            )

        demande_sodeci = _parse_oui_non(d.get("DEMANDE SODECI"))
        if demande_sodeci is not None:
            DemarcheAdministrative.objects.create(
                immeuble=immeuble,
                organisme=DemarcheAdministrative.SODECI,
                demande_initiee=demande_sodeci,
                type_demande=type_demande if demande_cie is None else "",
            )

        nb_crees += 1

    return nb_crees, nb_ignores_vides, nb_a_completer
