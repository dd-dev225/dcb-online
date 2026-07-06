"""Rétablit le zéro de tête des IDABON perdu à l'import (la source de facturation
stocke l'IDABON comme un nombre). Forme canonique : 8 chiffres numériques, lettre
éventuelle conservée (demande utilisateur : « on doit le 0 dans l'app »).

Le padding est injectif (aucun IDABON ne commence par 0 avant migration, donc pas
de collision) et idempotent (réappliqué sur une valeur déjà à 8 chiffres, il ne
change rien)."""

from django.db import migrations


def _pad(idabon):
    if not idabon:
        return idabon
    s = str(idabon).strip().upper()
    nb_chiffres = sum(c.isdigit() for c in s)
    if 0 < nb_chiffres < 8:
        s = "0" * (8 - nb_chiffres) + s
    return s


def pad_idabons(apps, schema_editor):
    Client = apps.get_model("clients", "Client")
    existants = set(Client.objects.values_list("idabon", flat=True))
    a_modifier = []
    for client in Client.objects.all():
        nouveau = _pad(client.idabon)
        if nouveau != client.idabon and nouveau not in existants:
            client.idabon = nouveau
            a_modifier.append(client)
    Client.objects.bulk_update(a_modifier, ["idabon"], batch_size=1000)


def revert(apps, schema_editor):
    # Retire les zéros de tête pour revenir à la forme "nombre" de la source.
    Client = apps.get_model("clients", "Client")
    a_modifier = []
    for client in Client.objects.all():
        sans_zero = str(client.idabon).lstrip("0") if client.idabon else client.idabon
        if sans_zero != client.idabon:
            client.idabon = sans_zero
            a_modifier.append(client)
    Client.objects.bulk_update(a_modifier, ["idabon"], batch_size=1000)


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0010_remove_client_source"),
    ]

    operations = [
        migrations.RunPython(pad_idabons, revert),
    ]
