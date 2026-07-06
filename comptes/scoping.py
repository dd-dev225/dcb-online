"""Point unique de contrôle d'accès aux données par profil utilisateur.

Tout queryset affiché dans un dashboard doit être filtré via get_scope_filter(user)
avant d'être passé à un callback Dash. Centraliser ici permet de tester la logique
de scoping indépendamment des vues/dash apps.

Le scoping suit la hiérarchie réelle de la DCB (core.Entite, arbre Direction >
Sous-Direction > Service) : un utilisateur voit le cumul (rollup) de son nœud et de
tous ses descendants. Un Directeur (nœud racine) voit donc tout sans restriction
explicite, un Sous-Directeur voit tous les services sous sa Sous-Direction, un Chef
de Service ne voit que son propre service, sans qu'aucun code de vue n'ait besoin
de distinguer ces trois cas, ce qui correspond directement au "pilotage différencié"
demandé : chaque niveau suit ses indicateurs, les niveaux supérieurs voient l'agrégat.
"""

from django.db.models import Q


def get_scope_filter(
    user, *, entite_field="entite", dr_field="direction_regionale", charge_affaires_field=None
):
    """Retourne un Q() à appliquer à un queryset scopé par entité (+ sous-arbre) et DR.

    Principe unifié : chaque utilisateur voit l'entité de son profil ET tous ses
    descendants (rollup), éventuellement restreint à ses Directions Régionales.

    - Pas de profil ou pas d'entité assignée : Q(pk__in=[]) pour ne rien montrer
      plutôt que de fuiter des données par défaut.
    - Entité (rollup) : un Directeur (nœud racine "dcb") voit tout ; un Sous-Directeur
      tous ses services ; un Chef de Service son seul service, sans cas particulier.
    - DR (directions_regionales, ManyToMany) : sous-filtre. C'est LUI qui réalise le
      "pilotage différencié" au niveau du Chargé d'Affaires : chaque Chargé
      (portee_individuelle=True) se voit affecter ses DR, et son portefeuille est
      alors l'ensemble des clients de son entité situés dans CES DR (son segment) —
      et non plus un rattachement client par client via charge_affaires (qui n'était
      quasiment jamais renseigné, d'où un portefeuille vide). Un Chef de Service ou
      un Chargé sans DR affectée voit tout son service (repli naturel).

    charge_affaires_field est conservé pour compatibilité de signature mais n'est
    plus utilisé : la répartition passe désormais par les DR.
    """
    if not user.is_authenticated:
        return Q(pk__in=[])

    profile = getattr(user, "profile", None)
    if profile is None or profile.entite_id is None:
        return Q(pk__in=[])

    scope = Q(**{f"{entite_field}__in": profile.entite.descendants_ids()})
    dr_ids = list(profile.directions_regionales.values_list("id", flat=True))
    if dr_ids:
        scope &= Q(**{f"{dr_field}__in": dr_ids})
    return scope
