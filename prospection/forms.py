"""Formulaire de collecte numérique pour la prospection terrain de la SDGU.
Digitalise la trame de Fiche de prospection_VF.pdf (sections I "Cibles",
II "Projets", III "Démarches CIE/SODECI"), pas encore utilisée sur le terrain
faute de support numérique (cf. informations clients/dcb/Guichet Unique/info.txt)."""

from django.contrib.auth import get_user_model
from django import forms

from core.models import Entite

from .models import DemarcheAdministrative, ImmeubleProspecte

OUI_NON_CHOICES = [("oui", "Oui"), ("non", "Non")]

User = get_user_model()


class ImmeubleProspecteForm(forms.ModelForm):
    class Meta:
        model = ImmeubleProspecte
        fields = [
            "date_visite",
            "nom_structure",
            "type_cible",
            "constructeur",
            "interlocuteur",
            "fonction_interlocuteur",
            "contact",
            "email",
            "situation_geographique",
            "zone_prospection",
            "dex",
            "direction_regionale",
            "type_construction",
            "nb_niveaux",
            "nb_appartements_bureaux",
            "details_construction",
            "stade_avancement",
            "date_debut_travaux",
            "date_prev_fin_travaux",
            "delai_livraison",
            "poste_existant",
            "observations",
        ]
        labels = {
            "nom_structure": "Structure prospectée",
            "type_cible": "Cible",
            "date_visite": "Date de la visite",
            "nb_niveaux": "Nombre de niveaux",
            "nb_appartements_bureaux": "Nombre d'appartements / bureaux",
            "date_debut_travaux": "Début des travaux (ex: 2025, ou \"Janvier 2026\")",
            "date_prev_fin_travaux": "Fin prévue des travaux (ex: 2027, ou \"Décembre 2026\")",
            "delai_livraison": "Délai de livraison prévu (ex: 2026/2027)",
            "poste_existant": "Poste de transformation déjà existant ?",
        }
        widgets = {
            "date_visite": forms.DateInput(attrs={"type": "date"}),
            "observations": forms.Textarea(attrs={"rows": 3}),
            "poste_existant": forms.Select(choices=[("", "Inconnu"), (True, "Oui"), (False, "Non")]),
        }

    def __init__(self, *args, allow_commercial_reassign=False, **kwargs):
        super().__init__(*args, **kwargs)
        if allow_commercial_reassign:
            # Réassignation de portefeuille (cf. info.txt "Affectation des
            # portefeuilles") : seulement proposée à qui voit toute la
            # Sous-Direction (Sous-Directeur/Direction), pas à un compte
            # individuel qui ne doit pas pouvoir s'attribuer le portefeuille
            # d'un collègue.
            self.fields["commercial"] = forms.ModelChoiceField(
                queryset=User.objects.filter(profile__entite__code=Entite.GUICHET_UNIQUE).order_by("username"),
                required=False,
                label="Commercial assigné",
            )
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-control")
            if name == "nom_structure":
                field.required = True


class DemarcheAdministrativeForm(forms.Form):
    """Une instance par organisme (CIE/SODECI), instanciée 2 fois avec un prefix
    différent dans la vue. Reproduit les sections III.A/III.B de la fiche
    officielle, suivies en parallèle plutôt que fusionnées."""

    demande_initiee = forms.ChoiceField(
        choices=OUI_NON_CHOICES, initial="non", label="Demande déjà initiée ?", widget=forms.RadioSelect
    )
    type_demande = forms.ChoiceField(
        choices=[("", "—")] + DemarcheAdministrative.TYPE_DEMANDE_CHOICES, required=False, label="Type de demande"
    )
    statut = forms.ChoiceField(
        choices=[("", "—")] + DemarcheAdministrative.STATUT_CHOICES, required=False, label="Statut du dossier"
    )
    numero_demande = forms.CharField(required=False, label="Numéro de demande")
    details_non_conformite = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Détails si non-conforme"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "demande_initiee":
                field.widget.attrs.setdefault("class", "form-control")
