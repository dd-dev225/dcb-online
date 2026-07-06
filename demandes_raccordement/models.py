from django.db import models

from clients.models import Client
from core.models import DirectionRegionale


class DemandeRaccordement(models.Model):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="demandes")
    direction_regionale = models.ForeignKey(
        DirectionRegionale, on_delete=models.PROTECT, related_name="demandes"
    )
    numdi = models.CharField(max_length=30)
    typdi = models.CharField(max_length=5)  # 02/03/04 = raccordement, 07 = résiliation
    date_initiation = models.DateField(null=True, blank=True)
    montant_demande = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    montant_net = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        # Nom de table figé à l'ancien nom (connection_requests_...) : l'app a
        # été renommée en demandes_raccordement, mais la table SQL existante
        # (données réelles) ne doit pas être recréée/renommée.
        db_table = "connection_requests_demanderaccordement"
        verbose_name = "Demande de raccordement"
        verbose_name_plural = "Demandes de raccordement"

    def __str__(self):
        return self.numdi


class SuiviDemande(models.Model):
    demande = models.OneToOneField(DemandeRaccordement, on_delete=models.CASCADE, related_name="suivi")
    etape = models.CharField(max_length=50, blank=True)
    date_paiement = models.DateField(null=True, blank=True)
    date_validation_devis = models.DateField(null=True, blank=True)
    date_execution = models.DateField(null=True, blank=True)
    duree_validation_devis = models.PositiveIntegerField(null=True, blank=True)
    duree_totale = models.PositiveIntegerField(null=True, blank=True)
    tranche_delai = models.CharField(max_length=30, blank=True)  # "<=5j", "7-14j", ">30j"...

    class Meta:
        db_table = "connection_requests_suividemande"
        verbose_name = "Suivi de demande"
        verbose_name_plural = "Suivis de demande"

    def __str__(self):
        return f"Suivi {self.demande.numdi}"
