from django.conf import settings
from django.db import models

from core.models import DirectionRegionale, Entite

from .nomenclature import BRANCHE_ACTIVITE_CHOICES, SECTEUR_ACTIVITE_CHOICES


class Client(models.Model):
    idabon = models.CharField(max_length=20, unique=True)
    nom_prenoms = models.CharField(max_length=255, blank=True)
    # Provenance du client (répartition du portefeuille rendue EXPLICITE, demande
    # utilisateur). La base MAÎTRESSE est "Client DCB.xlsx" (référentiel Saphir, quasi
    # tous les clients, statique) ; "V_Fait_Fact_HT_DCB.xlsx" est la base de
    # facturation (dynamique, clients facturés sur la période). Un client peut être
    # dans l'une, l'autre, ou les deux — ces deux drapeaux permettent de savoir sur
    # quelle base repose une répartition et de le montrer à l'écran.
    dans_client_dcb = models.BooleanField(default=False, verbose_name="Présent dans le référentiel Client DCB")
    dans_facturation = models.BooleanField(default=False, verbose_name="Présent dans la base de facturation")
    # Agence / exploitation de rattachement (colonne EXPLOITATION de Client DCB).
    agence = models.CharField(max_length=100, blank=True, verbose_name="Exploitation / Agence")
    localisation = models.CharField(max_length=255, blank=True)
    # Groupe électrogène du client (variables de la fiche Client DCB à compléter).
    groupe_electrogene_dispo = models.BooleanField(null=True, blank=True, verbose_name="Groupe électrogène disponible ?")
    groupe_electrogene_puissance = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Puissance groupe électrogène (kVA)"
    )
    # Liste fermée (nomenclature officielle), pas un texte libre. Valeurs réelles
    # extraites de data/V_Fait_Fact_HT_DCB.xlsx, cf. clients.nomenclature. Les
    # ~5 200 clients déjà importés utilisent déjà exactement ces valeurs.
    secteur_activite = models.CharField(max_length=100, blank=True, choices=SECTEUR_ACTIVITE_CHOICES)
    branche_activite = models.CharField(max_length=100, blank=True, choices=BRANCHE_ACTIVITE_CHOICES)
    direction_regionale = models.ForeignKey(
        DirectionRegionale, on_delete=models.PROTECT, null=True, blank=True, related_name="clients"
    )
    entite = models.ForeignKey(
        Entite, on_delete=models.PROTECT, null=True, blank=True, related_name="clients"
    )
    # Présence dans informations clients/dcb/liste_clients_strategiques.xlsx (TOP 100 + 25 clients sensibles)
    # OU validé depuis via le workflow de proposition (cf. champs strategique_* ci-dessous).
    # Seul ce booléen est utilisé dans le scoping/les dashboards, jamais le statut "en attente".
    est_strategique = models.BooleanField(default=False)
    # Workflow de proposition : un Chargé Stratégiques peut proposer un client existant
    # (déjà dans la base HT, identifié par idabon/référence raccordement) comme nouveau
    # client stratégique, la base de clients stratégiques grandit dans le temps, elle
    # n'est plus figée à l'import initial. Validation par un niveau supérieur (Chef de
    # Service Stratégiques / Sous-Directeur SDRCB / Direction) avant que est_strategique
    # ne passe à True, pour éviter qu'un Chargé ne s'attribue un client sans contrôle.
    strategique_en_attente = models.BooleanField(default=False)
    strategique_propose_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="propositions_strategiques",
    )
    strategique_propose_le = models.DateTimeField(null=True, blank=True)
    strategique_valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="validations_strategiques",
    )
    strategique_valide_le = models.DateTimeField(null=True, blank=True)

    # Niveau individuel (Chargé d'Affaires) du "pilotage différencié" : chaque Chargé
    # gère son propre portefeuille de clients (cf. comptes.scoping, portee_individuelle).
    charge_affaires = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="portefeuille_clients"
    )

    # --- Fiche client enrichie (Chargés d'Affaires SDRCB) ---------------------------
    # Champs demandés par le Sous-Directeur SDRCB pour disposer d'une base centralisée,
    # normalisée et dynamique : une partie est déjà disponible via les exports HT
    # (puissance souscrite, référence raccordement -> cf. Abonnement.psabon/refraccord),
    # le reste se complète manuellement ou par import Excel au fil du travail des
    # Chargés d'Affaires sur leur portefeuille.
    a_contrat = models.BooleanField(null=True, blank=True, verbose_name="Contrat signé ?")
    contrat_document = models.FileField(
        upload_to="contrats_clients/", null=True, blank=True, verbose_name="Contrat (archivage numérique)"
    )
    contrat_reference_physique = models.CharField(
        max_length=100, blank=True, verbose_name="Référence d'archivage physique (si pas de numérique)"
    )
    fiche_maj_le = models.DateTimeField(null=True, blank=True)
    fiche_maj_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="fiches_completees"
    )

    # --- Contrôle par le Chef de Service (workflow chargé -> chef -> SDRCB) ----------
    # Un Chargé complète la fiche (fiche_maj_*), le Chef de Service la contrôle
    # (fiche_controlee_*), puis la SDRCB consulte le taux de complétion contrôlé et
    # exporte. Toute nouvelle modification par un Chargé remet fiche_controlee à False
    # (le contrôle précédent ne vaut plus pour les nouvelles données).
    fiche_controlee = models.BooleanField(default=False, verbose_name="Fiche contrôlée par le chef")
    fiche_controlee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="fiches_controlees"
    )
    fiche_controlee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ["idabon"]

    def __str__(self):
        return f"{self.idabon} - {self.nom_prenoms}".strip(" -")


class ClientStrategiqueNonRattache(models.Model):
    """Ligne de informations clients/dcb/liste_clients_strategiques.xlsx que l'import
    n'a pas pu rattacher sans ambiguïté à un Client existant. Trois cas distincts
    (cf. TYPE_CHOICES) :
    - IDENTIFIANT manquant dans le fichier source ;
    - IDENTIFIANT (même après normalisation, cf. importers.utils.normalize_identifiant)
      ne correspondant à aucun Client.idabon connu (faute de frappe, client jamais
      facturé sur la période couverte par l'export...) ;
    - IDENTIFIANT correspondant bien à un Client connu, mais ce Client porte déjà une
      AUTRE raison sociale dans la base de facturation : deux lignes du fichier source
      partagent le même IDENTIFIANT avec des interlocuteurs/contacts totalement
      différents (ex. "JEBACO SARL" et "LES ACIERIES DE COTE D'IVOIRE" partagent
      l'IDENTIFIANT 03219510 alors que ce sont deux sociétés distinctes) — l'une des
      deux lignes a vraisemblablement été associée au mauvais IDABON par erreur de
      saisie. Ce n'est PAS un doublon inoffensif à ignorer (demande utilisateur
      explicite suite à vérification) : la ligne qui ne correspond pas au nom officiel
      du Client est conservée ici avec client_associe renseigné, pour investigation.

    Rejouée intégralement à chaque import (snapshot des anomalies courantes à la
    date du dernier import, pas un historique à cumuler), même principe que
    reseau.ZoneIndustrielle. Visible sur la plateforme (cf. clients.views.
    liste_strategiques_non_rattaches) pour que la Chargée du Service Stratégiques
    & Sensibles puisse investiguer elle-même (demande utilisateur explicite),
    plutôt que de rester une anomalie silencieuse visible seulement dans les logs
    d'import."""

    MANQUANT = "manquant"
    INTROUVABLE = "introuvable"
    AMBIGU = "ambigu"
    TYPE_CHOICES = [
        (MANQUANT, "Identifiant manquant dans le fichier source"),
        (INTROUVABLE, "Identifiant introuvable dans la base de facturation"),
        (AMBIGU, "Identifiant déjà attribué à un autre client dans le fichier source"),
    ]

    type_anomalie = models.CharField(max_length=20, choices=TYPE_CHOICES, default=INTROUVABLE)
    raison_sociale = models.CharField(max_length=255, blank=True)
    identifiant_brut = models.CharField(max_length=30, blank=True, verbose_name="Identifiant (fichier source)")
    direction = models.CharField(max_length=100, blank=True)
    exploitation = models.CharField(max_length=100, blank=True)
    interlocuteurs = models.CharField(max_length=255, blank=True)
    fonction = models.CharField(max_length=150, blank=True)
    contact = models.CharField(max_length=100, blank=True)
    email = models.CharField(max_length=255, blank=True)
    # Renseigné uniquement pour type_anomalie == AMBIGU : le Client qui possède
    # réellement cet IDABON dans la base de facturation, pour orienter l'investigation.
    client_associe = models.ForeignKey(
        Client, on_delete=models.SET_NULL, null=True, blank=True, related_name="conflits_strategiques"
    )
    importe_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Client stratégique non rattaché"
        verbose_name_plural = "Clients stratégiques non rattachés"
        ordering = ["raison_sociale"]

    def __str__(self):
        return f"{self.raison_sociale} ({self.identifiant_brut or 'identifiant manquant'})"


class Abonnement(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="abonnements")
    refraccord = models.CharField(max_length=30, blank=True)
    typabon = models.CharField(max_length=10, blank=True)
    posabon = models.CharField(max_length=5, blank=True)  # "02" = actif
    psabon = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tranche_puissance = models.CharField(max_length=30, blank=True)
    typcomptage = models.CharField(max_length=20, blank=True)
    codtarif = models.CharField(max_length=10, blank=True)
    # Infos techniques demandées dans la fiche client enrichie, absentes des exports
    # HT actuels (data/), donc toujours saisies manuellement/par import pour l'instant.
    depart = models.CharField(max_length=50, blank=True, verbose_name="Départ HT")
    poste = models.CharField(max_length=100, blank=True, verbose_name="Poste source HT/MT")
    # Variables issues de la fiche Client DCB (référentiel Saphir).
    numero_poste_client = models.CharField(max_length=50, blank=True, verbose_name="N° poste client")
    date_abonnement = models.DateField(null=True, blank=True, verbose_name="Date d'abonnement")

    class Meta:
        verbose_name = "Abonnement"
        verbose_name_plural = "Abonnements"

    def __str__(self):
        return f"{self.client.idabon} / {self.refraccord or self.pk}"


class Interlocuteur(models.Model):
    """Contact rattaché à un client, plusieurs par client et par rôle (un client peut
    avoir 2 interlocuteurs commerciaux, par exemple), demandé explicitement par les
    Chargés d'Affaires plutôt qu'un seul contact figé par type."""

    REPRESENTANT_LEGAL = "representant_legal"
    TECHNIQUE = "technique"
    COMMERCIAL = "commercial"
    ROLE_CHOICES = [
        (REPRESENTANT_LEGAL, "Représentant légal"),
        (TECHNIQUE, "Interlocuteur technique (incident réseau)"),
        (COMMERCIAL, "Interlocuteur commercial / facturation"),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="interlocuteurs")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    nom = models.CharField(max_length=255)
    fonction = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    telephone = models.CharField(max_length=30, blank=True)

    class Meta:
        verbose_name = "Interlocuteur client"
        verbose_name_plural = "Interlocuteurs client"
        ordering = ["client", "role"]

    def __str__(self):
        return f"{self.nom} ({self.get_role_display()}), {self.client.idabon}"


class HistoriqueFiche(models.Model):
    """Trace qui a modifié quoi sur une fiche client, et quand (demande
    utilisateur, cf. rapport "Fonctionnalités proposées" : utile en cas de
    désaccord sur "qui a changé quoi", surtout depuis que plusieurs rôles peuvent
    éditer une même fiche). Liste des champs modifiés en texte libre plutôt qu'un
    diff complet valeur par valeur (cf. ModelForm.changed_data dans la vue) : plus
    simple à constituer et largement suffisant pour répondre à "qui a touché ce
    champ", sans avoir à stocker/afficher d'anciennes valeurs."""

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="historique")
    modifie_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    modifie_le = models.DateTimeField(auto_now_add=True)
    champs_modifies = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Historique de fiche client"
        verbose_name_plural = "Historiques de fiche client"
        ordering = ["-modifie_le"]

    def __str__(self):
        return f"{self.client.idabon} : {self.champs_modifies} ({self.modifie_le:%d/%m/%Y})"
