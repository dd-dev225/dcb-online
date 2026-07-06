"""Rattache chaque ImmeubleProspecte à sa Direction Régionale d'après sa zone de
prospection (cf. prospection.zones), pour la cartographie par DR demandée
(croisement avec les contraintes réseau du Support Technique). Ne touche jamais un
immeuble qui a déjà une direction_regionale (import terrain jugé plus fiable que
la correspondance texte). Idempotente : sans effet sur un immeuble déjà rattaché."""

from django.core.management.base import BaseCommand

from core.models import DirectionRegionale
from prospection.models import ImmeubleProspecte
from prospection.zones import dr_code_pour_zone


class Command(BaseCommand):
    help = "Rattache les immeubles prospectés à leur DR d'après leur zone de prospection (correspondance quartier -> DR)."

    def handle(self, *args, **options):
        dr_by_code = {dr.code: dr for dr in DirectionRegionale.objects.all()}
        a_maj = []
        non_matches = set()

        for immeuble in ImmeubleProspecte.objects.filter(direction_regionale__isnull=True).exclude(zone_prospection=""):
            code = dr_code_pour_zone(immeuble.zone_prospection)
            if code and code in dr_by_code:
                immeuble.direction_regionale = dr_by_code[code]
                a_maj.append(immeuble)
            elif not code:
                non_matches.add(immeuble.zone_prospection)

        ImmeubleProspecte.objects.bulk_update(a_maj, ["direction_regionale"])
        self.stdout.write(self.style.SUCCESS(f"{len(a_maj)} immeubles rattachés à leur DR."))
        if non_matches:
            self.stdout.write(self.style.WARNING(f"Zones sans correspondance ({len(non_matches)}) : {sorted(non_matches)}"))
