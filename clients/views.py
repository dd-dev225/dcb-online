from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

import pandas as pd

from facturation.models import Facture, Recouvrement
from core.excel import excel_response
from core.models import DirectionRegionale, Entite

from .forms import AbonnementFormSet, ClientForm, InterlocuteurFormSet, ProposerClientForm
from .models import Client, ClientStrategiqueNonRattache, HistoriqueFiche
from .permissions import (
    est_dans_sdrcb,
    peut_controler_fiches,
    peut_proposer_strategique,
    peut_valider_strategique,
    peut_voir_liste_financiere,
)
from .scoping import get_client_scope
from .services import colonnes_manquantes, importer_fiches_depuis_dataframe


def sdrcb_required(view_func):
    """Lecture/écriture sur le portefeuille, réservé à la SDRCB (Chargés
    d'Affaires, Chefs de Service, Sous-Directeur), pas à la Direction (cf.
    clients.permissions : gérer un portefeuille client est le métier de la SDRCB)."""

    def wrapped(request, *args, **kwargs):
        if not est_dans_sdrcb(request.user):
            raise PermissionDenied("Réservé aux comptes de la Sous-Direction Relation Clients Business.")
        return view_func(request, *args, **kwargs)

    return wrapped


def liste_financiere_required(view_func):
    """Simple consultation (pas d'action) : ouverte à la SDRCB ET à la Direction,
    contrairement à sdrcb_required qui réserve les actions du portefeuille à la
    seule SDRCB."""

    def wrapped(request, *args, **kwargs):
        if not peut_voir_liste_financiere(request.user):
            raise PermissionDenied("Réservé à la Direction et à la Sous-Direction Relation Clients Business.")
        return view_func(request, *args, **kwargs)

    return wrapped


def _calculer_ca_historique(client):
    """CA sur les 12/36 DERNIERS MOIS FACTURÉS DISPONIBLES (pas calendaires strict),
    plus robuste qu'une fenêtre de dates fixe si la facturation a des trous."""
    factures = (
        Facture.objects.filter(client=client)
        .values("periode__annee", "periode__mois")
        .annotate(total=Sum("montant_facture_ttc"))
        .order_by("-periode__annee", "-periode__mois")
    )
    rows = list(factures)
    ca_1an = sum(r["total"] or 0 for r in rows[:12])
    ca_3ans = sum(r["total"] or 0 for r in rows[:36])
    return ca_1an, ca_3ans


@login_required
@sdrcb_required
def liste_portefeuille(request):
    qs = Client.objects.filter(get_client_scope(request.user)).select_related("entite", "direction_regionale")
    total = qs.count()

    # Recherche contextuelle par nom / raison sociale ou IDABON (demande
    # utilisateur) : icontains sur les deux champs, insensible à la casse. Reste
    # dans le périmètre déjà scopé de l'utilisateur.
    recherche = request.GET.get("q", "").strip()
    if recherche:
        qs = qs.filter(Q(nom_prenoms__icontains=recherche) | Q(idabon__icontains=recherche))
    nb_resultats = qs.count()

    # Pagination plutôt qu'un slice fixe [:500] : un grand portefeuille (Service
    # Abidjan, ~2000 clients selon les newsletters internes) restait jusqu'ici
    # tronqué sans avertissement au-delà de 500 lignes (demande utilisateur, cf.
    # rapport "Fonctionnalités proposées").
    page = Paginator(qs.order_by("nom_prenoms", "idabon"), 50).get_page(request.GET.get("page"))

    clients = []
    for c in page:
        nb_champs_remplis = sum(
            bool(v) for v in [c.secteur_activite, c.a_contrat is not None, c.contrat_document or c.contrat_reference_physique]
        )
        clients.append({"client": c, "completion": f"{nb_champs_remplis}/3", "nb_interlocuteurs": c.interlocuteurs.count()})

    return render(
        request,
        "clients/liste_portefeuille.html",
        {
            "clients": clients,
            "page_obj": page,
            "total": total,
            "recherche": recherche,
            "nb_resultats": nb_resultats,
            "peut_controler": peut_controler_fiches(request.user),
            "peut_valider": peut_valider_strategique(request.user),
            "peut_proposer": peut_proposer_strategique(request.user),
            "nb_en_attente": Client.objects.filter(get_client_scope(request.user), strategique_en_attente=True).count(),
        },
    )


@login_required
@sdrcb_required
def fiche_client(request, idabon):
    """Beaucoup de champs sont déjà disponibles depuis l'import HT (puissance
    souscrite, référence raccordement...) et affichés en lecture seule ; seuls les
    champs absents des exports (interlocuteurs, contrat, départ/poste) sont
    éditables ici, le formulaire complète plutôt que ne duplique les données."""
    client = get_object_or_404(Client.objects.filter(get_client_scope(request.user)), idabon=idabon)

    if request.method == "POST":
        form_client = ClientForm(request.POST, request.FILES, instance=client)
        formset_abonnements = AbonnementFormSet(request.POST, instance=client, prefix="abon")
        formset_interlocuteurs = InterlocuteurFormSet(request.POST, instance=client, prefix="interlocuteurs")
        if form_client.is_valid() and formset_abonnements.is_valid() and formset_interlocuteurs.is_valid():
            champs_modifies = list(form_client.changed_data)
            if formset_abonnements.has_changed():
                champs_modifies.append("abonnements (départ/poste)")
            if formset_interlocuteurs.has_changed():
                champs_modifies.append("interlocuteurs")

            client = form_client.save(commit=False)
            client.fiche_maj_le = timezone.now()
            client.fiche_maj_par = request.user
            # Toute modification réelle invalide le contrôle précédent du chef : la
            # fiche repasse "à contrôler" (workflow chargé -> chef -> SDRCB).
            if champs_modifies and client.fiche_controlee:
                client.fiche_controlee = False
                client.fiche_controlee_par = None
                client.fiche_controlee_le = None
            client.save()
            formset_abonnements.save()
            formset_interlocuteurs.save()

            # Historique des modifications (demande utilisateur, cf. rapport
            # "Fonctionnalités proposées") : seulement s'il y a eu un changement
            # réel, pas une simple re-soumission du formulaire à l'identique.
            if champs_modifies:
                HistoriqueFiche.objects.create(
                    client=client, modifie_par=request.user, champs_modifies=", ".join(champs_modifies)
                )

            messages.success(request, f"Fiche de {client.nom_prenoms or client.idabon} mise à jour.")
            return redirect("clients:liste_portefeuille")
    else:
        form_client = ClientForm(instance=client)
        formset_abonnements = AbonnementFormSet(instance=client, prefix="abon")
        formset_interlocuteurs = InterlocuteurFormSet(instance=client, prefix="interlocuteurs")

    ca_1an, ca_3ans = _calculer_ca_historique(client)

    return render(
        request,
        "clients/fiche_client.html",
        {
            "client": client,
            "form_client": form_client,
            "formset_abonnements": formset_abonnements,
            "formset_interlocuteurs": formset_interlocuteurs,
            "ca_1an": ca_1an,
            "ca_3ans": ca_3ans,
            "historique": client.historique.select_related("modifie_par")[:10],
        },
    )


@login_required
@liste_financiere_required
def detail_client(request, idabon):
    """Consultation en LECTURE SEULE des informations d'un client, ouverte à qui
    peut voir la vue financière (Direction comprise, contrairement à la fiche
    éditable réservée à la SDRCB). Répond au besoin de consulter un client depuis
    la vue financière sans droit d'édition."""
    client = get_object_or_404(
        Client.objects.filter(get_client_scope(request.user)).select_related("entite", "direction_regionale"),
        idabon=idabon,
    )
    ca_1an, ca_3ans = _calculer_ca_historique(client)
    agg = Recouvrement.objects.filter(client=client).aggregate(f=Sum("montant_facture"), p=Sum("montant_paye"))
    impaye_total = float(agg["f"] or 0) - float(agg["p"] or 0)

    return render(
        request,
        "clients/detail_client.html",
        {
            "client": client,
            "abonnements": client.abonnements.all(),
            "interlocuteurs": client.interlocuteurs.all(),
            "ca_1an": ca_1an,
            "ca_3ans": ca_3ans,
            "impaye_total": impaye_total,
            "nb_reclamations": client.reclamations.count(),
            "peut_editer": est_dans_sdrcb(request.user),
        },
    )


def _completion_str(client):
    """Nombre de critères de complétude renseignés (même définition que
    kpi_qualite_fiches et la colonne du portefeuille), sans requête supplémentaire."""
    n = sum([
        bool(client.secteur_activite),
        client.a_contrat is not None,
        bool(client.contrat_document) or bool(client.contrat_reference_physique),
    ])
    return f"{n}/3"


@login_required
def controle_fiches(request):
    """Contrôle par le Chef de Service (ou Sous-Directeur) des fiches complétées par
    ses Chargés d'Affaires, et consultation du taux de complétion contrôlé. Chaque
    validation marque la fiche contrôlée ; une modification ultérieure du Chargé la
    repasse « à contrôler » (cf. fiche_client)."""
    if not peut_controler_fiches(request.user):
        raise PermissionDenied("Réservé aux Chefs de Service et à la Sous-Direction Relation Clients Business.")

    scope = get_client_scope(request.user)

    if request.method == "POST":
        client = Client.objects.filter(scope, idabon=request.POST.get("controler", "")).first()
        if client is not None:
            client.fiche_controlee = True
            client.fiche_controlee_par = request.user
            client.fiche_controlee_le = timezone.now()
            client.save(update_fields=["fiche_controlee", "fiche_controlee_par", "fiche_controlee_le"])
            messages.success(request, f"Fiche de {client.nom_prenoms or client.idabon} contrôlée.")
        return redirect(f"{request.path}?{request.GET.urlencode()}")

    qs = Client.objects.filter(scope)
    completes_q = (
        Q(secteur_activite__gt="") & Q(a_contrat__isnull=False)
        & (Q(contrat_document__gt="") | Q(contrat_reference_physique__gt=""))
    )
    total = qs.count()
    stats = {
        "total": total,
        "completes": qs.filter(completes_q).count(),
        "controlees": qs.filter(fiche_controlee=True).count(),
        "a_controler": qs.filter(fiche_maj_le__isnull=False, fiche_controlee=False).count(),
    }
    stats["taux_completion"] = (stats["completes"] / total * 100) if total else 0
    stats["taux_controle"] = (stats["controlees"] / total * 100) if total else 0

    filtre = request.GET.get("filtre", "")
    liste = qs.select_related("entite", "direction_regionale", "fiche_maj_par")
    if filtre == "a_controler":
        liste = liste.filter(fiche_maj_le__isnull=False, fiche_controlee=False)
    elif filtre == "controlees":
        liste = liste.filter(fiche_controlee=True)
    elif filtre == "completes":
        liste = liste.filter(completes_q)

    page = Paginator(liste.order_by("nom_prenoms", "idabon"), 50).get_page(request.GET.get("page"))
    clients = [{"client": c, "completion": _completion_str(c)} for c in page]

    return render(
        request,
        "clients/controle_fiches.html",
        {"clients": clients, "page_obj": page, "stats": stats, "filtre": filtre},
    )


@login_required
def importer_clients_dcb(request):
    """Import in-app d'un nouvel export SAPHIR (format Client DCB.xlsx) : ajoute les
    nouveaux clients à la base maîtresse et enrichit les existants (sans écraser),
    via la même logique que la commande CLI. Réservé au Chef de Service / Sous-
    Directeur, car cela affecte la base partagée."""
    if not peut_controler_fiches(request.user):
        raise PermissionDenied("Réservé aux Chefs de Service et à la Sous-Direction Relation Clients Business.")

    resultat = None
    erreur = None
    if request.method == "POST" and request.FILES.get("fichier"):
        from importers.management.commands.import_clients_dcb_global import importer_dcb

        fichier = request.FILES["fichier"]
        df = None
        try:
            df = pd.read_excel(fichier, sheet_name="HT GLOBAL")
        except ValueError:
            try:
                fichier.seek(0)
                df = pd.read_excel(fichier)
            except Exception:
                df = None
        except Exception:
            df = None

        if df is None:
            erreur = "Fichier illisible : vérifiez qu'il s'agit d'un export SAPHIR au format Client DCB.xlsx."
        else:
            resultat = importer_dcb(df)
            messages.success(
                request,
                f"Import SAPHIR : {resultat['crees']} nouveaux clients ajoutés, {resultat['enrichis']} enrichis, "
                f"{resultat['interlocuteurs']} interlocuteurs créés.",
            )
            return redirect("clients:liste_portefeuille")

    return render(request, "clients/importer_clients_dcb.html", {"resultat": resultat, "erreur": erreur})


@login_required
@sdrcb_required
def proposer_client_strategique(request):
    """Le client doit déjà exister dans la base HT (import_clients_abonnements),
    on ne crée jamais un client de zéro ici, seulement le rattachement au
    portefeuille stratégique + portefeuille personnel, en attente de validation.

    Réservé au(x) Chargé(e)(s) du Service Stratégiques & Sensibles : ce n'est pas
    une capacité générale de tout Chargé d'Affaires SDRCB (demande utilisateur
    explicite, Abidjan/Intérieur ne proposent pas de client stratégique)."""
    if not peut_proposer_strategique(request.user):
        raise PermissionDenied("Réservé au(x) Chargé(e)(s) du Service Stratégiques & Sensibles.")

    resultat = None
    erreur = None
    if request.method == "POST":
        form = ProposerClientForm(request.POST)
        if form.is_valid():
            identifiant = form.cleaned_data["identifiant"].strip()
            client = (
                Client.objects.filter(idabon=identifiant).first()
                or Client.objects.filter(abonnements__refraccord=identifiant).first()
            )
            if client is None:
                erreur = "Aucun client trouvé avec cet IDABON ou cette référence de raccordement dans la base HT."
            elif client.est_strategique:
                erreur = f"{client.nom_prenoms or client.idabon} est déjà un client stratégique."
            elif client.strategique_en_attente:
                erreur = f"{client.nom_prenoms or client.idabon} est déjà proposé, en attente de validation."
            else:
                client.strategique_en_attente = True
                client.strategique_propose_par = request.user
                client.strategique_propose_le = timezone.now()
                client.charge_affaires = request.user
                client.save()
                resultat = client
                messages.success(
                    request,
                    f"{client.nom_prenoms or client.idabon} proposé comme client stratégique, en attente de validation.",
                )
                return redirect("clients:liste_portefeuille")
    else:
        form = ProposerClientForm()

    return render(request, "clients/proposer_client.html", {"form": form, "erreur": erreur, "resultat": resultat})


@login_required
@sdrcb_required
def valider_clients_strategiques(request):
    if not peut_valider_strategique(request.user):
        raise PermissionDenied("Réservé au Chef de Service / Sous-Directeur (validation des propositions).")

    if request.method == "POST":
        client = get_object_or_404(Client, pk=request.POST.get("client_id"))
        if request.POST.get("action") == "valider":
            from core.models import Entite  # import local : seul ce cas d'usage en a besoin

            client.est_strategique = True
            client.entite = Entite.objects.get(code=Entite.STRATEGIQUES_SENSIBLES)
            client.strategique_en_attente = False
            client.strategique_valide_par = request.user
            client.strategique_valide_le = timezone.now()
            client.save()
            messages.success(request, f"{client.nom_prenoms or client.idabon} validé comme client stratégique.")
        else:
            client.strategique_en_attente = False
            client.charge_affaires = None
            client.save()
            messages.warning(request, f"Proposition pour {client.nom_prenoms or client.idabon} refusée.")
        return redirect("clients:valider_clients_strategiques")

    propositions = Client.objects.filter(strategique_en_attente=True).select_related("strategique_propose_par")
    return render(request, "clients/valider_strategiques.html", {"propositions": propositions})


@login_required
def liste_strategiques_non_rattaches(request):
    """Clients de informations clients/dcb/liste_clients_strategiques.xlsx que
    l'import (import_clients_strategiques) n'a pas réussi à rattacher à un Client
    existant (IDABON erroné dans le fichier source, client jamais facturé...). Pas
    une anomalie silencieuse de log : visible ici pour que la Chargée du Service
    Stratégiques & Sensibles puisse investiguer elle-même (demande utilisateur
    explicite). Ouvert en lecture à la Direction aussi, même principe que
    liste_financiere_required."""
    profile = getattr(request.user, "profile", None)
    if not (peut_proposer_strategique(request.user) or (profile and profile.is_direction)):
        raise PermissionDenied("Réservé à la Direction et au Service Clients Stratégiques et Sensibles.")

    return render(
        request,
        "clients/liste_strategiques_non_rattaches.html",
        {"non_rattaches": ClientStrategiqueNonRattache.objects.all()},
    )


@login_required
@sdrcb_required
def exporter_portefeuille(request):
    qs = Client.objects.filter(get_client_scope(request.user)).prefetch_related("interlocuteurs", "abonnements")

    lignes = []
    for c in qs:
        abonnement = c.abonnements.first()
        ligne = {
            "IDABON": c.idabon,
            "Nom/Raison sociale": c.nom_prenoms,
            "Secteur d'activité": c.secteur_activite,
            "DR": c.direction_regionale.code if c.direction_regionale else "",
            "Stratégique": "Oui" if c.est_strategique else ("En attente" if c.strategique_en_attente else "Non"),
            "Contrat signé": {True: "Oui", False: "Non"}.get(c.a_contrat, ""),
            "Référence raccordement": abonnement.refraccord if abonnement else "",
            "Puissance souscrite (kW)": abonnement.psabon if abonnement else "",
            "Départ": abonnement.depart if abonnement else "",
            "Poste": abonnement.poste if abonnement else "",
        }
        for role, libelle in [("representant_legal", "Représentant légal"), ("technique", "Interlocuteur technique"), ("commercial", "Interlocuteur commercial")]:
            interlocuteur = next((i for i in c.interlocuteurs.all() if i.role == role), None)
            ligne[f"{libelle} - Nom"] = interlocuteur.nom if interlocuteur else ""
            ligne[f"{libelle} - Contact"] = interlocuteur.telephone if interlocuteur else ""
        lignes.append(ligne)

    df = pd.DataFrame(lignes)
    return excel_response(df, "portefeuille_clients.xlsx", sheet_name="Portefeuille", titre="Portefeuille clients — DCB")


@login_required
@sdrcb_required
def importer_fiches_clients(request):
    erreur = None
    if request.method == "POST" and request.FILES.get("fichier"):
        fichier = request.FILES["fichier"]
        try:
            # dtype=str sur IDABON : sinon, si la colonne ne contient que des
            # valeurs numériques, pandas l'infère en int64 et perd tout zéro de
            # tête avant même que importer_fiches_depuis_dataframe ne s'exécute.
            df = pd.read_excel(fichier, dtype={"IDABON": str})
        except Exception:
            df = None
        if df is None:
            erreur = "Fichier illisible : vérifiez qu'il s'agit bien d'un .xlsx."
        else:
            manquantes = colonnes_manquantes(df)
            if manquantes:
                erreur = f"Colonnes manquantes dans le fichier : {', '.join(manquantes)}."
            else:
                nb_maj, nb_introuvables = importer_fiches_depuis_dataframe(
                    df, get_client_scope(request.user), maj_par=request.user
                )
                messages.success(
                    request,
                    f"{nb_maj} fiches mises à jour ({nb_introuvables} IDABON introuvables dans votre portefeuille).",
                )
                return redirect("clients:liste_portefeuille")

    return render(request, "clients/importer_fiches.html", {"erreur": erreur})


# Tri par colonne, ordre par défaut décroissant : seul "tri" pilote la colonne,
# "dir" l'ordre (asc/desc), gardé séparé plutôt qu'un simple préfixe "-" devant
# le nom de colonne, pour que le lien de tri d'une colonne puisse basculer dir
# sans avoir à connaître le nom ORM réel.
CHAMP_PAR_TRI = {
    "idabon": "idabon",
    "nom": "nom_prenoms",
    "entite": "entite__libelle",
    "dr": "direction_regionale__code",
    "strategique": "est_strategique",
    "ca": "ca_total",
    "impaye": "impaye_total",
}


def _filtrer_trier_financiere(request):
    """Filtres + tri partagés entre liste_financiere (paginée, à l'écran) et
    exporter_financiere (export complet) : on ne veut surtout pas que l'export
    diverge silencieusement de ce que l'utilisateur a sous les yeux."""
    qs = Client.objects.filter(get_client_scope(request.user)).select_related("entite", "direction_regionale")

    entite_filtre = request.GET.get("entite", "")
    dr_filtre = request.GET.get("dr", "")
    strategique_filtre = request.GET.get("strategique", "")
    recherche = request.GET.get("q", "").strip()
    tri = request.GET.get("tri", "ca")
    direction_tri = request.GET.get("dir", "desc")

    if entite_filtre:
        qs = qs.filter(entite__code=entite_filtre)
    if dr_filtre:
        qs = qs.filter(direction_regionale__code=dr_filtre)
    if strategique_filtre == "oui":
        qs = qs.filter(est_strategique=True)
    elif strategique_filtre == "non":
        qs = qs.filter(est_strategique=False)
    if recherche:
        qs = qs.filter(Q(idabon__icontains=recherche) | Q(nom_prenoms__icontains=recherche))

    qs = qs.annotate(
        ca_total=Sum("factures__montant_facture_ttc"),
        impaye_total=Sum(F("recouvrements__montant_facture") - F("recouvrements__montant_paye")),
    )
    champ = CHAMP_PAR_TRI.get(tri, "ca_total")
    qs = qs.order_by(champ if direction_tri == "asc" else f"-{champ}")
    return qs, entite_filtre, dr_filtre, strategique_filtre, recherche, tri, direction_tri


@login_required
@liste_financiere_required
def liste_financiere(request):
    """Vue intégrale, filtrable et triable de "Top clients par CA" / "Clients
    critiques" : ces deux tableaux n'affichent que 10/20 lignes dans les
    dashboards (cf. performance_entite.py, engagement_direction.py/
    engagement_entite.py), avec un lien "Voir la liste complète" qui pointe ici.
    tri=ca ou tri=impaye (avec dir=asc/desc) reproduit ces mêmes ordres par
    défaut, mais toute colonne reste cliquable pour retrier.

    Filtres/tri mémorisés par utilisateur (demande utilisateur, cf. rapport
    "Fonctionnalités proposées") : une arrivée SANS aucun paramètre (lien de menu,
    pas un clic sur "Filtrer"/un en-tête) reprend les derniers réglages enregistrés
    sur le profil, plutôt que de toujours retomber sur les filtres par défaut."""
    if not request.GET and request.user.profile.preferences_filtres.get("financiere"):
        return redirect(f"{request.path}?{request.user.profile.preferences_filtres['financiere']}")
    if request.GET:
        querystring_sans_page = request.GET.copy()
        querystring_sans_page.pop("page", None)
        request.user.profile.preferences_filtres["financiere"] = querystring_sans_page.urlencode()
        request.user.profile.save(update_fields=["preferences_filtres"])

    qs, entite_filtre, dr_filtre, strategique_filtre, recherche, tri, direction_tri = _filtrer_trier_financiere(request)

    page = Paginator(qs, 50).get_page(request.GET.get("page"))

    return render(
        request,
        "clients/liste_financiere.html",
        {
            "page_obj": page,
            "tri": tri,
            "dir": direction_tri,
            "colonnes_tri": {
                "idabon": "IDABON",
                "nom": "Nom / Raison sociale",
                "entite": "Entité",
                "dr": "DR",
                "strategique": "Stratégique",
                "ca": "CA total (FCFA)",
                "impaye": "Impayé (FCFA)",
            },
            "entite_filtre": entite_filtre,
            "dr_filtre": dr_filtre,
            "strategique_filtre": strategique_filtre,
            "recherche": recherche,
            "entites_dispo": Entite.objects.filter(
                code__in=[Entite.ABIDJAN, Entite.INTERIEUR, Entite.STRATEGIQUES_SENSIBLES, Entite.ADMINISTRATION]
            ),
            "drs_dispo": DirectionRegionale.objects.all(),
        },
    )


@login_required
@liste_financiere_required
def exporter_financiere(request):
    """Export Excel de la liste financière, avec les MÊMES filtres/tri que la
    page à l'écran (cf. _filtrer_trier_financiere) : sans pagination, contrairement
    à liste_financiere, pour récupérer l'intégralité du résultat filtré, pas
    seulement la page affichée."""
    qs, *_rest = _filtrer_trier_financiere(request)

    lignes = [
        {
            "IDABON": c.idabon,
            "Nom/Raison sociale": c.nom_prenoms,
            "Entité": str(c.entite) if c.entite else "",
            "DR": c.direction_regionale.code if c.direction_regionale else "",
            "Stratégique": "Oui" if c.est_strategique else "Non",
            "CA total (FCFA)": c.ca_total or 0,
            "Impayé (FCFA)": c.impaye_total or 0,
        }
        for c in qs
    ]

    df = pd.DataFrame(lignes)
    return excel_response(df, "vue_financiere_clients.xlsx", sheet_name="Vue financière", titre="Vue financière clients — DCB")
