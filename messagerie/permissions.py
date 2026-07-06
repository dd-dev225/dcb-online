"""Qui peut écrire à qui : une entité ne peut contacter que sa hiérarchie directe
(ses ancêtres en remontant jusqu'à la racine, et son propre sous-arbre), pas une
branche latérale de l'organigramme. Décision utilisateur explicite : pas de
messagerie libre entre n'importe quelles entités."""

from core.models import Entite


def entites_contactables(entite):
    """Ancêtres (remonter jusqu'à la racine) + descendants (propre sous-arbre,
    sans l'entité elle-même) : c'est la définition même de "sa hiérarchie
    directe", pas besoin d'aller chercher les frères/sœurs d'une autre branche."""
    if entite is None:
        return Entite.objects.none()

    ids = set(entite.descendants_ids())
    ids.discard(entite.pk)

    courant = entite.parent
    while courant is not None:
        ids.add(courant.pk)
        courant = courant.parent

    return Entite.objects.filter(pk__in=ids)


def peut_contacter(entite_source, entite_cible):
    if entite_source is None or entite_cible is None or entite_source.pk == entite_cible.pk:
        return False
    return entites_contactables(entite_source).filter(pk=entite_cible.pk).exists()
