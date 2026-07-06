"""Étape 3 du pipeline d'import, à exécuter après import_clients_abonnements.

Source : informations clients/dcb/liste_clients_strategiques.xlsx (feuille
"CLIENTS STRATEGIQUES", 127 lignes : 100 grands comptes + 25 clients sensibles
selon l'organigramme).

IDENTIFIANT y est zero-paddé (ex: "02113310") alors que Client.idabon ne l'est pas
forcément (ex: "2113310"). La jointure se fait donc après normalisation (chiffres
uniquement, zéros de tête retirés), pas par égalité stricte de chaîne.

Les lignes problématiques ne sont pas silencieusement ignorées : elles sont
conservées dans ClientStrategiqueNonRattache pour que la Chargée du Service
Stratégiques & Sensibles puisse les voir sur la plateforme et investiguer
elle-même (demande utilisateur explicite). Trois cas (cf. ClientStrategiqueNonRattache.
TYPE_CHOICES) :
  1. IDENTIFIANT manquant.
  2. IDENTIFIANT introuvable dans la base de facturation.
  3. IDENTIFIANT AMBIGU : deux lignes du fichier source partagent le même
     IDENTIFIANT mais avec des raisons sociales différentes (vérifié manuellement :
     ce sont bien deux sociétés distinctes avec des interlocuteurs/contacts/emails
     différents, pas un doublon de saisie anodin — donc PAS à ignorer). Dans ce cas
     seule la ligne dont la raison sociale correspond au nom officiel du Client
     (Client.nom_prenoms, déjà importé depuis la base de facturation) est traitée
     comme un rattachement valide ; l'autre/les autres ligne(s) sont conservées ici
     avec client_associe pointant vers le Client qui possède réellement cet IDABON.

Cette table est rejouée intégralement à chaque import (delete+recreate), comme
reseau.ZoneIndustrielle : c'est un snapshot des anomalies courantes, pas un
historique à cumuler.
"""

import re

import pandas as pd
from django.core.management.base import BaseCommand

from clients.models import Client, ClientStrategiqueNonRattache
from core.models import Entite
from importers.utils import INFO_CLIENTS_DIR, normalize_identifiant


def _texte(valeur):
    return "" if pd.isna(valeur) else str(valeur).strip()


def _nom_normalise(valeur):
    """Compare les raisons sociales en ignorant les suffixes entre parenthèses
    (ex: "S.A.R.C.I SA(Niangon)" vs "S.A.R.C.I SA" dans la base de facturation) et
    la casse/espacement, sans viser une normalisation métier plus poussée."""
    sans_parentheses = re.sub(r"\([^)]*\)", "", _texte(valeur))
    return re.sub(r"\s+", " ", sans_parentheses).strip().upper()


def _meme_societe(nom_fichier, nom_officiel):
    a, b = _nom_normalise(nom_fichier), _nom_normalise(nom_officiel)
    if not a or not b:
        return False
    return a == b or a in b or b in a


class Command(BaseCommand):
    help = "Marque Client.est_strategique et bascule l'entité vers Stratégiques&Sensibles."

    def handle(self, *args, **options):
        path = INFO_CLIENTS_DIR / "dcb" / "liste_clients_strategiques.xlsx"
        self.stdout.write(f"Lecture de {path}...")
        # dtype=str : IDENTIFIANT est déjà zero-paddé dans cette source (cf.
        # docstring). normalize_identifiant() neutralise l'écart avec Client.idabon
        # à la comparaison, mais encore faut-il que pandas ne l'ait pas déjà
        # tronqué avant que ce code n'intervienne.
        df = pd.read_excel(path, sheet_name="CLIENTS STRATEGIQUES", dtype={"IDENTIFIANT": str})

        strategiques_entite = Entite.objects.get(code=Entite.STRATEGIQUES_SENSIBLES)
        client_by_norm_id = {normalize_identifiant(c.idabon): c for c in Client.objects.all()}

        # Identifiants partagés par plusieurs raisons sociales distinctes dans le
        # fichier source : à traiter au cas par cas (cf. docstring), pas comme un
        # rattachement automatique pour chaque ligne du groupe.
        identifiants_normalises = df["IDENTIFIANT"].dropna().apply(normalize_identifiant)
        noms_par_identifiant = {}
        for norm, nom in zip(identifiants_normalises, df.loc[identifiants_normalises.index, "RAISON SOCIALE"]):
            noms_par_identifiant.setdefault(norm, set()).add(_nom_normalise(nom))
        identifiants_ambigus = {norm for norm, noms in noms_par_identifiant.items() if len(noms) > 1}

        matched, unmatched = 0, 0
        to_update = []
        non_rattaches = []
        for _, ligne in df.iterrows():
            identifiant = ligne["IDENTIFIANT"]
            raison_sociale = ligne.get("RAISON SOCIALE")
            norm = None if pd.isna(identifiant) else normalize_identifiant(identifiant)
            client = client_by_norm_id.get(norm) if norm else None

            if client is not None and norm in identifiants_ambigus:
                if not _meme_societe(raison_sociale, client.nom_prenoms):
                    unmatched += 1
                    non_rattaches.append(
                        ClientStrategiqueNonRattache(
                            type_anomalie=ClientStrategiqueNonRattache.AMBIGU,
                            client_associe=client,
                            raison_sociale=_texte(raison_sociale),
                            identifiant_brut=_texte(identifiant),
                            direction=_texte(ligne.get("DIRECTION")),
                            exploitation=_texte(ligne.get("EXPLOITATION")),
                            interlocuteurs=_texte(ligne.get("INTERLOCUTEURS")),
                            fonction=_texte(ligne.get("FONCTION")),
                            contact=_texte(ligne.get("CONTACT ")),
                            email=_texte(ligne.get("EMAIL")),
                        )
                    )
                    continue
                # Sinon : c'est la ligne dont la raison sociale correspond au nom
                # officiel du Client -> rattachement normal ci-dessous.

            if client is None:
                unmatched += 1
                non_rattaches.append(
                    ClientStrategiqueNonRattache(
                        type_anomalie=ClientStrategiqueNonRattache.MANQUANT
                        if norm is None
                        else ClientStrategiqueNonRattache.INTROUVABLE,
                        raison_sociale=_texte(raison_sociale),
                        identifiant_brut=_texte(identifiant),
                        direction=_texte(ligne.get("DIRECTION")),
                        exploitation=_texte(ligne.get("EXPLOITATION")),
                        interlocuteurs=_texte(ligne.get("INTERLOCUTEURS")),
                        fonction=_texte(ligne.get("FONCTION")),
                        contact=_texte(ligne.get("CONTACT ")),
                        email=_texte(ligne.get("EMAIL")),
                    )
                )
                continue

            client.est_strategique = True
            client.entite = strategiques_entite
            to_update.append(client)
            matched += 1

        Client.objects.bulk_update(to_update, ["est_strategique", "entite"])

        ClientStrategiqueNonRattache.objects.all().delete()
        ClientStrategiqueNonRattache.objects.bulk_create(non_rattaches)

        self.stdout.write(
            self.style.SUCCESS(
                f"Clients stratégiques : {matched} rattachés, {unmatched} non rattachés "
                f"(consultables sur /clients/portefeuille/strategiques-non-rattaches/)."
            )
        )
