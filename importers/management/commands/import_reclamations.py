"""Étape 8 (dernière) du pipeline d'import V1.

Source : data/Etat des Sollicitations HT.xlsx (337 lignes, feuille "Reclamation_HT").
Toutes les colonnes source sont stockées dans Reclamation (cf. reclamations.models).

Snapshot : delete + recreate à chaque run.
"""

import pandas as pd
from django.core.management.base import BaseCommand

from clients.models import Client
from reclamations.models import Reclamation
from core.models import DirectionRegionale
from importers.utils import DATA_DIR, find_column, normalize_identifiant, parse_date_flexible

BATCH_SIZE = 2000


def _texte(v, maxlen=None):
    if pd.isna(v):
        return ""
    s = str(v).strip()
    return s[:maxlen] if maxlen else s


def _entier(v):
    try:
        f = float(v)
        return int(round(f))
    except (TypeError, ValueError):
        return None


def _entier_positif(v):
    n = _entier(v)
    return n if n is not None and n >= 0 else None


class Command(BaseCommand):
    help = "Importe Reclamation depuis data/Etat des Sollicitations HT.xlsx (toutes colonnes)."

    def handle(self, *args, **options):
        path = DATA_DIR / "Etat des Sollicitations HT.xlsx"
        self.stdout.write(f"Lecture de {path}...")
        df = pd.read_excel(path, sheet_name="Reclamation_HT")
        self.stdout.write(f"{len(df)} lignes.")

        # Colonnes (noms avec possible mojibake -> find_column)
        C = {
            "dr":                find_column(df, "DR"),
            "num":               find_column(df, "Num", "Sollicitation"),
            "auteur_creation":   find_column(df, "Auteur", "Creation"),
            "agence":            find_column(df, "Agence"),
            "date_creation":     find_column(df, "Date", "Cr"),
            "canal":             find_column(df, "Canal"),
            "statut":            find_column(df, "Statut"),
            "priorite":          find_column(df, "Priorit"),
            "nom_client":        find_column(df, "Nom client"),
            "contact":           find_column(df, "Contact"),
            "email":             find_column(df, "Email"),
            "identifiant":       find_column(df, "Identifiant"),
            "branchement":       find_column(df, "Branchement"),
            "type_client":       find_column(df, "Type client"),
            "segment_client":    find_column(df, "Segment client"),
            "sous_segment":      find_column(df, "Sous segment"),
            "type_sollicitation":find_column(df, "Type Sollicitation"),
            "type_reclamation":  find_column(df, "Type", "clamation"),
            "typologie":         find_column(df, "Typologie"),
            "sous_typo":         find_column(df, "Sous Typ"),
            "nature":            find_column(df, "Nature"),
            "rapport_creation":  find_column(df, "Rapport", "Cr"),
            "partenaire":        find_column(df, "Partenaire"),
            "nb_relances":       find_column(df, "Relance"),
            "groupe_dest":       find_column(df, "Groupe"),
            "date_modif":        find_column(df, "Date modification"),
            "motif_modif":       find_column(df, "Motif Modification"),
            "statut_client":     find_column(df, "Statut Client"),
            "motif_retab":       find_column(df, "tablissement"),
            "date_traitement":   find_column(df, "Date de traitement"),
            "delai_trait":       find_column(df, "lai de traitement"),
            "delai_cont_trait":  find_column(df, "contractuel de traitement"),
            "ecart_trait":       find_column(df, "Ecart"),
            "acteur_trait":      find_column(df, "Acteur"),
            "rapport_trait":     find_column(df, "Rapport de traitement"),
            "date_verif":        find_column(df, "Date de", "rification"),
            "delai_verif":       find_column(df, "lai de", "rification"),
            "delai_cont_verif":  find_column(df, "contractuel de", "rification"),
            "ecart_verif":       find_column(df, "Ecart.1"),
            "auteur_cloture":    find_column(df, "Auteur", "ture"),
            "rapport_verif":     find_column(df, "Rapport de", "rification"),
        }

        dr_by_code   = {dr.code: dr for dr in DirectionRegionale.objects.all()}
        client_by_norm = {normalize_identifiant(c.idabon): c for c in Client.objects.all()}

        to_create = []
        rattaches, sans_dr = 0, 0

        for _, row in df.iterrows():
            dr = dr_by_code.get(_texte(row[C["dr"]]))
            if dr is None:
                sans_dr += 1
                continue

            identifiant_brut = _texte(row[C["identifiant"]])
            client = None
            if identifiant_brut:
                client = client_by_norm.get(normalize_identifiant(identifiant_brut))
            rattaches += int(client is not None)

            to_create.append(Reclamation(
                # Identification
                numero_sollicitation  = _texte(row[C["num"]], 25),
                direction_regionale   = dr,
                agence                = _texte(row[C["agence"]], 30),
                auteur_creation       = _texte(row[C["auteur_creation"]], 50),
                # Canal / dates
                date_creation         = parse_date_flexible(row[C["date_creation"]]),
                canal                 = _texte(row[C["canal"]], 30),
                statut                = _texte(row[C["statut"]], 30),
                priorite              = _texte(row[C["priorite"]], 20),
                # Client
                client                = client,
                identifiant_contrat   = identifiant_brut[:20],
                nom_client            = _texte(row[C["nom_client"]], 100),
                contact               = _texte(row[C["contact"]], 30),
                email                 = _texte(row[C["email"]], 100),
                branchement           = _texte(row[C["branchement"]], 20),
                type_client           = _texte(row[C["type_client"]], 30),
                segment_client        = _texte(row[C["segment_client"]], 30),
                sous_segment          = _texte(row[C["sous_segment"]], 50),
                # Qualification
                type_sollicitation    = _texte(row[C["type_sollicitation"]], 20),
                type_reclamation      = _texte(row[C["type_reclamation"]], 20),
                typologie_reclamation = _texte(row[C["typologie"]], 20),
                sous_typologie        = _texte(row[C["sous_typo"]], 20),
                nature_reclamation    = _texte(row[C["nature"]], 50),
                rapport_creation      = _texte(row[C["rapport_creation"]]),
                partenaire            = _texte(row[C["partenaire"]], 100),
                nombre_relances       = _entier_positif(row[C["nb_relances"]]),
                groupe_destinataire   = _texte(row[C["groupe_dest"]], 120),
                # Modifications / suivi
                date_modification     = parse_date_flexible(row[C["date_modif"]]),
                motif_modification    = _texte(row[C["motif_modif"]], 255),
                statut_client         = _texte(row[C["statut_client"]], 50),
                motif_retablissement  = _texte(row[C["motif_retab"]], 255),
                # Traitement
                date_cloture          = parse_date_flexible(row[C["date_traitement"]]),
                delai_traitement      = _entier_positif(row[C["delai_trait"]]),
                delai_contractuel_traitement = _entier(row[C["delai_cont_trait"]]),
                ecart_traitement      = _entier(row[C["ecart_trait"]]),
                acteur_traitement     = _texte(row[C["acteur_trait"]], 50),
                rapport_traitement    = _texte(row[C["rapport_trait"]]),
                # Vérification
                date_verification     = parse_date_flexible(row[C["date_verif"]]),
                delai_verification    = _entier(row[C["delai_verif"]]),
                delai_contractuel_verification = _entier(row[C["delai_cont_verif"]]),
                ecart_verification    = _entier(row[C["ecart_verif"]]),
                auteur_cloture        = _texte(row[C["auteur_cloture"]], 50),
                rapport_verification  = _texte(row[C["rapport_verif"]]),
            ))

        Reclamation.objects.all().delete()
        for i in range(0, len(to_create), BATCH_SIZE):
            Reclamation.objects.bulk_create(to_create[i : i + BATCH_SIZE])

        self.stdout.write(self.style.SUCCESS(
            f"Reclamation : {len(to_create)} créées "
            f"({rattaches} rattachées à un client, {sans_dr} ignorées sans DR)."
        ))
