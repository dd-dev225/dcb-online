"""Scoping de ImmeubleProspecte et OperateurImmobilier, partagé entre
dashboards.data (graphiques) et prospection.views (liste/édition/export/import),
pour ne pas dupliquer la règle.

Ni ImmeubleProspecte ni OperateurImmobilier n'ont de champ "entite" : ces modèles
appartiennent entièrement à la Sous-Direction Guichet Unique (aucune autre entité
n'y a accès), donc pas de rollup hiérarchique entite__in à faire comme pour
comptes.scoping.get_scope_filter.

La répartition à l'intérieur de la SDGU suit la même logique de pilotage
différencié que la SDRCB, mais sur l'axe CCGC (Conseillère Client Grands
Comptes) plutôt que Direction Régionale (demande utilisateur explicite) :
- un CCGC individuel (portee_individuelle=True, profile.ccgc_supervisees =
  UNE valeur, ex. ["BOGA"]) : voit uniquement son propre portefeuille ;
- un "cadre" qui supervise un GROUPE de CCGC (portee_individuelle=False,
  ccgc_supervisees = PLUSIEURS valeurs, ex. cadre_guichet_unique supervise
  ["BOGA", "DIOMANDE"], cadre_charge_affaires_guichet supervise ["SYLLA"]) :
  voit le cumul des CCGC de son groupe ;
- Sous-Directeur / Direction (ccgc_supervisees vide) : voit tout le
  sous-arbre Guichet Unique, comme avant.

OperateurImmobilier.ccgc est un champ propre et à 100% renseigné : la
correspondance directe. ImmeubleProspecte n'a que ccgc_nom (texte brut du
fichier terrain), rattaché aux codes CCGC via prospection.ccgc.
"""

from django.db.models import Q

from core.models import Entite

from .ccgc import q_immeubles_pour_ccgc


def _ccgc_supervisees(user):
    profile = getattr(user, "profile", None)
    return list(profile.ccgc_supervisees) if profile and profile.ccgc_supervisees else []


def get_operateur_scope(user):
    """Scope OperateurImmobilier : direct sur le champ ccgc (propre, 100%
    renseigné)."""
    profile = getattr(user, "profile", None)
    if profile is None or profile.entite_id is None:
        return Q(pk__in=[])
    ccgc = _ccgc_supervisees(user)
    if ccgc:
        return Q(ccgc__in=ccgc)
    if profile.is_direction or profile.entite.code == Entite.GUICHET_UNIQUE:
        return Q()
    return Q(pk__in=[])


def get_immeuble_scope(user):
    """Scope ImmeubleProspecte : via ccgc_nom (texte brut), rattaché aux codes
    CCGC connus. Un immeuble dont le ccgc_nom ne correspond à aucune CCGC connue
    (ex. "M. DIBY") n'apparaît donc pour aucun compte individuel/cadre, seulement
    pour le Sous-Directeur/Direction (qui voient tout, y compris le non classé) —
    c'est un signal de données à qualifier, pas une perte silencieuse."""
    profile = getattr(user, "profile", None)
    if profile is None or profile.entite_id is None:
        return Q(pk__in=[])
    ccgc = _ccgc_supervisees(user)
    if ccgc:
        return q_immeubles_pour_ccgc(ccgc)
    if profile.is_direction or profile.entite.code == Entite.GUICHET_UNIQUE:
        return Q()
    return Q(pk__in=[])


def get_visite_scope(user):
    """Scope VisitePlanifiee : une visite n'a pas de CCGC propre, elle hérite de
    celle de sa cible (operateur.ccgc ou immeuble via ccgc_nom). On calcule donc
    les identifiants visibles sur chacune des deux cibles puis on filtre la visite
    sur l'une ou l'autre (toute visite a au moins une cible, cf. planning_visites,
    qui refuse la création sans operateur NI immeuble)."""
    from .models import ImmeubleProspecte, OperateurImmobilier

    op_ids = OperateurImmobilier.objects.filter(get_operateur_scope(user)).values_list("pk", flat=True)
    im_ids = ImmeubleProspecte.objects.filter(get_immeuble_scope(user)).values_list("pk", flat=True)
    return Q(operateur_id__in=op_ids) | Q(immeuble_id__in=im_ids)


def peut_administrer_base(user):
    """Réassignation de portefeuille, import en masse : réservé au Sous-Directeur
    Guichet Unique (voit toute la Sous-Direction, pas un portefeuille individuel
    ni un groupe de CCGC). PAS la Direction, qui consulte les indicateurs mais ne
    doit pas opérer la base de prospection elle-même (demande utilisateur
    explicite)."""
    profile = getattr(user, "profile", None)
    if profile is None or profile.entite_id is None or _ccgc_supervisees(user):
        return False
    return profile.entite.code == Entite.GUICHET_UNIQUE
