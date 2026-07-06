from django.conf import settings
from django.db import models

from core.models import DirectionRegionale, Entite


class UserProfile(models.Model):
    """Lien User <-> nœud de l'arbre Entite (cf. core.Entite), point de départ du
    scoping hiérarchique des dashboards : un utilisateur voit toujours le cumul
    (rollup) de son nœud + de tous ses descendants (comptes.scoping.get_scope_filter).

    profile.entite = nœud racine "DCB"  -> vue agrégée totale (Directeur).
    profile.entite = un nœud quelconque -> restreint à ce nœud + son sous-arbre
        (Sous-Directeur : tout son périmètre ; Chef de Service : son service seul).
    profile.directions_regionales -> sous-filtre optionnel (peut en couvrir plusieurs,
        ex: une Chargée d'Affaires gérant DRAS+DRAN), utile pour un compte du Service
        Intérieur/Abidjan qui veut restreindre son portefeuille à ses DR.
    profile.portee_individuelle -> bascule le scoping sur le portefeuille personnel
        (Client.charge_affaires) plutôt que sur tout le service : c'est CE champ,
        pas le libellé du rôle, qui pilote ce comportement (cf. comptes.scoping).
        Volontairement découplé de `role` : `role` ne sert qu'à l'affichage et doit
        pouvoir refléter fidèlement n'importe quel titre source (ex: "Assistant
        Technique") sans jamais risquer de modifier le scoping par accident.
    profile.role -> étiquette d'affichage uniquement, fidèle aux titres exacts des
        newsletters DCB (Parlons Métiers), n'intervient jamais dans le scoping.
    """

    DIRECTEUR = "directeur"
    SOUS_DIRECTEUR = "sous_directeur"
    CHEF_SERVICE = "chef_service"
    # Le Service Prospection et Suivi de Projets de Raccordements (SDSTB, N°60) est
    # dirigé par un "Responsable", pas un "Chef de Service" (titre réservé, dans les
    # sources, au Service Installation Intérieure & Industrielle), ne pas généraliser
    # CHEF_SERVICE à un nœud Service dont la source ne documente pas ce titre précis.
    RESPONSABLE = "responsable"
    # Niveau "Cadre Chargée d'Affaires [Abidjan|Intérieur|Clients Stratégiques]"
    # (N56, SDRCB) et "Cadre Chargée d'Affaires" (N57, SDGU) : même titre racine,
    # la zone/portefeuille étant déjà portée par profile.entite, pas dupliquée ici.
    CADRE_CHARGE_AFFAIRES = "cadre_charge_affaires"
    CADRE_GUICHET_UNIQUE = "cadre_guichet_unique"
    CONSEILLER_GRANDS_COMPTES = "conseiller_grands_comptes"
    # Niveau le plus opérationnel de la SDRCB/Administration (N56) et de la SDSTB
    # (N60), précédemment oubliés dans l'app alors que documentés dans les sources.
    ASSISTANTE_APPUI_COMMERCIAL = "assistante_appui_commercial"
    ASSISTANT_TECHNIQUE = "assistant_technique"
    ROLE_CHOICES = [
        (DIRECTEUR, "Directeur"),
        (SOUS_DIRECTEUR, "Sous-Directeur"),
        (CHEF_SERVICE, "Chef de Service"),
        (RESPONSABLE, "Responsable"),
        (CADRE_CHARGE_AFFAIRES, "Cadre Chargée d'Affaires"),
        (CADRE_GUICHET_UNIQUE, "Cadre Guichet Unique"),
        (CONSEILLER_GRANDS_COMPTES, "Conseiller Client Grands Comptes"),
        (ASSISTANTE_APPUI_COMMERCIAL, "Assistante Appui Commercial"),
        (ASSISTANT_TECHNIQUE, "Assistant Technique"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    entite = models.ForeignKey(
        Entite, on_delete=models.PROTECT, null=True, blank=True, related_name="utilisateurs"
    )
    # Une Chargée d'Affaires gère en réalité plusieurs DR à la fois (ex: DRAS+DRAN
    # pour une même personne, cf. tableau DEX/DR/Chargée fourni par l'utilisateur),
    # ManyToMany plutôt qu'une seule DR par profil. Vide = pas de sous-filtre DR
    # (cas du Service Intérieur géré dans son ensemble, ou de tout profil dont le
    # périmètre se limite déjà à son entité).
    directions_regionales = models.ManyToManyField(
        DirectionRegionale, blank=True, related_name="utilisateurs"
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, blank=True)
    portee_individuelle = models.BooleanField(default=False)

    # Pendant de directions_regionales pour la Sous-Direction Guichet Unique : la
    # répartition y suit la même logique que la SDRCB (un "cadre" supervise un
    # GROUPE de CCGC, un CCGC individuel gère son propre portefeuille), mais la
    # granularité est la CCGC (3 valeurs fixes : BOGA/DIOMANDE/SYLLA, cf.
    # prospection.OperateurImmobilier.CCGC_CHOICES), pas la Direction Régionale.
    # Liste JSON plutôt qu'un M2M vers un modèle dédié : la CCGC n'a pas d'autre
    # existence dans l'app que ces 3 choix figés sur OperateurImmobilier, un
    # modèle séparé juste pour porter une M2M serait disproportionné. Vide = pas
    # de restriction par CCGC (cas Sous-Directeur/Direction, qui voient tout le
    # sous-arbre Guichet Unique via le rollup d'entité habituel).
    # - un CCGC individuel (portee_individuelle=True) : une seule valeur, ex. ["BOGA"] ;
    # - un "cadre" qui supervise un groupe (portee_individuelle=False) : plusieurs
    #   valeurs, ex. ["BOGA", "DIOMANDE"] (cadre_guichet_unique) ou ["SYLLA"]
    #   (cadre_charge_affaires_guichet).
    ccgc_supervisees = models.JSONField(default=list, blank=True)

    # Infos personnelles modifiables par l'utilisateur lui-même (menu "Mon profil").
    # Nom/prénom/email restent sur le modèle User natif de Django (déjà prévus pour
    # ça), seuls la civilité, la photo et le téléphone n'ont pas d'équivalent natif.
    M = "m"
    MME = "mme"
    MLLE = "mlle"
    CIVILITE_CHOICES = [(M, "M."), (MME, "Mme"), (MLLE, "Mlle")]

    civilite = models.CharField(max_length=10, choices=CIVILITE_CHOICES, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    photo = models.ImageField(upload_to="profil_photos/", null=True, blank=True)

    # Mémorise les derniers filtres/tri utilisés sur la liste financière (demande
    # utilisateur, cf. rapport "Fonctionnalités proposées" : éviter de ressaisir
    # les mêmes filtres à chaque visite). Clé libre par page plutôt qu'un champ par
    # filtre, pour pouvoir réutiliser ce même champ sur d'autres pages plus tard
    # sans nouvelle migration (cf. clients.views.liste_financiere).
    preferences_filtres = models.JSONField(default=dict, blank=True)

    @property
    def photo_url(self):
        return self.photo.url if self.photo else None

    @property
    def display_name(self):
        """Civilité + Nom si disponibles, sinon nom complet, sinon nom d'utilisateur,
        utilisé pour la formule de salutation (cf. comptes.context_processors)."""
        civilite_label = self.get_civilite_display() if self.civilite else ""
        if self.user.last_name:
            # Convention administrative française : NOM en majuscules, Prénom normal.
            return f"{civilite_label} {self.user.last_name.upper()}".strip()
        if self.user.get_full_name():
            return self.user.get_full_name()
        return self.user.username

    class Meta:
        # Nom de table figé à l'ancien nom (accounts_...) : l'app a été
        # renommée en comptes, mais la table SQL existante (données réelles)
        # ne doit pas être recréée/renommée.
        db_table = "accounts_userprofile"
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateur"

    def __str__(self):
        return self.user.username

    @property
    def is_direction(self):
        return bool(self.entite_id) and self.entite.niveau == Entite.DIRECTION


class DemandeAcces(models.Model):
    """Soumise depuis la page publique (pas de login requis), traitée ensuite via
    l'admin Django par la Direction : pas de création de compte immédiate, l'app
    n'a pas d'inscription libre (decision utilisateur explicite). Le compte
    lui-même reste créé à la main (UserProfile) une fois la demande validée, cette
    table ne fait que tracer qui a demandé quoi et où en est la validation."""

    EN_ATTENTE = "en_attente"
    VALIDEE = "validee"
    REFUSEE = "refusee"
    STATUT_CHOICES = [
        (EN_ATTENTE, "En attente"),
        (VALIDEE, "Validée"),
        (REFUSEE, "Refusée"),
    ]

    nom_complet = models.CharField(max_length=150)
    email = models.EmailField()
    entite_souhaitee = models.ForeignKey(
        Entite, on_delete=models.SET_NULL, null=True, blank=True, related_name="demandes_acces"
    )
    role_souhaite = models.CharField(max_length=150, blank=True)
    justification = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=EN_ATTENTE)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_demandeacces"
        verbose_name = "Demande d'accès"
        verbose_name_plural = "Demandes d'accès"
        ordering = ["-cree_le"]

    def __str__(self):
        return f"{self.nom_complet} ({self.get_statut_display()})"
