from django.db import models

from clients.models import Client
from core.models import DirectionRegionale


class Reclamation(models.Model):
    """Sollicitation HT importée depuis data/Etat des Sollicitations HT.xlsx.

    Toutes les colonnes source sont conservées. Les champs vides à 100 % dans
    l'export actuel (rapport_creation, partenaire, date_modification, motif_modification,
    statut_client, motif_retablissement) sont stockés pour anticiper les exports futurs
    qui pourraient les renseigner."""

    # --- Identification -----------------------------------------------------------
    numero_sollicitation = models.CharField(max_length=25, blank=True)
    direction_regionale = models.ForeignKey(
        DirectionRegionale, on_delete=models.PROTECT, related_name="reclamations"
    )
    agence = models.CharField(max_length=30, blank=True)
    auteur_creation = models.CharField(max_length=50, blank=True)

    # --- Canal / dates ------------------------------------------------------------
    date_creation = models.DateField(null=True, blank=True)
    canal = models.CharField(max_length=30, blank=True)
    statut = models.CharField(max_length=30, blank=True)
    priorite = models.CharField(max_length=20, blank=True)

    # --- Client (rattachement) ----------------------------------------------------
    # client : FK résolu depuis Identifiant/Ref Contrat via normalize_identifiant.
    # identifiant_contrat : valeur brute du fichier, conservée même quand la FK
    # est résolue (utile pour investiguer les 149 non-rattachés).
    client = models.ForeignKey(
        Client, on_delete=models.SET_NULL, null=True, blank=True, related_name="reclamations"
    )
    identifiant_contrat = models.CharField(max_length=20, blank=True)
    nom_client = models.CharField(max_length=100, blank=True)
    contact = models.CharField(max_length=30, blank=True)
    email = models.CharField(max_length=100, blank=True)
    branchement = models.CharField(max_length=20, blank=True, verbose_name="Branchement / Adresse technique")
    type_client = models.CharField(max_length=30, blank=True)
    segment_client = models.CharField(max_length=30, blank=True)
    sous_segment = models.CharField(max_length=50, blank=True)

    # --- Qualification de la sollicitation ----------------------------------------
    type_sollicitation = models.CharField(max_length=20, blank=True)
    # type_reclamation et typologie_reclamation ont la même valeur que type_sollicitation
    # dans l'export actuel ("Réclamation HT") mais sont conservés car présents dans la source.
    type_reclamation = models.CharField(max_length=20, blank=True)
    typologie_reclamation = models.CharField(max_length=20, blank=True)
    sous_typologie = models.CharField(max_length=20, blank=True)
    nature_reclamation = models.CharField(max_length=50, blank=True)
    rapport_creation = models.TextField(blank=True)
    partenaire = models.CharField(max_length=100, blank=True)
    nombre_relances = models.PositiveSmallIntegerField(null=True, blank=True)
    groupe_destinataire = models.CharField(max_length=120, blank=True)

    # --- Modifications / suivi ----------------------------------------------------
    date_modification = models.DateField(null=True, blank=True)
    motif_modification = models.CharField(max_length=255, blank=True)
    statut_client = models.CharField(max_length=50, blank=True)
    motif_retablissement = models.CharField(max_length=255, blank=True)

    # --- Traitement ---------------------------------------------------------------
    date_cloture = models.DateField(null=True, blank=True, verbose_name="Date de traitement")
    delai_traitement = models.PositiveIntegerField(null=True, blank=True, verbose_name="Délai de traitement (jours)")
    delai_contractuel_traitement = models.IntegerField(null=True, blank=True)
    ecart_traitement = models.IntegerField(null=True, blank=True, verbose_name="Écart traitement (réel - contractuel)")
    acteur_traitement = models.CharField(max_length=50, blank=True)
    rapport_traitement = models.TextField(blank=True)

    # --- Vérification -------------------------------------------------------------
    date_verification = models.DateField(null=True, blank=True)
    delai_verification = models.IntegerField(null=True, blank=True)
    delai_contractuel_verification = models.IntegerField(null=True, blank=True)
    ecart_verification = models.IntegerField(null=True, blank=True)
    auteur_cloture = models.CharField(max_length=50, blank=True)
    rapport_verification = models.TextField(blank=True)

    class Meta:
        # Nom de table figé à l'ancien nom (complaints_...) : l'app a été
        # renommée en reclamations, mais la table SQL existante (données
        # réelles) ne doit pas être recréée/renommée.
        db_table = "complaints_reclamation"
        verbose_name = "Réclamation HT"
        verbose_name_plural = "Réclamations HT"

    def __str__(self):
        return f"{self.numero_sollicitation or f'#{self.pk}'} : {self.nature_reclamation}"
