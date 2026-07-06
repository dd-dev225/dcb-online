from django.urls import path

from . import views

app_name = "reclamations"

urlpatterns = [
    path("", views.liste_reclamations, name="liste_reclamations"),
    path("exporter/", views.exporter_reclamations, name="exporter_reclamations"),
]
