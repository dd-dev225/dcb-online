"""Importe les opérateurs immobiliers (promoteurs) suivis par la SDGU depuis
informations clients/dcb/Guichet Unique/Portefeuille Operateurs Imm/
BASE OPERATEURS PAR COMMERCIALE.xlsx (3 feuilles : BOGA, DIOMANDE, SYLLA).

Snapshot : supprime + recrée à chaque run.
Après l'import, met à jour le FK operateur sur les ImmeubleProspecte dont le
champ constructeur correspond (correspondance souple sur préfixe normalisé).
"""

import re

import pandas as pd
from django.core.management.base import BaseCommand

from importers.utils import INFO_CLIENTS_DIR
from prospection.models import ImmeubleProspecte, OperateurImmobilier

CCGC_SHEET_MAP = {
    "BOGA": OperateurImmobilier.BOGA,
    "DIOMANDE": OperateurImmobilier.DIOMANDE,
    "SYLLA": OperateurImmobilier.SYLLA,
}

PATH = (
    INFO_CLIENTS_DIR
    / "dcb"
    / "Guichet Unique"
    / "Portefeuille Operateurs Imm"
    / "BASE OPERATEURS PAR COMMERCIALE.xlsx"
)


def _normalise(nom):
    """Clé de matching : majuscules, sans ponctuation ni espaces superflus."""
    return re.sub(r"[^A-Z0-9]", "", str(nom).upper())


def _col_nom(df):
    """Retourne la colonne 'nom de l'opérateur' quelle que soit la feuille."""
    for c in df.columns:
        if "operat" in c.lower() or c.upper() in ("NOM", "OPERATEURS"):
            return c
    return df.columns[1]  # fallback : 2e colonne


def _col_contact(df):
    for c in df.columns:
        if "contact" in c.lower():
            return c
    return None


class Command(BaseCommand):
    help = "Importe OperateurImmobilier depuis BASE OPERATEURS PAR COMMERCIALE.xlsx (SDGU)."

    def handle(self, *args, **options):
        self.stdout.write(f"Lecture de {PATH}...")

        to_create = []
        for sheet, ccgc_code in CCGC_SHEET_MAP.items():
            df = pd.read_excel(PATH, sheet_name=sheet, dtype=str)
            col_nom = _col_nom(df)
            col_contact = _col_contact(df)
            for _, row in df.iterrows():
                nom = str(row[col_nom]).strip() if pd.notna(row[col_nom]) else ""
                if not nom or nom.lower() in ("nan", "n", "n°"):
                    continue
                contact = str(row[col_contact]).strip() if col_contact and pd.notna(row[col_contact]) else ""
                to_create.append(OperateurImmobilier(
                    nom=nom[:255],
                    contact=contact[:150],
                    ccgc=ccgc_code,
                ))

        OperateurImmobilier.objects.all().delete()
        OperateurImmobilier.objects.bulk_create(to_create)
        self.stdout.write(f"{len(to_create)} opérateurs créés.")

        # Lier les ImmeubleProspecte via CONSTRUCTEUR -> OperateurImmobilier.nom
        ops = {_normalise(op.nom): op for op in OperateurImmobilier.objects.all()}
        rattaches = 0
        for imm in ImmeubleProspecte.objects.exclude(constructeur=""):
            cle = _normalise(imm.constructeur)
            # Matching exact d'abord, puis sur le préfixe le plus long en common
            op = ops.get(cle)
            if op is None:
                # Cherche un opérateur dont la clé normalisée est contenue dans constructeur
                for cle_op, candidat in ops.items():
                    if len(cle_op) >= 4 and (cle_op in cle or cle in cle_op):
                        op = candidat
                        break
            if op and imm.operateur_id != op.pk:
                imm.operateur = op
                imm.save(update_fields=["operateur"])
                rattaches += 1

        self.stdout.write(self.style.SUCCESS(
            f"OperateurImmobilier : {len(to_create)} importés, {rattaches} immeubles rattachés."
        ))
