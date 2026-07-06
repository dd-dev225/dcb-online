"""Étape 4 du pipeline d'import, même source que import_clients_abonnements.

Une Facture par ligne filtrée TYPFACT=="E0" de data/V_Fait_Fact_HT_DCB.xlsx.
Client/Abonnement/Periode sont résolus via des dictionnaires chargés une fois en
mémoire (évite le N+1 sur 100k+ lignes).

NUMFACT n'est PAS un identifiant de facture unique (vérifié : seulement 819 valeurs
distinctes sur 100 639 lignes filtrées, donc un compteur/séquence sans rapport avec
la grain réelle de la table). Il est conservé comme simple attribut d'affichage,
mais la clé d'idempotence de l'import est (client, abonnement, periode), qui
correspond à la vraie granularité d'une ligne (un abonnement facturé sur un mois).
"""

import pandas as pd
from django.core.management.base import BaseCommand

from facturation.models import Facture
from clients.models import Abonnement, Client
from importers.utils import (
    DATA_DIR,
    find_column,
    format_idabon,
    format_refraccord,
    get_or_create_periode_cache,
    periode_annee_mois,
)

BATCH_SIZE = 2000


class Command(BaseCommand):
    help = "Importe Facture depuis data/V_Fait_Fact_HT_DCB.xlsx (TYPFACT=E0)."

    def handle(self, *args, **options):
        path = DATA_DIR / "V_Fait_Fact_HT_DCB.xlsx"
        self.stdout.write(f"Lecture de {path}...")
        # dtype=str sur les identifiants : évite que pandas n'infère IDABON/REFRACCORD/
        # NUMFACT en numérique et ne perde un éventuel zéro de tête (cf. import_clients_abonnements).
        df = pd.read_excel(path, dtype={"IDABON": str, "REFRACCORD": str, "NUMFACT": str})
        # Renomme la colonne à accent abîmé en nom ASCII sûr (cf. import_clients_abonnements).
        df = df.rename(columns={find_column(df, "penalit", "ttc"): "penalite_ttc_src"})
        df = df[df["TYPFACT"] == "E0"]
        self.stdout.write(f"{len(df)} lignes après filtre TYPFACT=E0.")

        client_by_idabon = {c.idabon: c for c in Client.objects.all()}
        abon_by_key = {
            (a.client.idabon, a.refraccord): a
            for a in Abonnement.objects.select_related("client").all()
        }
        periode_cache = {}

        existing_keys = set(
            Facture.objects.values_list("client__idabon", "abonnement_id", "periode__annee", "periode__mois")
        )
        to_create = []
        for row in df.itertuples(index=False):
            idabon = format_idabon(getattr(row, "IDABON"))
            client = client_by_idabon.get(idabon)
            if client is None:
                continue
            refraccord = format_refraccord(getattr(row, "REFRACCORD")) or ""
            abonnement = abon_by_key.get((idabon, refraccord))
            annee, mois = periode_annee_mois(getattr(row, "Periode"))
            key = (idabon, abonnement.pk if abonnement else None, annee, mois)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            periode = get_or_create_periode_cache(periode_cache, getattr(row, "Periode"))
            to_create.append(
                Facture(
                    client=client,
                    abonnement=abonnement,
                    periode=periode,
                    numfact=str(getattr(row, "NUMFACT") or ""),
                    typfact=str(getattr(row, "TYPFACT")),
                    consommation_kwh=getattr(row, "Kwhs") if pd.notna(getattr(row, "Kwhs")) else None,
                    montant_facture_ttc=getattr(row, "Mont_fact") if pd.notna(getattr(row, "Mont_fact")) else None,
                    montant_tva_11=getattr(row, "tva_11") if pd.notna(getattr(row, "tva_11")) else None,
                    montant_tva_20=getattr(row, "tva_20") if pd.notna(getattr(row, "tva_20")) else None,
                    penalite_ttc=getattr(row, "penalite_ttc_src") if pd.notna(getattr(row, "penalite_ttc_src")) else None,
                )
            )

        for i in range(0, len(to_create), BATCH_SIZE):
            Facture.objects.bulk_create(to_create[i : i + BATCH_SIZE])
        self.stdout.write(self.style.SUCCESS(f"Facture : {len(to_create)} créées."))
