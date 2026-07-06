"""Import Excel en masse pour la fiche client enrichie, même esprit que
prospection.services (un seul parseur partagé, tolérant, jamais bloquant sur une
ligne ambiguë). Met à jour des clients EXISTANTS (identifiés par idabon ou
référence de raccordement) : n'en crée jamais, un client doit déjà exister dans la
base HT (import_clients_abonnements) avant qu'on puisse compléter sa fiche."""

import pandas as pd
from django.utils import timezone

from .models import Abonnement, Client, Interlocuteur

COLONNES_ATTENDUES = ["IDABON"]

ROLE_PAR_COLONNE_PREFIX = {
    "REPRESENTANT": Interlocuteur.REPRESENTANT_LEGAL,
    "TECHNIQUE": Interlocuteur.TECHNIQUE,
    "COMMERCIAL": Interlocuteur.COMMERCIAL,
}


def colonnes_manquantes(df):
    return [c for c in COLONNES_ATTENDUES if c not in df.columns]


def _clean_str(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _parse_oui_non(value):
    v = _clean_str(value).upper()
    if v in ("OUI", "TRUE", "1"):
        return True
    if v in ("NON", "FALSE", "0"):
        return False
    return None


def importer_fiches_depuis_dataframe(df, scope, maj_par):
    """Met à jour Client/Abonnement/Interlocuteur pour chaque ligne dont l'IDABON
    correspond à un client du périmètre `scope` (Q() déjà filtré par portefeuille,
    on ne met jamais à jour un client hors du périmètre de qui importe). Colonnes
    reconnues : IDABON (obligatoire), SECTEUR_ACTIVITE, BRANCHE_ACTIVITE, A_CONTRAT,
    CONTRAT_REFERENCE_PHYSIQUE, DEPART, POSTE, puis pour chaque rôle (REPRESENTANT/
    TECHNIQUE/COMMERCIAL) : <ROLE>_NOM, <ROLE>_FONCTION, <ROLE>_EMAIL, <ROLE>_TEL.

    Retourne (nb_maj, nb_introuvables)."""
    nb_maj, nb_introuvables = 0, 0
    for d in df.to_dict("records"):
        idabon = _clean_str(d.get("IDABON"))
        if not idabon:
            continue
        client = Client.objects.filter(scope, idabon=idabon).first()
        if client is None:
            nb_introuvables += 1
            continue

        if _clean_str(d.get("SECTEUR_ACTIVITE")):
            client.secteur_activite = _clean_str(d.get("SECTEUR_ACTIVITE"))
        if _clean_str(d.get("BRANCHE_ACTIVITE")):
            client.branche_activite = _clean_str(d.get("BRANCHE_ACTIVITE"))
        a_contrat = _parse_oui_non(d.get("A_CONTRAT"))
        if a_contrat is not None:
            client.a_contrat = a_contrat
        if _clean_str(d.get("CONTRAT_REFERENCE_PHYSIQUE")):
            client.contrat_reference_physique = _clean_str(d.get("CONTRAT_REFERENCE_PHYSIQUE"))
        client.fiche_maj_le = timezone.now()
        client.fiche_maj_par = maj_par
        client.save()

        depart = _clean_str(d.get("DEPART"))
        poste = _clean_str(d.get("POSTE"))
        if depart or poste:
            for abonnement in client.abonnements.all():
                if depart:
                    abonnement.depart = depart
                if poste:
                    abonnement.poste = poste
                abonnement.save(update_fields=["depart", "poste"])

        for prefix, role in ROLE_PAR_COLONNE_PREFIX.items():
            nom = _clean_str(d.get(f"{prefix}_NOM"))
            if not nom:
                continue
            Interlocuteur.objects.update_or_create(
                client=client,
                role=role,
                nom=nom,
                defaults={
                    "fonction": _clean_str(d.get(f"{prefix}_FONCTION")),
                    "email": _clean_str(d.get(f"{prefix}_EMAIL")),
                    "telephone": _clean_str(d.get(f"{prefix}_TEL")),
                },
            )

        nb_maj += 1

    return nb_maj, nb_introuvables
