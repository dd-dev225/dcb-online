"""Rétablit le zéro de tête de REFRACCORD (référence raccordement) perdu à
l'import : même bug, même cause et même correctif que l'IDABON (migration 0011) —
la source de facturation stocke aussi REFRACCORD comme un nombre. Vérifié sur
V_Fait_Fact_HT_DCB.xlsx : 19 533 cellules `int` / 467 `str` sur un échantillon de
20 000 lignes, exactement la même signature que la colonne IDABON.

Le padding est déterministe et injectif (deux valeurs numériques distinctes ne
peuvent jamais padder vers la même chaîne de 8 chiffres), donc sans risque de
collision, même en l'absence de contrainte d'unicité sur ce champ."""

from django.db import migrations


def _pad(refraccord):
    if not refraccord:
        return refraccord
    s = str(refraccord).strip().upper()
    nb_chiffres = sum(c.isdigit() for c in s)
    if 0 < nb_chiffres < 8:
        s = "0" * (8 - nb_chiffres) + s
    return s


def pad_refraccords(apps, schema_editor):
    Abonnement = apps.get_model("clients", "Abonnement")
    a_modifier = []
    for abonnement in Abonnement.objects.exclude(refraccord=""):
        nouveau = _pad(abonnement.refraccord)
        if nouveau != abonnement.refraccord:
            abonnement.refraccord = nouveau
            a_modifier.append(abonnement)
    Abonnement.objects.bulk_update(a_modifier, ["refraccord"], batch_size=1000)


def revert(apps, schema_editor):
    Abonnement = apps.get_model("clients", "Abonnement")
    a_modifier = []
    for abonnement in Abonnement.objects.exclude(refraccord=""):
        sans_zero = abonnement.refraccord.lstrip("0")
        if sans_zero != abonnement.refraccord:
            abonnement.refraccord = sans_zero
            a_modifier.append(abonnement)
    Abonnement.objects.bulk_update(a_modifier, ["refraccord"], batch_size=1000)


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0013_client_fiche_controlee_client_fiche_controlee_le_and_more"),
    ]

    operations = [
        migrations.RunPython(pad_refraccords, revert),
    ]
