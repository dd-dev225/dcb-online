"""Étape 7 du pipeline d'import.

Source : data/V_Recouvr_HT.xlsx (272 048 lignes, déjà utilisé pour le référentiel
DR à l'étape 1). Recouvrement.facture reste volontairement null=True : faire
correspondre précisément chaque ligne de recouvrement à une Facture exacte n'est
pas fiable avec les clés disponibles ; le rattachement client+période suffit pour
les KPIs de taux de recouvrement (cf. dashboards Performance).
"""

import pandas as pd
from django.core.management.base import BaseCommand

from facturation.models import Recouvrement
from clients.models import Client
from importers.utils import DATA_DIR, format_idabon, get_or_create_periode_cache

BATCH_SIZE = 2000


class Command(BaseCommand):
    help = "Importe Recouvrement depuis data/V_Recouvr_HT.xlsx."

    def handle(self, *args, **options):
        path = DATA_DIR / "V_Recouvr_HT.xlsx"
        self.stdout.write(f"Lecture de {path}...")
        # dtype=str sur l'identifiant (cf. import_clients_abonnements).
        df = pd.read_excel(path, dtype={"idabon": str})

        client_by_idabon = {c.idabon: c for c in Client.objects.all()}
        periode_cache = {}
        skipped_no_client = 0

        to_create = []
        for row in df.itertuples(index=False):
            idabon = format_idabon(getattr(row, "idabon"))
            client = client_by_idabon.get(idabon)
            if client is None:
                skipped_no_client += 1
                continue
            periode = get_or_create_periode_cache(periode_cache, getattr(row, "Periode"))
            to_create.append(
                Recouvrement(
                    client=client,
                    periode=periode,
                    montant_facture=getattr(row, "Montfact") if pd.notna(getattr(row, "Montfact")) else 0,
                    montant_paye=getattr(row, "MontPaye") if pd.notna(getattr(row, "MontPaye")) else 0,
                )
            )

        for i in range(0, len(to_create), BATCH_SIZE):
            Recouvrement.objects.bulk_create(to_create[i : i + BATCH_SIZE])
        self.stdout.write(
            self.style.SUCCESS(
                f"Recouvrement : {len(to_create)} créés ({skipped_no_client} ignorés sans client)."
            )
        )
