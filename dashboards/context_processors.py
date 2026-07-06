"""Alimente la navbar (recherche, cloche notifications, enveloppe activité
récente) sur toutes les pages, séparé de comptes.context_processors.profile_context
parce que ce dernier reste volontairement sans dépendance vers les apps métier
(clients, facturation...) ; ici on en a besoin (alertes_navbar/activite_recente_navbar
interrogent Client), donc ce processeur vit dans dashboards, qui dépend déjà de
clients via dashboards.data."""

from clients.permissions import peut_voir_liste_financiere
from messagerie.models import Message

from . import data


def navbar_context(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    profile = getattr(user, "profile", None)
    entite = getattr(profile, "entite", None)
    messages_recus = (
        Message.objects.filter(entite_destinataire=entite).select_related("entite_expeditrice")
        if entite is not None
        else Message.objects.none()
    )

    alertes = data.alertes_navbar(user)
    activite_recente = data.activite_recente_navbar(user)

    return {
        "peut_chercher_client": peut_voir_liste_financiere(user),
        "alertes_navbar": alertes,
        "activite_recente_navbar": activite_recente,
        # Une seule cloche regroupe les deux (cf. base.html) : le badge compte donc
        # les deux listes ensemble, pas chacune séparément.
        "nb_alertes_total": len(alertes) + len(activite_recente),
        "nb_messages_non_lus": messages_recus.exclude(lu_par=user).count(),
        "messages_recents_navbar": messages_recus[:5],
    }
