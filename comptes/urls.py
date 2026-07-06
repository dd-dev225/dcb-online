from django.urls import path

from . import views

app_name = "comptes"

urlpatterns = [
    path("profil/", views.profile, name="profile"),
    path("parametres/", views.parametres, name="parametres"),
    path("demande-acces/", views.demande_acces, name="demande_acces"),
]
