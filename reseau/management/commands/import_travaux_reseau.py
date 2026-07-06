"""Importe TravauxReseau depuis tous les fichiers MANTBCC GLOBAL <année>.xlsx.

Même principe que import_incidents_reseau (cf. ce fichier pour le détail des
choix : colonnes retrouvées par nom plutôt que position, upsert par lots
bulk_create/bulk_update pour la vitesse, et surtout import INCRÉMENTAL qui
COMPLÈTE la base existante au lieu de la recharger, demande utilisateur
explicite puisque ces fichiers arrivent chaque semaine/mois).
code_rattachement est ici la clé naturelle (équivalent de numero_incident pour
les incidents).
"""

import pandas as pd
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import DirectionRegionale
from importers.utils import INFO_CLIENTS_DIR, find_column
from reseau.models import TravauxReseau
from reseau.zones import construire_zone_par_depart, normaliser_site

TAILLE_LOT = 2000
TAILLE_LOT_MAJ = 500  # cf. import_incidents_reseau.py pour la justification

CHAMPS_MAJ = [
    "direction_regionale", "poste_site", "nom_depart", "zone_industrielle",
    "date_heure_debut", "date_heure_fin", "duree_minutes", "imputation",
    "puissance_coupee_kw", "energie_non_distribuee_mwh", "nb_reclamations",
    "nature", "lieu_defaut", "type_manoeuvre", "description",
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
    help = "Importe (complète) TravauxReseau depuis tous les fichiers MANTBCC GLOBAL <année>.xlsx disponibles."

    def handle(self, *args, **options):
        dossier = INFO_CLIENTS_DIR / "dcb" / "Support Technique" / "base pertubation"
        fichiers = sorted(dossier.glob("*/MANTBCC GLOBAL *.xlsx"))
        if not fichiers:
            self.stdout.write(self.style.WARNING(f"Aucun fichier MANTBCC trouvé sous {dossier}."))
            return

        dr_par_code = {dr.code: dr for dr in DirectionRegionale.objects.all()}
        zone_par_depart = construire_zone_par_depart()
        pk_par_code = dict(TravauxReseau.objects.values_list("code_rattachement", "pk"))

        nb_crees, nb_maj, nb_sans_dr, nb_sans_code = 0, 0, 0, 0

        for path in fichiers:
            self.stdout.write(f"Lecture de {path}...")
            df = pd.read_excel(path, dtype={"CODE_RATTACHEMENT": str})

            col_code = find_column(df, "code_rattachement")
            col_dr = find_column(df, "nom_abrege")
            col_poste = find_column(df, "poste_nom_site")
            col_depart = find_column(df, "nom_expl")
            col_debut = find_column(df, "date_heure_debut")
            col_fin = _colonne_optionnelle(df, "date_heure_fin")
            col_duree = _colonne_optionnelle(df, "duree")
            col_imputation = _colonne_optionnelle(df, "imputation")
            col_puissance = _colonne_optionnelle(df, "puissance_coupee")
            col_end = _colonne_optionnelle(df, "end") or _colonne_optionnelle(df, "end", "mwh")
            col_reclam = _colonne_optionnelle(df, "reclamation")
            col_nature = _colonne_optionnelle(df, "nature")
            col_lieu = _colonne_optionnelle(df, "lieu_defaut")
            col_type_man = _colonne_optionnelle(df, "type_manoeuvre")
            col_desc = _colonne_optionnelle(df, "description")

            a_creer, a_maj = {}, {}
            for row in df.itertuples(index=False):
                code = _texte(row, col_code, defaut="")
                if not code:
                    nb_sans_code += 1
                    continue

                dr = dr_par_code.get(_texte(row, col_dr))
                if dr is None:
                    nb_sans_dr += 1

                nom_depart = _texte(row, col_depart)
                poste = _texte(row, col_poste)
                zone = zone_par_depart.get((normaliser_site(poste), normaliser_site(nom_depart)))

                instance = TravauxReseau(
                    code_rattachement=code,
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
                    nature=_texte(row, col_nature),
                    lieu_defaut=_texte(row, col_lieu),
                    type_manoeuvre=_texte(row, col_type_man),
                    description=_texte(row, col_desc)[:255],
                )
                pk_existant = pk_par_code.get(code)
                if pk_existant is None:
                    a_creer.pop(code, None)
                    a_creer[code] = instance
                else:
                    instance.pk = pk_existant
                    a_maj.pop(code, None)
                    a_maj[code] = instance

            if a_creer:
                lot = list(a_creer.values())
                TravauxReseau.objects.bulk_create(lot, batch_size=TAILLE_LOT)
                for inst in lot:
                    pk_par_code[inst.code_rattachement] = inst.pk
                nb_crees += len(lot)
            if a_maj:
                TravauxReseau.objects.bulk_update(list(a_maj.values()), CHAMPS_MAJ, batch_size=TAILLE_LOT_MAJ)
                nb_maj += len(a_maj)

        self.stdout.write(
            self.style.SUCCESS(
                f"TravauxReseau : {nb_crees} créés, {nb_maj} mis à jour "
                f"({nb_sans_dr} sans DR reconnue, {nb_sans_code} sans code ignorés)."
            )
        )
