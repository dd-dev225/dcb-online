"""Formulaires de la fiche client enrichie, demandés par le Sous-Directeur SDRCB
pour que les Chargés d'Affaires centralisent les informations commerciales/
techniques/interlocuteurs de leur portefeuille (cf. clients.views.fiche_client)."""

from django import forms
from django.forms import inlineformset_factory

from .models import Abonnement, Client, Interlocuteur


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["secteur_activite", "branche_activite", "a_contrat", "contrat_document", "contrat_reference_physique"]
        labels = {
            "secteur_activite": "Secteur d'activité",
            "branche_activite": "Branche d'activité",
            "a_contrat": "Contrat signé ?",
            "contrat_document": "Contrat (fichier numérique)",
            "contrat_reference_physique": "Référence d'archivage physique (si pas de numérique)",
        }
        widgets = {
            "a_contrat": forms.Select(choices=[("", "Inconnu"), (True, "Oui"), (False, "Non")]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class AbonnementTechniqueForm(forms.ModelForm):
    """Seuls depart/poste sont éditables : refraccord/psabon/tranche_puissance
    viennent de l'import HT et ne doivent pas être réécrits à la main (source de
    vérité = l'export, pas la saisie manuelle)."""

    class Meta:
        model = Abonnement
        fields = ["depart", "poste"]
        labels = {"depart": "Départ HT", "poste": "Poste source HT/MT"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


# extra=3 (pas 1) : un client a souvent plusieurs interlocuteurs (représentant
# légal + technique + commercial, parfois plusieurs du même type). Avec extra=1,
# on ne pouvait en saisir qu'un de plus que l'existant sans repasser par le
# formulaire après enregistrement. Pas de JS "ajouter une ligne" en V1, donc on
# part large plutôt que de forcer plusieurs aller-retours.
InterlocuteurFormSet = inlineformset_factory(
    Client,
    Interlocuteur,
    fields=["role", "nom", "fonction", "email", "telephone"],
    extra=3,
    can_delete=True,
    widgets={
        "role": forms.Select(attrs={"class": "form-control"}),
        "nom": forms.TextInput(attrs={"class": "form-control"}),
        "fonction": forms.TextInput(attrs={"class": "form-control"}),
        "email": forms.EmailInput(attrs={"class": "form-control"}),
        "telephone": forms.TextInput(attrs={"class": "form-control"}),
    },
)

# extra=0/can_delete=False : on édite seulement les abonnements déjà importés depuis
# la base HT (depart/poste, absents de cet export), on n'en crée/supprime pas ici.
AbonnementFormSet = inlineformset_factory(
    Client,
    Abonnement,
    form=AbonnementTechniqueForm,
    extra=0,
    can_delete=False,
)


class ProposerClientForm(forms.Form):
    """Recherche d'un client déjà présent dans la base HT (idabon ou référence de
    raccordement), la base de clients stratégiques grandit dans le temps, on ne se
    limite plus à la liste figée importée initialement."""

    identifiant = forms.CharField(
        label="IDABON ou référence de raccordement du client",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: 24D07701"}),
    )
