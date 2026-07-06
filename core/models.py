from django.conf import settings
from django.db import models


class DirectionRegionale(models.Model):
    """Référentiel DR vérifié sur data/V_Recouvr_HT.xlsx (couple DR/LIBDR)."""

    code = models.CharField(max_length=10, unique=True)  # "DRAS", "DRYOP"...
    code_numerique = models.PositiveSmallIntegerField(unique=True)  # 2, 3, 4, 21...
    libelle = models.CharField(max_length=100, blank=True)  # "DR Abidjan Sud"...
    zone = models.CharField(max_length=20, blank=True)  # "Abidjan" / "Intérieur"

    class Meta:
        verbose_name = "Direction régionale"
        verbose_name_plural = "Directions régionales"
        ordering = ["code_numerique"]

    def __str__(self):
        return self.code


class Entite(models.Model):
    """Nœud de l'organigramme réel de la DCB (Parlons Métiers N56/N57), modélisé en
    arbre : Direction (racine) -> Sous-Direction -> Service. Permet le "pilotage
    différencié" demandé : chaque nœud suit ses propres indicateurs, et un nœud
    parent voit automatiquement le cumul (rollup) de tout son sous-arbre
    (cf. comptes.scoping.get_scope_filter).

    Les noms des responsables ne sont pas stockés ici (cf. note de confidentialité
    du plan) : seuls le code, le libellé et la position dans l'arbre sont utiles.
    """

    DIRECTION = "direction"
    SOUS_DIRECTION = "sous_direction"
    SERVICE = "service"
    NIVEAU_CHOICES = [
        (DIRECTION, "Direction"),
        (SOUS_DIRECTION, "Sous-Direction"),
        (SERVICE, "Service"),
    ]

    # Racine
    DCB = "dcb"
    # Sous-Directions (enfants de DCB)
    SDRCB = "sdrcb"
    SUPPORT_TECHNIQUE = "support_technique"
    GUICHET_UNIQUE = "guichet_unique"
    # Services (enfants de SDRCB)
    ABIDJAN = "abidjan"
    INTERIEUR = "interieur"
    STRATEGIQUES_SENSIBLES = "strategiques_sensibles"
    ADMINISTRATION = "administration"
    # Services (enfants de SUPPORT_TECHNIQUE), cf. Parlons Métiers N°60
    PROSPECTION_RACCORDEMENT = "prospection_raccordement"
    INSTALLATION_INDUSTRIELLE = "installation_industrielle"

    code = models.SlugField(unique=True)
    libelle = models.CharField(max_length=100)
    niveau = models.CharField(max_length=20, choices=NIVEAU_CHOICES, default=SERVICE)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="enfants"
    )

    # Objectif et seuils propres à l'entité (demande utilisateur, cf. rapport
    # "Fonctionnalités proposées" : juger un chiffre par rapport à une cible plutôt
    # qu'un montant brut sans repère, et permettre des seuils de recouvrement
    # différents d'une entité à l'autre). Tous facultatifs : si vide, la Direction
    # n'a pas encore défini de cible/seuil propre à ce nœud, on retombe alors sur
    # les seuils globaux historiques (cf. dashboards.data.recouvrement_color).
    objectif_ca_mensuel_mds = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name="Objectif de CA mensuel (Mds FCFA)",
    )
    seuil_recouvrement_vert = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True,
        verbose_name="Seuil \"vert\" du taux de recouvrement (ex: 0.990)",
    )
    seuil_recouvrement_orange = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True,
        verbose_name="Seuil \"orange\" du taux de recouvrement (ex: 0.950)",
    )

    class Meta:
        verbose_name = "Entité"
        verbose_name_plural = "Entités"
        ordering = ["niveau", "libelle"]

    def __str__(self):
        return self.libelle

    def descendants_ids(self):
        """IDs de ce nœud + de tous ses descendants (rollup hiérarchique).
        Arbre à 3 niveaux maximum et quelques dizaines de nœuds : un parcours
        Python récursif est largement suffisant, pas besoin de MPTT/closure table."""
        ids = [self.pk]
        for enfant in self.enfants.all():
            ids.extend(enfant.descendants_ids())
        return ids

    def ancetres_ids(self):
        """IDs de ce nœud + de tous ses ancêtres (jusqu'à la racine DCB). Utilisé
        pour l'héritage des objectifs : un objectif posé sur un nœud parent (ex. la
        Direction) s'applique à tous ses descendants sauf s'ils en définissent un
        plus spécifique."""
        ids = [self.pk]
        parent = self.parent
        while parent is not None:
            ids.append(parent.pk)
            parent = parent.parent
        return ids


class Objectif(models.Model):
    """Cible fixée par le Directeur sur un indicateur, pour une entité donnée. Les
    entités concernées (l'entité elle-même et ses descendants, sauf objectif plus
    spécifique) le voient en regard de leur réalisé. Seul le Directeur en définit
    (cf. dashboards.views.gerer_objectifs)."""

    CA_MENSUEL = "ca_mensuel"
    TAUX_RECOUVREMENT = "taux_recouvrement"
    TAUX_COMPLETION = "taux_completion"
    TAUX_CONVERSION_CIE = "taux_conversion_cie"
    DELAI_RACCORDEMENT = "delai_raccordement"
    INDICATEUR_CHOICES = [
        (CA_MENSUEL, "CA mensuel (Mds FCFA)"),
        (TAUX_RECOUVREMENT, "Taux de recouvrement (%)"),
        (TAUX_COMPLETION, "Taux de complétion des fiches (%)"),
        (TAUX_CONVERSION_CIE, "Taux de conversion Guichet Unique → CIE (%)"),
        (DELAI_RACCORDEMENT, "Délai moyen de raccordement (jours)"),
    ]
    # Sens de comparaison : un délai est meilleur quand il est PLUS BAS.
    PLUS_BAS_EST_MIEUX = {DELAI_RACCORDEMENT}

    entite = models.ForeignKey("Entite", on_delete=models.CASCADE, related_name="objectifs")
    indicateur = models.CharField(max_length=30, choices=INDICATEUR_CHOICES)
    valeur_cible = models.DecimalField(max_digits=12, decimal_places=2)
    defini_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="objectifs_definis"
    )
    defini_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Objectif"
        verbose_name_plural = "Objectifs"
        unique_together = ("entite", "indicateur")
        ordering = ["entite__libelle", "indicateur"]

    def __str__(self):
        return f"{self.entite} · {self.get_indicateur_display()} = {self.valeur_cible}"


class Periode(models.Model):
    annee = models.PositiveSmallIntegerField()
    mois = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "Période"
        verbose_name_plural = "Périodes"
        unique_together = ("annee", "mois")
        ordering = ["annee", "mois"]

    def __str__(self):
        return f"{self.annee}-{self.mois:02d}"
