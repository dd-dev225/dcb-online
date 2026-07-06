from collections import Counter

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from clients.models import Client
from core.excel import excel_response
from dashboards.views import support_technique_required

from .forms import EvenementQualiteFormSet, FicheQualiteFournitureForm, ReleveTensionFormSet
from .models import (
    EvenementQualite,
    FicheQualiteFourniture,
    IncidentReseau,
    LienFicheQualite,
    ReleveTension,
    TravauxReseau,
    ZoneIndustrielle,
)


def _heure_locale_naive(dt):
    """Excel n'accepte pas les datetimes avec fuseau horaire (ValueError de
    pandas.to_excel) : on convertit en heure locale (Africa/Abidjan) puis on
    retire le fuseau avant export."""
    return timezone.localtime(dt).replace(tzinfo=None) if dt else None

COLONNES_TRI_INCIDENTS = {
    "date_heure_debut": "Début",
    "direction_regionale": "DR",
    "nom_depart": "Départ",
    "zone_industrielle": "Zone industrielle",
    "duree_minutes": "Durée (min)",
    "cause": "Cause",
}

COLONNES_TRI_TRAVAUX = {
    "date_heure_debut": "Début",
    "direction_regionale": "DR",
    "nom_depart": "Départ",
    "zone_industrielle": "Zone industrielle",
    "duree_minutes": "Durée (min)",
    "nature": "Nature",
}


def _filtrer_trier(request, queryset, colonnes_tri):
    zone = request.GET.get("zone", "")
    dr = request.GET.get("dr", "")
    recherche = request.GET.get("q", "")
    tri = request.GET.get("tri", "date_heure_debut")
    direction_tri = request.GET.get("dir", "desc")

    if zone:
        queryset = queryset.filter(zone_industrielle__nom=zone)
    if dr:
        queryset = queryset.filter(direction_regionale__code=dr)
    if recherche:
        queryset = queryset.filter(nom_depart__icontains=recherche)

    if tri not in colonnes_tri:
        tri = "date_heure_debut"
    ordre = tri if direction_tri == "asc" else f"-{tri}"
    queryset = queryset.order_by(ordre, "-date_heure_debut" if tri != "date_heure_debut" else "pk")

    return queryset, zone, dr, recherche, tri, direction_tri


@login_required
@support_technique_required
def dashboard(request):
    return render(request, "reseau/dashboard.html")


@login_required
@support_technique_required
def cartographie_immeubles(request):
    """Croisement demandé par la SDGU : la cartographie des immeubles prospectés
    par DR transmise au Support Technique, mise en regard des contraintes réseau
    (incidents, énergie non distribuée) de la même DR — pour identifier les zones
    où le réseau est déjà sous tension et anticiper la saturation des postes/
    transformateurs avant qu'un promoteur ne dépose sa demande de raccordement."""
    from django.db.models import Avg, Count, Sum

    from core.models import DirectionRegionale
    from prospection.models import ImmeubleProspecte
    from reseau.models import IncidentReseau

    lignes = []
    for dr in DirectionRegionale.objects.filter(zone="Abidjan").order_by("code"):
        immeubles = ImmeubleProspecte.objects.filter(direction_regionale=dr)
        prioritaires = immeubles.filter(nb_niveaux__gte=ImmeubleProspecte.SEUIL_NIVEAUX_PRIORITAIRE)
        sans_poste = prioritaires.filter(poste_existant=False)
        incidents = IncidentReseau.objects.filter(direction_regionale=dr)
        agg = incidents.aggregate(nb=Count("id"), end=Sum("energie_non_distribuee_mwh"), duree=Avg("duree_minutes"))

        lignes.append(
            {
                "dr": dr,
                "nb_immeubles": immeubles.count(),
                "nb_prioritaires": prioritaires.count(),
                "nb_sans_poste": sans_poste.count(),
                "nb_incidents": agg["nb"] or 0,
                "energie_non_distribuee": agg["end"] or 0,
                "duree_moyenne": agg["duree"],
                "a_risque": (agg["nb"] or 0) > 0 and sans_poste.count() > 0,
            }
        )

    immeubles_a_risque = (
        ImmeubleProspecte.objects.filter(
            nb_niveaux__gte=ImmeubleProspecte.SEUIL_NIVEAUX_PRIORITAIRE,
            poste_existant=False,
            direction_regionale__in=[l["dr"] for l in lignes if l["a_risque"]],
        )
        .select_related("direction_regionale")
        .order_by("-nb_niveaux")[:30]
    )

    return render(
        request,
        "reseau/cartographie_immeubles.html",
        {"lignes": lignes, "immeubles_a_risque": immeubles_a_risque},
    )


@login_required
@support_technique_required
def liste_incidents(request):
    qs = IncidentReseau.objects.select_related("direction_regionale", "zone_industrielle")
    qs, zone, dr, recherche, tri, direction_tri = _filtrer_trier(request, qs, COLONNES_TRI_INCIDENTS)

    page = Paginator(qs, 50).get_page(request.GET.get("page"))

    return render(
        request,
        "reseau/liste_incidents.html",
        {
            "incidents": page,
            "page_obj": page,
            "total": qs.count(),
            "zones_disponibles": ZoneIndustrielle.objects.order_by("nom"),
            "zone_selectionnee": zone,
            "dr_selectionnee": dr,
            "recherche": recherche,
            "tri": tri,
            "dir": direction_tri,
            "colonnes_tri": COLONNES_TRI_INCIDENTS,
        },
    )


@login_required
@support_technique_required
def exporter_incidents(request):
    qs = IncidentReseau.objects.select_related("direction_regionale", "zone_industrielle")
    qs, *_ = _filtrer_trier(request, qs, COLONNES_TRI_INCIDENTS)

    lignes = [
        {
            "N° incident": i.numero_incident,
            "DR": i.direction_regionale.code if i.direction_regionale else "",
            "Poste": i.poste_site,
            "Départ": i.nom_depart,
            "Zone industrielle": i.zone_industrielle.nom if i.zone_industrielle else "",
            "Début": _heure_locale_naive(i.date_heure_debut),
            "Fin": _heure_locale_naive(i.date_heure_fin),
            "Durée (min)": i.duree_minutes,
            "Puissance coupée (kW)": float(i.puissance_coupee_kw) if i.puissance_coupee_kw is not None else None,
            "Énergie non distribuée (MWh)": float(i.energie_non_distribuee_mwh) if i.energie_non_distribuee_mwh is not None else None,
            "Réclamations": i.nb_reclamations,
            "Lieu du défaut": i.lieu_defaut,
            "Cause": i.cause,
            "Description": i.description,
        }
        for i in qs.iterator(chunk_size=2000)
    ]

    df = pd.DataFrame(lignes)
    return excel_response(df, "incidents_reseau.xlsx", sheet_name="Incidents", titre="Incidents réseau HTA/HTB — Support Technique", couleur_entete="E74A3B")


@login_required
@support_technique_required
def liste_travaux(request):
    qs = TravauxReseau.objects.select_related("direction_regionale", "zone_industrielle")
    qs, zone, dr, recherche, tri, direction_tri = _filtrer_trier(request, qs, COLONNES_TRI_TRAVAUX)

    page = Paginator(qs, 50).get_page(request.GET.get("page"))

    return render(
        request,
        "reseau/liste_travaux.html",
        {
            "travaux": page,
            "page_obj": page,
            "total": qs.count(),
            "zones_disponibles": ZoneIndustrielle.objects.order_by("nom"),
            "zone_selectionnee": zone,
            "dr_selectionnee": dr,
            "recherche": recherche,
            "tri": tri,
            "dir": direction_tri,
            "colonnes_tri": COLONNES_TRI_TRAVAUX,
        },
    )


@login_required
@support_technique_required
def exporter_travaux(request):
    qs = TravauxReseau.objects.select_related("direction_regionale", "zone_industrielle")
    qs, *_ = _filtrer_trier(request, qs, COLONNES_TRI_TRAVAUX)

    lignes = [
        {
            "Code rattachement": t.code_rattachement,
            "DR": t.direction_regionale.code if t.direction_regionale else "",
            "Poste": t.poste_site,
            "Départ": t.nom_depart,
            "Zone industrielle": t.zone_industrielle.nom if t.zone_industrielle else "",
            "Début": _heure_locale_naive(t.date_heure_debut),
            "Fin": _heure_locale_naive(t.date_heure_fin),
            "Durée (min)": t.duree_minutes,
            "Puissance coupée (kW)": float(t.puissance_coupee_kw) if t.puissance_coupee_kw is not None else None,
            "Nature": t.nature,
            "Type manœuvre": t.type_manoeuvre,
            "Lieu": t.lieu_defaut,
            "Description": t.description,
        }
        for t in qs.iterator(chunk_size=2000)
    ]

    df = pd.DataFrame(lignes)
    return excel_response(df, "travaux_reseau.xlsx", sheet_name="Travaux", titre="Travaux réseau — Support Technique", couleur_entete="2E9E4F")


# --- Fiche Qualité de Fourniture --------------------------------------------
# Digitalisation de la fiche de collecte jusqu'ici envoyée par mail au client
# (cf. informations clients/dcb/Support Technique/Fiche Qualite de Fourniture/) :
# le Support Technique génère un lien unique (generer_lien_qualite), le client le
# remplit lui-même sans compte (fiche_qualite_publique), et le Support Technique
# consolide/traite les fiches reçues (liste_fiches_qualite, detail_fiche_qualite).


def fiche_qualite_publique(request, token):
    """Vue PUBLIQUE (aucune authentification requise) : accès via le lien unique
    envoyé au client. Remplace l'envoi d'un document Word/PDF à remplir à la main."""
    lien = get_object_or_404(LienFicheQualite.objects.select_related("client"), token=token)

    if not lien.actif:
        return render(request, "reseau/fiche_qualite_publique_inactif.html", {"lien": lien})

    if request.method == "POST":
        form = FicheQualiteFournitureForm(request.POST, request.FILES)
        evenements_fs = EvenementQualiteFormSet(request.POST, prefix="evt")
        releves_fs = ReleveTensionFormSet(request.POST, prefix="ten")

        formulaires_valides = form.is_valid() and evenements_fs.is_valid() and releves_fs.is_valid()
        evenements_renseignes = (
            [f.cleaned_data for f in evenements_fs if f.cleaned_data.get("date")] if formulaires_valides else []
        )

        if formulaires_valides and evenements_renseignes:
            fiche = form.save(commit=False)
            fiche.lien = lien
            fiche.client = lien.client
            fiche.save()

            for data in evenements_renseignes:
                EvenementQualite.objects.create(
                    fiche=fiche,
                    date=data["date"],
                    heure_debut=data.get("heure_debut"),
                    heure_fin=data.get("heure_fin"),
                    phenomenes=data.get("phenomenes") or [],
                    autre_description=data.get("autre_description", ""),
                )
            for f in releves_fs:
                data = f.cleaned_data
                if any(data.get(k) is not None for k in ("date", "heure", "u12", "u23", "u31", "v1", "v2", "v3")):
                    ReleveTension.objects.create(
                        fiche=fiche,
                        date=data.get("date"),
                        heure=data.get("heure"),
                        u12=data.get("u12"),
                        u23=data.get("u23"),
                        u31=data.get("u31"),
                        v1=data.get("v1"),
                        v2=data.get("v2"),
                        v3=data.get("v3"),
                        appareil_mesure=data.get("appareil_mesure", ""),
                    )

            return render(request, "reseau/fiche_qualite_publique_merci.html", {"fiche": fiche})

        if formulaires_valides and not evenements_renseignes:
            messages.error(request, "Veuillez renseigner au moins un événement (date de l'incident).")
    else:
        initial = {"nom_entreprise": lien.client.nom_prenoms} if lien.client else {}
        form = FicheQualiteFournitureForm(initial=initial)
        evenements_fs = EvenementQualiteFormSet(prefix="evt")
        releves_fs = ReleveTensionFormSet(prefix="ten")

    return render(
        request,
        "reseau/fiche_qualite_publique.html",
        {"form": form, "evenements_fs": evenements_fs, "releves_fs": releves_fs, "lien": lien},
    )


@login_required
@support_technique_required
def generer_lien_qualite(request):
    """Génère un lien de collecte à envoyer au client, optionnellement
    pré-rattaché à un client connu du portefeuille (recherché par IDABON ou nom)
    pour enrichir automatiquement la fiche soumise."""
    recherche = request.GET.get("q", "")
    clients_trouves = []
    if recherche:
        clients_trouves = list(
            Client.objects.filter(Q(idabon__icontains=recherche) | Q(nom_prenoms__icontains=recherche))
            .prefetch_related("interlocuteurs")
            .order_by("nom_prenoms")[:20]
        )

    if request.method == "POST":
        idabon = request.POST.get("client_idabon", "")
        client = Client.objects.filter(idabon=idabon).first() if idabon else None
        LienFicheQualite.objects.create(client=client, cree_par=request.user)
        messages.success(
            request,
            f"Lien généré pour « {client.nom_prenoms} »." if client else "Lien générique généré.",
        )
        return redirect(f"{request.path}?q={recherche}" if recherche else request.path)

    liens = list(
        LienFicheQualite.objects.select_related("client")
        .prefetch_related("client__interlocuteurs")
        .annotate(nb_fiches=Count("fiches"))
        .order_by("-cree_le")[:30]
    )
    for lien in liens:
        lien.url_absolue = request.build_absolute_uri(reverse("reseau:fiche_qualite_publique", args=[lien.token]))
        interlocuteur_technique = (
            next((i for i in lien.client.interlocuteurs.all() if i.email and i.role == "technique"), None)
            if lien.client
            else None
        )
        interlocuteur_avec_email = next((i for i in lien.client.interlocuteurs.all() if i.email), None) if lien.client else None
        lien.email_destinataire = (
            interlocuteur_technique.email
            if interlocuteur_technique
            else (interlocuteur_avec_email.email if interlocuteur_avec_email else "")
        )

    return render(
        request,
        "reseau/generer_lien_qualite.html",
        {"recherche": recherche, "clients_trouves": clients_trouves, "liens": liens},
    )


@login_required
@support_technique_required
def liste_fiches_qualite(request):
    qs = FicheQualiteFourniture.objects.select_related("client", "lien", "traite_par").prefetch_related("evenements")
    statut = request.GET.get("statut", "")
    recherche = request.GET.get("q", "")
    if statut:
        qs = qs.filter(statut=statut)
    if recherche:
        qs = qs.filter(
            Q(nom_entreprise__icontains=recherche)
            | Q(nom_correspondant__icontains=recherche)
            | Q(client__idabon__icontains=recherche)
        )

    total = qs.count()
    nb_nouveau = qs.filter(statut=FicheQualiteFourniture.NOUVEAU).count()
    nb_en_cours = qs.filter(statut=FicheQualiteFourniture.EN_COURS).count()
    nb_traite = qs.filter(statut=FicheQualiteFourniture.TRAITE).count()

    # Répartition des phénomènes déclarés : champ JSON (liste), pas de Count()
    # ORM possible dessus, agrégation faite en Python.
    compteur_phenomenes = Counter()
    for evt in EvenementQualite.objects.filter(fiche__in=qs).only("phenomenes"):
        compteur_phenomenes.update(evt.phenomenes or [])
    libelles_phenomenes = dict(EvenementQualite.PHENOMENE_CHOICES)
    phenomenes = [
        {"libelle": libelles_phenomenes.get(code, code), "nb": nb}
        for code, nb in compteur_phenomenes.most_common()
    ]

    page = Paginator(qs.order_by("-soumis_le"), 30).get_page(request.GET.get("page"))

    return render(
        request,
        "reseau/liste_fiches_qualite.html",
        {
            "fiches": page,
            "page_obj": page,
            "total": total,
            "nb_nouveau": nb_nouveau,
            "nb_en_cours": nb_en_cours,
            "nb_traite": nb_traite,
            "phenomenes": phenomenes,
            "phenomene_max": phenomenes[0]["nb"] if phenomenes else 0,
            "statuts": FicheQualiteFourniture.STATUT_CHOICES,
            "statut_filtre": statut,
            "recherche": recherche,
        },
    )


@login_required
@support_technique_required
def detail_fiche_qualite(request, pk):
    fiche = get_object_or_404(
        FicheQualiteFourniture.objects.select_related("client", "lien", "traite_par").prefetch_related(
            "evenements", "releves_tension"
        ),
        pk=pk,
    )

    if request.method == "POST":
        statut = request.POST.get("statut", "")
        if statut in dict(FicheQualiteFourniture.STATUT_CHOICES):
            fiche.statut = statut
            fiche.note_traitement = request.POST.get("note_traitement", "")
            fiche.traite_par = request.user
            fiche.traite_le = timezone.now()
            fiche.save()
            messages.success(request, "Fiche mise à jour.")
            return redirect("reseau:detail_fiche_qualite", pk=fiche.pk)

    return render(request, "reseau/detail_fiche_qualite.html", {"fiche": fiche})


@login_required
@support_technique_required
def exporter_fiches_qualite(request):
    qs = FicheQualiteFourniture.objects.select_related("client", "traite_par").prefetch_related("evenements")
    statut = request.GET.get("statut", "")
    recherche = request.GET.get("q", "")
    if statut:
        qs = qs.filter(statut=statut)
    if recherche:
        qs = qs.filter(
            Q(nom_entreprise__icontains=recherche)
            | Q(nom_correspondant__icontains=recherche)
            | Q(client__idabon__icontains=recherche)
        )

    lignes = []
    for f in qs.order_by("-soumis_le").iterator(chunk_size=500):
        phenomenes = sorted({p for evt in f.evenements.all() for p in evt.phenomenes_libelles})
        lignes.append(
            {
                "Entreprise": f.nom_entreprise,
                "Client (IDABON)": f.client.idabon if f.client else "",
                "Correspondant": f.nom_correspondant,
                "Téléphone": f.telephone,
                "Email": f.email,
                "Nb événements": f.evenements.count(),
                "Phénomènes observés": ", ".join(phenomenes),
                "Fréquence": f.get_frequence_phenomene_display() if f.frequence_phenomene else "",
                "Statut": f.get_statut_display(),
                "Soumis le": _heure_locale_naive(f.soumis_le),
                "Traité par": (f.traite_par.get_full_name() or f.traite_par.username) if f.traite_par else "",
                "Traité le": _heure_locale_naive(f.traite_le),
            }
        )

    df = pd.DataFrame(lignes)
    return excel_response(
        df,
        "fiches_qualite_fourniture.xlsx",
        sheet_name="Fiches qualité",
        titre="Fiches Qualité de Fourniture : Support Technique",
        couleur_entete="E74A3B",
    )
