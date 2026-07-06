from django.contrib import admin

from .models import Facture, Recouvrement


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ("numfact", "client", "periode", "typfact", "montant_facture_ttc")
    list_filter = ("typfact", "periode")
    search_fields = ("numfact", "client__idabon")


@admin.register(Recouvrement)
class RecouvrementAdmin(admin.ModelAdmin):
    list_display = ("client", "periode", "montant_facture", "montant_paye")
    list_filter = ("periode",)
    search_fields = ("client__idabon",)
