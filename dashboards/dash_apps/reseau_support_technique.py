"""Dashboard "Qualité du réseau" de la Sous-Direction Support Technique Business.

Source des données : incidents (pannes/perturbations, INCIBCC) et travaux
programmés (MANTBCC) sur le réseau HTA/HTB, cf. reseau.models et reseau.data.
Reproduit, avec de vraies données plutôt que des chiffres figés sur une seule
date, la logique du reporting mensuel "Perturbation en Zone Industrielle"
(informations clients/dcb/Support Technique/PERTURBATION EN ZONE INDUSTRIELLE
- MR AKITIKPA.pptx) : suivi des incidents par zone industrielle prioritaire et
des départs les plus perturbés.

Contrairement aux autres dash apps (cf. dashboards/dash_apps/_components.py),
ces données ne sont pas scopées par utilisateur (reseau.data n'a pas
d'équivalent get_scope_filter) : le contrôle d'accès est fait une fois, au
niveau de la vue Django qui sert cette page
(dashboards.views.support_technique_required), pas ligne à ligne ici."""

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dash_table, dcc, html
from dash.dependencies import Input, Output
from django_plotly_dash import DjangoDash

from dashboards.dash_apps._components import (
    BLUE,
    CIE_STYLESHEET,
    GREEN,
    ORANGE,
    PIE_SEQUENCE,
    apply_compact_layout,
    apply_horizontal_bar_layout,
    chart_card,
    choropleth_dr,
    graph,
    horizontal_bar_trace,
    stat_card,
)
from reseau import data

app = DjangoDash("ReseauSupportTechnique", external_stylesheets=[CIE_STYLESHEET])

app.layout = dbc.Container(
    [
        dcc.Dropdown(
            id="rst-n-mois",
            options=[{"label": f"{n} derniers mois", "value": n} for n in (3, 6, 12, 24)],
            value=12,
            clearable=False,
            className="mb-4",
            style={"width": "260px"},
        ),

        dbc.Row(
            [
                dbc.Col(dbc.Spinner(html.Div(id="rst-kpi-incidents")), width=12, md=6, xl=3),
                dbc.Col(dbc.Spinner(html.Div(id="rst-kpi-duree")), width=12, md=6, xl=3),
                dbc.Col(dbc.Spinner(html.Div(id="rst-kpi-end")), width=12, md=6, xl=3),
                dbc.Col(dbc.Spinner(html.Div(id="rst-kpi-travaux")), width=12, md=6, xl=3),
            ],
        ),

        dbc.Row(
            [
                dbc.Col(chart_card("Évolution mensuelle des incidents", graph("rst-evolution"), icon="fa-chart-area"), width=12, md=8),
                dbc.Col(chart_card("Incidents par zone industrielle", graph("rst-par-zone"), icon="fa-chart-pie"), width=12, md=4),
            ],
            className="mb-2",
        ),

        dbc.Row(
            [
                dbc.Col(chart_card("Départs les plus perturbés", graph("rst-top-departs"), icon="fa-chart-bar"), width=12, md=6),
                dbc.Col(chart_card("Causes principales", graph("rst-causes"), icon="fa-chart-bar"), width=12, md=6),
            ],
            className="mb-2",
        ),

        dbc.Row(
            dbc.Col(chart_card("Répartition géographique des incidents par DR", graph("rst-carte-dr"), icon="fa-map-marked-alt"), width=12),
            className="mb-2",
        ),

        dbc.Row(
            dbc.Col(
                chart_card(
                    "Incidents les plus récents",
                    html.Div(
                        [
                            dash_table.DataTable(
                                id="rst-incidents-table", page_size=15, sort_action="native",
                                style_as_list_view=True, style_header={"fontWeight": "bold"},
                            ),
                            # target="_blank" : cf. note sandbox iframe dans les autres
                            # dash apps (engagement_entite.py et al.).
                            html.A(
                                [html.I(className="fas fa-list mr-1"), "Voir la liste complète (avec filtres)"],
                                href="/reseau/incidents/",
                                target="_blank",
                                className="btn btn-sm btn-outline-primary mt-2",
                            ),
                        ]
                    ),
                    icon="fa-table",
                ),
                width=12,
            ),
        ),
    ],
    fluid=True,
)


@app.expanded_callback(
    Output("rst-kpi-incidents", "children"),
    Output("rst-kpi-duree", "children"),
    Output("rst-kpi-end", "children"),
    Output("rst-kpi-travaux", "children"),
    Output("rst-evolution", "figure"),
    Output("rst-par-zone", "figure"),
    Output("rst-top-departs", "figure"),
    Output("rst-causes", "figure"),
    Output("rst-carte-dr", "figure"),
    Output("rst-incidents-table", "data"),
    Output("rst-incidents-table", "columns"),
    [Input("rst-n-mois", "value")],
)
def update(n_mois, **kwargs):
    nb_incidents = data.kpi_nb_incidents(n_mois)
    kpi_incidents = stat_card("Incidents réseau", f"{nb_incidents:,}".replace(",", " "), "fa-bolt", "danger")

    duree = data.kpi_duree_moyenne_minutes(n_mois)
    kpi_duree = stat_card("Durée moyenne de coupure", f"{duree:.0f} min" if duree is not None else "—",
                           "fa-clock", "warning")

    end_mwh = data.kpi_energie_non_distribuee_mwh(n_mois)
    kpi_end = stat_card("Énergie non distribuée", f"{end_mwh:,.1f} MWh".replace(",", " "), "fa-plug", "primary")

    nb_travaux = data.kpi_nb_travaux(n_mois)
    kpi_travaux = stat_card("Travaux programmés", f"{nb_travaux:,}".replace(",", " "), "fa-tools", "info")

    serie = data.incidents_evolution_mensuelle(n_mois)
    labels_evol = [f"{m:02d}/{a}" for a, m, _ in serie]
    valeurs_evol = [n for _, _, n in serie]
    fig_evol = go.Figure(go.Bar(x=labels_evol, y=valeurs_evol, marker_color=ORANGE,
                                 hovertemplate="%{x}<br><b>%{y} incidents</b><extra></extra>"))
    apply_compact_layout(fig_evol, yaxis_title="Nb incidents", angle_ticks=True)

    zones = data.incidents_par_zone(n_mois)
    fig_zone = go.Figure(
        go.Pie(labels=[z for z, _ in zones], values=[n for _, n in zones], hole=0.55,
               marker={"colors": PIE_SEQUENCE}, textinfo="percent",
               hovertemplate="%{label}<br>%{value} incidents<extra></extra>")
    ) if zones else go.Figure()
    apply_compact_layout(fig_zone)
    fig_zone.update_layout(legend={"orientation": "h", "y": -0.1})

    top_departs = data.top_departs_perturbes(n_mois, limite=10)
    fig_top = go.Figure(
        horizontal_bar_trace(
            [f"{nom} ({poste})" for nom, poste, _ in top_departs],
            [n for _, _, n in top_departs],
            GREEN,
            hover_suffix=" incidents",
        )
    )
    apply_horizontal_bar_layout(fig_top, xaxis_title="Nb incidents")

    causes = data.causes_principales(n_mois)
    fig_causes = go.Figure(
        horizontal_bar_trace([c for c, _ in causes], [n for _, n in causes], BLUE, hover_suffix=" incidents")
    )
    apply_horizontal_bar_layout(fig_causes, xaxis_title="Nb incidents")

    fig_carte = choropleth_dr(dict(data.incidents_par_dr(n_mois)), colorbar_titre="Incidents", colorscale="Reds", hover_suffix=" incidents")

    from reseau.models import IncidentReseau

    derniers = list(
        IncidentReseau.objects.filter(date_heure_debut__isnull=False)
        .order_by("-date_heure_debut")
        .values("numero_incident", "direction_regionale__code", "nom_depart", "date_heure_debut", "duree_minutes", "cause")[:50]
    )
    table_data = [
        {
            "numero_incident": d["numero_incident"],
            "dr": d["direction_regionale__code"] or "—",
            "nom_depart": d["nom_depart"],
            "date_heure_debut": d["date_heure_debut"].strftime("%d/%m/%Y %H:%M") if d["date_heure_debut"] else "—",
            "duree_minutes": d["duree_minutes"] if d["duree_minutes"] is not None else "—",
            "cause": d["cause"] or "—",
        }
        for d in derniers
    ]
    columns = [
        {"name": "N° incident", "id": "numero_incident"},
        {"name": "DR", "id": "dr"},
        {"name": "Départ", "id": "nom_depart"},
        {"name": "Début", "id": "date_heure_debut"},
        {"name": "Durée (min)", "id": "duree_minutes"},
        {"name": "Cause", "id": "cause"},
    ]

    return (
        kpi_incidents, kpi_duree, kpi_end, kpi_travaux,
        fig_evol, fig_zone, fig_top, fig_causes, fig_carte,
        table_data, columns,
    )
