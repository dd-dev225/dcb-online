from django.urls import path

from . import views

app_name = "clients"

urlpatterns = [
    path("portefeuille/", views.liste_portefeuille, name="liste_portefeuille"),
    # Chemins littéraux AVANT <str:idabon>/, sinon ce dernier les capture comme un IDABON.
    path("portefeuille/proposer-strategique/", views.proposer_client_strategique, name="proposer_client_strategique"),
    path("portefeuille/valider-strategiques/", views.valider_clients_strategiques, name="valider_clients_strategiques"),
    path(
        "portefeuille/strategiques-non-rattaches/",
        views.liste_strategiques_non_rattaches,
        name="liste_strategiques_non_rattaches",
    ),
    path("portefeuille/exporter/", views.exporter_portefeuille, name="exporter_portefeuille"),
    path("portefeuille/importer/", views.importer_fiches_clients, name="importer_fiches_clients"),
    path("portefeuille/importer-saphir/", views.importer_clients_dcb, name="importer_clients_dcb"),
    path("controle/", views.controle_fiches, name="controle_fiches"),
    path("financiere/", views.liste_financiere, name="liste_financiere"),
    path("financiere/exporter/", views.exporter_financiere, name="exporter_financiere"),
    path("consulter/<str:idabon>/", views.detail_client, name="detail_client"),
    path("portefeuille/<str:idabon>/", views.fiche_client, name="fiche_client"),
]
