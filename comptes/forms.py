from django import forms
from django.contrib.auth.forms import AuthenticationForm

from comptes.models import DemandeAcces, UserProfile
from core.models import DirectionRegionale, Entite


class CieLoginForm(AuthenticationForm):
    """AuthenticationForm standard, avec la classe Bootstrap `form-control` ajoutée
    aux widgets pour s'intégrer au gabarit SB Admin 2 (cf. comptes/templates/login.html)."""

    username = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))


class ProfileForm(forms.Form):
    """Formulaire "Mon Profil" : nom/prénom/email vivent sur le User natif Django,
    civilité/téléphone/photo sur UserProfile (cf. comptes.models) : un seul
    formulaire pour les deux, sauvegardés ensemble dans la vue (comptes/views.py)."""

    civilite = forms.ChoiceField(label="Civilité", choices=[("", "—")] + UserProfile.CIVILITE_CHOICES,
                                  required=False, widget=forms.Select(attrs={"class": "form-control"}))
    first_name = forms.CharField(label="Prénom", max_length=150, required=False,
                                  widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(label="Nom", max_length=150, required=False,
                                 widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(label="Email", required=False,
                              widget=forms.EmailInput(attrs={"class": "form-control"}))
    telephone = forms.CharField(label="Téléphone", max_length=30, required=False,
                                 widget=forms.TextInput(attrs={"class": "form-control"}))
    photo = forms.ImageField(label="Photo de profil", required=False,
                              widget=forms.ClearableFileInput(attrs={"class": "form-control-file"}))

    def save(self, user):
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.save(update_fields=["first_name", "last_name", "email"])

        profile = user.profile
        profile.civilite = self.cleaned_data["civilite"]
        profile.telephone = self.cleaned_data["telephone"]
        if self.cleaned_data.get("photo"):
            profile.photo = self.cleaned_data["photo"]
        profile.save(update_fields=["civilite", "telephone", "photo"])

    @classmethod
    def from_user(cls, user, data=None, files=None):
        initial = {
            "civilite": getattr(user.profile, "civilite", ""),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "telephone": getattr(user.profile, "telephone", ""),
        }
        if data is not None:
            return cls(data, files, initial=initial)
        return cls(initial=initial)


class DemandeAccesForm(forms.ModelForm):
    """Page publique (pas de login) : la personne ne connaît pas forcément le
    découpage exact de l'organigramme, entite_souhaitee/role_souhaite restent
    indicatifs, c'est la Direction qui tranche à la validation (cf. comptes.models.
    DemandeAcces)."""

    class Meta:
        model = DemandeAcces
        fields = ["nom_complet", "email", "entite_souhaitee", "role_souhaite", "justification"]
        labels = {
            "nom_complet": "Nom complet",
            "email": "Email professionnel",
            "entite_souhaitee": "Entité / Service souhaité",
            "role_souhaite": "Rôle souhaité",
            "justification": "Pourquoi avez-vous besoin d'un accès ?",
        }
        widgets = {
            "nom_complet": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "entite_souhaitee": forms.Select(attrs={"class": "form-control"}),
            "role_souhaite": forms.TextInput(attrs={"class": "form-control"}),
            "justification": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["entite_souhaitee"].queryset = Entite.objects.exclude(code=Entite.DCB)
        self.fields["entite_souhaitee"].empty_label = "Je ne sais pas"
        self.fields["entite_souhaitee"].required = False


class ParametresForm(forms.Form):
    """"Mon périmètre" : la Direction Régionale n'est aujourd'hui modifiable que
    par un admin via /admin/ ; demande utilisateur explicite que la Chargée
    d'Affaires puisse le faire elle-même. Limité aux DR de SA zone (Abidjan ou
    Intérieur, cf. profile.entite) pour qu'elle ne puisse pas se déclarer sur une
    zone qui n'est pas la sienne par erreur.

    Important à savoir, et à dire à l'utilisateur : pour un profil à portée
    individuelle (portee_individuelle=True, le cas de toutes les Chargées
    d'Affaires aujourd'hui), comptes.scoping.get_scope_filter bascule directement
    sur client__charge_affaires=user et n'utilise PAS directions_regionales pour
    filtrer les données. Ce champ reste donc déclaratif (utile pour la fiche/
    l'organigramme), pas un levier qui change immédiatement le portefeuille visible
    tant que cette logique de scoping n'évolue pas."""

    directions_regionales = forms.ModelMultipleChoiceField(
        queryset=DirectionRegionale.objects.none(),
        required=False,
        label="Directions Régionales couvertes",
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, zone=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = DirectionRegionale.objects.all()
        if zone:
            qs = qs.filter(zone=zone)
        self.fields["directions_regionales"].queryset = qs

    def save(self, user):
        user.profile.directions_regionales.set(self.cleaned_data["directions_regionales"])
