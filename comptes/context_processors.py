"""Injecte le profil (rôle/entité/is_direction/salutation) dans le contexte de TOUS
les templates, puisque base.html (sidebar + topbar) en a besoin sur chaque page, pas
seulement sur la page d'accueil, ce qui évite de dupliquer cette logique dans chaque vue
de dashboards/views.py."""

from django.utils import timezone

from core.models import Entite


def profile_context(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    profile = getattr(user, "profile", None)
    entite = getattr(profile, "entite", None)

    heure_locale = timezone.localtime(timezone.now()).hour
    salutation = "Bonjour" if 5 <= heure_locale < 18 else "Bonsoir"

    return {
        "is_direction": bool(profile) and profile.is_direction,
        "entite": entite,
        # Métier à part (prospection immobilière, pas de Client/Facture) : sa propre
        # page plutôt que Performance/Engagement (cf. dashboards.dash_apps.
        # prospection_guichet_unique), la sidebar en a besoin pour afficher son
        # lien dédié uniquement aux comptes concernés.
        "is_guichet_unique": bool(entite) and entite.code == Entite.GUICHET_UNIQUE,
        # Portefeuille clients (fiche enrichie, clients stratégiques) : propre à la
        # SDRCB et ses Services, pas à la Direction (même principe que Guichet
        # Unique, calcul inline plutôt qu'un import de clients.permissions pour ne
        # pas faire dépendre comptes d'une app de plus haut niveau).
        "is_sdrcb": bool(entite) and entite.pk in Entite.objects.get(code=Entite.SDRCB).descendants_ids(),
        # Lien "Clients stratégiques non rattachés" dans la sidebar : propre au
        # Service Stratégiques & Sensibles (cf. clients.permissions.
        # peut_proposer_strategique), pas à toute la SDRCB (Abidjan/Intérieur ne
        # sont pas concernés par cette anomalie de rattachement).
        "is_service_strategiques": bool(entite)
        and entite.pk in Entite.objects.get(code=Entite.STRATEGIQUES_SENSIBLES).descendants_ids(),
        # Qualité du réseau (incidents/travaux HTA, cf. reseau app) : propre à la
        # Sous-Direction Support Technique Business et ses Services, même principe
        # que is_sdrcb ci-dessus.
        "is_support_technique": bool(entite)
        and entite.pk in Entite.objects.get(code=Entite.SUPPORT_TECHNIQUE).descendants_ids(),
        # "Mes paramètres" (périmètre par DR) n'a de sens que pour Abidjan/Intérieur,
        # cf. comptes.views.parametres et son ZONE_PAR_ENTITE.
        "a_parametres_perimetre": bool(entite) and entite.code in (Entite.ABIDJAN, Entite.INTERIEUR),
        "role": profile.get_role_display() if profile and profile.role else None,
        "salutation": salutation,
        "display_name": profile.display_name if profile else user.username,
    }
