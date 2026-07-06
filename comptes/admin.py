from django.contrib import admin

from .models import DemandeAcces, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "entite", "liste_dr")
    list_filter = ("role", "entite", "directions_regionales")
    autocomplete_fields = ("user",)
    filter_horizontal = ("directions_regionales",)

    def liste_dr(self, obj):
        return ", ".join(dr.code for dr in obj.directions_regionales.all())

    liste_dr.short_description = "DR"


@admin.register(DemandeAcces)
class DemandeAccesAdmin(admin.ModelAdmin):
    list_display = ("nom_complet", "email", "entite_souhaitee", "statut", "cree_le")
    list_filter = ("statut", "entite_souhaitee")
    list_editable = ("statut",)
    readonly_fields = ("cree_le",)
