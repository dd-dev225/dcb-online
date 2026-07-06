from django.db import models

from clients.models import Abonnement, Client
from core.models import Periode


class Facture(models.Model):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="factures")
    abonnement = models.ForeignKey(
        Abonnement, on_delete=models.PROTECT, null=True, blank=True, related_name="factures"
    )
    periode = models.ForeignKey(Periode, on_delete=models.PROTECT, related_name="factures")
    numfact = models.CharField(max_length=30, blank=True)
    typfact = models.CharField(max_length=5)  # "E0" = facture normale (filtre qualité, pas segment)
    consommation_kwh = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    montant_facture_ttc = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    montant_tva_11 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    montant_tva_20 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    penalite_ttc = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        # Nom de table figé à l'ancien nom (billing_...) : l'app a été renommée
        # en facturation, mais la table SQL existante (données réelles) ne doit
        # pas être recréée/renommée.
        db_table = "billing_facture"
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        indexes = [models.Index(fields=["periode", "typfact"])]

    def __str__(self):
        return self.numfact or f"Facture #{self.pk}"


class Recouvrement(models.Model):
    facture = models.ForeignKey(
        Facture, on_delete=models.CASCADE, null=True, blank=True, related_name="recouvrements"
    )
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="recouvrements")
    periode = models.ForeignKey(Periode, on_delete=models.PROTECT, related_name="recouvrements")
    montant_facture = models.DecimalField(max_digits=14, decimal_places=2)
    montant_paye = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = "billing_recouvrement"
        verbose_name = "Recouvrement"
        verbose_name_plural = "Recouvrements"

    @property
    def impaye(self):
        return self.montant_facture - self.montant_paye

    @property
    def taux_recouvrement(self):
        if not self.montant_facture:
            return None
        return self.montant_paye / self.montant_facture

    def __str__(self):
        return f"{self.client.idabon} / {self.periode}"
