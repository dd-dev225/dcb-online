from django.contrib import admin

from .models import Abonnement, Client, HistoriqueFiche, Interlocuteur


class AbonnementInline(admin.TabularInline):
    model = Abonnement
    extra = 0


class InterlocuteurInline(admin.TabularInline):
    model = Interlocuteur
    extra = 0


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("idabon", "nom_prenoms", "entite", "direction_regionale", "est_strategique", "strategique_en_attente", "charge_affaires")
    list_filter = ("entite", "direction_regionale", "est_strategique", "strategique_en_attente")
    search_fields = ("idabon", "nom_prenoms")
    autocomplete_fields = ("charge_affaires", "strategique_propose_par", "strategique_valide_par", "fiche_maj_par")
    inlines = [AbonnementInline, InterlocuteurInline]


@admin.register(HistoriqueFiche)
class HistoriqueFicheAdmin(admin.ModelAdmin):
    list_display = ("client", "modifie_par", "modifie_le", "champs_modifies")
    list_filter = ("modifie_le",)
    search_fields = ("client__idabon", "client__nom_prenoms")
    autocomplete_fields = ("client", "modifie_par")
