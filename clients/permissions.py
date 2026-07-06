"""Contrôle d'accès pour la fiche client enrichie / le portefeuille des Chargés
d'Affaires, distinct de comptes.scoping (qui filtre les DONNÉES visibles) : ici on
décide qui a le droit d'AGIR (proposer/éditer/valider), pas seulement de regarder.

Principe repris de prospection (Guichet Unique) : la Direction garde la vue
d'ensemble (cf. la carte de synthèse SDRCB sur la page d'accueil) mais n'opère pas
elle-même cette activité : gérer un portefeuille client est le métier de la SDRCB,
pas de la Direction."""

from core.models import Entite


def _sdrcb_descendant_ids():
    return Entite.objects.get(code=Entite.SDRCB).descendants_ids()


def est_dans_sdrcb(user):
    """Vrai pour tout profil rattaché à la SDRCB ou un de ses Services (Abidjan,
    Intérieur, Stratégiques & Sensibles, Administration), pas pour la Direction
    (dont l'entité est le nœud racine "dcb", parent de SDRCB, pas un descendant)."""
    profile = getattr(user, "profile", None)
    if profile is None or profile.entite_id is None:
        return False
    return profile.entite_id in _sdrcb_descendant_ids()


def peut_valider_strategique(user):
    """Validation d'une proposition de client stratégique : réservé à qui voit tout
    un service ou plus (Chef de Service Stratégiques, Sous-Directeur SDRCB), pas à
    un Chargé d'Affaires individuel, qui ne doit pas pouvoir valider sa propre
    proposition (cf. portee_individuelle)."""
    profile = getattr(user, "profile", None)
    if profile is None or profile.entite_id is None or profile.portee_individuelle:
        return False
    return est_dans_sdrcb(user)


def peut_proposer_strategique(user):
    """Proposer un client comme stratégique : réservé au(x) Chargé(e)(s) du Service
    Stratégiques & Sensibles, PAS à n'importe quel Chargé d'Affaires SDRCB
    (Abidjan/Intérieur compris). Ce rôle est spécifique à ce service (demande
    utilisateur explicite), pas une capacité générale de la fiche client enrichie."""
    profile = getattr(user, "profile", None)
    if profile is None or profile.entite_id is None:
        return False
    return profile.entite_id in Entite.objects.get(code=Entite.STRATEGIQUES_SENSIBLES).descendants_ids()


def peut_controler_fiches(user):
    """Contrôle des fiches complétées par les Chargés d'Affaires : réservé à qui
    supervise tout un service ou plus (Chef de Service, Sous-Directeur SDRCB), pas
    à un Chargé individuel (qui ne contrôle pas son propre travail)."""
    profile = getattr(user, "profile", None)
    if profile is None or profile.entite_id is None or profile.portee_individuelle:
        return False
    return est_dans_sdrcb(user)


def peut_voir_liste_financiere(user):
    """Liste complète "Top clients par CA"/"Clients critiques" : simple lecture,
    donc ouverte à la SDRCB ET à la Direction (qui voit déjà ces mêmes tableaux,
    en aperçu de 10 lignes, dans Performance/Engagement-Direction), contrairement
    aux actions d'écriture du portefeuille, réservées à la SDRCB seule."""
    profile = getattr(user, "profile", None)
    if profile is None or profile.entite_id is None:
        return False
    return profile.is_direction or est_dans_sdrcb(user)
