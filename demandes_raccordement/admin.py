from django.contrib import admin

from .models import DemandeRaccordement, SuiviDemande


class SuiviDemandeInline(admin.StackedInline):
    model = SuiviDemande
    extra = 0


@admin.register(DemandeRaccordement)
class DemandeRaccordementAdmin(admin.ModelAdmin):
    list_display = ("numdi", "client", "direction_regionale", "typdi", "date_initiation")
    list_filter = ("direction_regionale", "typdi")
    search_fields = ("numdi", "client__idabon")
    inlines = [SuiviDemandeInline]
