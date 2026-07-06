"""Dashboard de pilotage de la Sous-Direction Guichet Unique CIE-SODECI (SDGU).

Métier différent du reste de la DCB (pas de Client/Facture, cf.
prospection.models) : ici le pilotage porte sur la PROSPECTION immobilière en
amont de toute demande formelle (recensement_sdgu.xlsx, info.txt) : nombre
d'immeubles suivis, taux de conversion en demande CIE/SODECI (indicateur de
réussite mis en avant par la SDGU elle-même), répartition géographique par
quartier, par stade d'avancement et par hauteur de bâtiment (cible prioritaire
R+5 et plus), portefeuille par commercial. Une page à part plutôt qu'intégrée à
Performance/Engagement (décision produit) : le Directeur garde malgré tout une
vue de synthèse via une carte dédiée sur Performance-Direction.
"""

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dash_table, dcc, html
from dash.dependencies import Input, Output
from django_plotly_dash import DjangoDash

from dashboards import data
from dashboards.dash_apps._components import (
    BLUE,
    CIE_STYLESHEET,
    GREEN,
    ORANGE,
    PIE_SEQUENCE,
    apply_compact_layout,
    apply_horizontal_bar_layout,
    chart_card,
    graph,
    horizontal_bar_trace,
    stat_card,
)

app = DjangoDash("ProspectionGuichetUnique", external_stylesheets=[CIE_STYLESHEET])

app.layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(dbc.Spinner(html.Div(id="pgu-kpi-immeubles")), width=12, md=6, xl=3),
                dbc.Col(dbc.Spinner(html.Div(id="pgu-kpi-prioritaires")), width=12, md=6, xl=3),
                dbc.Col(dbc.Spinner(html.Div(id="pgu-kpi-conversion-cie")), width=12, md=6, xl=3),
                dbc.Col(dbc.Spinner(html.Div(id="pgu-kpi-conversion-sodeci")), width=12, md=6, xl=3),
            ],
        ),

        dbc.Row(
            [
                dbc.Col(chart_card("Immeubles suivis par quartier", graph("pgu-zone"), icon="fa-map-marker-alt"), width=12, md=8),
                dbc.Col(chart_card("Stade d'avancement des travaux", graph("pgu-stade"), icon="fa-chart-pie"), width=12, md=4),
            ],
            className="mb-2",
        ),

        dbc.Row(
            [
                dbc.Col(chart_card("Répartition par hauteur de bâtiment", graph("pgu-niveaux"), icon="fa-building"), width=12, md=6),
                # Masqué pour la Direction (cf. callback) : "Portefeuille par commercial" est
                # une donnée d'affectation interne à la Sous-Direction (qui gère quel
                # immeuble), pas un indicateur de pilotage global, demande utilisateur
                # explicite. dbc.Col accepte un id directement, pas besoin d'un wrapper Div
                # qui casserait la grille Bootstrap (col-12 col-md-6).
                dbc.Col(
                    chart_card("Portefeuille par commercial", graph("pgu-portefeuille"), icon="fa-users"),
                    id="pgu-portefeuille-col",
                    width=12,
                    md=6,
                ),
            ],
            className="mb-2",
        ),

        dbc.Row(
            dbc.Col(
                chart_card(
                    "Cibles prioritaires à relancer (R+5 et plus, sans poste ni demande CIE)",
                    dash_table.DataTable(
                        id="pgu-a-prioriser",
                        page_size=10,
                        sort_action="native",
                        style_as_list_view=True,
                        style_header={"fontWeight": "bold"},
                        style_cell={"textAlign": "left"},
                    ),
                    icon="fa-exclamation-triangle",
                ),
                width=12,
            ),
        ),

        dcc.Interval(id="pgu-init", n_intervals=0, max_intervals=1, interval=1),
    ],
    fluid=True,
)


@app.expanded_callback(
    Output("pgu-kpi-immeubles", "children"),
    Output("pgu-kpi-prioritaires", "children"),
    Output("pgu-kpi-conversion-cie", "children"),
    Output("pgu-kpi-conversion-sodeci", "children"),
    Output("pgu-zone", "figure"),
    Output("pgu-stade", "figure"),
    Output("pgu-niveaux", "figure"),
    Output("pgu-portefeuille", "figure"),
    Output("pgu-portefeuille-col", "style"),
    Output("pgu-a-prioriser", "data"),
    Output("pgu-a-prioriser", "columns"),
    [Input("pgu-init", "n_intervals")],
)
def update(_n, **kwargs):
    user = kwargs["user"]
    profile = getattr(user, "profile", None)
    # "Portefeuille par commercial" = affectation interne (qui gère quel
    # immeuble) : utile au Sous-Directeur/à l'équipe pour répartir le travail,
    # mais pas un indicateur de pilotage pour la Direction (demande explicite).
    style_portefeuille = {"display": "none"} if (profile and profile.is_direction) else {}

    nb_immeubles = data.kpi_nb_immeubles_prospectes(user)
    kpi_immeubles = stat_card("Immeubles suivis", f"{nb_immeubles:,}".replace(",", " "), "fa-city", "primary")

    nb_prioritaires = data.kpi_nb_cibles_prioritaires(user)
    kpi_prioritaires = stat_card("Cibles prioritaires (R+5 et +)", f"{nb_prioritaires:,}".replace(",", " "), "fa-bullseye", "warning")

    taux_cie = data.kpi_taux_conversion_cie(user)
    kpi_conv_cie = stat_card("Taux de conversion → demande CIE", f"{taux_cie * 100:.0f}%" if taux_cie is not None else "—", "fa-bolt", "success")

    taux_sodeci = data.kpi_taux_conversion_sodeci(user)
    kpi_conv_sodeci = stat_card("Taux de conversion → demande SODECI", f"{taux_sodeci * 100:.0f}%" if taux_sodeci is not None else "—", "fa-tint", "info")

    zones, nb_zones = data.repartition_par_zone(user, top_n=10)
    fig_zone = go.Figure(horizontal_bar_trace(zones, nb_zones, ORANGE, hover_suffix=" immeubles"))
    apply_horizontal_bar_layout(fig_zone, xaxis_title="Nb immeubles", height=340)

    stades, nb_stades = data.repartition_par_stade(user)
    fig_stade = go.Figure(go.Pie(labels=stades, values=nb_stades, hole=0.55, marker={"colors": PIE_SEQUENCE}, textinfo="percent"))
    apply_compact_layout(fig_stade, height=340)  # même hauteur que pgu-zone (même rangée), espacement régulier
    fig_stade.update_layout(legend={"orientation": "h", "y": -0.1})

    tranches, nb_tranches = data.repartition_par_tranche_niveaux(user)
    fig_niveaux = go.Figure(go.Bar(x=tranches, y=nb_tranches, marker_color=GREEN, hovertemplate="%{x}<br><b>%{y} immeubles</b><extra></extra>"))
    apply_compact_layout(fig_niveaux, yaxis_title="Nb immeubles")

    commerciaux, nb_par_commercial = data.portefeuille_par_commercial(user)
    fig_portefeuille = go.Figure(horizontal_bar_trace(commerciaux, nb_par_commercial, BLUE, hover_suffix=" immeubles", max_len=40))
    apply_horizontal_bar_layout(fig_portefeuille, xaxis_title="Nb immeubles")

    a_prioriser = data.immeubles_a_prioriser(user, limit=20)
    columns = [
        {"name": "Structure", "id": "nom_structure"},
        {"name": "Quartier", "id": "zone_prospection"},
        {"name": "Hauteur", "id": "nb_niveaux"},
        {"name": "Interlocuteur", "id": "interlocuteur"},
        {"name": "Contact", "id": "contact"},
    ]

    return (
        kpi_immeubles, kpi_prioritaires, kpi_conv_cie, kpi_conv_sodeci,
        fig_zone, fig_stade, fig_niveaux, fig_portefeuille, style_portefeuille,
        a_prioriser, columns,
    )
