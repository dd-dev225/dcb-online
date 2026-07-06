"""Dev settings: SQLite, DEBUG on. Source des données: imports depuis DCB ONLINE/data (cf. management commands de l'app importers)."""

from .base import *  # noqa: F401,F403
from .base import BASE_DIR

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# SQLite en dev : sans réglage, le journal est en mode "rollback" (un seul accès
# exclusif à la fois) et le busy_timeout est de 5 s. Or django-plotly-dash envoie
# plusieurs requêtes en parallèle (layout, dependencies, update-component) et chaque
# POST réécrit la session : pendant qu'une agrégation lourde (vue Direction, non
# mise en cache car périmètre global) tient la base en lecture, ces écritures
# dépassaient les 5 s -> "database is locked" et lenteur en cascade (cf. logs).
#   - journal_mode=WAL : lecteurs et un écrivain peuvent travailler simultanément.
#   - busy_timeout=20000 : on patiente 20 s pour obtenir le verrou avant d'échouer.
#   - transaction_mode=IMMEDIATE : la transaction prend le verrou d'écriture d'emblée
#     plutôt que de démarrer en lecteur puis tenter une montée en écrivain (cause
#     classique du "database is locked" sous SQLite).
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,
            'transaction_mode': 'IMMEDIATE',
            'init_command': (
                'PRAGMA journal_mode=WAL;'
                'PRAGMA synchronous=NORMAL;'
                'PRAGMA busy_timeout=20000;'
            ),
        },
    }
}

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboards:home'
LOGOUT_REDIRECT_URL = 'login'
