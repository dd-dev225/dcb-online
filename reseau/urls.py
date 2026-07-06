from django.urls import path

from . import views

app_name = "reseau"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("cartographie-immeubles/", views.cartographie_immeubles, name="cartographie_immeubles"),
    path("incidents/", views.liste_incidents, name="liste_incidents"),
    path("incidents/exporter/", views.exporter_incidents, name="exporter_incidents"),
    path("travaux/", views.liste_travaux, name="liste_travaux"),
    path("travaux/exporter/", views.exporter_travaux, name="exporter_travaux"),
    path("qualite-fourniture/", views.liste_fiches_qualite, name="liste_fiches_qualite"),
    path("qualite-fourniture/exporter/", views.exporter_fiches_qualite, name="exporter_fiches_qualite"),
    path("qualite-fourniture/lien/", views.generer_lien_qualite, name="generer_lien_qualite"),
    path("qualite-fourniture/<int:pk>/", views.detail_fiche_qualite, name="detail_fiche_qualite"),
    path("qualite-fourniture/repondre/<uuid:token>/", views.fiche_qualite_publique, name="fiche_qualite_publique"),
]
