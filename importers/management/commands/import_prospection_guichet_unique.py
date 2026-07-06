"""Importe l'activité de la Sous-Direction Guichet Unique CIE-SODECI (SDGU) depuis
informations clients/dcb/Guichet Unique/recensement_sdgu.xlsx, feuille "ACTIONS_IMM"
(346 immeubles recensés au 28/05). Réimport complet depuis la source d'origine,
pour (re)initialiser la base. Pour ajouter de nouveaux prospects au fil de l'eau
sans toucher à l'existant (y compris les corrections faites depuis l'app), utiliser
plutôt l'import web (/guichet-unique/prospects/importer/), qui partage le même
parsing (cf. prospection.services) mais n'efface jamais rien.

La feuille "ACTIONS_IMM" est un journal d'actions/visites, pas un registre à une
ligne par immeuble : un même immeuble (même nom_structure + zone_prospection)
réapparaît à plusieurs lignes à mesure que la prospection avance (DATE/STADE
D'AVANCEMENT diffèrent), dédoublonner par ce couple effacerait cet historique.
L'idempotence de CETTE commande se fait donc en repartant de zéro à chaque
exécution (supprime les lignes précédemment importées par elle avant de les
recréer), pas en faisant correspondre des lignes individuellement, faute
d'identifiant stable en source (colonne "N" n'est qu'un numéro de ligne).
"""

import pandas as pd
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from importers.utils import INFO_CLIENTS_DIR
from prospection.models import ImmeubleProspecte
from prospection.services import importer_depuis_dataframe

User = get_user_model()


class Command(BaseCommand):
    help = "Importe ImmeubleProspecte/DemarcheAdministrative depuis recensement_sdgu.xlsx (SDGU)."

    def handle(self, *args, **options):
        path = INFO_CLIENTS_DIR / "dcb" / "Guichet Unique" / "recensement_sdgu.xlsx"
        self.stdout.write(f"Lecture de {path}...")
        df = pd.read_excel(path, sheet_name="ACTIONS_IMM")

        cree_par = User.objects.filter(username="sousdir_guichet_unique").first()

        # Rafraîchissement complet : supprime uniquement ce que cette commande a
        # importé précédemment (cree_par=ce marqueur), pas les prospects saisis
        # depuis via le formulaire de collecte ou l'import web (cree_par=l'auteur réel).
        supprimees, _ = ImmeubleProspecte.objects.filter(cree_par=cree_par).delete()
        if supprimees:
            self.stdout.write(f"{supprimees} immeubles précédemment importés supprimés avant réimport.")

        nb_crees, nb_ignores_vides, nb_a_completer = importer_depuis_dataframe(df, cree_par)

        self.stdout.write(
            self.style.SUCCESS(
                f"ImmeubleProspecte : {nb_crees} créés ({nb_ignores_vides} lignes vides ignorées, "
                f"dont {nb_a_completer} importés avec un nom provisoire \"(à compléter)\" car le nom "
                f"de structure manquait mais d'autres données étaient présentes)."
            )
        )
