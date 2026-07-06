"""Formulaire public de la Fiche Qualité de Fourniture, digitalisation de la
fiche de collecte envoyée jusqu'ici par mail au client (cf. informations
clients/dcb/Support Technique/Fiche Qualite de Fourniture/). Champs, libellés
et choix repris à l'identique du prototype Fiche_Reclamations_CIE_XLSForm V1.xlsx
pour rester cohérent avec ce qui a déjà été validé côté Support Technique.

Les sections 3 (événements, 1 à 5) et 5 (relevés de tension, 0 à 5) sont des
groupes répétés dans le formulaire source ; ici elles sont rendues comme des
formsets à taille fixe (5 blocs), le client ne remplissant que ceux dont il a
besoin plutôt que de déclarer un compteur au préalable."""

from django import forms
from django.forms import formset_factory

from .models import EvenementQualite, FicheQualiteFourniture


class FicheQualiteFournitureForm(forms.ModelForm):
    # Déclarés explicitement : le champ modèle sous-jacent est un JSONField, dont
    # le ModelForm génère par défaut un forms.JSONField (qui attend une CHAÎNE
    # JSON en entrée). CheckboxSelectMultiple.value_from_datadict() renvoie une
    # LISTE (getlist), ce qui fait planter JSONField.to_python() avec "the JSON
    # object must be str, bytes or bytearray, not list". MultipleChoiceField
    # gère nativement les listes et son cleaned_data (une liste) s'enregistre
    # directement dans le JSONField du modèle.
    methode_constat = forms.MultipleChoiceField(
        required=True,
        choices=FicheQualiteFourniture.METHODE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Type(s) de constat utilisé(s)",
        help_text="Sélectionnez tout ce qui s'applique",
    )
    conditions_constat = forms.MultipleChoiceField(
        required=True,
        choices=FicheQualiteFourniture.CONDITION_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Conditions au moment du constat",
        help_text="Sélectionnez tout ce qui s'applique",
    )
    documents_joints = forms.MultipleChoiceField(
        required=False,
        choices=FicheQualiteFourniture.DOCUMENT_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Types de documents joints",
        help_text="Cochez tout ce qui est joint",
    )

    class Meta:
        model = FicheQualiteFourniture
        fields = [
            "nom_entreprise",
            "gps_latitude",
            "gps_longitude",
            "nom_correspondant",
            "telephone",
            "email",
            "methode_constat",
            "obs_visuelle",
            "obs_appareil",
            "obs_enregistrement",
            "obs_autre_constat",
            "frequence_phenomene",
            "frequence_detail",
            "conditions_constat",
            "conditions_detail",
            "documents_joints",
            "photo_jointe",
            "rapport_joint",
            "documents_observations",
            "observations_finales",
        ]
        labels = {
            "nom_entreprise": "Nom de l'entreprise",
            "gps_latitude": "Latitude GPS (facultatif)",
            "gps_longitude": "Longitude GPS (facultatif)",
            "nom_correspondant": "Nom du Correspondant Technique",
            "telephone": "Contact (téléphone)",
            "email": "Adresse email",
            "obs_visuelle": "Observations : Observation à l'œil nu",
            "obs_appareil": "Observations : Appareil de mesure",
            "obs_enregistrement": "Observations : Enregistrement automatique",
            "obs_autre_constat": "Observations : Autre méthode de constat",
            "frequence_phenomene": "Fréquence observée du phénomène",
            "frequence_detail": "Précisions sur la fréquence",
            "conditions_detail": "Précisions sur les conditions",
            "photo_jointe": "Photo ou capture d'écran",
            "rapport_joint": "Scan du rapport technique ou des données",
            "documents_observations": "Observations sur les documents joints",
            "observations_finales": "Observations ou remarques complémentaires",
        }
        help_texts = {
            "nom_entreprise": "Ex : SIVOA, SOLIBRA, SIFCA...",
            "nom_correspondant": "Prénom et Nom",
            "telephone": "Ex : 07 00 00 00 00",
            "email": "Ex : contact@entreprise.ci",
            "obs_autre_constat": "Obligatoire si « Autre » est coché.",
            "frequence_phenomene": "Choisissez la fréquence la plus représentative",
            "frequence_detail": "Ex : chaque soir entre 18h et 22h, tous les lundis...",
            "conditions_detail": "Ex : après travaux CIE, coupure chez le voisin également...",
            "documents_observations": "Précisez ici si « Autre document » a été coché",
            "observations_finales": "Toute information utile non couverte par les sections précédentes",
        }
        widgets = {
            "gps_latitude": forms.NumberInput(attrs={"step": "0.000001"}),
            "gps_longitude": forms.NumberInput(attrs={"step": "0.000001"}),
            "obs_visuelle": forms.TextInput(),
            "obs_appareil": forms.TextInput(),
            "obs_enregistrement": forms.TextInput(),
            "obs_autre_constat": forms.TextInput(),
            "frequence_phenomene": forms.RadioSelect(),
            "conditions_detail": forms.TextInput(),
            "documents_observations": forms.TextInput(),
            "observations_finales": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxSelectMultiple, forms.RadioSelect, forms.ClearableFileInput)):
                field.widget.attrs.setdefault("class", "form-control")
        for name in ("nom_entreprise", "nom_correspondant", "telephone"):
            self.fields[name].required = True

    def clean(self):
        cleaned_data = super().clean()
        if "autre_constat" in (cleaned_data.get("methode_constat") or []) and not cleaned_data.get("obs_autre_constat"):
            self.add_error("obs_autre_constat", "Ce champ est obligatoire quand « Autre » est sélectionné.")
        return cleaned_data


class EvenementQualiteForm(forms.Form):
    date = forms.DateField(required=False, label="Date", widget=forms.DateInput(attrs={"type": "date"}))
    heure_debut = forms.TimeField(required=False, label="Heure de début", widget=forms.TimeInput(attrs={"type": "time"}))
    heure_fin = forms.TimeField(
        required=False, label="Heure de fin", help_text="Laisser vide si inconnue", widget=forms.TimeInput(attrs={"type": "time"})
    )
    phenomenes = forms.MultipleChoiceField(
        required=False,
        label="Phénomène(s) électrique(s) observé(s)",
        help_text="Sélectionnez tout ce qui s'applique",
        choices=EvenementQualite.PHENOMENE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )
    autre_description = forms.CharField(
        required=False, label="Description si « Autre » coché", help_text="Comment le phénomène s'est-il manifesté ?"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("date") and not cleaned_data.get("phenomenes"):
            self.add_error("phenomenes", "Veuillez sélectionner au moins un phénomène observé.")
        if "autre" in (cleaned_data.get("phenomenes") or []) and not cleaned_data.get("autre_description"):
            self.add_error("autre_description", "Ce champ est obligatoire quand « Autre » est sélectionné.")
        return cleaned_data


class ReleveTensionForm(forms.Form):
    date = forms.DateField(required=False, label="Date du relevé", widget=forms.DateInput(attrs={"type": "date"}))
    heure = forms.TimeField(required=False, label="Heure du relevé", widget=forms.TimeInput(attrs={"type": "time"}))
    u12 = forms.DecimalField(
        required=False, max_digits=8, decimal_places=1, min_value=0, max_value=40000,
        label="U12 (Volt)", help_text="Tension composée entre phases 1 et 2 (Ex : 14800)",
    )
    u23 = forms.DecimalField(
        required=False, max_digits=8, decimal_places=1, min_value=0, max_value=40000,
        label="U23 (Volt)", help_text="Tension composée entre phases 2 et 3",
    )
    u31 = forms.DecimalField(
        required=False, max_digits=8, decimal_places=1, min_value=0, max_value=40000,
        label="U31 (Volt)", help_text="Tension composée entre phases 3 et 1",
    )
    v1 = forms.DecimalField(
        required=False, max_digits=8, decimal_places=1, min_value=0, max_value=25000,
        label="V1 (Volt)", help_text="Tension simple phase 1 (Ex : 8500)",
    )
    v2 = forms.DecimalField(
        required=False, max_digits=8, decimal_places=1, min_value=0, max_value=25000,
        label="V2 (Volt)", help_text="Tension simple phase 2",
    )
    v3 = forms.DecimalField(
        required=False, max_digits=8, decimal_places=1, min_value=0, max_value=25000,
        label="V3 (Volt)", help_text="Tension simple phase 3",
    )
    appareil_mesure = forms.CharField(
        required=False, label="Appareil de mesure", help_text="Ex : Multimètre Fluke 87V, Analyseur de réseau..."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


EvenementQualiteFormSet = formset_factory(EvenementQualiteForm, extra=5, max_num=5)
ReleveTensionFormSet = formset_factory(ReleveTensionForm, extra=5, max_num=5)
