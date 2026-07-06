from django.conf import settings
from django.db import models


class Message(models.Model):
    """Message entre deux entités de l'organigramme DCB (cf. core.Entite), pas
    entre deux personnes : le destinataire est une entité entière, lue par tous
    ses membres (boîte partagée), pas une personne nommée. Demande utilisateur
    explicite : les échanges doivent respecter la hiérarchie (cf.
    messagerie.permissions.entites_contactables), pas être libres entre n'importe
    quelles entités.
    """

    expediteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="messages_envoyes"
    )
    entite_expeditrice = models.ForeignKey(
        "core.Entite", on_delete=models.CASCADE, related_name="messages_envoyes"
    )
    entite_destinataire = models.ForeignKey(
        "core.Entite", on_delete=models.CASCADE, related_name="messages_recus"
    )
    contenu = models.TextField()
    envoye_le = models.DateTimeField(auto_now_add=True)
    lu_par = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="messages_lus")

    class Meta:
        # Nom de table figé à l'ancien nom (messaging_...) : l'app a été
        # renommée en messagerie, mais la table SQL existante ne doit pas être
        # recréée/renommée.
        db_table = "messaging_message"
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ["-envoye_le"]

    def __str__(self):
        return f"{self.entite_expeditrice} -> {self.entite_destinataire} ({self.envoye_le:%d/%m/%Y})"
