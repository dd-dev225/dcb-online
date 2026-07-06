import calendar as calendar_module
from datetime import date

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.excel import excel_response
from core.models import DirectionRegionale
from dashboards.views import guichet_unique_required, guichet_unique_write_required

from .forms import DemarcheAdministrativeForm, ImmeubleProspecteForm
from .models import DemarcheAdministrative, ImmeubleProspecte, OperateurImmobilier, VisitePlanifiee
from .scoping import get_immeuble_scope, get_operateur_scope, get_visite_scope, peut_administrer_base
from .services import colonnes_manquantes, importer_depuis_dataframe
from .zones import dr_code_pour_zone


def _peut_reassigner(user):
    profile = getattr(user, "profile", None)
    return bool(profile) and not profile.portee_individuelle


def _enregistrer_prospect(request, form_immeuble, form_cie, form_sodeci, immeuble_existant=None):
    """Logique commune création/édition : sauvegarde l'immeuble et ses 2
    démarches (CIE/SODECI), en conservant les PK des démarches existantes en
    édition plutôt que de les recréer (update_or_create par organisme)."""
    immeuble = form_immeuble.save(commit=False)
    if "commercial" in form_immeuble.cleaned_data:
        immeuble.commercial = form_immeuble.cleaned_data["commercial"] or request.user
    elif immeuble_existant is None:
        immeuble.commercial = request.user
    if immeuble_existant is None:
        immeuble.cree_par = request.user
    immeuble.save()

    for organisme, sous_form in ((DemarcheAdministrative.CIE, form_cie), (DemarcheAdministrative.SODECI, form_sodeci)):
        DemarcheAdministrative.objects.update_or_create(
            immeuble=immeuble,
            organisme=organisme,
            defaults={
                "demande_initiee": sous_form.cleaned_data["demande_initiee"] == "oui",
                "type_demande": sous_form.cleaned_data["type_demande"],
                "statut": sous_form.cleaned_data["statut"],
                "numero_demande": sous_form.cleaned_data["numero_demande"],
                "details_non_conformite": sous_form.cleaned_data["details_non_conformite"],
            },
        )
    return immeuble


def _demarche_initial(immeuble, organisme):
    demarche = immeuble.demarches.filter(organisme=organisme).first()
    if demarche is None:
        return {}
    return {
        "demande_initiee": "oui" if demarche.demande_initiee else "non",
        "type_demande": demarche.type_demande,
        "statut": demarche.statut,
        "numero_demande": demarche.numero_demande,
        "details_non_conformite": demarche.details_non_conformite,
    }


@login_required
@guichet_unique_write_required
def nouveau_prospect(request):
    """Version numérique de la Fiche de prospection_VF.pdf, réservé à la
    Sous-Direction Guichet Unique (cf. dashboards.views.guichet_unique_write_required) :
    la Direction consulte les indicateurs mais ne lance pas elle-même une fiche."""
    allow_reassign = _peut_reassigner(request.user)
    if request.method == "POST":
        form_immeuble = ImmeubleProspecteForm(request.POST, allow_commercial_reassign=allow_reassign)
        form_cie = DemarcheAdministrativeForm(request.POST, prefix="cie")
        form_sodeci = DemarcheAdministrativeForm(request.POST, prefix="sodeci")
        if form_immeuble.is_valid() and form_cie.is_valid() and form_sodeci.is_valid():
            immeuble = _enregistrer_prospect(request, form_immeuble, form_cie, form_sodeci)
            messages.success(request, f"Prospect « {immeuble.nom_structure} » enregistré avec succès.")
            return redirect("prospection:liste_prospects")
    else:
        form_immeuble = ImmeubleProspecteForm(allow_commercial_reassign=allow_reassign)
        form_cie = DemarcheAdministrativeForm(prefix="cie")
        form_sodeci = DemarcheAdministrativeForm(prefix="sodeci")

    return render(
        request,
        "prospection/prospect_form.html",
        {"form_immeuble": form_immeuble, "form_cie": form_cie, "form_sodeci": form_sodeci, "immeuble": None},
    )


@login_required
@guichet_unique_write_required
def modifier_prospect(request, pk):
    """Beaucoup de fiches importées sont incomplètes (cf. info.txt), cette vue
    permet de les corriger/compléter plutôt que de les ressaisir de zéro."""
    immeuble = get_object_or_404(ImmeubleProspecte.objects.filter(get_immeuble_scope(request.user)), pk=pk)
    allow_reassign = _peut_reassigner(request.user)

    if request.method == "POST":
        form_immeuble = ImmeubleProspecteForm(request.POST, instance=immeuble, allow_commercial_reassign=allow_reassign)
        form_cie = DemarcheAdministrativeForm(request.POST, prefix="cie")
        form_sodeci = DemarcheAdministrativeForm(request.POST, prefix="sodeci")
        if form_immeuble.is_valid() and form_cie.is_valid() and form_sodeci.is_valid():
            _enregistrer_prospect(request, form_immeuble, form_cie, form_sodeci, immeuble_existant=immeuble)
            messages.success(request, f"Prospect « {immeuble.nom_structure} » mis à jour.")
            return redirect("prospection:liste_prospects")
    else:
        form_immeuble = ImmeubleProspecteForm(instance=immeuble, allow_commercial_reassign=allow_reassign)
        if allow_reassign:
            form_immeuble.fields["commercial"].initial = immeuble.commercial_id
        form_cie = DemarcheAdministrativeForm(prefix="cie", initial=_demarche_initial(immeuble, DemarcheAdministrative.CIE))
        form_sodeci = DemarcheAdministrativeForm(prefix="sodeci", initial=_demarche_initial(immeuble, DemarcheAdministrative.SODECI))

    return render(
        request,
        "prospection/prospect_form.html",
        {"form_immeuble": form_immeuble, "form_cie": form_cie, "form_sodeci": form_sodeci, "immeuble": immeuble},
    )


@login_required
@guichet_unique_required
def detail_prospect(request, pk):
    """Consultation en lecture seule de TOUTES les informations d'un prospect,
    ouverte à qui peut voir le Guichet Unique (Direction comprise, contrairement à
    l'édition réservée à la SDGU). Répond au besoin de consulter intégralement une
    fiche sur la plateforme sans passer par le formulaire d'édition ni l'export."""
    immeuble = get_object_or_404(
        ImmeubleProspecte.objects.filter(get_immeuble_scope(request.user))
        .select_related("commercial__profile", "direction_regionale", "operateur")
        .prefetch_related("demarches"),
        pk=pk,
    )
    cie = immeuble.demarches.filter(organisme=DemarcheAdministrative.CIE).first()
    sodeci = immeuble.demarches.filter(organisme=DemarcheAdministrative.SODECI).first()
    return render(
        request,
        "prospection/prospect_detail.html",
        {
            "immeuble": immeuble,
            "cie": cie,
            "sodeci": sodeci,
            "peut_modifier": not getattr(request.user.profile, "is_direction", False),
        },
    )


@login_required
@guichet_unique_required
def liste_operateurs(request):
    """Portefeuille des opérateurs immobiliers, scopé par CCGC (cf.
    prospection.scoping : un CCGC individuel voit son propre portefeuille, un
    "cadre" (cadre_guichet_unique, cadre_charge_affaires_guichet) voit le cumul
    de son groupe de CCGC, la Direction/Sous-Direction voit tout), avec
    segmentation qualitative (Top / Prioritaire / Standard, projet clé 2026,
    sensible) et recherche par nom (demande utilisateur : retrouver un opérateur,
    ou le sélectionner pour planifier une visite)."""
    profile = request.user.profile
    base = OperateurImmobilier.objects.filter(get_operateur_scope(request.user))

    if request.method == "POST" and not profile.is_direction:
        op = base.filter(pk=request.POST.get("operateur")).first()
        if op is not None:
            op.segment = request.POST.get("segment", op.segment)
            op.projet_2026 = request.POST.get("projet_2026") == "on"
            op.sensible = request.POST.get("sensible") == "on"
            op.zone = request.POST.get("zone", op.zone).strip()
            op.save(update_fields=["segment", "projet_2026", "sensible", "zone"])
            messages.success(request, f"Opérateur « {op.nom} » mis à jour.")
        return redirect(f"{request.path}?{request.GET.urlencode()}")

    stats = {
        "total": base.count(),
        "top": base.filter(segment=OperateurImmobilier.TOP).count(),
        "prioritaires": base.filter(segment=OperateurImmobilier.PRIORITAIRE).count(),
        "projet_2026": base.filter(projet_2026=True).count(),
    }

    qs = base
    q = request.GET.get("q", "").strip()
    seg = request.GET.get("segment", "")
    ccgc = request.GET.get("ccgc", "")
    if q:
        qs = qs.filter(nom__icontains=q)
    if seg:
        qs = qs.filter(segment=seg)
    if ccgc:
        qs = qs.filter(ccgc=ccgc)
    if request.GET.get("projet") == "2026":
        qs = qs.filter(projet_2026=True)

    page = Paginator(qs.order_by("-projet_2026", "segment", "nom"), 50).get_page(request.GET.get("page"))

    return render(
        request,
        "prospection/liste_operateurs.html",
        {
            "operateurs": page,
            "page_obj": page,
            "stats": stats,
            "segments": OperateurImmobilier.SEGMENT_CHOICES,
            "ccgc_choices": OperateurImmobilier.CCGC_CHOICES,
            "q": q,
            "seg_selectionne": seg,
            "ccgc_selectionne": ccgc,
            "projet_filtre": request.GET.get("projet", ""),
            "peut_editer": not profile.is_direction,
        },
    )


def _trimestre_courant():
    """T3 = juillet-août-septembre, T4 = octobre-novembre-décembre (demande
    utilisateur explicite : découpage du dernier semestre). En dehors de cette
    fenêtre, on retombe sur T3 par défaut (le plus proche à venir)."""
    from datetime import date

    aujourdhui = date.today()
    if aujourdhui.month in (10, 11, 12):
        return aujourdhui.year, VisitePlanifiee.T4
    return aujourdhui.year, VisitePlanifiee.T3


def _prefill_localisation(operateur, immeuble):
    """Dérive (direction_regionale, commune_quartier) par défaut pour une
    nouvelle visite, depuis sa cible : le champ "zone" d'un opérateur (texte
    libre) est rattaché à sa DR via la même table de correspondance que les
    immeubles (prospection.zones), pour éviter de ressaisir une DR déjà connue
    par ailleurs. Reste un point de départ : le formulaire permet de corriger."""
    if immeuble is not None:
        commune = immeuble.zone_prospection
        dr = immeuble.direction_regionale
        if dr is None and commune:
            code = dr_code_pour_zone(commune)
            dr = DirectionRegionale.objects.filter(code=code).first() if code else None
        return dr, commune
    if operateur is not None and operateur.zone:
        code = dr_code_pour_zone(operateur.zone)
        dr = DirectionRegionale.objects.filter(code=code).first() if code else None
        return dr, operateur.zone
    return None, ""


@login_required
@guichet_unique_required
def planning_visites(request):
    """Planning trimestriel de visites (opérateurs ET immeubles), prévu vs
    réalisé, avec DR et commune/quartier renseignés pour chaque visite (demande
    utilisateur explicite). Objectif SDGU : couvrir 100% des opérateurs à projet
    clé 2026 sur le trimestre, avec au moins un contact mensuel — la synthèse
    ci-dessous mesure cet écart. Scope aligné sur la hiérarchie CCGC (cf.
    prospection.scoping.get_visite_scope)."""
    annee_defaut, trimestre_defaut = _trimestre_courant()
    annee = int(request.GET.get("annee", annee_defaut))
    trimestre = request.GET.get("trimestre", trimestre_defaut)
    q_operateur = request.GET.get("q_operateur", "").strip()
    q_immeuble = request.GET.get("q_immeuble", "").strip()

    if request.method == "POST":
        if request.POST.get("marquer_realisee"):
            visite = VisitePlanifiee.objects.filter(
                get_visite_scope(request.user), pk=request.POST["marquer_realisee"]
            ).first()
            if visite is not None:
                visite.date_realisee = request.POST.get("date_realisee") or date.today()
                visite.compte_rendu = request.POST.get("compte_rendu", visite.compte_rendu)
                visite.save(update_fields=["date_realisee", "compte_rendu"])
                messages.success(request, "Visite marquée réalisée.")
        else:
            operateur_id = request.POST.get("operateur") or None
            immeuble_id = request.POST.get("immeuble") or None
            if operateur_id or immeuble_id:
                operateur = OperateurImmobilier.objects.filter(pk=operateur_id).first() if operateur_id else None
                immeuble = ImmeubleProspecte.objects.filter(pk=immeuble_id).first() if immeuble_id else None
                dr_defaut, commune_defaut = _prefill_localisation(operateur, immeuble)
                dr_id = request.POST.get("direction_regionale") or (dr_defaut.pk if dr_defaut else None)
                commune = request.POST.get("commune_quartier", "").strip() or commune_defaut
                VisitePlanifiee.objects.create(
                    annee=annee, trimestre=trimestre,
                    operateur=operateur, immeuble=immeuble,
                    direction_regionale_id=dr_id,
                    commune_quartier=commune,
                    mois_prevu=request.POST.get("mois_prevu") or None,
                    date_prevue=request.POST.get("date_prevue") or None,
                    commercial=request.user,
                )
                messages.success(request, "Visite planifiée.")
        return redirect(f"{request.path}?annee={annee}&trimestre={trimestre}")

    visites = VisitePlanifiee.objects.filter(get_visite_scope(request.user), annee=annee, trimestre=trimestre).select_related(
        "operateur", "immeuble", "commercial", "direction_regionale"
    )

    stats = {
        "total": visites.count(),
        "realisees": visites.filter(date_realisee__isnull=False).count(),
    }
    stats["taux"] = (stats["realisees"] / stats["total"] * 100) if stats["total"] else 0

    operateurs_top = OperateurImmobilier.objects.filter(get_operateur_scope(request.user)).filter(
        Q(segment__in=[OperateurImmobilier.TOP, OperateurImmobilier.PRIORITAIRE]) | Q(projet_2026=True)
    ).distinct()
    couverts = visites.filter(operateur__in=operateurs_top).values_list("operateur_id", flat=True).distinct()
    stats["operateurs_prioritaires"] = operateurs_top.count()
    stats["operateurs_couverts"] = len(set(couverts))

    # Recherche par nom (demande utilisateur : planifier ou retrouver un
    # opérateur/immeuble) : sans recherche, liste bornée à 100 pour rester
    # praticable dans un <select> ; une recherche narrows sans limite.
    operateurs_dispo = OperateurImmobilier.objects.filter(get_operateur_scope(request.user)).order_by("nom")
    immeubles_dispo = ImmeubleProspecte.objects.filter(get_immeuble_scope(request.user)).order_by("nom_structure")
    if q_operateur:
        operateurs_dispo = operateurs_dispo.filter(nom__icontains=q_operateur)
    else:
        operateurs_dispo = operateurs_dispo[:100]
    if q_immeuble:
        immeubles_dispo = immeubles_dispo.filter(nom_structure__icontains=q_immeuble)
    else:
        immeubles_dispo = immeubles_dispo[:100]

    return render(
        request,
        "prospection/planning_visites.html",
        {
            "visites": visites.order_by("date_realisee", "mois_prevu"),
            "stats": stats,
            "annee": annee,
            "trimestre": trimestre,
            "trimestres": VisitePlanifiee.TRIMESTRE_CHOICES,
            "operateurs_dispo": operateurs_dispo,
            "immeubles_dispo": immeubles_dispo,
            "q_operateur": q_operateur,
            "q_immeuble": q_immeuble,
            "operateur_preselectionne": request.GET.get("operateur", ""),
            "immeuble_preselectionne": request.GET.get("immeuble", ""),
            "directions_regionales": DirectionRegionale.objects.all().order_by("code"),
        },
    )


@login_required
@guichet_unique_required
def exporter_planning(request):
    """Export Excel du planning du trimestre affiché (demande utilisateur),
    même scope et mêmes filtres que la vue à l'écran."""
    annee_defaut, trimestre_defaut = _trimestre_courant()
    annee = int(request.GET.get("annee", annee_defaut))
    trimestre = request.GET.get("trimestre", trimestre_defaut)

    visites = (
        VisitePlanifiee.objects.filter(get_visite_scope(request.user), annee=annee, trimestre=trimestre)
        .select_related("operateur", "immeuble", "commercial", "direction_regionale")
        .order_by("mois_prevu", "date_prevue")
    )

    lignes = [
        {
            "Cible": v.cible_nom,
            "Type": "Opérateur" if v.operateur_id else "Immeuble",
            "DR": v.direction_regionale.code if v.direction_regionale else "",
            "Commune / Quartier": v.commune_quartier,
            "Mois prévu": v.mois_prevu,
            "Date prévue": v.date_prevue,
            "Date réalisée": v.date_realisee,
            "Statut": "Réalisée" if v.est_realisee else "Planifiée",
            "Compte-rendu": v.compte_rendu,
            "Planifiée par": v.commercial.username if v.commercial else "",
        }
        for v in visites
    ]
    df = pd.DataFrame(lignes)
    return excel_response(
        df, f"planning_visites_{trimestre}_{annee}.xlsx", sheet_name="Planning",
        titre=f"Planning de visites — {trimestre} {annee} — Guichet Unique", couleur_entete="F7941E",
    )


@login_required
@guichet_unique_required
def calendrier_visites(request):
    """Agenda mensuel dédié (demande utilisateur explicite), vue calendrier
    classique (grille de semaines) plutôt qu'une simple liste : chaque jour du
    mois affiche les visites dont la date prévue tombe ce jour-là, avec un
    marquage visuel des visites déjà réalisées."""
    annee = int(request.GET.get("annee", date.today().year))
    mois = int(request.GET.get("mois", date.today().month))

    visites = (
        VisitePlanifiee.objects.filter(
            get_visite_scope(request.user), date_prevue__year=annee, date_prevue__month=mois
        )
        .select_related("operateur", "immeuble", "direction_regionale")
        .order_by("date_prevue")
    )
    visites_par_jour = {}
    for v in visites:
        visites_par_jour.setdefault(v.date_prevue.day, []).append(v)

    cal = calendar_module.Calendar(firstweekday=0)  # semaine commençant lundi
    semaines = [
        [(jour, visites_par_jour.get(jour, [])) for jour in semaine]
        for semaine in cal.monthdayscalendar(annee, mois)
    ]
    # Vue liste (mobile) : la grille à 7 colonnes fixes devient illisible sur un
    # écran étroit (colonnes compressées à ~50px, cf. retour utilisateur), donc on
    # prépare aussi une liste chronologique jour par jour, affichée uniquement
    # en dessous du seuil `md` (cf. template, classes d-md-none / d-none d-md-block).
    jours_avec_visites = [
        {"jour": jour, "date": date(annee, mois, jour), "visites": visites_par_jour[jour]}
        for jour in sorted(visites_par_jour)
    ]

    mois_precedent = (annee, mois - 1) if mois > 1 else (annee - 1, 12)
    mois_suivant = (annee, mois + 1) if mois < 12 else (annee + 1, 1)

    return render(
        request,
        "prospection/calendrier_visites.html",
        {
            "semaines": semaines,
            "jours_avec_visites": jours_avec_visites,
            "annee": annee,
            "mois": mois,
            "nom_mois": calendar_module.month_name[mois].capitalize(),
            "jours_semaine": ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
            "annee_precedente": mois_precedent[0], "mois_precedent": mois_precedent[1],
            "annee_suivante": mois_suivant[0], "mois_suivant": mois_suivant[1],
            "aujourdhui": date.today(),
            "total_mois": visites.count(),
        },
    )


@login_required
@guichet_unique_required
def liste_prospects(request):
    qs = ImmeubleProspecte.objects.filter(get_immeuble_scope(request.user)).select_related("commercial__profile")

    zone = request.GET.get("zone", "")
    stade = request.GET.get("stade", "")
    if zone:
        qs = qs.filter(zone_prospection=zone)
    if stade:
        qs = qs.filter(stade_avancement=stade)

    zones_disponibles = (
        ImmeubleProspecte.objects.filter(get_immeuble_scope(request.user))
        .exclude(zone_prospection="")
        .values_list("zone_prospection", flat=True)
        .distinct()
        .order_by("zone_prospection")
    )

    page = Paginator(qs, 50).get_page(request.GET.get("page"))

    return render(
        request,
        "prospection/liste_prospects.html",
        {
            "prospects": page,
            "page_obj": page,
            "total": qs.count(),
            "zones_disponibles": zones_disponibles,
            "stades_disponibles": ImmeubleProspecte.STADE_CHOICES,
            "zone_selectionnee": zone,
            "stade_selectionne": stade,
            "peut_administrer": peut_administrer_base(request.user),
        },
    )


@login_required
@guichet_unique_required
def export_prospects(request):
    """Export Excel du périmètre visible par l'utilisateur (son portefeuille
    seul pour un compte individuel, toute la SDGU pour Sous-Directeur/Direction),
    pour d'autres travaux (rapports, retraitements hors application)."""
    qs = (
        ImmeubleProspecte.objects.filter(get_immeuble_scope(request.user))
        .select_related("commercial", "direction_regionale")
        .prefetch_related("demarches")
    )

    lignes = []
    for immeuble in qs:
        cie = immeuble.demarches.filter(organisme=DemarcheAdministrative.CIE).first()
        sodeci = immeuble.demarches.filter(organisme=DemarcheAdministrative.SODECI).first()
        lignes.append(
            {
                "Structure": immeuble.nom_structure,
                "Cible": immeuble.get_type_cible_display() if immeuble.type_cible else "",
                "Constructeur": immeuble.constructeur,
                "Interlocuteur": immeuble.interlocuteur,
                "Fonction": immeuble.fonction_interlocuteur,
                "Contact": immeuble.contact,
                "Email": immeuble.email,
                "Situation géographique": immeuble.situation_geographique,
                "Quartier": immeuble.zone_prospection,
                "DEX": immeuble.get_dex_display() if immeuble.dex else "",
                "DR": immeuble.direction_regionale.code if immeuble.direction_regionale else "",
                "Hauteur (niveaux)": immeuble.nb_niveaux,
                "Appartements/Bureaux": immeuble.nb_appartements_bureaux,
                "Stade d'avancement": immeuble.get_stade_avancement_display() if immeuble.stade_avancement else "",
                "Date début travaux": immeuble.date_debut_travaux,
                "Date prév. fin travaux": immeuble.date_prev_fin_travaux,
                "Délai de livraison": immeuble.delai_livraison,
                "Poste existant": {True: "Oui", False: "Non"}.get(immeuble.poste_existant, ""),
                "Cible prioritaire (R+5 et +)": "Oui" if immeuble.est_cible_prioritaire else "Non",
                "Demande CIE initiée": "Oui" if cie and cie.demande_initiee else ("Non" if cie else ""),
                "Statut CIE": cie.get_statut_display() if cie and cie.statut else "",
                "Demande SODECI initiée": "Oui" if sodeci and sodeci.demande_initiee else ("Non" if sodeci else ""),
                "Statut SODECI": sodeci.get_statut_display() if sodeci and sodeci.statut else "",
                "Commercial": immeuble.commercial.profile.get_role_display() if immeuble.commercial and getattr(immeuble.commercial, "profile", None) else "",
                "Observations": immeuble.observations,
            }
        )

    df = pd.DataFrame(lignes)
    return excel_response(df, "prospects_guichet_unique.xlsx", sheet_name="Prospects", titre="Prospects — Guichet Unique CIE-SODECI")


@login_required
@guichet_unique_write_required
def importer_prospects(request):
    """Ajoute de nouveaux prospects depuis un fichier Excel (même format que
    recensement_sdgu.xlsx) SANS toucher à l'existant, contrairement à la
    commande d'import historique (rafraîchissement complet), pensée pour la mise
    à jour ponctuelle de la base par la Sous-Direction elle-même."""
    if not peut_administrer_base(request.user):
        raise PermissionDenied("Réservé au Sous-Directeur Guichet Unique (affecte toute la base partagée).")

    erreur = None
    resultat = None
    if request.method == "POST" and request.FILES.get("fichier"):
        fichier = request.FILES["fichier"]
        try:
            df = pd.read_excel(fichier, sheet_name="ACTIONS_IMM")
        except ValueError:
            try:
                fichier.seek(0)
                df = pd.read_excel(fichier)
            except Exception:
                df = None
        if df is None:
            erreur = "Fichier illisible : vérifiez qu'il s'agit bien d'un .xlsx au format recensement_sdgu.xlsx."
        else:
            manquantes = colonnes_manquantes(df)
            if manquantes:
                erreur = f"Colonnes manquantes dans le fichier : {', '.join(manquantes)}."
            else:
                nb_crees, nb_ignores_vides, nb_a_completer = importer_depuis_dataframe(df, cree_par=request.user)
                resultat = (nb_crees, nb_ignores_vides, nb_a_completer)
                messages.success(
                    request,
                    f"{nb_crees} nouveaux prospects ajoutés ({nb_ignores_vides} lignes vides ignorées, "
                    f"dont {nb_a_completer} sans nom de structure à compléter).",
                )
                return redirect("prospection:liste_prospects")

    return render(request, "prospection/importer_prospects.html", {"erreur": erreur, "resultat": resultat})
