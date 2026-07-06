"""Étape 5 du pipeline d'import.

Source : data/V_Fait_Raccord_Dash_DCB.xlsx (16 colonnes). Contrairement à
V_Fait_Fact_HT_DCB, le DR y est déjà numérique simple (pas de concaténation
"02-DRAS"), et Date_Periode y est un numéro de série Excel brut (cf. parse_date_flexible).
Cette source n'a pas de date d'initiation propre : Date_Periode (période de
facturation de la demande) est utilisée comme valeur d'approximation pour
date_initiation, affinée si besoin par import_pnex.py (source avec Date_initiation
réelle) sur les NUMDI communs.
"""

import pandas as pd
from django.core.management.base import BaseCommand

from clients.models import Client
from demandes_raccordement.models import DemandeRaccordement
from core.models import DirectionRegionale
from importers.utils import DATA_DIR, format_idabon, parse_date_flexible

BATCH_SIZE = 2000


class Command(BaseCommand):
    help = "Importe DemandeRaccordement depuis data/V_Fait_Raccord_Dash_DCB.xlsx."

    def handle(self, *args, **options):
        path = DATA_DIR / "V_Fait_Raccord_Dash_DCB.xlsx"
        self.stdout.write(f"Lecture de {path}...")
        # dtype=str sur les identifiants (cf. import_clients_abonnements).
        df = pd.read_excel(path, dtype={"IDABON": str, "NUMDI": str})

        client_by_idabon = {c.idabon: c for c in Client.objects.all()}
        dr_by_code = {dr.code_numerique: dr for dr in DirectionRegionale.objects.all()}
        existing_numdi = set(DemandeRaccordement.objects.values_list("numdi", flat=True))

        to_create = []
        skipped_no_client, skipped_no_dr = 0, 0
        for row in df.itertuples(index=False):
            numdi = str(getattr(row, "NUMDI"))
            if numdi in existing_numdi:
                continue
            idabon = format_idabon(getattr(row, "IDABON"))
            client = client_by_idabon.get(idabon)
            if client is None:
                skipped_no_client += 1
                continue
            dr = dr_by_code.get(getattr(row, "DR"))
            if dr is None:
                skipped_no_dr += 1
                continue
            to_create.append(
                DemandeRaccordement(
                    client=client,
                    direction_regionale=dr,
                    numdi=numdi,
                    typdi=str(getattr(row, "TYPDI")),
                    date_initiation=parse_date_flexible(getattr(row, "Date_Periode")),
                    montant_demande=getattr(row, "MONTDDE") if pd.notna(getattr(row, "MONTDDE")) else None,
                    montant_net=getattr(row, "Montant_Net") if pd.notna(getattr(row, "Montant_Net")) else None,
                )
            )
            existing_numdi.add(numdi)

        for i in range(0, len(to_create), BATCH_SIZE):
            DemandeRaccordement.objects.bulk_create(to_create[i : i + BATCH_SIZE])
        self.stdout.write(
            self.style.SUCCESS(
                f"DemandeRaccordement : {len(to_create)} créées "
                f"({skipped_no_client} ignorées sans client, {skipped_no_dr} sans DR)."
            )
        )
