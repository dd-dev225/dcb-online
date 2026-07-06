"""Affecte zone_industrielle sur IncidentReseau/TravauxReseau déjà importés.

Commande de correction ponctuelle : les deux importeurs (import_incidents_reseau,
import_travaux_reseau) classent déjà la zone à l'import, mais un bulk_update
ligne à ligne sur ~90 000 lignes existantes (cas d'une correction de la logique
de rapprochement après import initial, cf. reseau.zones) s'est avéré beaucoup
trop lent sous SQLite. Cette commande fait la même chose en une fraction du
temps : au lieu d'une requête UPDATE par ligne, une requête UPDATE par couple
(poste_site, nom_depart) DISTINCT (quelques centaines au total, contre des
dizaines de milliers de lignes), puisque toutes les lignes qui partagent le
même couple reçoivent la même zone."""

from django.core.management.base import BaseCommand

from reseau.models import IncidentReseau, TravauxReseau
from reseau.zones import construire_zone_par_depart, normaliser_site


class Command(BaseCommand):
    help = "Classe IncidentReseau/TravauxReseau par zone industrielle, par lots groupés (rapide)."

    def handle(self, *args, **options):
        zone_par_depart = construire_zone_par_depart()

        for label, modele in (("IncidentReseau", IncidentReseau), ("TravauxReseau", TravauxReseau)):
            # .order_by() vide est indispensable : sans lui, Django ajoute le tri par
            # défaut du modèle (date_heure_debut) à la requête, ce qui casse le
            # DISTINCT (il devient distinct sur (poste, départ, date...) au lieu de
            # (poste, départ) seul) et fait tourner update() des dizaines de fois sur
            # les mêmes lignes pour rien (idempotent donc sans incidence sur le
            # résultat, mais inutilement lent).
            paires = modele.objects.order_by().values_list("poste_site", "nom_depart").distinct()
            nb_lignes_maj, nb_paires_maj = 0, 0
            for poste, depart in paires:
                zone = zone_par_depart.get((normaliser_site(poste), normaliser_site(depart)))
                nb = modele.objects.filter(poste_site=poste, nom_depart=depart).update(zone_industrielle=zone)
                if zone is not None:
                    nb_lignes_maj += nb
                    nb_paires_maj += 1
            self.stdout.write(self.style.SUCCESS(f"{label} : {nb_lignes_maj} lignes classées sur {nb_paires_maj} couples (poste, départ) reconnus."))
