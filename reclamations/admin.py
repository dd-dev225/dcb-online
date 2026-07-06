from django.contrib import admin

from .models import Reclamation


@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "direction_regionale", "type_reclamation", "statut", "date_creation")
    list_filter = ("direction_regionale", "type_reclamation", "statut")
    search_fields = ("client__idabon",)
