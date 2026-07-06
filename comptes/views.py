from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from comptes.forms import DemandeAccesForm, ParametresForm, ProfileForm
from core.models import Entite


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm.from_user(request.user, data=request.POST, files=request.FILES)
        if form.is_valid():
            form.save(request.user)
            messages.success(request, "Profil mis à jour.")
            return redirect("comptes:profile")
    else:
        form = ProfileForm.from_user(request.user)

    return render(request, "comptes/profile.html", {"form": form})


def demande_acces(request):
    """Page publique (pas de login) : la personne soumet une demande, la
    Direction la traite ensuite via l'admin Django (cf. comptes.models.
    DemandeAcces) ; pas de création de compte automatique."""
    if request.method == "POST":
        form = DemandeAccesForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre demande a été envoyée. Vous serez contacté(e) une fois traitée.")
            return redirect("comptes:demande_acces")
    else:
        form = DemandeAccesForm()

    return render(request, "comptes/demande_acces.html", {"form": form})


ZONE_PAR_ENTITE = {Entite.ABIDJAN: "Abidjan", Entite.INTERIEUR: "Intérieur"}


@login_required
def parametres(request):
    """"Mon périmètre" : réservé aux entités Abidjan/Intérieur, où la notion de
    zone/DR a un sens (cf. ParametresForm). Les autres entités (Stratégiques,
    Guichet Unique, Support Technique...) n'ont pas ce concept de zone DR."""
    profile = getattr(request.user, "profile", None)
    code_entite = profile.entite.code if profile and profile.entite_id else None
    zone = ZONE_PAR_ENTITE.get(code_entite)
    if zone is None:
        raise PermissionDenied("Le périmètre par Direction Régionale ne concerne que les Services Abidjan/Intérieur.")

    if request.method == "POST":
        form = ParametresForm(request.POST, zone=zone, initial={"directions_regionales": profile.directions_regionales.all()})
        if form.is_valid():
            form.save(request.user)
            messages.success(request, "Périmètre mis à jour.")
            return redirect("comptes:parametres")
    else:
        form = ParametresForm(zone=zone, initial={"directions_regionales": profile.directions_regionales.all()})

    return render(request, "comptes/parametres.html", {"form": form})
