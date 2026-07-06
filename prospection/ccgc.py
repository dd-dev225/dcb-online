"""Correspondance entre la colonne texte libre ImmeubleProspecte.ccgc_nom (valeur
brute du fichier terrain recensement_sdgu.xlsx) et le code CCGC canonique
(OperateurImmobilier.CCGC_CHOICES : BOGA/DIOMANDE/SYLLA), pour pouvoir scoper les
immeubles par CCGC exactement comme les opérateurs (dont le champ `ccgc` est déjà
propre et à 100% renseigné).

Seules 4 valeurs distinctes existent dans les données actuelles (vérifié) : les
fautes de frappe/variantes de saisie ("BOGGA" pour "BOGA") empêchent une
correspondance par simple inclusion de sous-chaîne, d'où une table figée plutôt
qu'une heuristique floue (même principe que prospection.zones pour les DR)."""

CCGC_NOM_VERS_CODE = {
    "MME BOGGA": "BOGA",
    "MME BOGA": "BOGA",
    "MME DIOMANDE / N'DJESSAN": "DIOMANDE",
    "MME DIOMANDE": "DIOMANDE",
    "MME SYLLA": "SYLLA",
}


def ccgc_code_pour_nom(ccgc_nom):
    """Retourne le code CCGC (BOGA/DIOMANDE/SYLLA) correspondant à la valeur brute
    ccgc_nom, ou None si aucune correspondance connue (ex. "M. DIBY", qui ne
    correspond à aucune des 3 CCGC identifiées — laissé non classé plutôt que
    forcé sur une hypothèse non vérifiée)."""
    if not ccgc_nom:
        return None
    return CCGC_NOM_VERS_CODE.get(ccgc_nom.strip().upper())


def q_immeubles_pour_ccgc(codes):
    """Q() filtrant ImmeubleProspecte sur les CCGC données, via ccgc_nom (texte
    brut, casse variable dans les données réelles : "Mme BOGGA" en base contre
    "MME BOGGA" en clé de CCGC_NOM_VERS_CODE) : on combine un iexact par variante
    connue plutôt qu'un simple __in, qui échouerait silencieusement sur la casse.
    Retourne Q(pk__in=[]) (rien) si codes est vide ou si aucune variante connue ne
    correspond, jamais un Q() vide qui laisserait tout passer par erreur."""
    from django.db.models import Q

    codes = set(codes)
    variantes = [nom_brut for nom_brut, code in CCGC_NOM_VERS_CODE.items() if code in codes]
    if not variantes:
        return Q(pk__in=[])
    q = Q()
    for variante in variantes:
        q |= Q(ccgc_nom__iexact=variante)
    return q
