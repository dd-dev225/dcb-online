from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from core.models import Entite, Objectif

from . import data


def _is_direction(user):
    profile = getattr(user, "profile", None)
    return bool(profile) and profile.is_direction


def direction_required(view_func):
    """Seul le nœud racine de l'organigramme (Direction Commerciale Business) doit
    voir la vue agrégée totale, déterminé par la position dans l'arbre Entite
    (profile.is_direction), pas par un groupe Django séparé à maintenir en double."""

    def wrapped(request, *args, **kwargs):
        if not _is_direction(request.user):
            raise PermissionDenied("Réservé au compte Direction.")
        return view_func(request, *args, **kwargs)

    return wrapped


def entite_required(view_func):
    """Tout profil disposant d'une entité assignée et qui n'est pas le nœud racine :
    Sous-Directeur, Chef de Service ou niveau opérationnel."""

    def wrapped(request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)
        if _is_direction(request.user) or profile is None or profile.entite_id is None:
            raise PermissionDenied("Réservé aux comptes disposant d'un nœud d'organigramme assigné.")
        return view_func(request, *args, **kwargs)

    return wrapped


def _est_guichet_unique(user):
    profile = getattr(user, "profile", None)
    return profile is not None and profile.entite_id is not None and profile.entite.code == Entite.GUICHET_UNIQUE


def guichet_unique_required(view_func):
    """Lecture (dashboard, liste, export) : Sous-Direction Guichet Unique ET
    Direction (la Direction garde "les grandes lignes" de toutes les activités
    pour décider, cf. demande utilisateur), pas les autres entités, dont
    l'activité n'a rien à voir avec la prospection immobilière."""

    def wrapped(request, *args, **kwargs):
        if not (_is_direction(request.user) or _est_guichet_unique(request.user)):
            raise PermissionDenied("Réservé à la Direction et à la Sous-Direction Guichet Unique.")
        return view_func(request, *args, **kwargs)

    return wrapped


def guichet_unique_write_required(view_func):
    """Écriture (créer/modifier un prospect, importer) : Sous-Direction Guichet
    Unique UNIQUEMENT. La Direction pilote/décide à partir des indicateurs mais
    ne doit pas pouvoir lancer elle-même une fiche de prospection (demande
    utilisateur explicite) ; ce n'est pas son métier opérationnel."""

    def wrapped(request, *args, **kwargs):
        if not _est_guichet_unique(request.user):
            raise PermissionDenied("Réservé aux comptes de la Sous-Direction Guichet Unique (pas la Direction).")
        return view_func(request, *args, **kwargs)

    return wrapped


def _est_support_technique(user):
    """Sous-Direction Support Technique Business OU l'un de ses Services enfants
    (Prospection Raccordement, Installation Industrielle) : contrairement à
    Guichet Unique (un nœud feuille), Support Technique a un sous-arbre, d'où la
    vérification par descendants_ids() plutôt qu'une simple égalité de code."""
    profile = getattr(user, "profile", None)
    if profile is None or profile.entite_id is None:
        return False
    try:
        racine = Entite.objects.get(code=Entite.SUPPORT_TECHNIQUE)
    except Entite.DoesNotExist:
        return False
    return profile.entite_id in racine.descendants_ids()


def support_technique_required(view_func):
    """Lecture (dashboard, listes incidents/travaux, export) : Sous-Direction
    Support Technique Business ET Direction, même logique que guichet_unique_required."""

    def wrapped(request, *args, **kwargs):
        if not (_is_direction(request.user) or _est_support_technique(request.user)):
            raise PermissionDenied("Réservé à la Direction et à la Sous-Direction Support Technique Business.")
        return view_func(request, *args, **kwargs)

    return wrapped


# is_direction/entite/role sont injectés dans le contexte de TOUTE page par
# comptes.context_processors.profile_context (la sidebar/topbar de base.html en a
# besoin partout, pas seulement sur la page d'accueil). Les vues ci-dessous n'ont
# donc rien à passer explicitement.


def _formater_delta(delta_pct):
    """Petit badge de variation vs la période précédente (demande utilisateur,
    cf. rapport "Fonctionnalités proposées"), None si pas assez d'historique pour
    le calculer plutôt que d'afficher un delta trompeur (cf. data._delta_pourcentage)."""
    if delta_pct is None:
        return None
    return {
        "texte": f"{delta_pct:+.1f}% vs mois précédent",
        "sens": "hausse" if delta_pct >= 0 else "baisse",
    }


def _stat(label, valeur, icone, badge=None, delta_pct=None):
    return {
        "label": label,
        "valeur": valeur,
        "icone": icone,
        "badge": badge,
        "aide": data.AIDE_PAR_LIBELLE.get(label),
        "delta": _formater_delta(delta_pct),
    }


def _bouton(label, url_name, icone):
    return {"label": label, "url": url_name, "icone": icone}


COULEUR_BOOTSTRAP_PAR_RECOUVREMENT = {"vert": "success", "orange": "warning", "rouge": "danger", "gris": "secondary"}


def _section_sdrcb(user, perf_url, eng_url):
    """Indicateurs globaux Relation Clients Business. kpi_*(user) respecte déjà
    le scope de l'appelant (rollup d'entité ou portefeuille individuel), donc cette
    fonction donne le bon chiffre que ce soit pour la Direction, un Sous-Directeur,
    un Chef de Service ou une Chargée d'Affaires, sans cas particulier à coder ici."""
    periode, ca_mds, delta_ca = data.kpi_ca_dernier_mois_avec_delta(user)
    nb_clients = data.kpi_nb_clients_dernier_mois(user)
    taux, couleur_taux = data.kpi_taux_recouvrement_global(user)
    nb_reclam = data.kpi_nb_reclamations(user)
    taux_qualite, nb_completes, nb_total_fiches = data.kpi_qualite_fiches(user)

    stats = [
        _stat("CA du mois" + (f" ({periode})" if periode else ""), f"{ca_mds:,.1f} Mds FCFA".replace(",", " ") if ca_mds is not None else "—", "fa-coins", delta_pct=delta_ca),
        _stat("Clients facturés", f"{nb_clients:,}".replace(",", " ") if nb_clients is not None else "—", "fa-users"),
        _stat("Taux de recouvrement", f"{taux * 100:.1f}%" if taux is not None else "—", "fa-hand-holding-usd", COULEUR_BOOTSTRAP_PAR_RECOUVREMENT[couleur_taux]),
        _stat("Réclamations", f"{nb_reclam:,}".replace(",", " "), "fa-comment-dots"),
        _stat(
            "Fiches complètes",
            f"{nb_completes}/{nb_total_fiches} ({taux_qualite * 100:.0f}%)" if taux_qualite is not None else "—",
            "fa-clipboard-check",
        ),
    ]

    # Objectif de CA mensuel : facultatif (core.Entite.objectif_ca_mensuel_mds),
    # demande utilisateur cf. rapport "Fonctionnalités proposées" : juger le CA par
    # rapport à une cible plutôt qu'un montant brut sans repère. N'apparaît que si
    # la Direction a défini une cible pour CETTE entité précisément (via /admin/).
    entite = getattr(getattr(user, "profile", None), "entite", None)
    objectif = entite.objectif_ca_mensuel_mds if entite else None
    if objectif and ca_mds is not None:
        objectif = float(objectif)
        atteinte_pct = (ca_mds / objectif) * 100
        stats.append(_stat(
            "Objectif de CA mensuel",
            f"{ca_mds:,.1f} / {objectif:,.1f} Mds FCFA ({atteinte_pct:.0f}%)".replace(",", " "),
            "fa-bullseye",
            "success" if atteinte_pct >= 100 else ("warning" if atteinte_pct >= 80 else "danger"),
        ))

    return {
        "titre": "Relation Clients Business",
        "icone": "fa-handshake",
        "couleur": "primary",
        "stats": stats,
        "boutons": [_bouton("Performance", perf_url, "fa-chart-line"), _bouton("Engagement", eng_url, "fa-handshake")],
    }


def _section_support_technique(boutons):
    """Pas de portefeuille Client/Facture propre (cf. historique Guichet Unique) :
    Support Technique traite TOUTE demande de raccordement de la DCB, donc son
    indicateur est le même quel que soit le viewer de ce sous-arbre, pas besoin de
    le recalculer par utilisateur (cf. dashboards.data.synthese_support_technique)."""
    s = data.synthese_support_technique()
    return {
        "titre": "Support Technique Business",
        "icone": "fa-tools",
        "couleur": "info",
        "stats": [
            _stat("Demandes en cours", f"{s['nb_demandes_en_cours']:,}".replace(",", " "), "fa-tools"),
            _stat("Durée moyenne de traitement", f"{s['duree_moyenne_jours']} jours" if s["duree_moyenne_jours"] is not None else "—", "fa-clock"),
        ],
        "boutons": boutons,
    }


def _section_guichet_unique(user):
    nb = data.kpi_nb_immeubles_prospectes(user)
    nb_prio = data.kpi_nb_cibles_prioritaires(user)
    taux_cie = data.kpi_taux_conversion_cie(user)
    return {
        "titre": "Guichet Unique CIE-SODECI",
        "icone": "fa-city",
        "couleur": "warning",
        "stats": [
            _stat("Immeubles suivis", f"{nb:,}".replace(",", " "), "fa-building"),
            _stat("Cibles prioritaires (R+5 et +)", f"{nb_prio:,}".replace(",", " "), "fa-bullseye"),
            _stat("Taux de conversion → demande CIE", f"{taux_cie * 100:.0f}%" if taux_cie is not None else "—", "fa-bolt"),
        ],
        "boutons": [_bouton("Prospection immobilière", "dashboards:prospection_guichet_unique", "fa-city")],
    }


@login_required
def home(request):
    """Page d'accueil : les indicateurs du périmètre propre de l'utilisateur avec
    ses boutons d'accès au détail (Performance/Engagement, ou Prospection pour
    Guichet Unique), pour TOUTE entité de la DCB, pas seulement Direction/
    Sous-Directeur. Aucun jargon technique (rôle/entité/périmètre) : juste les
    chiffres qui comptent et où aller pour creuser."""
    context = {}
    profile = getattr(request.user, "profile", None)
    if profile is not None and profile.entite_id is not None:
        user = request.user
        est_direction = _is_direction(user)
        sdrcb_ids = Entite.objects.get(code=Entite.SDRCB).descendants_ids()
        support_ids = Entite.objects.get(code=Entite.SUPPORT_TECHNIQUE).descendants_ids()
        gu_ids = Entite.objects.get(code=Entite.GUICHET_UNIQUE).descendants_ids()

        if est_direction:
            # La Direction voit "les grandes lignes" des 3 Sous-Directions (demande
            # utilisateur), un seul bouton "Voir le détail" pour Support Technique
            # (pas de page Direction dédiée à ce seul sous-arbre, Engagement-Direction
            # couvre déjà délais/demandes au niveau global) et pour Guichet Unique
            # (page unique partagée, déjà scopée correctement pour la Direction).
            context["sections"] = [
                _section_sdrcb(user, "dashboards:performance_direction", "dashboards:engagement_direction"),
                _section_support_technique([_bouton("Voir le détail", "dashboards:engagement_direction", "fa-arrow-right")]),
                _section_guichet_unique(user),
            ]
        elif profile.entite_id in sdrcb_ids:
            context["sections"] = [_section_sdrcb(user, "dashboards:performance_entite", "dashboards:engagement_entite")]
        elif profile.entite_id in support_ids:
            context["sections"] = [
                _section_support_technique(
                    [_bouton("Performance", "dashboards:performance_entite", "fa-chart-line"),
                     _bouton("Engagement", "dashboards:engagement_entite", "fa-handshake")]
                )
            ]
        elif profile.entite_id in gu_ids:
            context["sections"] = [_section_guichet_unique(user)]

    return render(request, "dashboards/home.html", context)


@login_required
@direction_required
def performance_direction(request):
    return render(request, "dashboards/performance_direction.html")


@login_required
@direction_required
def engagement_direction(request):
    return render(request, "dashboards/engagement_direction.html")


@login_required
@entite_required
def performance_entite(request):
    return render(request, "dashboards/performance_entite.html")


@login_required
@entite_required
def engagement_entite(request):
    return render(request, "dashboards/engagement_entite.html")


@login_required
@guichet_unique_required
def prospection_guichet_unique(request):
    return render(request, "dashboards/prospection_guichet_unique.html")


@login_required
def objectifs(request):
    """Consultation des objectifs applicables à l'entité de l'utilisateur, en regard
    de son réalisé (demande utilisateur : le Directeur définit, les autres entités
    voient). Tout profil rattaché à une entité y a accès en lecture."""
    return render(
        request,
        "dashboards/objectifs.html",
        {"objectifs": data.objectifs_avec_realise(request.user), "peut_gerer": _is_direction(request.user)},
    )


@login_required
@direction_required
def gerer_objectifs(request):
    """Définition des objectifs par le Directeur : une cible par (entité, indicateur).
    update_or_create pour modifier sans dupliquer ; suppression possible."""
    if request.method == "POST":
        if request.POST.get("supprimer"):
            Objectif.objects.filter(pk=request.POST["supprimer"]).delete()
            messages.success(request, "Objectif supprimé.")
        else:
            entite = Entite.objects.filter(pk=request.POST.get("entite")).first()
            indicateur = request.POST.get("indicateur")
            valeur = request.POST.get("valeur_cible")
            if entite and indicateur in dict(Objectif.INDICATEUR_CHOICES) and valeur:
                Objectif.objects.update_or_create(
                    entite=entite, indicateur=indicateur,
                    defaults={"valeur_cible": valeur, "defini_par": request.user},
                )
                messages.success(request, "Objectif enregistré.")
        return redirect("dashboards:gerer_objectifs")

    return render(
        request,
        "dashboards/gerer_objectifs.html",
        {
            "objectifs": Objectif.objects.select_related("entite", "defini_par"),
            "entites": Entite.objects.all(),
            "indicateurs": Objectif.INDICATEUR_CHOICES,
        },
    )
