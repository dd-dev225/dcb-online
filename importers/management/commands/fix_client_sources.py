"""Commande one-shot : marque avec source='facturation' les clients qui existent
dans la base de facturation (V_Fait_Fact_HT_DCB.xlsx) mais sont absents du fichier
maître Client DCB.xlsx. Ces "clients gap" ont été créés par import_clients_abonnements
avant l'ajout du champ source et héritaient donc du défaut 'dcb_file' (incorrect).

À exécuter une seule fois après la migration 0009_client_source.
Pour les futures exécutions de import_clients_abonnements, les nouveaux clients gap
seront directement créés avec source='facturation' (cf. import_clients_abonnements.py).
"""

import pandas as pd
from django.core.management.base import BaseCommand

from clients.models import Client
from importers.utils import DATA_DIR, INFO_CLIENTS_DIR, normalize_identifiant


class Command(BaseCommand):
    help = "Corrige source='facturation' pour les clients absents du fichier maître Client DCB.xlsx."

    def handle(self, *args, **options):
        # Idabons présents dans le fichier maître DCB
        path_dcb = INFO_CLIENTS_DIR / "dcb" / "Client DCB.xlsx"
        self.stdout.write(f"Lecture de {path_dcb}...")
        df_dcb = pd.read_excel(path_dcb, sheet_name="HT GLOBAL", dtype=str)
        col_id = next(c for c in df_dcb.columns if "identifiant" in c.lower() or "idabon" in c.lower())
        dcb_idabons = {normalize_identifiant(v) for v in df_dcb[col_id].dropna()}
        self.stdout.write(f"{len(dcb_idabons)} idabons dans Client DCB.xlsx.")

        # Clients en base dont l'idabon n'est pas dans le fichier maître
        tous = list(Client.objects.values_list("pk", "idabon", "source"))
        gap_pks = [pk for pk, idabon, source in tous if normalize_identifiant(idabon) not in dcb_idabons]

        updated = Client.objects.filter(pk__in=gap_pks).update(source=Client.FACTURATION)
        self.stdout.write(self.style.SUCCESS(
            f"source mis à jour : {updated} clients gap marqués 'facturation' "
            f"({len(tous) - updated} clients restent 'dcb_file')."
        ))
