from django import forms

from .models import Message
from .permissions import entites_contactables


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["entite_destinataire", "contenu"]
        widgets = {
            "entite_destinataire": forms.Select(attrs={"class": "form-control"}),
            "contenu": forms.Textarea(attrs={"class": "form-control", "rows": 5, "placeholder": "Votre message..."}),
        }
        labels = {
            "entite_destinataire": "Destinataire",
            "contenu": "Message",
        }

    def __init__(self, *args, entite_expeditrice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["entite_destinataire"].queryset = entites_contactables(entite_expeditrice)
        self.fields["entite_destinataire"].empty_label = "Choisir une entité"
