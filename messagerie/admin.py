from django.contrib import admin

from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["entite_expeditrice", "entite_destinataire", "expediteur", "envoye_le"]
    list_filter = ["entite_expeditrice", "entite_destinataire"]
    readonly_fields = ["envoye_le"]
