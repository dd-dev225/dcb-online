"""Modèle de l'activité propre à la Sous-Direction Guichet Unique CIE-SODECI
(SDGU) : prospection des opérateurs immobiliers (SCI, promoteurs, immeubles en
construction) en amont de toute demande de raccordement formelle. Contrairement
au reste de la DCB, cette activité n'a pas de Client/Facture associé tant que le
projet n'a pas abouti à une demande, d'où un modèle dédié plutôt qu'un
rattachement (forcé) à clients/facturation.

Champs alignés sur deux sources réelles fournies par l'utilisateur (cf.
informations clients/dcb/Guichet Unique/) :
- recensement_sdgu.xlsx : suivi terrain actuel (346 immeubles au 28/05), feuille
  "ACTIONS_IMM", données hétérogènes, à nettoyer à l'import (cf. importers).
- Fiche de prospection_VF.pdf : trame officielle (cible SCI/Immeuble/Promoteur,
  démarches CIE et SODECI suivies en parallèle, caractéristiques du projet), pas
  encore utilisée sur le terrain mais sert de référence pour le formulaire de
  collecte numérique (cf. prospection.forms).
"""

from django.conf import settings
from django.db import models

from core.models import DirectionRegionale


class OperateurImmobilier(models.Model):
    """Promoteur / opérateur immobilier suivi par la SDGU.

    Distinct de Client (pas encore facturé, pas d'IDABON) et de ImmeubleProspecte
    (le promoteur est la société, l'immeuble est un projet qu'il porte). Un même
    opérateur peut avoir plusieurs projets en cours simultanément.

    Source : informations clients/dcb/Guichet Unique/Portefeuille Operateurs Imm/
      BASE OPERATEURS PAR COMMERCIALE.xlsx (3 feuilles : BOGA, DIOMANDE, SYLLA).
    Chaque feuille correspond au portefeuille d'une CCGC (Conseillère Client Grands
    Comptes). La répartition géographique des zones par CCGC est dans
    Repartition_Zones_CCGC.xlsx."""

    BOGA = "BOGA"
    DIOMANDE = "DIOMANDE"
    SYLLA = "SYLLA"
    CCGC_CHOICES = [
        (BOGA, "Mme BOGA"),
        (DIOMANDE, "Mme DIOMANDE"),
        (SYLLA, "Mme SYLLA"),
    ]

    # Segmentation qualitative de la base d'opérateurs (demande utilisateur : Top
    # Opérateurs, projets clés confirmés 2026, acteurs sensibles/stratégiques),
    # pour concentrer les efforts et le planning de visites sur les prioritaires.
    STANDARD = "standard"
    PRIORITAIRE = "prioritaire"
    TOP = "top"
    SEGMENT_CHOICES = [
        (STANDARD, "Standard"),
        (PRIORITAIRE, "Prioritaire"),
        (TOP, "Top opérateur"),
    ]

    nom = models.CharField(max_length=255)
    contact = models.CharField(max_length=150, blank=True)
    ccgc = models.CharField(max_length=20, choices=CCGC_CHOICES, blank=True,
                             verbose_name="CCGC responsable")
    zone = models.CharField(max_length=150, blank=True, verbose_name="Zone de prospection")
    segment = models.CharField(max_length=20, choices=SEGMENT_CHOICES, default=STANDARD)
    projet_2026 = models.BooleanField(default=False, verbose_name="Projet clé confirmé 2026")
    sensible = models.BooleanField(default=False, verbose_name="Opérateur sensible / stratégique")
    commercial = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="operateurs_geres",
        verbose_name="Compte utilisateur CCGC",
    )

    class Meta:
        verbose_name = "Opérateur immobilier"
        verbose_name_plural = "Opérateurs immobiliers"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class ImmeubleProspecte(models.Model):
    """Une structure prospectée (immeuble, SCI ou promoteur), pivot du suivi de la
    SDGU. Une ligne = un projet/bâtiment, indépendamment du nombre de démarches
    administratives qu'il génère (cf. DemarcheAdministrative)."""

    SCI = "sci"
    IMMEUBLE = "immeuble"
    PROMOTEUR = "promoteur"
    TYPE_CIBLE_CHOICES = [
        (SCI, "SCI"),
        (IMMEUBLE, "Immeuble"),
        (PROMOTEUR, "Promoteur immobilier"),
    ]

    VILLA = "villa"
    MIXTE = "mixte"
    TYPE_CONSTRUCTION_CHOICES = [
        (IMMEUBLE, "Immeuble"),
        (VILLA, "Villa"),
        (MIXTE, "Mixte"),
    ]

    TERRASSEMENT = "terrassement"
    GROS_OEUVRE = "gros_oeuvre"
    FINITION = "finition"
    STADE_CHOICES = [
        (TERRASSEMENT, "Terrassement"),
        (GROS_OEUVRE, "Gros œuvre"),
        (FINITION, "Finition"),
    ]

    # Seuil stratégique documenté (info.txt, échanges SDGU) : cible prioritaire =
    # immeubles R+5 et plus (+ R+4 ayant manifesté l'intention de construire un poste).
    SEUIL_NIVEAUX_PRIORITAIRE = 5

    date_visite = models.DateField(null=True, blank=True)
    nom_structure = models.CharField(max_length=255)
    constructeur = models.CharField(max_length=255, blank=True)
    type_cible = models.CharField(max_length=20, choices=TYPE_CIBLE_CHOICES, blank=True)

    interlocuteur = models.CharField(max_length=255, blank=True)
    fonction_interlocuteur = models.CharField(max_length=100, blank=True)
    contact = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)

    ABIDJAN = "abidjan"
    INTERIEUR = "interieur"
    DEX_CHOICES = [(ABIDJAN, "Abidjan"), (INTERIEUR, "Intérieur")]

    situation_geographique = models.CharField(max_length=255, blank=True)
    zone_prospection = models.CharField(max_length=100, blank=True)
    # Saisie manuelle en attendant une correspondance fiable quartier -> DR (les 14
    # DR/2 DEX existent déjà sur DirectionRegionale, mais aucune source du projet ne
    # relie un quartier d'Abidjan comme "Cocody" à un DR précis, cf. discussion
    # produit). dex permet de classer au moins Abidjan/Intérieur dès maintenant,
    # direction_regionale sera renseigné plus précisément quand la correspondance
    # sera fournie (script de bascule à écrire à ce moment, pas une déduction
    # automatique non fiable aujourd'hui).
    dex = models.CharField(max_length=20, choices=DEX_CHOICES, blank=True, verbose_name="DEX (Abidjan/Intérieur)")
    direction_regionale = models.ForeignKey(
        DirectionRegionale, on_delete=models.SET_NULL, null=True, blank=True, related_name="immeubles_prospectes"
    )

    type_construction = models.CharField(max_length=20, choices=TYPE_CONSTRUCTION_CHOICES, blank=True)
    nb_niveaux = models.PositiveSmallIntegerField(null=True, blank=True)  # parsé depuis "R+n"
    nb_appartements_bureaux = models.PositiveIntegerField(null=True, blank=True)
    details_construction = models.CharField(max_length=255, blank=True)

    stade_avancement = models.CharField(max_length=20, choices=STADE_CHOICES, blank=True)
    # Texte libre, PAS une vraie date : la source contient le plus souvent une
    # année brute ("2025") ou un mois textuel ("JANVIER", "DECEMBRE 2026", "FIN
    # OCTOBRE"), jamais une date précise jour/mois/année. Un DateField avait été
    # tenté puis abandonné : un import traitait ces valeurs comme des numéros de
    # série Excel (1899-12-30 + 2025 jours), produisant des dates absurdes comme
    # "1905-07-16". Même format que delai_livraison.
    date_debut_travaux = models.CharField(max_length=30, blank=True, default="")
    date_prev_fin_travaux = models.CharField(max_length=30, blank=True, default="")
    delai_livraison = models.CharField(max_length=20, blank=True)  # texte libre source ("2026/2027")

    poste_existant = models.BooleanField(null=True, blank=True)
    montant_bra_paye = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    observations = models.TextField(blank=True)

    # Opérateur immobilier (société promotrice), résolu depuis la colonne CONSTRUCTEUR
    # de recensement_sdgu via correspondance textuelle avec OperateurImmobilier.nom.
    # Null si le constructeur n'est pas dans la base des opérateurs connus.
    operateur = models.ForeignKey(
        OperateurImmobilier, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="immeubles",
    )
    # Valeur brute de la colonne "SDGU CIE/SODECI COMMERCIAL" dans la source
    # (ex: "Mme DIOMANDE / N'DJESSAN") — conservée pour ne rien perdre quand aucun
    # compte utilisateur ne correspond à ce nom dans le mapping de services.py.
    ccgc_nom = models.CharField(max_length=100, blank=True, verbose_name="CCGC (source brute)")

    commercial = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="prospects_geres"
    )
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="prospects_crees"
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Immeuble prospecté"
        verbose_name_plural = "Immeubles prospectés"
        ordering = ["-cree_le"]

    def __str__(self):
        return self.nom_structure

    @property
    def est_cible_prioritaire(self):
        """R+5 et plus (cf. SEUIL_NIVEAUX_PRIORITAIRE), sert à prioriser le
        portefeuille commercial, pas seulement à l'afficher."""
        return self.nb_niveaux is not None and self.nb_niveaux >= self.SEUIL_NIVEAUX_PRIORITAIRE


class DemarcheAdministrative(models.Model):
    """Démarche CIE ou SODECI initiée pour un immeuble prospecté. Les deux sont
    suivies en parallèle (cf. Fiche de prospection_VF.pdf, sections III.A/III.B),
    d'où une ligne par organisme plutôt que des colonnes dupliquées sur
    ImmeubleProspecte. Le passage à "demande initiée" est l'indicateur de réussite
    de la prospection mis en avant par la SDGU (info.txt, 2e échange)."""

    CIE = "cie"
    SODECI = "sodeci"
    ORGANISME_CHOICES = [(CIE, "CIE"), (SODECI, "SODECI")]

    RACCORDEMENT = "raccordement"
    BRANCHEMENT = "branchement"
    COMPTEUR_CHANTIER = "compteur_chantier"
    TYPE_DEMANDE_CHOICES = [
        (RACCORDEMENT, "Raccordement"),
        (BRANCHEMENT, "Branchement"),
        (COMPTEUR_CHANTIER, "Compteur chantier"),
    ]

    NON_INITIE = "non_initie"
    DEPOSE = "depose"
    EN_TRAITEMENT = "en_traitement"
    TRAITE = "traite"
    NON_CONFORME = "non_conforme"
    STATUT_CHOICES = [
        (NON_INITIE, "Non-initié"),
        (DEPOSE, "Déposé"),
        (EN_TRAITEMENT, "En traitement"),
        (TRAITE, "Traité"),
        (NON_CONFORME, "Non-conforme"),
    ]

    immeuble = models.ForeignKey(ImmeubleProspecte, on_delete=models.CASCADE, related_name="demarches")
    organisme = models.CharField(max_length=10, choices=ORGANISME_CHOICES)
    demande_initiee = models.BooleanField(default=False)
    type_demande = models.CharField(max_length=20, choices=TYPE_DEMANDE_CHOICES, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, blank=True)
    numero_demande = models.CharField(max_length=50, blank=True)
    details_non_conformite = models.TextField(blank=True)

    class Meta:
        verbose_name = "Démarche administrative"
        verbose_name_plural = "Démarches administratives"
        unique_together = ("immeuble", "organisme")

    def __str__(self):
        return f"{self.get_organisme_display()} : {self.immeuble.nom_structure}"


class VisitePlanifiee(models.Model):
    """Planning de visites trimestriel de la SDGU (demande utilisateur explicite :
    « ne plus subir les demandes, anticiper » — planification et visibilité à long
    terme sur le dernier semestre, découpé en 2 trimestres Juillet-Août-Septembre /
    Octobre-Novembre-Décembre). Une visite cible SOIT un opérateur immobilier SOIT
    un immeuble (jamais les deux, cf. clean()) : le planning couvre les deux mailles
    demandées, la relance mensuelle des Top opérateurs comme le suivi terrain d'un
    projet précis. Prévu ET réalisé sont suivis séparément pour mesurer la
    couverture (objectif : 100% des opérateurs à projet clé visités par trimestre,
    au moins un contact par mois)."""

    T3 = "T3"  # Juillet-Août-Septembre
    T4 = "T4"  # Octobre-Novembre-Décembre
    TRIMESTRE_CHOICES = [(T3, "T3 (Juil.-Août-Sept.)"), (T4, "T4 (Oct.-Nov.-Déc.)")]

    annee = models.PositiveSmallIntegerField()
    trimestre = models.CharField(max_length=2, choices=TRIMESTRE_CHOICES)
    operateur = models.ForeignKey(
        OperateurImmobilier, on_delete=models.CASCADE, null=True, blank=True, related_name="visites_planifiees"
    )
    immeuble = models.ForeignKey(
        ImmeubleProspecte, on_delete=models.CASCADE, null=True, blank=True, related_name="visites_planifiees"
    )
    # Localisation de la visite (demande utilisateur explicite : "il faut
    # préciser la DR et la commune/quartier"). Pré-remplie depuis la cible
    # (operateur.zone ou immeuble.direction_regionale/zone_prospection) à la
    # création, mais reste éditable : une visite peut viser une adresse précise
    # différente de la zone par défaut de l'opérateur/immeuble.
    direction_regionale = models.ForeignKey(
        DirectionRegionale, on_delete=models.SET_NULL, null=True, blank=True, related_name="visites_planifiees"
    )
    commune_quartier = models.CharField(max_length=150, blank=True)
    mois_prevu = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="Mois prévu (1-12)",
    )
    date_prevue = models.DateField(null=True, blank=True)
    date_realisee = models.DateField(null=True, blank=True)
    compte_rendu = models.TextField(blank=True)
    commercial = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="visites_planifiees"
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Visite planifiée"
        verbose_name_plural = "Visites planifiées"
        ordering = ["-annee", "-trimestre", "mois_prevu"]

    def __str__(self):
        cible = self.operateur.nom if self.operateur_id else (self.immeuble.nom_structure if self.immeuble_id else "?")
        return f"{cible} — {self.trimestre} {self.annee}"

    @property
    def cible_nom(self):
        if self.operateur_id:
            return self.operateur.nom
        if self.immeuble_id:
            return self.immeuble.nom_structure
        return "—"

    @property
    def est_realisee(self):
        return self.date_realisee is not None
