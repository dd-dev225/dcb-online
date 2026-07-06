"""Étape 1 du pipeline d'import (cf. plan, section "Pipeline d'import V1").

Peuple core.DirectionRegionale depuis le référentiel Dim_DR (table de référence
codée en dur dans Model_Dede.bim), vérifiée cohérente à 100% avec les couples
(DR, LIBDR, DEX) observés empiriquement dans data/V_Recouvr_HT.xlsx. DRCS = "DR
Centre Sud" confirmé par l'utilisateur (une image fournie à tort comme source
suggérait un temps "DR Centre Est", corrigé, ne pas réintroduire ce libellé).

Le périmètre DCB = segment "Business" est confirmé numériquement : le nombre de
clients facturés en 2026-01 dans data/V_Fait_Fact_HT_DCB.xlsx (filtré TYPFACT=E0)
est exactement 3667, identique au chiffre "Business" d'une table de segmentation
HT (Business/ADM et assimilés/Network, total 8162) fournie par l'utilisateur.

Peuple aussi core.Entite avec l'arbre hiérarchique complet de l'organigramme DCB
(Parlons Métiers N56/N57/N60) : Direction -> Sous-Directions -> Services. Valeurs
fixes, pas de fichier source dédié (l'organigramme n'est documenté que par les
newsletters internes, pas par une base de données).
"""

from django.core.management.base import BaseCommand

from core.models import DirectionRegionale, Entite

# Référentiel Dim_DR (Model_Dede.bim) : (Code_DR, Code_DR_Num, Libelle_DR, Zone).
DIM_DR = [
    ("DRABO", 22, "DR Abidjan ABOBO", "Abidjan"),
    ("DRAN", 4, "DR Abidjan Nord", "Abidjan"),
    ("DRAS", 2, "DR Abidjan Sud", "Abidjan"),
    ("DRYOP", 3, "DR Yop", "Abidjan"),
    ("DRBC", 24, "DR Basse Côte", "Intérieur"),
    ("DRC", 41, "DR Centre", "Intérieur"),
    ("DRCO", 42, "DR Centre Ouest", "Intérieur"),
    ("DRCS", 45, "DR Centre Sud", "Intérieur"),
    ("DRE", 21, "DR Est", "Intérieur"),
    ("DRLO", 26, "DR Littoral Ouest", "Intérieur"),
    ("DRN", 43, "DR Nord", "Intérieur"),
    ("DRO", 44, "DR Ouest", "Intérieur"),
    ("DRSE", 25, "DR Sud Est", "Intérieur"),
    ("DRSO", 23, "DR Sud Ouest", "Intérieur"),
]

# Arbre de l'organigramme : (code, libelle, niveau, parent_code ou None pour la racine).
ENTITES = [
    (Entite.DCB, "Direction Commerciale Business", Entite.DIRECTION, None),
    (Entite.SDRCB, "Sous-Direction Relation Clients Business", Entite.SOUS_DIRECTION, Entite.DCB),
    (Entite.SUPPORT_TECHNIQUE, "Sous-Direction Support Technique Business", Entite.SOUS_DIRECTION, Entite.DCB),
    (Entite.GUICHET_UNIQUE, "Sous-Direction Guichet Unique CIE-SODECI", Entite.SOUS_DIRECTION, Entite.DCB),
    (Entite.ABIDJAN, "Service Clients Business Abidjan", Entite.SERVICE, Entite.SDRCB),
    (Entite.INTERIEUR, "Service Clients Business Intérieur", Entite.SERVICE, Entite.SDRCB),
    (Entite.STRATEGIQUES_SENSIBLES, "Service Clients Stratégiques et Sensibles", Entite.SERVICE, Entite.SDRCB),
    (Entite.ADMINISTRATION, "Service Administration Commerciale", Entite.SERVICE, Entite.SDRCB),
    (
        Entite.PROSPECTION_RACCORDEMENT,
        "Service Prospection et Suivi de Projets de Raccordements",
        Entite.SERVICE,
        Entite.SUPPORT_TECHNIQUE,
    ),
    (
        Entite.INSTALLATION_INDUSTRIELLE,
        "Service Technique Installation Intérieure et Industrielle",
        Entite.SERVICE,
        Entite.SUPPORT_TECHNIQUE,
    ),
]


class Command(BaseCommand):
    help = "Importe le référentiel DirectionRegionale (Dim_DR) et l'arbre Entite (organigramme DCB)."

    def handle(self, *args, **options):
        created, updated = 0, 0
        for code, code_num, libelle, zone in DIM_DR:
            _, was_created = DirectionRegionale.objects.update_or_create(
                code=code, defaults={"code_numerique": code_num, "libelle": libelle, "zone": zone}
            )
            created += int(was_created)
            updated += int(not was_created)
        self.stdout.write(self.style.SUCCESS(f"DirectionRegionale : {created} créées, {updated} mises à jour."))

        ent_created, ent_updated = 0, 0
        # L'ordre de ENTITES place toujours un nœud après son parent : pas de tri
        # topologique nécessaire, la liste est déjà écrite racine -> feuilles.
        for code, libelle, niveau, parent_code in ENTITES:
            parent = Entite.objects.get(code=parent_code) if parent_code else None
            _, was_created = Entite.objects.update_or_create(
                code=code, defaults={"libelle": libelle, "niveau": niveau, "parent": parent}
            )
            ent_created += int(was_created)
            ent_updated += int(not was_created)
        self.stdout.write(
            self.style.SUCCESS(f"Entite : {ent_created} créées, {ent_updated} mises à jour (sur {len(ENTITES)}).")
        )
