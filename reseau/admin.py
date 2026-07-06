from django.contrib import admin

from .models import DepartZoneIndustrielle, IncidentReseau, TravauxReseau, ZoneIndustrielle


class DepartZoneIndustrielleInline(admin.TabularInline):
    model = DepartZoneIndustrielle
    extra = 0


@admin.register(ZoneIndustrielle)
class ZoneIndustrielleAdmin(admin.ModelAdmin):
    list_display = ("nom",)
    inlines = [DepartZoneIndustrielleInline]


@admin.register(IncidentReseau)
class IncidentReseauAdmin(admin.ModelAdmin):
    list_display = (
        "numero_incident", "direction_regionale", "nom_depart", "zone_industrielle",
        "date_heure_debut", "duree_minutes", "cause",
    )
    list_filter = ("direction_regionale", "zone_industrielle")
    search_fields = ("numero_incident", "nom_depart", "poste_site")
    date_hierarchy = "date_heure_debut"


@admin.register(TravauxReseau)
class TravauxReseauAdmin(admin.ModelAdmin):
    list_display = (
        "code_rattachement", "direction_regionale", "nom_depart", "zone_industrielle",
        "date_heure_debut", "duree_minutes", "nature",
    )
    list_filter = ("direction_regionale", "zone_industrielle")
    search_fields = ("code_rattachement", "nom_depart", "poste_site")
    date_hierarchy = "date_heure_debut"
