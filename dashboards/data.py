"""Requêtes ORM scopées (via comptes.scoping.get_scope_filter) qui alimentent les
dash apps. Centralisées ici pour rester testables indépendamment des callbacks Dash
et pour éviter de dupliquer la logique d'agrégation entre les 4 dashboards.

Les seuils de couleur du taux de recouvrement (Vert/Orange/Rouge) reproduisent la
mesure DAX "R Statut Recouvrement" du modèle Power BI (Model_Nene.bim) : Vert >= 99%,
Orange >= 95%, Rouge sinon.
"""

import functools
from collections import Counter

from django.core.cache import cache
from django.db.models import Avg, Count, F, Q, Sum

from comptes.scoping import get_scope_filter
from facturation.models import Facture, Recouvrement
from clients.models import Client
from clients.scoping import get_client_scope
from reclamations.models import Reclamation
from demandes_raccordement.models import SuiviDemande
from prospection.models import DemarcheAdministrative, ImmeubleProspecte
from prospection.scoping import get_immeuble_scope

# Mise en cache des agrégations lourdes (demande utilisateur, cf. rapport
# "Fonctionnalités proposées" : la vue Direction agrège l'ensemble des clients,
# nettement plus lente que les vues scopées à une seule entité, observé sur la
# liste financière). Clé par entité + portée individuelle plutôt que par
# utilisateur : tous les comptes qui partagent le même périmètre (ex: toute la
# Direction) reçoivent le même résultat, donc une seule entrée de cache suffit
# pour tous, y compris un compte à portée individuelle (où la clé inclut alors
# l'utilisateur, puisque son portefeuille personnel lui est propre).
def cache_agregation(ttl_secondes=300):
    def decorateur(fonction):
        @functools.wraps(fonction)
        def wrapper(user, *args, **kwargs):
            profile = getattr(user, "profile", None)
            if profile is None:
                return fonction(user, *args, **kwargs)
            # Périmètre de cache : un compte à portée individuelle a son propre
            # portefeuille (clé par utilisateur) ; sinon tous les comptes qui
            # partagent le même périmètre reçoivent le même résultat, donc une seule
            # entrée suffit. Le cas Direction (entite_id None = périmètre global)
            # était auparavant exclu du cache et recalculait l'agrégation sur
            # l'ensemble des factures à chaque chargement : c'est précisément la vue
            # la plus lourde, donc celle qui profite le plus du cache.
            # Le périmètre inclut les DR : depuis que le portefeuille est scopé par
            # entité + DR (cf. comptes.scoping), deux profils de même entité mais
            # de DR différentes voient des données différentes et ne doivent pas
            # partager la même entrée de cache.
            dr_ids = sorted(profile.directions_regionales.values_list("id", flat=True))
            dr_suffixe = ("+dr" + "-".join(map(str, dr_ids))) if dr_ids else ""
            if profile.portee_individuelle:
                portee = f"u{user.pk}{dr_suffixe}"
            elif profile.entite_id is not None:
                portee = f"e{profile.entite_id}{dr_suffixe}"
            else:
                portee = "direction"
            cle = f"dashdata:{fonction.__name__}:{portee}:{args}:{sorted(kwargs.items())}"
            valeur = cache.get(cle)
            if valeur is None:
                valeur = fonction(user, *args, **kwargs)
                cache.set(cle, valeur, ttl_secondes)
            return valeur

        return wrapper

    return decorateur

# Aide contextuelle affichée au survol d'un "?" à côté du libellé d'un indicateur
# (demande utilisateur, cf. rapport "Fonctionnalités proposées" : éviter de
# redemander à chaque fois ce qu'un indicateur veut dire). Centralisé ici (plutôt
# que dans dashboards.views ou dash_apps._components séparément) puisque les deux
# affichent les mêmes libellés et importent déjà ce module.
AIDE_PAR_LIBELLE = {
    "Taux de recouvrement": "Part du montant facturé qui a effectivement été payé (paiements reçus / montant facturé).",
    "Taux de non-facturation": "Part des abonnements actifs qui n'ont pas été facturés sur la période.",
    "Cibles prioritaires (R+5 et +)": "Immeubles de 5 étages et plus, jugés prioritaires par la Sous-Direction Guichet Unique.",
    "Taux de conversion → demande CIE": "Part des immeubles prospectés pour lesquels une demande de raccordement CIE a été initiée.",
    "Taux de conversion → demande SODECI": "Part des immeubles prospectés pour lesquels une demande SODECI a été initiée.",
    "Clients facturés": "Nombre de clients distincts ayant reçu au moins une facture sur la période.",
    "Durée moyenne de traitement": "Délai moyen entre l'initiation d'une demande de raccordement et son exécution.",
    "Fiches complètes": "Part des clients dont la fiche a un secteur d'activité, un statut de contrat et un contrat (document ou référence) renseignés.",
    "Incidents réseau": "Nombre de pannes/perturbations enregistrées sur le réseau HTA/HTB sur la période (source : exports INCIBCC).",
    "Durée moyenne de coupure": "Durée moyenne entre le début et la fin d'un incident réseau sur la période.",
    "Énergie non distribuée": "Cumul de l'énergie (MWh) non livrée aux clients du fait des incidents réseau sur la période.",
    "Travaux programmés": "Nombre de manœuvres/travaux planifiés sur le réseau sur la période (source : exports MANTBCC).",
    "DMR (délai moyen de traitement)": "Délai Moyen de traitement des Réclamations (DMR), en jours, calculé sur les réclamations traitées.",
    "Taux de réclamations Hors Délai (> 5j)": "Part des réclamations traitées dont le délai réel de traitement dépasse 5 jours (seuil Hors Délai).",
}


def _facture_scope(user):
    return get_scope_filter(
        user,
        entite_field="client__entite",
        dr_field="client__direction_regionale",
        charge_affaires_field="client__charge_affaires",
    )


def _recouvrement_scope(user):
    return get_scope_filter(
        user,
        entite_field="client__entite",
        dr_field="client__direction_regionale",
        charge_affaires_field="client__charge_affaires",
    )


def _client_scope(user):
    from clients.scoping import get_client_scope
    return get_client_scope(user)


def _suivi_scope(user):
    return get_scope_filter(
        user,
        entite_field="demande__client__entite",
        dr_field="demande__direction_regionale",
        charge_affaires_field="demande__client__charge_affaires",
    )


def _reclamation_scope(user):
    return get_scope_filter(
        user,
        entite_field="client__entite",
        dr_field="direction_regionale",
        charge_affaires_field="client__charge_affaires",
    )


def recouvrement_color(taux, entite=None):
    """Seuils globaux historiques (Vert >= 99%, Orange >= 95%, cf. Model_Nene.bim),
    sauf si l'entité a ses propres seuils (core.Entite.seuil_recouvrement_*, demande
    utilisateur cf. rapport "Fonctionnalités proposées" : une Sous-Direction au
    profil de risque différent peut vouloir une sensibilité d'alerte différente).
    entite reste optionnel : tous les appels existants sans contexte d'entité
    précis continuent de fonctionner avec les seuils globaux, inchangés."""
    if taux is None:
        return "gris"
    seuil_vert = float(entite.seuil_recouvrement_vert) if entite and entite.seuil_recouvrement_vert is not None else 0.99
    seuil_orange = float(entite.seuil_recouvrement_orange) if entite and entite.seuil_recouvrement_orange is not None else 0.95
    if taux >= seuil_vert:
        return "vert"
    if taux >= seuil_orange:
        return "orange"
    return "rouge"


@cache_agregation()
def ca_evolution(user, n_periodes=12):
    """CA facturé (Mont_fact TTC) par période, n derniers mois disponibles."""
    qs = (
        Facture.objects.filter(_facture_scope(user))
        .values("periode__annee", "periode__mois")
        .annotate(ca=Sum("montant_facture_ttc"))
        .order_by("periode__annee", "periode__mois")
    )
    rows = list(qs)[-n_periodes:]
    return [f"{r['periode__annee']}-{r['periode__mois']:02d}" for r in rows], [
        float(r["ca"] or 0) for r in rows
    ]


@cache_agregation()
def ca_par_entite(user):
    qs = (
        Facture.objects.filter(_facture_scope(user))
        .values("client__entite__libelle")
        .annotate(ca=Sum("montant_facture_ttc"))
        .order_by("-ca")
    )
    rows = [r for r in qs if r["client__entite__libelle"]]
    return [r["client__entite__libelle"] for r in rows], [float(r["ca"] or 0) for r in rows]


@cache_agregation()
def base_clients_evolution(user, n_periodes=12):
    qs = (
        Facture.objects.filter(_facture_scope(user))
        .values("periode__annee", "periode__mois")
        .annotate(nb_clients=Count("client", distinct=True))
        .order_by("periode__annee", "periode__mois")
    )
    rows = list(qs)[-n_periodes:]
    return [f"{r['periode__annee']}-{r['periode__mois']:02d}" for r in rows], [
        r["nb_clients"] for r in rows
    ]


@cache_agregation()
def energie_evolution(user, n_periodes=12):
    qs = (
        Facture.objects.filter(_facture_scope(user))
        .values("periode__annee", "periode__mois")
        .annotate(mwh=Sum("consommation_kwh"))
        .order_by("periode__annee", "periode__mois")
    )
    rows = list(qs)[-n_periodes:]
    return [f"{r['periode__annee']}-{r['periode__mois']:02d}" for r in rows], [
        float((r["mwh"] or 0) / 1000) for r in rows
    ]


@cache_agregation()
def recouvrement_par_dr(user):
    qs = (
        Recouvrement.objects.filter(_recouvrement_scope(user))
        .values("client__direction_regionale__code")
        .annotate(facture=Sum("montant_facture"), paye=Sum("montant_paye"))
        .order_by("client__direction_regionale__code")
    )
    drs, taux, couleurs = [], [], []
    for r in qs:
        if not r["client__direction_regionale__code"]:
            continue
        facture = float(r["facture"] or 0)
        t = float(r["paye"] or 0) / facture if facture else None
        drs.append(r["client__direction_regionale__code"])
        taux.append(t)
        couleurs.append(recouvrement_color(t))
    return drs, taux, couleurs


@cache_agregation()
def ca_par_dr(user):
    """CA facturé (TYPFACT E0) agrégé par Direction Régionale, pour la carte
    choroplèthe. Retourne un dict {code_DR: montant} restreint au périmètre de
    l'utilisateur (les DR hors périmètre n'apparaissent pas)."""
    qs = (
        Facture.objects.filter(_facture_scope(user), typfact="E0")
        .values("client__direction_regionale__code")
        .annotate(total=Sum("montant_facture_ttc"))
        .order_by()
    )
    result = {}
    for r in qs:
        code = r["client__direction_regionale__code"]
        if code:
            result[code] = float(r["total"] or 0)
    return result


@cache_agregation()
def top_clients_ca(user, limit=10):
    qs = (
        Facture.objects.filter(_facture_scope(user))
        .values("client__idabon", "client__nom_prenoms")
        .annotate(ca=Sum("montant_facture_ttc"))
        .order_by("-ca")[:limit]
    )
    return list(qs)


def taux_non_facturation(user):
    total = Client.objects.filter(_client_scope(user)).count()
    factures_dernier = (
        Facture.objects.filter(_facture_scope(user)).order_by("-periode__annee", "-periode__mois").first()
    )
    if not factures_dernier or not total:
        return None
    derniere_periode = factures_dernier.periode
    factures_clients = (
        Facture.objects.filter(_facture_scope(user), periode=derniere_periode)
        .values("client")
        .distinct()
        .count()
    )
    return 1 - (factures_clients / total)


def delais_raccordement_par_tranche(user):
    qs = (
        SuiviDemande.objects.filter(_suivi_scope(user))
        .exclude(tranche_delai="")
        .values("tranche_delai")
        .annotate(nb=Count("id"))
        .order_by("tranche_delai")
    )
    rows = list(qs)
    return [r["tranche_delai"] for r in rows], [r["nb"] for r in rows]


def reclamations_par_type(user):
    qs = (
        Reclamation.objects.filter(_reclamation_scope(user))
        .values("type_reclamation")
        .annotate(nb=Count("id"))
        .order_by("-nb")
    )
    rows = list(qs)
    return [r["type_reclamation"] or "(non renseigné)" for r in rows], [r["nb"] for r in rows]


@cache_agregation()
def reclamations_par_dr(user):
    """Nombre de réclamations par Direction Régionale (pour la carte de répartition
    spatiale de l'Engagement). Dict {code_DR: nb}, restreint au périmètre."""
    qs = (
        Reclamation.objects.filter(_reclamation_scope(user))
        .values("direction_regionale__code")
        .annotate(nb=Count("id"))
    )
    return {r["direction_regionale__code"]: r["nb"] for r in qs if r["direction_regionale__code"]}


@cache_agregation()
def reclamations_par_segment_client(user):
    """Réclamations réparties par segment de client (Business, Premium, Silver,
    Platinum, Network, Grand Public...). Plus pertinent que le type de réclamation,
    constant ('Réclamation HT') sur le périmètre DCB. La casse des libellés est
    harmonisée (ex. 'Grand public'/'Grand Public' fusionnés)."""
    canon = {"grand public": "Grand Public", "clients business": "Clients Business"}
    compte = {}
    qs = (
        Reclamation.objects.filter(_reclamation_scope(user))
        .values("sous_segment")
        .annotate(nb=Count("id"))
    )
    for r in qs:
        libelle = " ".join((r["sous_segment"] or "").split()) or "(non renseigné)"
        libelle = canon.get(libelle.lower(), libelle)
        compte[libelle] = compte.get(libelle, 0) + r["nb"]
    items = sorted(compte.items(), key=lambda kv: kv[1], reverse=True)
    return [k for k, _ in items], [v for _, v in items]


def taux_traitement_reclamations(user):
    qs = Reclamation.objects.filter(_reclamation_scope(user))
    total = qs.count()
    traitees = qs.exclude(date_cloture__isnull=True).count()
    return (traitees / total) if total else None


# Seuil au-delà duquel une réclamation traitée est considérée "Hors Délai" (demande
# utilisateur explicite : > 5 jours). Appuyé sur delai_traitement (jours réels de
# traitement, cf. reclamations.Reclamation), pas sur l'écart au délai contractuel
# (delai_contractuel_traitement), qui suit une logique différente et n'est pas
# celle demandée ici.
SEUIL_HORS_DELAI_JOURS = 5


@cache_agregation()
def kpi_dmr(user):
    """DMR : Délai Moyen de traitement des Réclamations (en jours), sur les
    réclamations dont le délai est connu (traitées). None si aucune donnée."""
    agg = (
        Reclamation.objects.filter(_reclamation_scope(user))
        .exclude(delai_traitement__isnull=True)
        .aggregate(m=Avg("delai_traitement"))
    )
    return agg["m"]


@cache_agregation()
def kpi_taux_reclamations_hors_delai(user):
    """Part des réclamations TRAITÉES dont le délai réel dépasse
    SEUIL_HORS_DELAI_JOURS (5 jours). Calculé sur les seules réclamations dont le
    délai est connu (les réclamations encore en cours n'ont pas de délai final et
    ne peuvent donc pas encore être qualifiées "Hors Délai"). Retourne
    (taux, nb_hors_delai, nb_avec_delai_connu)."""
    qs = Reclamation.objects.filter(_reclamation_scope(user)).exclude(delai_traitement__isnull=True)
    total = qs.count()
    if not total:
        return None, 0, 0
    hors_delai = qs.filter(delai_traitement__gt=SEUIL_HORS_DELAI_JOURS).count()
    return (hors_delai / total), hors_delai, total


@cache_agregation()
def kpi_ca_dernier_mois(user):
    """(libellé période, CA en Mds FCFA) du dernier mois facturé disponible."""
    labels, ca = ca_evolution(user, n_periodes=1)
    if not labels:
        return None, None
    return labels[-1], ca[-1] / 1e9


def _delta_pourcentage(dernier, precedent):
    """% de variation entre les deux derniers points d'une série, None si pas
    assez d'historique ou si le point précédent est nul (variation indéfinie)."""
    if precedent is None or dernier is None or precedent == 0:
        return None
    return (dernier - precedent) / precedent * 100


@cache_agregation()
def kpi_ca_dernier_mois_avec_delta(user):
    """Comme kpi_ca_dernier_mois, + variation en % vs le mois précédent (demande
    utilisateur, cf. rapport "Fonctionnalités proposées" : juger une variation
    sans recalcul manuel plutôt que d'afficher un chiffre brut sans repère)."""
    labels, ca = ca_evolution(user, n_periodes=2)
    if not labels:
        return None, None, None
    periode = labels[-1]
    ca_mds = ca[-1] / 1e9
    precedent = ca[-2] if len(ca) > 1 else None
    return periode, ca_mds, _delta_pourcentage(ca[-1], precedent)


@cache_agregation()
def kpi_nb_clients_dernier_mois(user):
    labels, nb = base_clients_evolution(user, n_periodes=1)
    return nb[-1] if nb else None


@cache_agregation()
def kpi_energie_dernier_mois(user):
    labels, mwh = energie_evolution(user, n_periodes=1)
    return mwh[-1] if mwh else None


@cache_agregation()
def kpi_energie_dernier_mois_avec_delta(user):
    """Comme kpi_energie_dernier_mois, + variation en % vs le mois précédent."""
    labels, mwh = energie_evolution(user, n_periodes=2)
    if not labels:
        return None, None
    precedent = mwh[-2] if len(mwh) > 1 else None
    return mwh[-1], _delta_pourcentage(mwh[-1], precedent)


@cache_agregation()
def kpi_taux_recouvrement_global(user):
    """Taux de recouvrement agrégé toutes DR confondues (pas le détail par DR).
    Les seuils vert/orange utilisés sont ceux de l'entité de l'utilisateur si elle
    en a défini (cf. recouvrement_color), sinon les seuils globaux historiques."""
    agg = Recouvrement.objects.filter(_recouvrement_scope(user)).aggregate(
        facture=Sum("montant_facture"), paye=Sum("montant_paye")
    )
    facture = float(agg["facture"] or 0)
    if not facture:
        return None, "gris"
    taux = float(agg["paye"] or 0) / facture
    entite = getattr(getattr(user, "profile", None), "entite", None)
    return taux, recouvrement_color(taux, entite=entite)


@cache_agregation()
def kpi_qualite_fiches(user):
    """% de clients dont la fiche est complète (secteur d'activité, statut
    contrat, et document ou référence physique de contrat renseignés), même
    critère que la colonne "Fiche complétée" du portefeuille (cf.
    clients.views.liste_portefeuille), agrégé plutôt que par client (demande
    utilisateur, cf. rapport "Fonctionnalités proposées" : prioriser les fiches à
    compléter en équipe plutôt que cliquer client par client)."""
    qs = Client.objects.filter(get_client_scope(user))
    total = qs.count()
    if not total:
        return None, 0, 0
    completes = qs.filter(
        Q(secteur_activite__gt="") & Q(a_contrat__isnull=False) & (Q(contrat_document__gt="") | Q(contrat_reference_physique__gt=""))
    ).count()
    return (completes / total), completes, total


@cache_agregation()
def kpi_nb_reclamations(user):
    return Reclamation.objects.filter(_reclamation_scope(user)).count()


def kpi_nb_demandes_en_cours(user):
    return (
        SuiviDemande.objects.filter(_suivi_scope(user))
        .exclude(date_execution__isnull=False)
        .count()
    )


def clients_critiques(user, limit=20):
    qs = (
        Recouvrement.objects.filter(_recouvrement_scope(user), client__est_strategique=True)
        .values("client__idabon", "client__nom_prenoms")
        .annotate(impaye=Sum(F("montant_facture") - F("montant_paye")))
        .order_by("-impaye")[:limit]
    )
    return list(qs)


# --- Prospection (Sous-Direction Guichet Unique) ---------------------------------
# Scope partagé avec prospection.views (liste/édition/export/import), cf.
# prospection.scoping pour la justification de la règle.

_immeuble_scope = get_immeuble_scope


def kpi_nb_immeubles_prospectes(user):
    return ImmeubleProspecte.objects.filter(_immeuble_scope(user)).count()


def kpi_nb_cibles_prioritaires(user):
    """Immeubles R+5 et plus (cible prioritaire documentée par la SDGU)."""
    return ImmeubleProspecte.objects.filter(
        _immeuble_scope(user), nb_niveaux__gte=ImmeubleProspecte.SEUIL_NIVEAUX_PRIORITAIRE
    ).count()


def _taux_conversion(user, organisme):
    qs = DemarcheAdministrative.objects.filter(
        immeuble__in=ImmeubleProspecte.objects.filter(_immeuble_scope(user)),
        organisme=organisme,
    )
    total = qs.count()
    if not total:
        return None
    return qs.filter(demande_initiee=True).count() / total


def kpi_taux_conversion_cie(user):
    """% d'immeubles dont la démarche CIE est passée de prospect à demande
    initiée, parmi ceux dont le statut est connu. C'est l'indicateur de réussite
    mis en avant par la SDGU elle-même (info.txt, 2e échange)."""
    return _taux_conversion(user, DemarcheAdministrative.CIE)


def kpi_taux_conversion_sodeci(user):
    return _taux_conversion(user, DemarcheAdministrative.SODECI)


def repartition_par_zone(user, top_n=10):
    qs = (
        ImmeubleProspecte.objects.filter(_immeuble_scope(user))
        .exclude(zone_prospection="")
        .values("zone_prospection")
        .annotate(nb=Count("id"))
        .order_by("-nb")[:top_n]
    )
    rows = list(qs)
    return [r["zone_prospection"] for r in rows], [r["nb"] for r in rows]


def repartition_par_stade(user):
    qs = (
        ImmeubleProspecte.objects.filter(_immeuble_scope(user))
        .exclude(stade_avancement="")
        .values("stade_avancement")
        .annotate(nb=Count("id"))
        .order_by("-nb")
    )
    labels = {
        ImmeubleProspecte.TERRASSEMENT: "Terrassement",
        ImmeubleProspecte.GROS_OEUVRE: "Gros œuvre",
        ImmeubleProspecte.FINITION: "Finition",
    }
    rows = list(qs)
    return [labels.get(r["stade_avancement"], r["stade_avancement"]) for r in rows], [r["nb"] for r in rows]


def repartition_par_tranche_niveaux(user):
    """Histogramme du nombre de niveaux (R+n), regroupé en tranches plutôt qu'une
    barre par valeur exacte (R+2..R+25 donnerait un axe illisible)."""
    tranches = [("R+1 à R+4", 1, 4), ("R+5 à R+9", 5, 9), ("R+10 à R+14", 10, 14), ("R+15 et +", 15, None)]
    qs = ImmeubleProspecte.objects.filter(_immeuble_scope(user), nb_niveaux__isnull=False)
    labels, valeurs = [], []
    for label, mini, maxi in tranches:
        filtre = Q(nb_niveaux__gte=mini)
        if maxi is not None:
            filtre &= Q(nb_niveaux__lte=maxi)
        labels.append(label)
        valeurs.append(qs.filter(filtre).count())
    return labels, valeurs


def portefeuille_par_commercial(user):
    """Une barre par compte (commercial_id), pas par rôle : plusieurs comptes
    Guichet Unique partagent le même libellé de rôle (3 Conseillers Client Grands
    Comptes distincts), les regrouper par rôle fusionnerait 3 portefeuilles
    différents sous une étiquette identique. On affiche le libellé de rôle, suffixé
    d'un numéro seulement quand il se répète, plutôt qu'un nom réel (cf. note de
    confidentialité du plan)."""
    from comptes.models import UserProfile

    qs = (
        ImmeubleProspecte.objects.filter(_immeuble_scope(user))
        .exclude(commercial=None)
        .values("commercial_id", "commercial__profile__role", "commercial__username")
        .annotate(nb=Count("id"))
        .order_by("-nb")
    )
    rows = list(qs)
    role_display = dict(UserProfile.ROLE_CHOICES)
    base_labels = [role_display.get(r["commercial__profile__role"], r["commercial__username"]) for r in rows]
    occurrences_totales = Counter(base_labels)
    vu = Counter()
    labels = []
    for label in base_labels:
        if occurrences_totales[label] > 1:
            vu[label] += 1
            labels.append(f"{label} #{vu[label]}")
        else:
            labels.append(label)
    return labels, [r["nb"] for r in rows]


def immeubles_a_prioriser(user, limit=20):
    """Cibles prioritaires (R+5+) sans poste existant ET sans démarche CIE initiée :
    une liste d'action commerciale immédiate plutôt qu'un simple inventaire."""
    sans_demande_cie = ~Q(
        demarches__organisme=DemarcheAdministrative.CIE, demarches__demande_initiee=True
    )
    qs = (
        ImmeubleProspecte.objects.filter(
            _immeuble_scope(user),
            nb_niveaux__gte=ImmeubleProspecte.SEUIL_NIVEAUX_PRIORITAIRE,
        )
        .filter(Q(poste_existant=False) | Q(poste_existant=None))
        .filter(sans_demande_cie)
        .distinct()
        .order_by("-nb_niveaux")[:limit]
        .values("nom_structure", "zone_prospection", "nb_niveaux", "interlocuteur", "contact")
    )
    return list(qs)


# --- Synthèse Support Technique (page d'accueil Direction/Sous-Directeur) -------
#
# Contrairement aux fonctions ci-dessus (scopées par get_scope_filter(user), donc
# relatives au profil de qui regarde), celle-ci calcule toujours le même périmètre,
# celui de TOUTE la Sous-Direction, quel que soit le viewer : la Direction et son
# Sous-Directeur doivent voir le même nombre. D'où un calcul global plutôt que par
# profil de l'appelant (pas de champ client__entite à filtrer ici, cf. docstring).


def synthese_support_technique():
    """Support Technique Business : pas de portefeuille Client/Facture propre (même
    constat que pour Guichet Unique, cf. historique). C'est elle qui traite
    techniquement TOUTE demande de raccordement de la DCB une fois transmise par
    Guichet Unique (cf. Parlons Métiers N57 : "transmise à la Sous-Direction Support
    Technique Business"), donc son périmètre naturel est l'ensemble de
    SuiviDemande, pas un sous-ensemble par client__entite (structurellement vide ici
    comme pour Guichet Unique avant qu'on lui trouve sa propre source de données)."""
    qs = SuiviDemande.objects.all()
    nb_en_cours = qs.exclude(date_execution__isnull=False).count()
    duree_moyenne = qs.exclude(duree_totale__isnull=True).aggregate(m=Avg("duree_totale"))["m"]
    return {
        "nb_demandes_en_cours": nb_en_cours,
        "duree_moyenne_jours": round(duree_moyenne) if duree_moyenne is not None else None,
    }


def realise_indicateur(user, indicateur):
    """Valeur RÉALISÉE d'un indicateur d'objectif, sur le périmètre de l'utilisateur,
    dans l'unité de la cible (Mds FCFA, %, jours). Sert à confronter réalisé/objectif
    (cf. objectifs_avec_realise)."""
    from core.models import Objectif

    if indicateur == Objectif.CA_MENSUEL:
        return kpi_ca_dernier_mois_avec_delta(user)[1]
    if indicateur == Objectif.TAUX_RECOUVREMENT:
        taux, _ = kpi_taux_recouvrement_global(user)
        return taux * 100 if taux is not None else None
    if indicateur == Objectif.TAUX_COMPLETION:
        taux = kpi_qualite_fiches(user)[0]
        return taux * 100 if taux is not None else None
    if indicateur == Objectif.TAUX_CONVERSION_CIE:
        t = kpi_taux_conversion_cie(user)
        return t * 100 if t is not None else None
    if indicateur == Objectif.DELAI_RACCORDEMENT:
        agg = SuiviDemande.objects.filter(_suivi_scope(user)).aggregate(m=Avg("duree_totale"))
        return agg["m"]
    return None


def objectifs_avec_realise(user):
    """Objectifs applicables à l'entité de l'utilisateur (posés sur son entité OU un
    ancêtre, le plus spécifique l'emportant), avec le réalisé de son périmètre et le
    statut atteint/non atteint. Vide si pas d'entité."""
    from core.models import Objectif

    profile = getattr(user, "profile", None)
    if profile is None or profile.entite_id is None:
        return []
    ancetres = profile.entite.ancetres_ids()  # du plus spécifique (self) au plus général
    ordre = {eid: i for i, eid in enumerate(ancetres)}
    par_indicateur = {}
    for o in Objectif.objects.filter(entite_id__in=ancetres).select_related("entite"):
        courant = par_indicateur.get(o.indicateur)
        if courant is None or ordre[o.entite_id] < ordre[courant.entite_id]:
            par_indicateur[o.indicateur] = o

    resultat = []
    for indicateur, o in par_indicateur.items():
        realise = realise_indicateur(user, indicateur)
        cible = float(o.valeur_cible)
        atteint = None
        if realise is not None:
            atteint = realise <= cible if indicateur in Objectif.PLUS_BAS_EST_MIEUX else realise >= cible
        resultat.append(
            {"libelle": o.get_indicateur_display(), "cible": cible, "realise": realise,
             "atteint": atteint, "entite": o.entite.libelle}
        )
    resultat.sort(key=lambda d: d["libelle"])
    return resultat


def alertes_navbar(user):
    """Alimente la cloche de notifications de la navbar (demande utilisateur :
    "rends les fonctionnels", pas de simple décor comme dans le template SB Admin 2
    d'origine). Uniquement des éléments réellement ACTIONNABLES par CET
    utilisateur, pas un doublon des KPI déjà visibles sur son tableau de bord."""
    from clients.permissions import peut_valider_strategique
    from clients.scoping import get_client_scope

    alertes = []
    if peut_valider_strategique(user):
        nb = Client.objects.filter(get_client_scope(user), strategique_en_attente=True).count()
        if nb:
            alertes.append(
                {
                    "label": f"{nb} proposition(s) de client stratégique en attente de validation",
                    "url": "clients:valider_clients_strategiques",
                    "icone": "fa-star",
                    "couleur": "warning",
                }
            )
    return alertes


def activite_recente_navbar(user, limit=5):
    """Flux d'activité récente sur les fiches client, affiché dans la cloche
    "Activité récente" de la navbar (distincte de l'enveloppe "Messages", qui
    porte la vraie messagerie entre entités, cf. app messagerie). Utile à la
    SDRCB/Direction pour voir qui a mis à jour quelle fiche, sans avoir à ouvrir
    le portefeuille complet."""
    from clients.scoping import get_client_scope

    qs = (
        Client.objects.filter(get_client_scope(user), fiche_maj_le__isnull=False)
        .select_related("fiche_maj_par")
        .order_by("-fiche_maj_le")[:limit]
    )
    return [
        {
            "idabon": c.idabon,
            "nom": c.nom_prenoms or c.idabon,
            "maj_par": c.fiche_maj_par.get_full_name() or c.fiche_maj_par.username if c.fiche_maj_par else "—",
            "maj_le": c.fiche_maj_le,
        }
        for c in qs
    ]
