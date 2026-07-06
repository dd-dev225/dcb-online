"""Import de la base MAÎTRESSE des clients : informations clients/dcb/Client DCB.xlsx
(feuille "HT GLOBAL", ~3793 lignes), export du référentiel client Saphir.

Contrairement à data/V_Fait_Fact_HT_DCB.xlsx (base de facturation, dynamique, clients
facturés sur une période), Client DCB.xlsx est la feuille de référence quasi complète
de tous les clients DCB (statique). C'est la base sur laquelle repose le portefeuille :
- elle marque chaque client rencontré comme `dans_client_dcb=True` ;
- elle CRÉE les clients absents de la facturation (clients non facturés sur la période) ;
- elle ENRICHIT (jamais n'écrase) les clients déjà présents avec les variables propres
  à la fiche Saphir : exploitation/agence, poste source, départ, n° poste client,
  interlocuteurs 1 & 2, secteur, puissance, groupe électrogène, localisation, date
  d'abonnement, statut de contrat (OK/KO).

Les jointures vers la facturation/le recouvrement se font par IDABON à 8 chiffres
(cf. importers.utils.format_idabon), forme canonique commune aux deux bases.
Idempotente : un second passage ne remplit que ce qui est encore vide.
"""

import re

import pandas as pd
from django.core.management.base import BaseCommand

from clients.models import Abonnement, Client, Interlocuteur
from clients.nomenclature import SECTEUR_ACTIVITE_CHOICES
from core.models import DirectionRegionale, Entite
from importers.utils import INFO_CLIENTS_DIR, format_idabon, parse_date_flexible

ZONE_TO_ENTITE_CODE = {"Abidjan": Entite.ABIDJAN, "Intérieur": Entite.INTERIEUR}
SECTEURS_VALIDES = {valeur for valeur, _ in SECTEUR_ACTIVITE_CHOICES}

# Accès par POSITION : les en-têtes de Client DCB.xlsx sont dupliqués ("FONCTION"
# apparaît deux fois) et mal formés (espaces multiples), donc non fiables par nom.
COL = {
    "dr": 1, "exploitation": 2, "raison": 3, "reference": 4, "identifiant": 5,
    "poste": 6, "depart": 7, "num_poste": 8,
    "int1_nom": 9, "int1_fonction": 10, "int1_contact1": 11, "int1_contact2": 12, "int1_email": 13,
    "int2_nom": 14, "int2_fonction": 15, "int2_contact1": 16, "int2_contact2": 17, "int2_email": 18,
    "secteur": 19, "puissance": 20, "ge_dispo": 21, "ge_puissance": 22,
    "localisation": 23, "date_abon": 24, "statut_contrat": 25,
}


def _texte(v):
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def _nombre(v):
    return v if (v is not None and not (isinstance(v, float) and pd.isna(v))) else None


def _secteur_valide(v):
    sans_code = re.sub(r"^\d+\s+", "", _texte(v))
    return sans_code if sans_code in SECTEURS_VALIDES else ""


def _code_dr(v):
    m = re.match(r"\s*(\d+)", _texte(v))
    return int(m.group(1)) if m else None


def _statut_contrat(v):
    """'OK' -> True, 'KO' -> False, sinon None (non renseigné)."""
    t = _texte(v).upper()
    if t.startswith("OK"):
        return True
    if t.startswith("KO"):
        return False
    return None


def _oui_non(v):
    t = _texte(v).upper()
    if t in ("OUI", "O", "YES", "DISPONIBLE", "1"):
        return True
    if t in ("NON", "N", "NO", "0"):
        return False
    return None


def importer_dcb(df):
    """Traite un DataFrame au format Client DCB.xlsx (export Saphir, accès par
    POSITION de colonne cf. COL) : crée les nouveaux clients, enrichit les existants
    (jamais d'écrasement), marque dans_client_dcb=True. Réutilisé par la commande
    CLI ET par l'import in-app (clients.views.importer_clients_dcb). Retourne un
    dict de compteurs."""
    dr_by_code = {dr.code_numerique: dr for dr in DirectionRegionale.objects.all()}
    entite_by_code = {e.code: e for e in Entite.objects.all()}
    client_by_idabon = {c.idabon: c for c in Client.objects.all()}

    crees = enrichis = abon_touches = interlocuteurs = 0

    for _, ligne in df.iterrows():
        idabon = format_idabon(ligne.iloc[COL["identifiant"]])
        if not idabon:
            continue
        dr = dr_by_code.get(_code_dr(ligne.iloc[COL["dr"]]))
        agence = _texte(ligne.iloc[COL["exploitation"]])
        secteur = _secteur_valide(ligne.iloc[COL["secteur"]])
        localisation = _texte(ligne.iloc[COL["localisation"]])
        ge_dispo = _oui_non(ligne.iloc[COL["ge_dispo"]])
        ge_puissance = _nombre(ligne.iloc[COL["ge_puissance"]])
        a_contrat = _statut_contrat(ligne.iloc[COL["statut_contrat"]])

        client = client_by_idabon.get(idabon)
        if client is None:
            entite_code = ZONE_TO_ENTITE_CODE.get(dr.zone) if dr else None
            client = Client(
                idabon=idabon,
                nom_prenoms=_texte(ligne.iloc[COL["raison"]]),
                secteur_activite=secteur,
                direction_regionale=dr,
                entite=entite_by_code.get(entite_code),
                agence=agence,
                localisation=localisation,
                groupe_electrogene_dispo=ge_dispo,
                groupe_electrogene_puissance=ge_puissance,
                a_contrat=a_contrat,
                dans_client_dcb=True,
            )
            client.save()
            client_by_idabon[idabon] = client
            crees += 1
        else:
            champs = ["dans_client_dcb"]
            client.dans_client_dcb = True
            if not client.secteur_activite and secteur:
                client.secteur_activite = secteur; champs.append("secteur_activite")
            if not client.direction_regionale_id and dr:
                client.direction_regionale = dr; champs.append("direction_regionale")
            if not client.agence and agence:
                client.agence = agence; champs.append("agence")
            if not client.localisation and localisation:
                client.localisation = localisation; champs.append("localisation")
            if client.groupe_electrogene_dispo is None and ge_dispo is not None:
                client.groupe_electrogene_dispo = ge_dispo; champs.append("groupe_electrogene_dispo")
            if client.groupe_electrogene_puissance is None and ge_puissance is not None:
                client.groupe_electrogene_puissance = ge_puissance; champs.append("groupe_electrogene_puissance")
            if client.a_contrat is None and a_contrat is not None:
                client.a_contrat = a_contrat; champs.append("a_contrat")
            client.save(update_fields=champs)
            if len(champs) > 1:
                enrichis += 1

        poste = _texte(ligne.iloc[COL["poste"]])
        depart = _texte(ligne.iloc[COL["depart"]])
        num_poste = _texte(ligne.iloc[COL["num_poste"]])
        reference = _texte(ligne.iloc[COL["reference"]])
        puissance = _nombre(ligne.iloc[COL["puissance"]])
        date_abon = parse_date_flexible(ligne.iloc[COL["date_abon"]])

        abon = client.abonnements.order_by("pk").first()
        if abon is None:
            Abonnement.objects.create(
                client=client, refraccord=reference, poste=poste, depart=depart,
                numero_poste_client=num_poste, psabon=puissance, date_abonnement=date_abon,
            )
            abon_touches += 1
        else:
            maj = []
            if not abon.poste and poste:
                abon.poste = poste; maj.append("poste")
            if not abon.depart and depart:
                abon.depart = depart; maj.append("depart")
            if not abon.numero_poste_client and num_poste:
                abon.numero_poste_client = num_poste; maj.append("numero_poste_client")
            if abon.psabon is None and puissance is not None:
                abon.psabon = puissance; maj.append("psabon")
            if abon.date_abonnement is None and date_abon is not None:
                abon.date_abonnement = date_abon; maj.append("date_abonnement")
            if maj:
                abon.save(update_fields=maj); abon_touches += 1

        for prefixe, role in (("int1", Interlocuteur.COMMERCIAL), ("int2", Interlocuteur.TECHNIQUE)):
            nom = _texte(ligne.iloc[COL[f"{prefixe}_nom"]])
            if nom and not client.interlocuteurs.filter(nom=nom).exists():
                Interlocuteur.objects.create(
                    client=client, role=role, nom=nom,
                    fonction=_texte(ligne.iloc[COL[f"{prefixe}_fonction"]]),
                    telephone=_texte(ligne.iloc[COL[f"{prefixe}_contact1"]]) or _texte(ligne.iloc[COL[f"{prefixe}_contact2"]]),
                    email=_texte(ligne.iloc[COL[f"{prefixe}_email"]]),
                )
                interlocuteurs += 1

    return {"crees": crees, "enrichis": enrichis, "abonnements": abon_touches, "interlocuteurs": interlocuteurs}


class Command(BaseCommand):
    help = "Import de la base maîtresse Client DCB.xlsx (référentiel Saphir) : crée/enrichit et marque dans_client_dcb."

    def handle(self, *args, **options):
        path = INFO_CLIENTS_DIR / "dcb" / "Client DCB.xlsx"
        self.stdout.write(f"Lecture de {path}...")
        try:
            df = pd.read_excel(path, sheet_name="HT GLOBAL")
        except ValueError:
            df = pd.read_excel(path)

        r = importer_dcb(df)
        self.stdout.write(
            self.style.SUCCESS(
                f"Client DCB.xlsx : {r['crees']} nouveaux clients, {r['enrichis']} enrichis, "
                f"{r['abonnements']} abonnements créés/complétés, {r['interlocuteurs']} interlocuteurs créés."
            )
        )
