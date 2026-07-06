from django.urls import path

from . import views

app_name = "dashboards"

urlpatterns = [
    path("", views.home, name="home"),
    path("performance/direction/", views.performance_direction, name="performance_direction"),
    path("performance/entite/", views.performance_entite, name="performance_entite"),
    path("engagement/direction/", views.engagement_direction, name="engagement_direction"),
    path("engagement/entite/", views.engagement_entite, name="engagement_entite"),
    path("guichet-unique/", views.prospection_guichet_unique, name="prospection_guichet_unique"),
    path("objectifs/", views.objectifs, name="objectifs"),
    path("objectifs/gerer/", views.gerer_objectifs, name="gerer_objectifs"),
]
