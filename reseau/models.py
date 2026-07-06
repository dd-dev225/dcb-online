import uuid

from django.conf import settings
from django.db import models

from core.models import DirectionRegionale


class ZoneIndustrielle(models.Model):
    """Référentiel des Zones Industrielles suivies de près par la Sous-Direction
    Support Technique Business (cf. informations clients/dcb/Support Technique/
    Info.txt : "Les 8 zones à regarder de près"). Ce sont elles que présente la
    Direction dans son reporting mensuel "Perturbation en Zone Industrielle"."""

    nom = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Zone industrielle"
        verbose_name_plural = "Zones industrielles"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class DepartZoneIndustrielle(models.Model):
    """Référentiel ZI_Departures_SS.xlsx : quel départ HTA alimente quelle Zone
    Industrielle, via quel Poste Source. Ni INCIBCC ni MANTBCC ne portent
    eux-mêmes l'information de zone : c'est cette table qui sert à classer un
    incident/des travaux par zone via leur NOM_EXPL (nom_depart)."""

    zone = models.ForeignKey(ZoneIndustrielle, on_delete=models.CASCADE, related_name="departs")
    poste_source = models.CharField(max_length=100, blank=True)
    nom_depart = models.CharField(max_length=150)

    class Meta:
        verbose_name = "Départ de zone industrielle"
        verbose_name_plural = "Départs de zone industrielle"
        unique_together = ("zone", "nom_depart")
        ordering = ["zone", "nom_depart"]

    def __str__(self):
        return f"{self.nom_depart} ({self.zone})"


class IncidentReseau(models.Model):
    """Incident (panne/perturbation) sur le réseau HTA/HTB, source : exports
    hebdomadaires/mensuels INCIBCC (informations clients/dcb/Support Technique/
    base pertubation/<année>/INCIBCC GLOBAL <année>.xlsx). Le schéma de cet
    export a varié dans le temps (les colonnes énergie/manœuvre du détail
    2023-2024 sont par exemple absentes du fichier 2025) : au-delà du socle
    commun, tout champ peut donc rester vide selon l'année de la source.

    numero_incident est la clé naturelle utilisée par l'import pour COMPLÉTER la
    base existante plutôt que la recharger en entier à chaque nouvel envoi
    (demande utilisateur explicite : ces fichiers arrivent chaque semaine/mois et
    doivent enrichir l'historique, pas le remplacer)."""

    numero_incident = models.CharField(max_length=30, unique=True)
    direction_regionale = models.ForeignKey(
        DirectionRegionale, on_delete=models.SET_NULL, null=True, blank=True, related_name="incidents_reseau"
    )
    poste_site = models.CharField(max_length=150, blank=True)
    nom_depart = models.CharField(max_length=150, blank=True)
    zone_industrielle = models.ForeignKey(
        ZoneIndustrielle, on_delete=models.SET_NULL, null=True, blank=True, related_name="incidents"
    )
    date_heure_debut = models.DateTimeField(null=True, blank=True)
    date_heure_fin = models.DateTimeField(null=True, blank=True)
    duree_minutes = models.PositiveIntegerField(null=True, blank=True)
    imputation = models.CharField(max_length=10, blank=True)
    puissance_coupee_kw = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    energie_non_distribuee_mwh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    nb_reclamations = models.PositiveIntegerField(null=True, blank=True)
    signalisation = models.CharField(max_length=100, blank=True)
    lieu_defaut = models.CharField(max_length=150, blank=True)
    description = models.CharField(max_length=255, blank=True)
    cause = models.CharField(max_length=150, blank=True)
    code_cause = models.CharField(max_length=20, blank=True)
    ouvrage_id = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = "Incident réseau"
        verbose_name_plural = "Incidents réseau"
        ordering = ["-date_heure_debut"]

    def __str__(self):
        return f"Incident {self.numero_incident} ({self.nom_depart})"


class TravauxReseau(models.Model):
    """Travaux/manœuvres programmés sur le réseau, source : MANTBCC GLOBAL
    <année>.xlsx (même dossier qu'IncidentReseau). code_rattachement est la clé
    naturelle, même logique d'import incrémental que IncidentReseau."""

    code_rattachement = models.CharField(max_length=30, unique=True)
    direction_regionale = models.ForeignKey(
        DirectionRegionale, on_delete=models.SET_NULL, null=True, blank=True, related_name="travaux_reseau"
    )
    poste_site = models.CharField(max_length=150, blank=True)
    nom_depart = models.CharField(max_length=150, blank=True)
    zone_industrielle = models.ForeignKey(
        ZoneIndustrielle, on_delete=models.SET_NULL, null=True, blank=True, related_name="travaux"
    )
    date_heure_debut = models.DateTimeField(null=True, blank=True)
    date_heure_fin = models.DateTimeField(null=True, blank=True)
    duree_minutes = models.PositiveIntegerField(null=True, blank=True)
    imputation = models.CharField(max_length=10, blank=True)
    puissance_coupee_kw = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    energie_non_distribuee_mwh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    nb_reclamations = models.PositiveIntegerField(null=True, blank=True)
    nature = models.CharField(max_length=150, blank=True)
    lieu_defaut = models.CharField(max_length=150, blank=True)
    type_manoeuvre = models.CharField(max_length=20, blank=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Travaux réseau"
        verbose_name_plural = "Travaux réseau"
        ordering = ["-date_heure_debut"]

    def __str__(self):
        return f"Travaux {self.code_rattachement} ({self.nom_depart})"


class LienFicheQualite(models.Model):
    """Lien unique et partageable envoyé à un client pour qu'il renseigne
    lui-même la fiche de collecte de qualité de fourniture, en remplacement de
    l'envoi d'un document à remplir à la main (cf. informations clients/dcb/
    Support Technique/Fiche Qualite de Fourniture/Fiche_Collecte_Reclamations_
    Client Business V2.pdf, déjà prototypée en formulaire KoboToolbox/XLSForm :
    Fiche_Reclamations_CIE_XLSForm V1.xlsx, structure reprise à l'identique ici).

    Le token UUID sert de clé d'accès PUBLIC (aucun compte requis côté client,
    conforme à l'usage réel : la fiche est envoyée par mail/lien à un
    correspondant technique externe). Un lien peut être pré-rattaché à un Client
    connu (pour enrichir automatiquement la fiche soumise) ou rester générique."""

    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    client = models.ForeignKey(
        "clients.Client", on_delete=models.SET_NULL, null=True, blank=True, related_name="liens_qualite_fourniture"
    )
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="liens_qualite_crees"
    )
    cree_le = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True, verbose_name="Lien actif (accepte encore des soumissions)")

    class Meta:
        verbose_name = "Lien fiche qualité de fourniture"
        verbose_name_plural = "Liens fiche qualité de fourniture"
        ordering = ["-cree_le"]

    def __str__(self):
        return f"Lien {self.token} ({self.client or 'générique'})"


class FicheQualiteFourniture(models.Model):
    """Fiche de collecte d'informations techniques liée à la qualité de la
    fourniture électrique, remplie par le client via un LienFicheQualite.
    Structure alignée section par section sur Fiche_Reclamations_CIE_XLSForm
    (même noms de choix, pour rester cohérent avec le prototype déjà validé) :
    2. Informations générales, 4. Éléments de constat, 6. Fréquence,
    7. Conditions, 8. Documents joints, 9. Observations. Les sections 3 et 5
    (événements et relevés de tension, 1 à 5 répétitions dans le formulaire
    source) sont normalisées en tables liées (EvenementQualite, ReleveTension)
    plutôt qu'en colonnes répétées evt_date_1..5, ten_U12_1..5."""

    METHODE_CHOICES = [
        ("observation_visuelle", "Observation à l'œil nu"),
        ("appareil_mesure", "Appareil de mesure"),
        ("enregistrement_auto", "Enregistrement automatique"),
        ("autre_constat", "Autre méthode de constat"),
    ]
    FREQUENCE_CHOICES = [
        ("ponctuel", "Ponctuel (une seule fois)"),
        ("quotidien", "Quotidien (tous les jours)"),
        ("hebdomadaire", "Hebdomadaire (chaque semaine)"),
        ("heures_precisees", "À des heures précises de la journée"),
        ("irregulier", "Irrégulier / aléatoire"),
        ("autre_freq", "Autre"),
    ]
    CONDITION_CHOICES = [
        ("temps_normal", "Atmosphère normale"),
        ("pluie", "Temps pluvieux"),
        ("orage_tonnerre", "Orage / tonnerre"),
        ("apres_travaux", "Après travaux sur le réseau"),
        ("forte_chaleur", "Forte chaleur"),
        ("autre_condition", "Autre"),
    ]
    DOCUMENT_CHOICES = [
        ("courbes", "Courbes de tension / données de mesure"),
        ("photos", "Photos ou captures d'écran"),
        ("rapport", "Rapport technique interne"),
        ("autre_doc", "Autre document"),
    ]

    NOUVEAU = "nouveau"
    EN_COURS = "en_cours"
    TRAITE = "traite"
    STATUT_CHOICES = [
        (NOUVEAU, "Nouveau"),
        (EN_COURS, "En cours d'analyse"),
        (TRAITE, "Traité"),
    ]

    lien = models.ForeignKey(
        LienFicheQualite, on_delete=models.SET_NULL, null=True, blank=True, related_name="fiches"
    )
    # Rattachement au Client connu, si le lien en portait un ou si le nom saisi
    # correspond à un client du portefeuille (résolution best-effort, jamais
    # bloquante : la fiche reste valable même sans correspondance, cf. relevant
    # du formulaire source qui ne demande qu'un texte libre "Nom de l'entreprise").
    client = models.ForeignKey(
        "clients.Client", on_delete=models.SET_NULL, null=True, blank=True, related_name="fiches_qualite_fourniture"
    )

    # --- 2. Informations générales du client ---
    nom_entreprise = models.CharField(max_length=255, verbose_name="Nom de l'entreprise")
    gps_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    gps_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    nom_correspondant = models.CharField(max_length=150, verbose_name="Correspondant technique")
    telephone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)

    # --- 4. Éléments de constat ---
    methode_constat = models.JSONField(default=list, blank=True)
    obs_visuelle = models.TextField(blank=True)
    obs_appareil = models.TextField(blank=True)
    obs_enregistrement = models.TextField(blank=True)
    obs_autre_constat = models.TextField(blank=True)

    # --- 6. Fréquence du phénomène ---
    frequence_phenomene = models.CharField(max_length=20, choices=FREQUENCE_CHOICES, blank=True)
    frequence_detail = models.CharField(max_length=255, blank=True)

    # --- 7. Conditions particulières ---
    conditions_constat = models.JSONField(default=list, blank=True)
    conditions_detail = models.CharField(max_length=255, blank=True)

    # --- 8. Documents joints ---
    documents_joints = models.JSONField(default=list, blank=True)
    photo_jointe = models.ImageField(upload_to="qualite_fourniture/photos/", null=True, blank=True)
    rapport_joint = models.FileField(upload_to="qualite_fourniture/rapports/", null=True, blank=True)
    documents_observations = models.TextField(blank=True)

    # --- 9. Observations finales ---
    observations_finales = models.TextField(blank=True)

    # --- Suivi/consolidation par le Support Technique (pas dans le formulaire
    # client d'origine, ajouté pour que la fiche soit exploitable en base plutôt
    # que juste "reçue") ---
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=NOUVEAU)
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fiches_qualite_traitees",
    )
    traite_le = models.DateTimeField(null=True, blank=True)
    note_traitement = models.TextField(blank=True)

    soumis_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fiche qualité de fourniture"
        verbose_name_plural = "Fiches qualité de fourniture"
        ordering = ["-soumis_le"]

    def __str__(self):
        return f"{self.nom_entreprise} du {self.soumis_le:%d/%m/%Y}"

    @property
    def methode_constat_libelles(self):
        libelles = dict(self.METHODE_CHOICES)
        return [libelles.get(code, code) for code in self.methode_constat]

    @property
    def conditions_constat_libelles(self):
        libelles = dict(self.CONDITION_CHOICES)
        return [libelles.get(code, code) for code in self.conditions_constat]

    @property
    def documents_joints_libelles(self):
        libelles = dict(self.DOCUMENT_CHOICES)
        return [libelles.get(code, code) for code in self.documents_joints]


class EvenementQualite(models.Model):
    """Un événement (coupure, variation de tension...) déclaré dans une fiche
    qualité de fourniture, section 3 du formulaire source, 1 à 5 événements par
    fiche, normalisée ici en table liée plutôt qu'en colonnes répétées
    evt_date_1..evt_date_5."""

    PHENOMENE_CHOICES = [
        ("coupure_intempestive", "Coupure intempestive"),
        ("microcoupure", "Microcoupure"),
        ("variation_tension", "Variation de tension"),
        ("inversion_phase", "Inversion de phase"),
        ("autre", "Autre"),
    ]

    fiche = models.ForeignKey(FicheQualiteFourniture, on_delete=models.CASCADE, related_name="evenements")
    date = models.DateField()
    heure_debut = models.TimeField(null=True, blank=True)
    heure_fin = models.TimeField(null=True, blank=True, verbose_name="Heure de fin (laisser vide si inconnue)")
    phenomenes = models.JSONField(default=list, blank=True)
    autre_description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Événement (fiche qualité)"
        verbose_name_plural = "Événements (fiche qualité)"
        ordering = ["date", "heure_debut"]

    def __str__(self):
        return f"{self.date} {self.heure_debut or ''}".strip()

    @property
    def phenomenes_libelles(self):
        libelles = dict(self.PHENOMENE_CHOICES)
        return [libelles.get(code, code) for code in self.phenomenes]


class ReleveTension(models.Model):
    """Un relevé de tension (0 à 5 par fiche, section 5 du formulaire source) :
    tensions composées U12/U23/U31 entre phases et tensions simples V1/V2/V3."""

    fiche = models.ForeignKey(FicheQualiteFourniture, on_delete=models.CASCADE, related_name="releves_tension")
    date = models.DateField(null=True, blank=True)
    heure = models.TimeField(null=True, blank=True)
    u12 = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True, verbose_name="U12 (V)")
    u23 = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True, verbose_name="U23 (V)")
    u31 = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True, verbose_name="U31 (V)")
    v1 = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True, verbose_name="V1 (V)")
    v2 = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True, verbose_name="V2 (V)")
    v3 = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True, verbose_name="V3 (V)")
    appareil_mesure = models.CharField(max_length=150, blank=True)

    class Meta:
        verbose_name = "Relevé de tension"
        verbose_name_plural = "Relevés de tension"
        ordering = ["date", "heure"]

    def __str__(self):
        return f"Relevé {self.date or '?'}"

    def __str__(self):
        return f"Travaux {self.code_rattachement} ({self.nom_depart})"
