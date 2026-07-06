from django.apps import AppConfig


class DashboardsConfig(AppConfig):
    name = 'dashboards'

    def ready(self):
        # Importer les modules dash_apps déclenche leur enregistrement DjangoDash(...).
        from dashboards.dash_apps import (  # noqa: F401
            engagement_direction,
            engagement_entite,
            performance_direction,
            performance_entite,
            prospection_guichet_unique,
            reseau_support_technique,
        )
