"""Étape 2 du pipeline d'import.

Source : data/V_Fait_Fact_HT_DCB.xlsx (105 505 lignes), filtré sur TYPFACT == "E0"
(facture normale, filtre qualité, cf. plan §0 ; ce n'est PAS un filtre de segment,
puisque tout ce dataset est déjà le périmètre Business "DCB").

Déduplique sur IDABON -> Client, puis sur (IDABON, REFRACCORD) -> Abonnement.
Client.entite est dérivé de DEX (Abidjan/Intérieur) ; l'override vers le service
Stratégiques&Sensibles se fait dans import_clients_strategiques.py (étape suivante).
"""

import pandas as pd
from django.core.management.base import BaseCommand

from clients.models import Abonnement, Client
from core.models import DirectionRegionale, Entite
from importers.utils import DATA_DIR, find_column, format_idabon, format_refraccord

BATCH_SIZE = 2000

DEX_TO_ENTITE_CODE = {
    "Abidjan": Entite.ABIDJAN,
    "Intérieur": Entite.INTERIEUR,
}


def _str_or_empty(value):
    """`str(value or "")` est piégeux pour une cellule vide : NaN est "vrai" au sens
    booléen Python (comme dans le bug NaN-or-0 déjà documenté ailleurs dans ce
    pipeline), donc `NaN or ""` vaut NaN, pas "", ce qui produit la chaîne littérale
    "nan" stockée en base plutôt qu'une chaîne vide. pd.notna() lève l'ambiguïté."""
    return str(value) if pd.notna(value) else ""


class Command(BaseCommand):
    help = "Importe Client et Abonnement depuis data/V_Fait_Fact_HT_DCB.xlsx (TYPFACT=E0)."

    def handle(self, *args, **options):
        path = DATA_DIR / "V_Fait_Fact_HT_DCB.xlsx"
        self.stdout.write(f"Lecture de {path}...")
        # dtype=str sur les colonnes identifiants : si IDABON/REFRACCORD ne contenait
        # QUE des valeurs numériques, pandas les inférerait en int64 et perdrait tout
        # zéro de tête (ex: "0218801" -> 218801). Aucun cas réel trouvé dans ce
        # fichier au moment de l'import (vérifié), mais ce n'est pas garanti pour
        # autant (dépend du contenu, pas du nom de la colonne), donc on fige le type
        # par sécurité plutôt que de compter sur la chance.
        df = pd.read_excel(path, dtype={"IDABON": str, "REFRACCORD": str})
        # Renomme les colonnes à accent abîmé en noms ASCII sûrs : pandas .itertuples()
        # remplace sinon ces colonnes par des noms positionnels (_1, _2...) illisibles.
        df = df.rename(
            columns={
                find_column(df, "secteur", "activit"): "secteur_activite_src",
                find_column(df, "branche", "activit"): "branche_activite_src",
            }
        )

        df = df[df["TYPFACT"] == "E0"]
        self.stdout.write(f"{len(df)} lignes après filtre TYPFACT=E0.")

        dr_by_code = {dr.code_numerique: dr for dr in DirectionRegionale.objects.all()}
        entite_by_code = {e.code: e for e in Entite.objects.all()}

        # --- Client ---
        clients_df = df.drop_duplicates(subset=["IDABON"], keep="last")
        existing_idabon = set(Client.objects.values_list("idabon", flat=True))
        to_create = []
        for row in clients_df.itertuples(index=False):
            idabon = format_idabon(getattr(row, "IDABON"))
            if idabon in existing_idabon:
                continue
            dr = dr_by_code.get(getattr(row, "DR"))
            entite_code = DEX_TO_ENTITE_CODE.get(str(getattr(row, "DEX")))
            to_create.append(
                Client(
                    idabon=idabon,
                    nom_prenoms=_str_or_empty(getattr(row, "Nom_Prenoms")),
                    secteur_activite=_str_or_empty(getattr(row, "secteur_activite_src")),
                    branche_activite=_str_or_empty(getattr(row, "branche_activite_src")),
                    direction_regionale=dr,
                    entite=entite_by_code.get(entite_code),
                    dans_facturation=True,
                )
            )
            existing_idabon.add(idabon)
        for i in range(0, len(to_create), BATCH_SIZE):
            Client.objects.bulk_create(to_create[i : i + BATCH_SIZE], ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f"Client : {len(to_create)} créés."))

        # --- Abonnement ---
        client_by_idabon = {c.idabon: c for c in Client.objects.all()}
        abon_df = df.drop_duplicates(subset=["IDABON", "REFRACCORD"], keep="last")
        existing_abon_keys = set(
            Abonnement.objects.values_list("client__idabon", "refraccord")
        )
        abon_to_create = []
        for row in abon_df.itertuples(index=False):
            idabon = format_idabon(getattr(row, "IDABON"))
            refraccord = format_refraccord(getattr(row, "REFRACCORD")) or ""
            if (idabon, refraccord) in existing_abon_keys:
                continue
            client = client_by_idabon.get(idabon)
            if client is None:
                continue
            posabon = getattr(row, "POSABON")
            abon_to_create.append(
                Abonnement(
                    client=client,
                    refraccord=refraccord,
                    typabon=_str_or_empty(getattr(row, "Typabon")),
                    posabon=str(int(posabon)).zfill(2) if pd.notna(posabon) else "",
                    psabon=getattr(row, "PSABON") if pd.notna(getattr(row, "PSABON")) else None,
                    tranche_puissance=_str_or_empty(getattr(row, "Tranche_Puissance")),
                    typcomptage=_str_or_empty(getattr(row, "TYPCOMPTAGE")),
                    codtarif=_str_or_empty(getattr(row, "CODTARIF")),
                )
            )
            existing_abon_keys.add((idabon, refraccord))
        for i in range(0, len(abon_to_create), BATCH_SIZE):
            Abonnement.objects.bulk_create(abon_to_create[i : i + BATCH_SIZE], ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f"Abonnement : {len(abon_to_create)} créés."))
