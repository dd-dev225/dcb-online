from django.urls import path

from . import views

app_name = "messagerie"

urlpatterns = [
    path("messages/", views.boite_reception, name="boite_reception"),
    path("messages/envoyes/", views.boite_envoi, name="boite_envoi"),
    path("messages/nouveau/", views.nouveau_message, name="nouveau_message"),
    # Chemins littéraux AVANT <int:message_id>/, sinon ce dernier les capturerait.
    path("messages/exporter/", views.exporter_reception, name="exporter_reception"),
    path("messages/envoyes/exporter/", views.exporter_envoi, name="exporter_envoi"),
    path("messages/<int:message_id>/", views.lire_message, name="lire_message"),
]
