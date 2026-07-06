from django.contrib import admin

from .models import DemarcheAdministrative, ImmeubleProspecte


class DemarcheAdministrativeInline(admin.TabularInline):
    model = DemarcheAdministrative
    extra = 0


@admin.register(ImmeubleProspecte)
class ImmeubleProspecteAdmin(admin.ModelAdmin):
    list_display = ("nom_structure", "zone_prospection", "nb_niveaux", "stade_avancement", "commercial")
    list_filter = ("zone_prospection", "stade_avancement", "type_cible")
    search_fields = ("nom_structure", "constructeur", "interlocuteur")
    inlines = [DemarcheAdministrativeInline]
