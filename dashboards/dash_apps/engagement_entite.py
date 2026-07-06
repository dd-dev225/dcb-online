"""Dashboard Engagement : vue Entité. Mêmes indicateurs que engagement_direction,
mais get_scope_filter restreint chaque requête à l'entité de l'utilisateur, c'est
ce dashboard qui démontre concrètement le "pilotage différencié" par service réel
de la DCB (Abidjan / Intérieur / Stratégiques&Sensibles / ...). Disposition en
grille façon SB Admin 2, cf. dashboards/dash_apps/_components.py (palette CIE,
hauteur compacte, barre d'outils masquée)."""

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dash_table, dcc, html
from dash.dependencies import Input, Output
from django_plotly_dash import DjangoDash

from dashboards import data
from dashboards.dash_apps._components import (
    CIE_STYLESHEET,
    ORANGE,
    apply_compact_layout,
    apply_horizontal_bar_layout,
    chart_card,
    choropleth_dr,
    graph,
    horizontal_bar_trace,
    stat_card,
)

app = DjangoDash("EngagementEntite", external_stylesheets=[CIE_STYLESHEET])

app.layout = dbc.Container(
    [
        # md=4 directement (pas de palier xl=3 intermédiaire) : avec 3 cartes, un
        # palier à 2 ou 4 par ligne (md=6/xl=3) laisse toujours une ligne à moitié
        # vide, un seul palier à 3 par ligne élimine ce trou à toute largeur.
        dbc.Row(
            [
                dbc.Col(dbc.Spinner(html.Div(id="ee-kpi-reclamations")), width=12, md=4),
                dbc.Col(dbc.Spinner(html.Div(id="ee-kpi-traitement")), width=12, md=4),
                dbc.Col(dbc.Spinner(html.Div(id="ee-kpi-demandes-cours")), width=12, md=4),
            ],
        ),
        dbc.Row(
            [
                dbc.Col(dbc.Spinner(html.Div(id="ee-kpi-dmr")), width=12, md=6),
                dbc.Col(dbc.Spinner(html.Div(id="ee-kpi-hors-delai")), width=12, md=6),
            ],
            className="mb-2",
        ),

        dbc.Row(
            [
                dbc.Col(chart_card("Demandes de mon entité par tranche de délai", graph("ee-delais-raccordement"), icon="fa-chart-bar"), width=12, md=6),
                dbc.Col(chart_card("Réclamations de mon entité par segment de client", graph("ee-reclamations-type"), icon="fa-chart-bar"), width=12, md=6),
            ],
            className="mb-2",
        ),

        dbc.Row(
            dbc.Col(chart_card("Répartition géographique des réclamations par DR", graph("ee-carte-dr"), icon="fa-map-marked-alt"), width=12),
            className="mb-2",
        ),

        dbc.Row(
            dbc.Col(
                chart_card(
                    "Clients critiques de mon entité (impayé décroissant)",
                    html.Div(
                        [
                            dash_table.DataTable(id="ee-clients-critiques", page_size=15, sort_action="native",
                                                  style_as_list_view=True, style_header={"fontWeight": "bold"}),
                            # target="_blank" : on est dans l'iframe sandboxée du dashboard
                            # (sandbox="... allow-popups ...", SANS allow-top-navigation,
                            # cf. django_plotly_dash/templatetags/plotly_dash.py), un lien
                            # target="_top"/"_parent" y est silencieusement bloqué par le
                            # navigateur (aucune erreur, le clic ne fait rien). allow-popups
                            # est en revanche déjà autorisé, donc on ouvre un nouvel onglet.
                            html.A(
                                [html.I(className="fas fa-list mr-1"), "Voir la liste complète (avec filtres)"],
                                href="/financiere/?tri=impaye&strategique=oui",
                                target="_blank",
                                className="btn btn-sm btn-outline-danger mt-2",
                            ),
                        ]
                    ),
                    icon="fa-table",
                ),
                width=12,
            ),
        ),

        dcc.Interval(id="ee-init", n_intervals=0, max_intervals=1, interval=1),
    ],
    fluid=True,
)


@app.expanded_callback(
    Output("ee-kpi-reclamations", "children"),
    Output("ee-kpi-traitement", "children"),
    Output("ee-kpi-demandes-cours", "children"),
    Output("ee-kpi-dmr", "children"),
    Output("ee-kpi-hors-delai", "children"),
    Output("ee-delais-raccordement", "figure"),
    Output("ee-reclamations-type", "figure"),
    Output("ee-carte-dr", "figure"),
    Output("ee-clients-critiques", "data"),
    Output("ee-clients-critiques", "columns"),
    [Input("ee-init", "n_intervals")],
)
def update(_n, **kwargs):
    user = kwargs["user"]

    nb_reclam = data.kpi_nb_reclamations(user)
    kpi_reclam = stat_card("Réclamations (total)", f"{nb_reclam:,}".replace(",", " "), "fa-comment-dots", "danger")

    taux = data.taux_traitement_reclamations(user)
    kpi_taux = stat_card("Taux de traitement réclamations",
                          f"{taux * 100:.1f}%" if taux is not None else "—",
                          "fa-check-circle", "success")

    nb_en_cours = data.kpi_nb_demandes_en_cours(user)
    kpi_en_cours = stat_card("Demandes de raccordement en cours", f"{nb_en_cours:,}".replace(",", " "),
                              "fa-tools", "warning")

    dmr = data.kpi_dmr(user)
    kpi_dmr = stat_card("DMR (délai moyen de traitement)", f"{dmr:.1f} j" if dmr is not None else "—",
                         "fa-stopwatch", "primary")

    taux_hd, nb_hd, nb_avec_delai = data.kpi_taux_reclamations_hors_delai(user)
    kpi_hors_delai = stat_card(
        "Taux de réclamations Hors Délai (> 5j)",
        f"{taux_hd * 100:.0f}% ({nb_hd}/{nb_avec_delai})" if taux_hd is not None else "—",
        "fa-exclamation-triangle", "danger",
    )

    tranches, nb = data.delais_raccordement_par_tranche(user)
    fig_delais = go.Figure(
        go.Bar(x=tranches, y=nb, marker_color=ORANGE, hovertemplate="%{x}<br><b>%{y} demandes</b><extra></extra>")
    )
    apply_compact_layout(fig_delais, yaxis_title="Nb demandes", angle_ticks=True)

    labels_seg, nb_seg = data.reclamations_par_segment_client(user)
    fig_reclam = go.Figure(horizontal_bar_trace(labels_seg, nb_seg, "#E74A3B", hover_suffix=" réclamations"))
    apply_horizontal_bar_layout(fig_reclam, xaxis_title="Nb réclamations")

    fig_carte = choropleth_dr(data.reclamations_par_dr(user), colorbar_titre="Réclamations", colorscale="Reds", hover_suffix=" réclamations")

    critiques = data.clients_critiques(user, limit=20)
    columns = [
        {"name": "Client (IDABON)", "id": "client__idabon"},
        {"name": "Nom/Raison sociale", "id": "client__nom_prenoms"},
        {"name": "Impayé (FCFA)", "id": "impaye"},
    ]

    return kpi_reclam, kpi_taux, kpi_en_cours, kpi_dmr, kpi_hors_delai, fig_delais, fig_reclam, fig_carte, critiques, columns
