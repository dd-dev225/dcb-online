"""Crée un compte de test par niveau de l'organigramme DCB (cf. core.Entite,
arbre Direction > Sous-Direction > Service) : chaque compte illustre le
"pilotage différencié" : il ne voit que son nœud + son sous-arbre
(comptes.scoping.get_scope_filter), les niveaux supérieurs voient le cumul.

Couvre désormais aussi le niveau le plus opérationnel documenté dans les
newsletters (Cadre Chargée d'Affaires, Assistant Technique, Assistante Appui
Commercial...), ainsi que le niveau DR pour Abidjan/Intérieur, plusieurs DR par
profil (UserProfile.directions_regionales, ManyToMany) : une Chargée d'Affaires
gère réellement plusieurs DR à la fois (ex: DRAS+DRAN pour une même personne,
tableau DEX/DR/Chargée fourni par l'utilisateur), pas une seule.

Tous les "Cadre Chargée d'Affaires" (Abidjan/Intérieur/Stratégiques) sont en
portee_individuelle=True : chacune gère son propre portefeuille de clients
(Client.charge_affaires), avec remontée automatique au Chef de Service puis au
Sous-Directeur (cf. comptes.scoping). Pas de nom réel utilisé (cf. note de
confidentialité du plan), seulement des comptes "secteurX" numérotés reflétant le
nombre réel de personnes par zone.

Mots de passe de démo, à changer avant tout usage hors environnement de
développement local. Ne crée plus de Group Django "Direction"/"Entite" : la
distinction se fait uniquement par la position dans l'arbre Entite
(profile.is_direction), pas par un groupe séparé à maintenir en double.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from comptes.models import UserProfile
from core.models import DirectionRegionale, Entite

DEMO_PASSWORD = "DcbDemo2026!"

# username, entite_code, role, portee_individuelle, dr_codes (liste, [] si pas de sous-filtre DR)
TEST_USERS = [
    ("directeur", Entite.DCB, UserProfile.DIRECTEUR, False, []),
    ("sousdir_relation_clients", Entite.SDRCB, UserProfile.SOUS_DIRECTEUR, False, []),
    ("sousdir_support_technique", Entite.SUPPORT_TECHNIQUE, UserProfile.SOUS_DIRECTEUR, False, []),
    ("sousdir_guichet_unique", Entite.GUICHET_UNIQUE, UserProfile.SOUS_DIRECTEUR, False, []),
    # SDRCB (N56), Service Abidjan : Chef de Service, puis 2 Chargées d'Affaires
    # réelles, chacune sur un groupe de DR (DRAS+DRAN / DRYOP+DRABO, cf. tableau
    # DEX/DR/Chargée fourni). cadre_affaires_abidjan_demo reste un exemple "sans
    # sous-filtre DR" (portefeuille illustratif déjà peuplé, cf. _assign_demo_portfolio).
    ("chef_abidjan", Entite.ABIDJAN, UserProfile.CHEF_SERVICE, False, []),
    ("cadre_affaires_abidjan_demo", Entite.ABIDJAN, UserProfile.CADRE_CHARGE_AFFAIRES, True, []),
    ("cadre_affaires_abidjan_secteur1_demo", Entite.ABIDJAN, UserProfile.CADRE_CHARGE_AFFAIRES, True, ["DRAS", "DRAN"]),
    ("cadre_affaires_abidjan_secteur2_demo", Entite.ABIDJAN, UserProfile.CADRE_CHARGE_AFFAIRES, True, ["DRYOP", "DRABO"]),
    # SDRCB, Service Intérieur : Chef de Service, puis 2 Chargées d'Affaires réelles
    # couvrant chacune 4-5 DR (cf. même tableau).
    ("chef_interieur", Entite.INTERIEUR, UserProfile.CHEF_SERVICE, False, []),
    ("cadre_affaires_interieur_demo", Entite.INTERIEUR, UserProfile.CADRE_CHARGE_AFFAIRES, True, []),
    ("cadre_affaires_interieur_secteur1_demo", Entite.INTERIEUR, UserProfile.CADRE_CHARGE_AFFAIRES, True, ["DRSE", "DRLO", "DRSO", "DRO"]),
    ("cadre_affaires_interieur_secteur2_demo", Entite.INTERIEUR, UserProfile.CADRE_CHARGE_AFFAIRES, True, ["DRCS", "DRN", "DRC", "DRCO", "DRE"]),
    ("chef_strategiques", Entite.STRATEGIQUES_SENSIBLES, UserProfile.CHEF_SERVICE, False, []),
    ("cadre_affaires_strategiques_demo", Entite.STRATEGIQUES_SENSIBLES, UserProfile.CADRE_CHARGE_AFFAIRES, True, []),
    ("chef_administration", Entite.ADMINISTRATION, UserProfile.CHEF_SERVICE, False, []),
    ("assistante_appui_commercial_demo", Entite.ADMINISTRATION, UserProfile.ASSISTANTE_APPUI_COMMERCIAL, False, []),
    # SDSTB (N60) : Responsable/Chef de Service, puis "Assistant Technique".
    ("responsable_raccordement", Entite.PROSPECTION_RACCORDEMENT, UserProfile.RESPONSABLE, False, []),
    ("assistant_technique_raccordement_demo", Entite.PROSPECTION_RACCORDEMENT, UserProfile.ASSISTANT_TECHNIQUE, False, []),
    ("chef_installation_industrielle", Entite.INSTALLATION_INDUSTRIELLE, UserProfile.CHEF_SERVICE, False, []),
    ("assistant_technique_installation_demo", Entite.INSTALLATION_INDUSTRIELLE, UserProfile.ASSISTANT_TECHNIQUE, False, []),
    # SDGU (N57) : pas de Service dédié (cf. discussion produit), rôles distincts
    # par le libellé uniquement, tous sur entite=guichet_unique. La répartition à
    # l'intérieur de la SDGU suit la même logique que la SDRCB mais sur l'axe CCGC
    # (Conseillère Client Grands Comptes) plutôt que Direction Régionale (demande
    # utilisateur explicite) : 3 CCGC individuelles (BOGA/DIOMANDE/SYLLA, chacune
    # portee_individuelle=True, un seul code CCGC) ; deux "cadres" qui supervisent
    # chacun un GROUPE de CCGC (portee_individuelle=False, plusieurs codes) :
    # cadre_guichet_unique supervise BOGA+DIOMANDE, cadre_charge_affaires_guichet
    # supervise SYLLA seule ; le Sous-Directeur voit le cumul de toute la
    # Sous-Direction (ccgc_supervisees vide -> tout le sous-arbre), comme les
    # autres niveaux SOUS_DIRECTEUR. Le détail des codes CCGC par compte est posé
    # séparément juste après (CCGC_SUPERVISEES), pas dans dr_codes qui ne
    # s'applique qu'aux Directions Régionales.
    ("cadre_charge_affaires_guichet", Entite.GUICHET_UNIQUE, UserProfile.CADRE_CHARGE_AFFAIRES, False, []),
    ("cadre_guichet_unique", Entite.GUICHET_UNIQUE, UserProfile.CADRE_GUICHET_UNIQUE, False, []),
    ("conseiller_grands_comptes_guichet", Entite.GUICHET_UNIQUE, UserProfile.CONSEILLER_GRANDS_COMPTES, True, []),
    ("conseiller_grands_comptes_guichet_2", Entite.GUICHET_UNIQUE, UserProfile.CONSEILLER_GRANDS_COMPTES, True, []),
    ("conseiller_grands_comptes_guichet_3", Entite.GUICHET_UNIQUE, UserProfile.CONSEILLER_GRANDS_COMPTES, True, []),
]

# CCGC supervisées par compte SDGU (cf. commentaire ci-dessus) : conseiller_*
# = une CCGC individuelle (son propre portefeuille), cadre_* = un groupe de CCGC
# (supervision). Absent de ce dict = pas de restriction par CCGC (Sous-Directeur).
CCGC_SUPERVISEES = {
    "cadre_guichet_unique": ["BOGA", "DIOMANDE"],
    "cadre_charge_affaires_guichet": ["SYLLA"],
    "conseiller_grands_comptes_guichet": ["SYLLA"],
    "conseiller_grands_comptes_guichet_2": ["BOGA"],
    "conseiller_grands_comptes_guichet_3": ["DIOMANDE"],
}

# Comptes obsolètes (anciens noms/rôles, ou remplacés par les comptes "secteurX"
# multi-DR ci-dessus) à supprimer si présents, pour éviter les doublons.
OBSOLETE_USERNAMES = [
    "charge_abidjan_demo", "chef_raccordement",
    "cadre_affaires_dryop_demo", "cadre_affaires_drc_demo",
]


class Command(BaseCommand):
    help = "Crée un compte de test par niveau de l'organigramme DCB, y compris le niveau opérationnel et DR."

    def handle(self, *args, **options):
        User = get_user_model()

        User.objects.filter(username__in=OBSOLETE_USERNAMES).delete()

        for username, entite_code, role, individuel, dr_codes in TEST_USERS:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(DEMO_PASSWORD)
            user.save()

            entite = Entite.objects.get(code=entite_code)
            drs = list(DirectionRegionale.objects.filter(code__in=dr_codes))
            ccgc = CCGC_SUPERVISEES.get(username, [])
            profile, _ = UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    "entite": entite, "role": role, "portee_individuelle": individuel,
                    "ccgc_supervisees": ccgc,
                },
            )
            profile.directions_regionales.set(drs)
            suffix = f" / DR={'+'.join(dr_codes)}" if dr_codes else ""
            suffix += f" / CCGC={'+'.join(ccgc)}" if ccgc else ""
            self.stdout.write(self.style.SUCCESS(f"{username} -> {entite.code} ({role}){suffix}"))

        self._assign_demo_portfolio()
        self._fixer_commercial_immeubles()
        self.stdout.write(self.style.WARNING(f"Mot de passe de démo pour ces comptes : {DEMO_PASSWORD}"))

    def _fixer_commercial_immeubles(self):
        """Corrige le FK ImmeubleProspecte.commercial pour qu'il reflète la
        vraie hiérarchie CCGC (import_operateurs_guichet_unique ne le peuple pas,
        une affectation antérieure l'avait fait pointer à tort vers les comptes
        "cadre" superviseurs plutôt que vers la CCGC individuelle propriétaire du
        portefeuille). Purement pour la cohérence d'affichage : le scoping réel
        (prospection.scoping) passe désormais par ccgc_nom, pas ce FK."""
        from prospection.ccgc import ccgc_code_pour_nom
        from prospection.models import ImmeubleProspecte

        User = get_user_model()
        compte_par_ccgc = {
            "BOGA": "conseiller_grands_comptes_guichet_2",
            "DIOMANDE": "conseiller_grands_comptes_guichet_3",
            "SYLLA": "conseiller_grands_comptes_guichet",
        }
        corriges = 0
        for immeuble in ImmeubleProspecte.objects.exclude(ccgc_nom=""):
            code = ccgc_code_pour_nom(immeuble.ccgc_nom)
            bon_username = compte_par_ccgc.get(code)
            bon_commercial = User.objects.filter(username=bon_username).first() if bon_username else None
            if immeuble.commercial_id != (bon_commercial.pk if bon_commercial else None):
                immeuble.commercial = bon_commercial
                immeuble.save(update_fields=["commercial"])
                corriges += 1
        if corriges:
            self.stdout.write(self.style.WARNING(f"{corriges} immeubles : commercial corrigé d'après ccgc_nom."))

    def _assign_demo_portfolio(self):
        """Affecte quelques clients à chaque Chargée d'Affaires démo, pour illustrer
        le niveau individuel (portee_individuelle=True). Affectation MANUELLE/
        illustrative, aucune source de données réelle ne fournit ce rattachement
        (cf. clients.Client.charge_affaires)."""
        from clients.models import Client

        User = get_user_model()
        repartition = [
            ("cadre_affaires_abidjan_demo", Entite.ABIDJAN, None, 5),
            ("cadre_affaires_abidjan_secteur1_demo", Entite.ABIDJAN, ["DRAS", "DRAN"], 5),
            ("cadre_affaires_abidjan_secteur2_demo", Entite.ABIDJAN, ["DRYOP", "DRABO"], 5),
            ("cadre_affaires_interieur_demo", Entite.INTERIEUR, None, 5),
            ("cadre_affaires_interieur_secteur1_demo", Entite.INTERIEUR, ["DRSE", "DRLO", "DRSO", "DRO"], 5),
            ("cadre_affaires_interieur_secteur2_demo", Entite.INTERIEUR, ["DRCS", "DRN", "DRC", "DRCO", "DRE"], 5),
            ("cadre_affaires_strategiques_demo", Entite.STRATEGIQUES_SENSIBLES, None, 5),
        ]
        for username, entite_code, dr_codes, n in repartition:
            user = User.objects.get(username=username)
            qs = Client.objects.filter(entite__code=entite_code, charge_affaires__isnull=True)
            if dr_codes:
                qs = qs.filter(direction_regionale__code__in=dr_codes)
            clients = qs.order_by("idabon")[:n]
            for c in clients:
                c.charge_affaires = user
                c.save(update_fields=["charge_affaires"])
            self.stdout.write(self.style.WARNING(f"{len(clients)} clients affectés (démo illustrative) à {username}."))
