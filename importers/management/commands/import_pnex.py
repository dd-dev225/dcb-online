"""Étape 6 du pipeline d'import.

Sources :
- data/V_PNEX_HT.xlsx (35 colonnes) : suivi détaillé des demandes en cours, avec
  IDABON -> peut créer une DemandeRaccordement à la volée si NUMDI absente (cas
  normal : ce flux est distinct de l'historique facturé de V_Fait_Raccord_Dash_DCB).
  DR y est concaténé "03-DRYOP" (cf. split_dr_code) ; Date_initiation est un YYYYMM.
- data/ADJ_PNEX_ HT.xlsx (23 colonnes, espace dans le nom de fichier) : vue ajustée
  SANS IDABON, donc ne peut que mettre à jour un SuiviDemande déjà créé via NUMDI,
  jamais en créer un nouveau (pas de client à rattacher).
"""

import pandas as pd
from django.core.management.base import BaseCommand

from clients.models import Client
from demandes_raccordement.models import DemandeRaccordement, SuiviDemande
from core.models import DirectionRegionale
from importers.utils import (
    DATA_DIR,
    clean_mojibake,
    format_idabon,
    parse_date_flexible,
    periode_annee_mois,
    split_dr_code,
)
from datetime import date


def _int_or_none(value):
    return int(value) if pd.notna(value) else None


class Command(BaseCommand):
    help = "Importe SuiviDemande (+ DemandeRaccordement si besoin) depuis V_PNEX_HT et ADJ_PNEX_ HT."

    def handle(self, *args, **options):
        self._import_v_pnex()
        self._import_adj_pnex()

    def _import_v_pnex(self):
        path = DATA_DIR / "V_PNEX_HT.xlsx"
        self.stdout.write(f"Lecture de {path}...")
        # dtype=str sur les identifiants (cf. import_clients_abonnements), vient en
        # complément de coerce_id_str ci-dessous, qui nettoie la représentation
        # ("3301903.0" -> "3301903") mais ne peut pas récupérer un zéro de tête déjà
        # perdu par l'inférence de type de pandas avant que le code Python n'intervienne.
        df = pd.read_excel(path, dtype={"IDABON": str, "NUMDI": str})

        client_by_idabon = {c.idabon: c for c in Client.objects.all()}
        dr_by_code = {dr.code: dr for dr in DirectionRegionale.objects.all()}
        demande_by_numdi = {d.numdi: d for d in DemandeRaccordement.objects.all()}

        created_demande, created_suivi, updated_suivi = 0, 0, 0
        skipped_no_client, skipped_no_dr = 0, 0

        for row in df.itertuples(index=False):
            numdi = str(getattr(row, "NUMDI"))
            demande = demande_by_numdi.get(numdi)

            if demande is None:
                idabon = format_idabon(getattr(row, "IDABON"))
                if idabon is None:
                    skipped_no_client += 1
                    continue
                client = client_by_idabon.get(idabon)
                if client is None:
                    skipped_no_client += 1
                    continue
                _, dr_libelle = split_dr_code(getattr(row, "DR"))
                dr = dr_by_code.get(dr_libelle)
                if dr is None:
                    skipped_no_dr += 1
                    continue
                annee, mois = periode_annee_mois(getattr(row, "Date_initiation"))
                demande = DemandeRaccordement.objects.create(
                    client=client,
                    direction_regionale=dr,
                    numdi=numdi,
                    typdi=str(getattr(row, "TYPDI")),
                    date_initiation=date(annee, mois, 1),
                    montant_demande=getattr(row, "MONTDDE") if pd.notna(getattr(row, "MONTDDE")) else None,
                    montant_net=getattr(row, "MONTASC") if pd.notna(getattr(row, "MONTASC")) else None,
                )
                demande_by_numdi[numdi] = demande
                created_demande += 1

            defaults = dict(
                etape=clean_mojibake(getattr(row, "Etape")),
                date_paiement=parse_date_flexible(getattr(row, "date_paiement")),
                date_validation_devis=parse_date_flexible(getattr(row, "date_validation_devis")),
                date_execution=parse_date_flexible(getattr(row, "date_execution")),
                duree_validation_devis=_int_or_none(getattr(row, "duree_Val_Devis")),
                duree_totale=_int_or_none(getattr(row, "dureedelademande")),
                tranche_delai=clean_mojibake(getattr(row, "tranche_delai")),
            )
            _, was_created = SuiviDemande.objects.update_or_create(demande=demande, defaults=defaults)
            created_suivi += int(was_created)
            updated_suivi += int(not was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"V_PNEX_HT : {created_demande} DemandeRaccordement créées, "
                f"{created_suivi} SuiviDemande créés, {updated_suivi} mis à jour "
                f"({skipped_no_client} sans client, {skipped_no_dr} sans DR)."
            )
        )

    def _import_adj_pnex(self):
        path = DATA_DIR / "ADJ_PNEX_ HT.xlsx"
        self.stdout.write(f"Lecture de {path}...")
        # dtype=str sur l'identifiant (cf. import_clients_abonnements).
        df = pd.read_excel(path, dtype={"NUMDI": str})

        suivi_by_numdi = {s.demande.numdi: s for s in SuiviDemande.objects.select_related("demande").all()}
        updated, skipped_unknown_numdi = 0, 0

        for row in df.itertuples(index=False):
            numdi = str(getattr(row, "NUMDI"))
            suivi = suivi_by_numdi.get(numdi)
            if suivi is None:
                skipped_unknown_numdi += 1
                continue
            if not suivi.etape:
                suivi.etape = clean_mojibake(getattr(row, "Etape"))
            if suivi.date_execution is None:
                suivi.date_execution = parse_date_flexible(getattr(row, "date_execution"))
            if suivi.duree_totale is None:
                suivi.duree_totale = _int_or_none(getattr(row, "Duree_To"))
            if not suivi.tranche_delai:
                suivi.tranche_delai = clean_mojibake(getattr(row, "tranche_Duree_To"))
            suivi.save(update_fields=["etape", "date_execution", "duree_totale", "tranche_delai"])
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"ADJ_PNEX_HT : {updated} SuiviDemande complétés "
                f"({skipped_unknown_numdi} NUMDI inconnus, ignorés faute de client à rattacher)."
            )
        )
