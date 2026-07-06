from django.contrib import admin

from .models import DirectionRegionale, Entite, Periode


@admin.register(DirectionRegionale)
class DirectionRegionaleAdmin(admin.ModelAdmin):
    list_display = ("code", "code_numerique", "libelle", "zone")
    search_fields = ("code", "libelle")


@admin.register(Entite)
class EntiteAdmin(admin.ModelAdmin):
    list_display = (
        "code", "libelle", "niveau", "parent",
        "objectif_ca_mensuel_mds", "seuil_recouvrement_vert", "seuil_recouvrement_orange",
    )
    list_editable = ("objectif_ca_mensuel_mds", "seuil_recouvrement_vert", "seuil_recouvrement_orange")
    list_filter = ("niveau",)


@admin.register(Periode)
class PeriodeAdmin(admin.ModelAdmin):
    list_display = ("annee", "mois")
    list_filter = ("annee",)
