from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render

import pandas as pd

from core.excel import excel_response
from dashboards.data import (
    SEUIL_HORS_DELAI_JOURS,
    _reclamation_scope,
    kpi_dmr,
    kpi_taux_reclamations_hors_delai,
    taux_traitement_reclamations,
)

from .models import Reclamation


def _filtrer(request, qs):
    statut = request.GET.get("statut", "")
    canal = request.GET.get("canal", "")
    segment = request.GET.get("segment", "")
    hors_delai = request.GET.get("hors_delai", "")
    if statut:
        qs = qs.filter(statut=statut)
    if canal:
        qs = qs.filter(canal=canal)
    if segment:
        qs = qs.filter(segment_client=segment)
    if hors_delai == "oui":
        qs = qs.filter(delai_traitement__gt=SEUIL_HORS_DELAI_JOURS)
    elif hors_delai == "non":
        qs = qs.filter(delai_traitement__lte=SEUIL_HORS_DELAI_JOURS)
    return qs, statut, canal, segment, hors_delai


@login_required
def liste_reclamations(request):
    """Vue dédiée (focus) sur les réclamations HT du périmètre de l'utilisateur,
    avec les indicateurs DMR (délai moyen de traitement) et taux de réclamations
    Hors Délai (> 5 jours, demande utilisateur explicite), en complément du taux de
    traitement déjà présent sur les dashboards Engagement. Scope identique à
    celui des KPI réclamations affichés ailleurs (_reclamation_scope)."""
    base = Reclamation.objects.filter(_reclamation_scope(request.user)).select_related(
        "client", "direction_regionale"
    )
    qs, statut, canal, segment, hors_delai = _filtrer(request, base)

    dmr = kpi_dmr(request.user)
    taux_hd, nb_hd, nb_avec_delai = kpi_taux_reclamations_hors_delai(request.user)
    taux_traitement = taux_traitement_reclamations(request.user)

    # Répartition par nature de réclamation (demande utilisateur), sur le
    # périmètre entier (pas seulement la page filtrée courante) pour donner une
    # vraie vue d'ensemble, avec un nombre plafonné de catégories affichées.
    nature = list(
        base.exclude(nature_reclamation="")
        .values("nature_reclamation")
        .annotate(nb=Count("id"))
        .order_by("-nb")
    )

    page = Paginator(qs.order_by("-date_creation"), 50).get_page(request.GET.get("page"))

    return render(
        request,
        "reclamations/liste_reclamations.html",
        {
            "reclamations": page,
            "page_obj": page,
            "total": base.count(),
            "dmr": dmr,
            # Fractions (0-1) converties en pourcentage ICI, pas dans le template :
            # {{ valeur|floatformat:0 }} sur une fraction brute (ex. 0.14) arrondit
            # à l'entier le plus proche AVANT le "%", donnant "0%" au lieu de "14%"
            # (bug constaté, capture à l'appui : "0% (19/135)" et "1%" au lieu de
            # ~92%). On passe donc déjà le nombre en base 100 au template.
            "taux_hors_delai_pct": (taux_hd * 100) if taux_hd is not None else None,
            "nb_hors_delai": nb_hd,
            "nb_avec_delai": nb_avec_delai,
            "taux_traitement_pct": (taux_traitement * 100) if taux_traitement is not None else None,
            "nature_reclamations": nature,
            "nature_max": nature[0]["nb"] if nature else 0,
            "seuil_hors_delai": SEUIL_HORS_DELAI_JOURS,
            "statuts": base.exclude(statut="").values_list("statut", flat=True).distinct().order_by("statut"),
            "canaux": base.exclude(canal="").values_list("canal", flat=True).distinct().order_by("canal"),
            "segments": base.exclude(segment_client="").values_list("segment_client", flat=True).distinct().order_by("segment_client"),
            "statut_filtre": statut,
            "canal_filtre": canal,
            "segment_filtre": segment,
            "hors_delai_filtre": hors_delai,
        },
    )


@login_required
def exporter_reclamations(request):
    base = Reclamation.objects.filter(_reclamation_scope(request.user)).select_related(
        "client", "direction_regionale"
    )
    qs, *_ = _filtrer(request, base)

    lignes = []
    for r in qs.order_by("-date_creation"):
        hors_delai = r.delai_traitement is not None and r.delai_traitement > SEUIL_HORS_DELAI_JOURS
        lignes.append(
            {
                "N° sollicitation": r.numero_sollicitation,
                "DR": r.direction_regionale.code if r.direction_regionale else "",
                "Client (IDABON)": r.client.idabon if r.client else r.identifiant_contrat,
                "Nom client": r.nom_client or (r.client.nom_prenoms if r.client else ""),
                "Segment": r.segment_client,
                "Nature": r.nature_reclamation,
                "Canal": r.canal,
                "Statut": r.statut,
                "Date de création": r.date_creation,
                "Date de clôture": r.date_cloture,
                "Délai de traitement (jours)": r.delai_traitement,
                "Hors Délai (> 5j)": "Oui" if hors_delai else ("Non" if r.delai_traitement is not None else ""),
            }
        )

    df = pd.DataFrame(lignes)
    return excel_response(df, "reclamations_ht.xlsx", sheet_name="Réclamations", titre="Réclamations HT — DCB", couleur_entete="E74A3B")
