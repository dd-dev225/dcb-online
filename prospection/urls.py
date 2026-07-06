from django.urls import path

from . import views

app_name = "prospection"

urlpatterns = [
    path("guichet-unique/operateurs/", views.liste_operateurs, name="liste_operateurs"),
    path("guichet-unique/planning/", views.planning_visites, name="planning_visites"),
    path("guichet-unique/planning/exporter/", views.exporter_planning, name="exporter_planning"),
    path("guichet-unique/calendrier/", views.calendrier_visites, name="calendrier_visites"),
    path("guichet-unique/prospects/", views.liste_prospects, name="liste_prospects"),
    path("guichet-unique/prospects/nouveau/", views.nouveau_prospect, name="nouveau_prospect"),
    path("guichet-unique/prospects/<int:pk>/", views.detail_prospect, name="detail_prospect"),
    path("guichet-unique/prospects/<int:pk>/modifier/", views.modifier_prospect, name="modifier_prospect"),
    path("guichet-unique/prospects/exporter/", views.export_prospects, name="export_prospects"),
    path("guichet-unique/prospects/importer/", views.importer_prospects, name="importer_prospects"),
]
