"""Agrégations pour le dashboard "Qualité du réseau" de la Sous-Direction Support
Technique Business. Contrairement à dashboards.data, ces fonctions ne sont pas
scopées par utilisateur (pas d'équivalent "portefeuille personnel" sur un
incident réseau, qui n'appartient à aucune entité commerciale) : la Sous-
Direction et la Direction voient le même périmètre complet, le contrôle d'accès
se fait au niveau de la vue (cf. dashboards.views.support_technique_required),
pas au niveau de la ligne."""

import functools

from django.core.cache import cache
from django.db.models import Avg, Count, F, Sum
from django.utils import timezone

from .models import IncidentReseau, TravauxReseau


def cache_agregation(ttl_secondes=300):
    """Équivalent de dashboards.data.cache_agregation mais sans clé par entité :
    toutes les vues Support Technique partagent le même périmètre, donc une
    seule entrée de cache par (fonction, args) suffit."""

    def decorateur(fonction):
        @functools.wraps(fonction)
        def wrapper(*args, **kwargs):
            cle = f"reseaudata:{fonction.__name__}:{args}:{sorted(kwargs.items())}"
            valeur = cache.get(cle)
            if valeur is None:
                valeur = fonction(*args, **kwargs)
                cache.set(cle, valeur, ttl_secondes)
            return valeur

        return wrapper

    return decorateur


def _depuis(mois):
    return timezone.now() - timezone.timedelta(days=30 * mois)


@cache_agregation()
def kpi_nb_incidents(mois=12):
    return IncidentReseau.objects.filter(date_heure_debut__gte=_depuis(mois)).count()


@cache_agregation()
def kpi_duree_moyenne_minutes(mois=12):
    valeur = IncidentReseau.objects.filter(
        date_heure_debut__gte=_depuis(mois), duree_minutes__isnull=False
    ).aggregate(m=Avg("duree_minutes"))["m"]
    return round(valeur, 1) if valeur is not None else None


@cache_agregation()
def kpi_energie_non_distribuee_mwh(mois=12):
    valeur = IncidentReseau.objects.filter(date_heure_debut__gte=_depuis(mois)).aggregate(
        s=Sum("energie_non_distribuee_mwh")
    )["s"]
    return round(float(valeur), 1) if valeur is not None else 0.0


@cache_agregation()
def kpi_nb_travaux(mois=12):
    return TravauxReseau.objects.filter(date_heure_debut__gte=_depuis(mois)).count()


@cache_agregation()
def incidents_evolution_mensuelle(mois=12):
    """Liste de (annee, mois, nb_incidents) sur les `mois` derniers mois, triée
    chronologiquement, pour le graphique d'évolution."""
    qs = (
        IncidentReseau.objects.filter(date_heure_debut__gte=_depuis(mois))
        .annotate(annee=F("date_heure_debut__year"), m=F("date_heure_debut__month"))
        .values("annee", "m")
        .annotate(total=Count("id"))
        .order_by("annee", "m")
    )
    return [(r["annee"], r["m"], r["total"]) for r in qs]


@cache_agregation()
def incidents_par_zone(mois=12):
    """[(nom_zone, nb_incidents), ...] triée décroissant, zones industrielles
    uniquement (incidents hors ZI exclus : pas le périmètre de ce graphique)."""
    qs = (
        IncidentReseau.objects.filter(date_heure_debut__gte=_depuis(mois), zone_industrielle__isnull=False)
        .values("zone_industrielle__nom")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    return [(r["zone_industrielle__nom"], r["total"]) for r in qs]


@cache_agregation()
def top_departs_perturbes(mois=12, zone=None, limite=10):
    """[(nom_depart, poste_site, nb_incidents), ...] : les départs les plus
    souvent en incident sur la période, toutes zones ou une zone particulière."""
    qs = IncidentReseau.objects.filter(date_heure_debut__gte=_depuis(mois))
    if zone:
        qs = qs.filter(zone_industrielle__nom=zone)
    qs = (
        qs.values("nom_depart", "poste_site")
        .annotate(total=Count("id"))
        .order_by("-total")[:limite]
    )
    return [(r["nom_depart"], r["poste_site"], r["total"]) for r in qs]


@cache_agregation()
def incidents_par_dr(mois=12):
    qs = (
        IncidentReseau.objects.filter(date_heure_debut__gte=_depuis(mois), direction_regionale__isnull=False)
        .values("direction_regionale__code")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    return [(r["direction_regionale__code"], r["total"]) for r in qs]


@cache_agregation()
def causes_principales(mois=12, limite=8):
    qs = (
        IncidentReseau.objects.filter(date_heure_debut__gte=_depuis(mois))
        .exclude(cause="")
        .values("cause")
        .annotate(total=Count("id"))
        .order_by("-total")[:limite]
    )
    return [(r["cause"], r["total"]) for r in qs]


@cache_agregation()
def liste_zones_industrielles():
    from .models import ZoneIndustrielle

    return list(ZoneIndustrielle.objects.values_list("nom", flat=True))
