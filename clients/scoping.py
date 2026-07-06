"""Scope Client pour le portefeuille des Chargés d'Affaires, wrapper autour de
comptes.scoping pour ne pas répéter les noms de champs (entite/direction_regionale/
charge_affaires sont directement sur Client, pas de chemin imbriqué comme pour les
autres apps qui interrogent Facture/SuiviDemande/etc.)."""

from comptes.scoping import get_scope_filter


def get_client_scope(user):
    return get_scope_filter(
        user, entite_field="entite", dr_field="direction_regionale", charge_affaires_field="charge_affaires"
    )
