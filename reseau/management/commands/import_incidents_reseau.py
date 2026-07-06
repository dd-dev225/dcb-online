"""Importe IncidentReseau depuis tous les fichiers INCIBCC GLOBAL <année>.xlsx.

Source : informations clients/dcb/Support Technique/base pertubation/<année>/
INCIBCC GLOBAL <année>.xlsx, un fichier par année (2023 à 2026 au moment
d'écrire ceci, mais la commande parcourt le dossier plutôt que de lister les
années en dur, pour absorber les prochains envois sans modification de code).

Le schéma de cet export a varié dans le temps (vérifié : 36 colonnes en 2023-
2024, 23 en 2025, 37 en 2026, certaines colonnes énergie/manœuvre disparaissant
puis réapparaissant). On retrouve donc chaque colonne par son NOM (cf.
importers.utils.find_column, tolérant aux accents) plutôt que par sa position,
et chaque champ logique reste optionnel si sa colonne est absente cette année.

IMPORTANT (demande utilisateur explicite) : ces fichiers arrivent chaque
semaine/mois et chacun doit COMPLÉTER la base déjà importée, jamais la
remplacer. numero_incident (clé naturelle, unique sur la durée de vie du
réseau) pilote donc un upsert (bulk_create + bulk_update par lots, sur la base
des pk déjà connus) : relancer cette commande après un nouvel envoi met
seulement à jour les incidents déjà connus (si une ligne a été corrigée à la
source) et ajoute les nouveaux, sans jamais dupliquer ni perdre d'historique.
"""

import pandas as pd
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import DirectionRegionale
from importers.utils import INFO_CLIENTS_DIR, find_column
from reseau.models import IncidentReseau
from reseau.zones import construire_zone_par_depart, normaliser_site

TAILLE_LOT = 2000
# bulk_update génère un paramètre SQL par (ligne x champ) ; avec 17 champs,
# SQLite (limite par défaut ~32 766 variables) déborde si ce lot est trop
# grand alors que bulk_create n'a pas ce souci (une seule requête INSERT
# multi-valeurs, pas un UPDATE par CASE/WHEN comme bulk_update).
TAILLE_LOT_MAJ = 500

CHAMPS_MAJ = [
    "direction_regionale", "poste_site", "nom_depart", "zone_industrielle",
    "date_heure_debut", "date_heure_fin", "duree_minutes", "imputation",
    "puissance_coupee_kw", "energie_non_distribuee_mwh", "nb_reclamations",
    "signalisation", "lieu_defaut", "description", "cause", "code_cause", "ouvrage_id",
]


def _colonne_optionnelle(df, *parts):
    try:
        return find_column(df, *parts)
    except KeyError:
        return None


def _valeur(row, col):
    if col is None:
        return None
    v = getattr(row, col, None)
    return v if pd.notna(v) else None


def _texte(row, col, defaut=""):
    v = _valeur(row, col)
    return str(v).strip() if v is not None else defaut


def _entier(row, col):
    v = _valeur(row, col)
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _decimal(row, col):
    v = _valeur(row, col)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _date_heure(row, col):
    v = _valeur(row, col)
    if v is None:
        return None
    ts = pd.Timestamp(v)
    if pd.isna(ts):
        return None
    dt = ts.to_pydatetime()
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


class Command(BaseCommand):
    help = "Importe (complète) IncidentReseau depuis tous les fichiers INCIBCC GLOBAL <année>.xlsx disponibles."

    def handle(self, *args, **options):
        dossier = INFO_CLIENTS_DIR / "dcb" / "Support Technique" / "base pertubation"
        fichiers = sorted(dossier.glob("*/INCIBCC GLOBAL *.xlsx"))
        if not fichiers:
            self.stdout.write(self.style.WARNING(f"Aucun fichier INCIBCC trouvé sous {dossier}."))
            return

        dr_par_code = {dr.code: dr for dr in DirectionRegionale.objects.all()}
        zone_par_depart = construire_zone_par_depart()
        pk_par_numero = dict(IncidentReseau.objects.values_list("numero_incident", "pk"))

        nb_crees, nb_maj, nb_sans_dr, nb_sans_numero = 0, 0, 0, 0

        for path in fichiers:
            self.stdout.write(f"Lecture de {path}...")
            df = pd.read_excel(path, dtype={"NUMERO_INCIDENT": str})

            col_numero = find_column(df, "numero", "incident")
            col_dr = find_column(df, "nom_abrege")
            col_poste = find_column(df, "poste_nom_site")
            col_depart = find_column(df, "nom_expl")
            col_debut = find_column(df, "date_heure_debut")
            col_fin = _colonne_optionnelle(df, "date_heure_fin")
            col_duree = _colonne_optionnelle(df, "duree")
            col_imputation = _colonne_optionnelle(df, "imputation")
            col_puissance = _colonne_optionnelle(df, "puissance_coupee")
            col_end = _colonne_optionnelle(df, "end_mwh") or _colonne_optionnelle(df, "end", "mwh")
            col_reclam = _colonne_optionnelle(df, "reclamation")
            col_signal = _colonne_optionnelle(df, "signalisation")
            col_lieu = _colonne_optionnelle(df, "lieu_defaut")
            col_desc = _colonne_optionnelle(df, "description")
            col_cause = _colonne_optionnelle(df, "cause")
            col_code_cause = _colonne_optionnelle(df, "code", "cause")
            col_ouvrage = _colonne_optionnelle(df, "ouvrage_id")

            # dict plutôt que liste : si NUMERO_INCIDENT se répète au sein du même
            # fichier (pas censé arriver, clé naturelle, mais sans garantie sur un
            # export externe), la dernière occurrence écrase la précédente au lieu
            # de provoquer une violation de contrainte unique sur bulk_create.
            a_creer, a_maj = {}, {}
            for row in df.itertuples(index=False):
                numero = _texte(row, col_numero, defaut="")
                if not numero:
                    nb_sans_numero += 1
                    continue

                dr = dr_par_code.get(_texte(row, col_dr))
                if dr is None:
                    nb_sans_dr += 1

                nom_depart = _texte(row, col_depart)
                poste = _texte(row, col_poste)
                zone = zone_par_depart.get((normaliser_site(poste), normaliser_site(nom_depart)))

                instance = IncidentReseau(
                    numero_incident=numero,
                    direction_regionale=dr,
                    poste_site=_texte(row, col_poste),
                    nom_depart=nom_depart,
                    zone_industrielle=zone,
                    date_heure_debut=_date_heure(row, col_debut),
                    date_heure_fin=_date_heure(row, col_fin),
                    duree_minutes=_entier(row, col_duree),
                    imputation=_texte(row, col_imputation),
                    puissance_coupee_kw=_decimal(row, col_puissance),
                    energie_non_distribuee_mwh=_decimal(row, col_end),
                    nb_reclamations=_entier(row, col_reclam),
                    signalisation=_texte(row, col_signal),
                    lieu_defaut=_texte(row, col_lieu),
                    description=_texte(row, col_desc)[:255],
                    cause=_texte(row, col_cause),
                    code_cause=_texte(row, col_code_cause),
                    ouvrage_id=_texte(row, col_ouvrage),
                )
                pk_existant = pk_par_numero.get(numero)
                if pk_existant is None:
                    a_creer.pop(numero, None)
                    a_creer[numero] = instance
                else:
                    instance.pk = pk_existant
                    a_maj.pop(numero, None)
                    a_maj[numero] = instance

            if a_creer:
                lot = list(a_creer.values())
                IncidentReseau.objects.bulk_create(lot, batch_size=TAILLE_LOT)
                for inst in lot:
                    pk_par_numero[inst.numero_incident] = inst.pk
                nb_crees += len(lot)
            if a_maj:
                IncidentReseau.objects.bulk_update(list(a_maj.values()), CHAMPS_MAJ, batch_size=TAILLE_LOT_MAJ)
                nb_maj += len(a_maj)

        self.stdout.write(
            self.style.SUCCESS(
                f"IncidentReseau : {nb_crees} créés, {nb_maj} mis à jour "
                f"({nb_sans_dr} sans DR reconnue, {nb_sans_numero} sans numéro ignorés)."
            )
        )
