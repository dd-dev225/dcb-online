from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

import pandas as pd

from core.excel import excel_response

from .forms import MessageForm
from .models import Message
from .permissions import entites_contactables


def _entite_utilisateur(user):
    profile = getattr(user, "profile", None)
    return getattr(profile, "entite", None)


@login_required
def boite_reception(request):
    entite = _entite_utilisateur(request.user)
    messages_recus = Message.objects.filter(entite_destinataire=entite).select_related(
        "entite_expeditrice", "expediteur"
    )
    ids_non_lus = set(messages_recus.exclude(lu_par=request.user).values_list("pk", flat=True))
    return render(
        request,
        "messagerie/boite_reception.html",
        {"messages_recus": messages_recus, "ids_non_lus": ids_non_lus},
    )


@login_required
def boite_envoi(request):
    entite = _entite_utilisateur(request.user)
    messages_envoyes = Message.objects.filter(entite_expeditrice=entite).select_related(
        "entite_destinataire", "expediteur"
    )
    return render(request, "messagerie/boite_envoi.html", {"messages_envoyes": messages_envoyes})


def _exporter_messages(queryset, colonne_entite, champ_entite, nom_fichier):
    lignes = [
        {
            colonne_entite: str(getattr(m, champ_entite)),
            "Message": m.contenu,
            "Date": m.envoye_le.strftime("%d/%m/%Y %H:%M"),
            "Par": (m.expediteur.get_full_name() or m.expediteur.username) if m.expediteur else "",
        }
        for m in queryset
    ]
    df = pd.DataFrame(lignes)
    return excel_response(df, f"{nom_fichier}.xlsx", sheet_name="Messages", titre="Messagerie interne : DCB")


@login_required
def exporter_reception(request):
    entite = _entite_utilisateur(request.user)
    qs = Message.objects.filter(entite_destinataire=entite).select_related("entite_expeditrice", "expediteur")
    return _exporter_messages(qs, "De", "entite_expeditrice", "messages_recus")


@login_required
def exporter_envoi(request):
    entite = _entite_utilisateur(request.user)
    qs = Message.objects.filter(entite_expeditrice=entite).select_related("entite_destinataire", "expediteur")
    return _exporter_messages(qs, "Vers", "entite_destinataire", "messages_envoyes")


@login_required
def lire_message(request, message_id):
    entite = _entite_utilisateur(request.user)
    message = get_object_or_404(Message, pk=message_id, entite_destinataire=entite)
    message.lu_par.add(request.user)
    return render(request, "messagerie/lire_message.html", {"message": message})


@login_required
def nouveau_message(request):
    entite = _entite_utilisateur(request.user)
    if request.method == "POST":
        form = MessageForm(request.POST, entite_expeditrice=entite)
        if form.is_valid():
            message = form.save(commit=False)
            message.expediteur = request.user
            message.entite_expeditrice = entite
            message.save()
            django_messages.success(request, "Message envoyé.")
            return redirect("messagerie:boite_envoi")
    else:
        form = MessageForm(entite_expeditrice=entite)

    return render(
        request,
        "messagerie/nouveau_message.html",
        {"form": form, "entites_contactables": entites_contactables(entite)},
    )
