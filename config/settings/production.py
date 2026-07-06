"""
Settings de production : à activer seulement une fois le moteur du serveur SQL
interne confirmé (probablement SQL Server vu l'usage de Power BI, non confirmé
à ce stade). Aucun identifiant en dur ici : tout vient des variables d'environnement.

Bascule recommandée (cf. plan) : un second alias "saphir_readonly" pointe en lecture
sur les vues SQL existantes (V_Fait_Fact_HT_DCB, etc.) via des modèles managed=False ;
les modèles métier (Client, Facture...) et les dashboards ne changent pas.
"""

import environ

from .base import *  # noqa: F401,F403
from .base import BASE_DIR

env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

DEBUG = False

SECRET_KEY = env('DJANGO_SECRET_KEY')
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=[])

DATABASES = {
    'default': env.db('DATABASE_URL'),
}

# Alias optionnel pour la bascule "scénario A" (lecture directe des vues Saphir/BDSTAT).
if env('SAPHIR_READONLY_URL', default=''):
    DATABASES['saphir_readonly'] = env.db('SAPHIR_READONLY_URL')

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboards:home'
LOGOUT_REDIRECT_URL = 'login'
