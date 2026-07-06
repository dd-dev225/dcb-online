"""Dashboard Performance : vue Entité (Service réel : Abidjan, Intérieur,
Stratégiques&Sensibles...). get_scope_filter restreint automatiquement toutes les
requêtes à l'entité de l'utilisateur connecté, un compte Entite ne voit jamais
les données des autres services. Disposition en grille façon SB Admin 2, cf.
dashboards/dash_apps/_components.py (palette CIE, courbes lissées + degradé)."""

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dash_table, dcc, html
from dash.dependencies import Input, Output
from django_plotly_dash import DjangoDash

from dashboards import data
from dashboards.dash_apps._components import BLUE, CIE_STYLESHEET, ORANGE, apply_compact_layout, chart_card, choropleth_dr, graph, smoothed_area_trace, stat_card

app = DjangoDash("PerformanceEntite", external_stylesheets=[CIE_STYLESHEET])

app.layout = dbc.Container(
    [
        dcc.Dropdown(
            id="pe-n-mois",
            options=[{"label": f"{n} derniers mois", "value": n} for n in (3, 6, 12, 24)],
            value=12,
            clearable=False,
            className="mb-4",
            style={"width": "260px"},
        ),

        # md=4 directement (pas de palier xl=4 intermédiaire) : avec 3 cartes, un
        # palier md=6 (2 par ligne) laisserait la 3e carte seule sur une ligne à
        # moitié vide entre les largeurs md et xl, un seul palier élimine ce trou.
        dbc.Row(
            [
                dbc.Col(dbc.Spinner(html.Div(id="pe-kpi-ca")), width=12, md=4),
                dbc.Col(dbc.Spinner(html.Div(id="pe-kpi-energie")), width=12, md=4),
                dbc.Col(dbc.Spinner(html.Div(id="pe-kpi-non-facturation")), width=12, md=4),
            ],
        ),

        dbc.Row(
            [
                dbc.Col(chart_card("Évolution du CA facturé", graph("pe-ca-evolution"), icon="fa-chart-area"), width=12, md=8),
                dbc.Col(chart_card("Énergie facturée (MWh)", graph("pe-energie"), icon="fa-chart-bar"), width=12, md=4),
            ],
            className="mb-2",
        ),

        dbc.Row(
            dbc.Col(chart_card("Répartition géographique du CA par DR", graph("pe-carte-dr"), icon="fa-map-marked-alt"), width=12),
            className="mb-2",
        ),

        dbc.Row(
            dbc.Col(
                chart_card(
                    "Top clients par CA",
                    html.Div(
                        [
                            dash_table.DataTable(
                                id="pe-top-clients",
                                page_size=10,
                                sort_action="native",
                                style_as_list_view=True,
                                style_header={"fontWeight": "bold"},
                            ),
                            # target="_blank" : on est dans l'iframe sandboxée du dashboard
                            # (sandbox="... allow-popups ...", SANS allow-top-navigation,
                            # cf. django_plotly_dash/templatetags/plotly_dash.py), un lien
                            # target="_top"/"_parent" y est silencieusement bloqué par le
                            # navigateur (aucune erreur, le clic ne fait rien). allow-popups
                            # est en revanche déjà autorisé, donc on ouvre un nouvel onglet.
                            html.A(
                                [html.I(className="fas fa-list mr-1"), "Voir la liste complète (avec filtres)"],
                                href="/financiere/?tri=ca",
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
    Output("pe-kpi-ca", "children"),
    Output("pe-kpi-energie", "children"),
    Output("pe-kpi-non-facturation", "children"),
    Output("pe-ca-evolution", "figure"),
    Output("pe-energie", "figure"),
    Output("pe-carte-dr", "figure"),
    Output("pe-top-clients", "data"),
    Output("pe-top-clients", "columns"),
    [Input("pe-n-mois", "value")],
)
def update(n_mois, **kwargs):
    user = kwargs["user"]

    periode_ca, ca_mds, delta_ca = data.kpi_ca_dernier_mois_avec_delta(user)
    kpi_ca = stat_card("CA du mois" + (f" ({periode_ca})" if periode_ca else ""),
                        f"{ca_mds:,.1f} Mds FCFA".replace(",", " ") if ca_mds is not None else "—",
                        "fa-coins", "primary", delta_pct=delta_ca)

    energie, delta_energie = data.kpi_energie_dernier_mois_avec_delta(user)
    kpi_energie = stat_card("Énergie facturée (MWh, dernier mois)",
                             f"{energie:,.0f}".replace(",", " ") if energie is not None else "—",
                             "fa-bolt", "warning", delta_pct=delta_energie)

    taux_nf = data.taux_non_facturation(user)
    kpi_nf = stat_card("Taux de non-facturation",
                        f"{taux_nf * 100:.1f}%" if taux_nf is not None else "—",
                        "fa-file-invoice", "info")

    labels, ca = data.ca_evolution(user, n_periodes=n_mois)
    fig_ca = go.Figure(smoothed_area_trace(labels, ca, ORANGE, hover_suffix=" FCFA"))
    apply_compact_layout(fig_ca, yaxis_title="FCFA", angle_ticks=True)

    labels_e, mwh = data.energie_evolution(user, n_periodes=n_mois)
    fig_energie = go.Figure(
        go.Bar(x=labels_e, y=mwh, marker_color=BLUE, hovertemplate="%{x}<br><b>%{y:,.0f} MWh</b><extra></extra>")
    )
    apply_compact_layout(fig_energie, yaxis_title="MWh", angle_ticks=True)

    fig_carte = choropleth_dr(data.ca_par_dr(user), colorbar_titre="CA (FCFA)", hover_suffix=" FCFA")

    top = data.top_clients_ca(user, limit=10)
    columns = [
        {"name": "Client (IDABON)", "id": "client__idabon"},
        {"name": "Nom/Raison sociale", "id": "client__nom_prenoms"},
        {"name": "CA (FCFA)", "id": "ca"},
    ]

    return kpi_ca, kpi_energie, kpi_nf, fig_ca, fig_energie, fig_carte, top, columns
