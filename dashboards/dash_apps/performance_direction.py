"""Dashboard Performance : vue Direction (agrégée, multi-entités).

Disposition reprise du template Bootstrap (SB Admin 2) : une rangée de "stat
cards" à liseré coloré (4 indicateurs clés du dernier mois), puis des cartes
graphiques organisées en grille (8/4, 6/6, 12) plutôt qu'empilées en une seule
colonne, cf. dashboards/dash_apps/_components.py pour les briques réutilisées
(palette CIE, courbes lissées + degradé, hauteur compacte, barre d'outils masquée).

Pas de restriction de queryset pour un compte du groupe Direction (cf.
comptes.scoping.get_scope_filter) : tous les graphiques couvrent l'ensemble du
périmètre Business. Le seul filtre interactif en V1 est la fenêtre temporelle
(nombre de mois affichés) ; le scoping par utilisateur passe par kwargs['user']
fourni par expanded_callback (django-plotly-dash).
"""

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output
from django_plotly_dash import DjangoDash

from dashboards import data
from dashboards.geo import dr_centroids, dr_geojson
from dashboards.dash_apps._components import (
    BLUE,
    CIE_STYLESHEET,
    GRAY,
    GREEN,
    ORANGE,
    PIE_SEQUENCE,
    apply_compact_layout,
    chart_card,
    graph,
    smoothed_area_trace,
    stat_card,
)

app = DjangoDash("PerformanceDirection", external_stylesheets=[CIE_STYLESHEET])

app.layout = dbc.Container(
    [
        dcc.Dropdown(
            id="pd-n-mois",
            options=[{"label": f"{n} derniers mois", "value": n} for n in (3, 6, 12, 24)],
            value=12,
            clearable=False,
            className="mb-4",
            style={"width": "260px"},
        ),

        # Rangée de stat cards (4 KPIs clés du dernier mois, façon SB Admin 2).
        dbc.Row(
            [
                dbc.Col(dbc.Spinner(html.Div(id="pd-kpi-ca")), width=12, md=6, xl=3),
                dbc.Col(dbc.Spinner(html.Div(id="pd-kpi-clients")), width=12, md=6, xl=3),
                dbc.Col(dbc.Spinner(html.Div(id="pd-kpi-energie")), width=12, md=6, xl=3),
                dbc.Col(dbc.Spinner(html.Div(id="pd-kpi-recouvrement")), width=12, md=6, xl=3),
            ],
        ),

        # CA (8 colonnes) + répartition par entité (4 colonnes).
        dbc.Row(
            [
                dbc.Col(chart_card("Évolution du CA facturé", graph("pd-ca-evolution"), icon="fa-chart-area"), width=12, md=8),
                dbc.Col(chart_card("Répartition du CA par Entité", graph("pd-ca-par-entite"), icon="fa-chart-pie"), width=12, md=4),
            ],
            className="mb-2",
        ),

        # Recouvrement par DR (6) + Base clients (6).
        dbc.Row(
            [
                dbc.Col(chart_card("Taux de recouvrement par DR", graph("pd-recouvrement-dr"), icon="fa-chart-bar"), width=12, md=6),
                dbc.Col(chart_card("Évolution de la base clients", graph("pd-base-clients"), icon="fa-chart-area"), width=12, md=6),
            ],
            className="mb-2",
        ),

        # Carte : répartition géographique du CA par DR (pleine largeur).
        dbc.Row(
            dbc.Col(chart_card("Répartition géographique du CA par DR", graph("pd-carte-dr"), icon="fa-map-marked-alt"), width=12),
            className="mb-2",
        ),

        # Énergie (pleine largeur).
        dbc.Row(
            dbc.Col(chart_card("Énergie facturée (MWh)", graph("pd-energie"), icon="fa-chart-bar"), width=12),
            className="mb-2",
        ),

        # Synthèse Guichet Unique : métier à part (prospection, pas de CA/Client),
        # donc pas de graphique détaillé ici (cf. dashboards.dash_apps.
        # prospection_guichet_unique), juste de quoi garder "les grandes lignes"
        # sans dupliquer son propre tableau de bord.
        dbc.Row(
            dbc.Col(html.H6([html.I(className="fas fa-city mr-2"), "Guichet Unique : synthèse"], className="text-gray-600 mt-2 mb-3"), width=12),
        ),
        # md=6 sans palier xl=3 : avec seulement 2 cartes, un palier à 4 par ligne
        # à partir de xl laisserait la moitié de la ligne vide à cette largeur.
        dbc.Row(
            [
                dbc.Col(dbc.Spinner(html.Div(id="pd-kpi-gu-immeubles")), width=12, md=6),
                dbc.Col(dbc.Spinner(html.Div(id="pd-kpi-gu-conversion")), width=12, md=6),
            ],
        ),
    ],
    fluid=True,
)


@app.expanded_callback(
    Output("pd-kpi-ca", "children"),
    Output("pd-kpi-clients", "children"),
    Output("pd-kpi-energie", "children"),
    Output("pd-kpi-recouvrement", "children"),
    Output("pd-ca-evolution", "figure"),
    Output("pd-ca-par-entite", "figure"),
    Output("pd-recouvrement-dr", "figure"),
    Output("pd-base-clients", "figure"),
    Output("pd-carte-dr", "figure"),
    Output("pd-energie", "figure"),
    Output("pd-kpi-gu-immeubles", "children"),
    Output("pd-kpi-gu-conversion", "children"),
    [Input("pd-n-mois", "value")],
)
def update(n_mois, **kwargs):
    user = kwargs["user"]

    periode_ca, ca_mds, delta_ca = data.kpi_ca_dernier_mois_avec_delta(user)
    kpi_ca = stat_card("CA du mois" + (f" ({periode_ca})" if periode_ca else ""),
                        f"{ca_mds:,.1f} Mds FCFA".replace(",", " ") if ca_mds is not None else "—",
                        "fa-coins", "primary", delta_pct=delta_ca)

    nb_clients = data.kpi_nb_clients_dernier_mois(user)
    kpi_clients = stat_card("Clients facturés (dernier mois)",
                             f"{nb_clients:,}".replace(",", " ") if nb_clients is not None else "—",
                             "fa-users", "info")

    energie, delta_energie = data.kpi_energie_dernier_mois_avec_delta(user)
    kpi_energie = stat_card("Énergie facturée (MWh, dernier mois)",
                             f"{energie:,.0f}".replace(",", " ") if energie is not None else "—",
                             "fa-bolt", "warning", delta_pct=delta_energie)

    taux_global, couleur_global = data.kpi_taux_recouvrement_global(user)
    color_map_bootstrap = {"vert": "success", "orange": "warning", "rouge": "danger", "gris": "secondary"}
    kpi_recouvr = stat_card("Taux de recouvrement global",
                             f"{taux_global * 100:.1f}%" if taux_global is not None else "—",
                             "fa-hand-holding-usd", color_map_bootstrap[couleur_global])

    labels, ca = data.ca_evolution(user, n_periodes=n_mois)
    fig_ca = go.Figure(smoothed_area_trace(labels, ca, ORANGE, hover_suffix=" FCFA"))
    apply_compact_layout(fig_ca, yaxis_title="FCFA", angle_ticks=True)

    entites, ca_entite = data.ca_par_entite(user)
    fig_entite = go.Figure(
        go.Pie(labels=entites, values=ca_entite, hole=0.55, marker={"colors": PIE_SEQUENCE},
               textinfo="percent", hovertemplate="%{label}<br>%{value:,.0f} FCFA<extra></extra>")
    )
    apply_compact_layout(fig_entite)
    fig_entite.update_layout(legend={"orientation": "h", "y": -0.1})

    drs, taux, couleurs = data.recouvrement_par_dr(user)
    color_map = {"vert": GREEN, "orange": ORANGE, "rouge": "#E74A3B", "gris": GRAY}
    fig_recouvr = go.Figure(
        go.Bar(
            x=drs,
            y=[t * 100 if t is not None else 0 for t in taux],
            marker_color=[color_map[c] for c in couleurs],
            hovertemplate="%{x}<br><b>%{y:.1f}%</b><extra></extra>",
        )
    )
    apply_compact_layout(fig_recouvr, yaxis_title="% recouvré", angle_ticks=True)

    labels_bc, nb_clients_serie = data.base_clients_evolution(user, n_periodes=n_mois)
    fig_bc = go.Figure(smoothed_area_trace(labels_bc, nb_clients_serie, GREEN))
    apply_compact_layout(fig_bc, yaxis_title="Nb clients", angle_ticks=True)

    ca_dr = data.ca_par_dr(user)
    codes_dr = list(ca_dr.keys())
    valeurs_dr = [ca_dr[c] for c in codes_dr]
    fig_carte = go.Figure(
        go.Choroplethmap(
            geojson=dr_geojson(),
            locations=codes_dr,
            z=valeurs_dr,
            featureidkey="properties.DR",
            colorscale="Oranges",
            marker_line_color="white",
            marker_line_width=0.6,
            colorbar={"title": "CA (FCFA)"},
            hovertemplate="<b>%{location}</b><br>%{z:,.0f} FCFA<extra></extra>",
        )
    )
    # Étiquettes au centre de chaque DR : code + CA (en Mds FCFA), demande
    # utilisateur (« étiquettes aux données »). Le fond coloré + la barre de
    # couleur tiennent lieu de légende.
    cents = dr_centroids()
    etiq_codes = [c for c in codes_dr if c in cents]
    fig_carte.add_trace(
        go.Scattermap(
            lon=[cents[c][0] for c in etiq_codes],
            lat=[cents[c][1] for c in etiq_codes],
            text=[f"{c}<br>{ca_dr[c] / 1e9:.0f} Mds" for c in etiq_codes],
            mode="text",
            textfont={"size": 10, "color": "#222"},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig_carte.update_layout(
        map_style="carto-positron",
        map_zoom=5.15,
        map_center={"lat": 7.6, "lon": -5.55},
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        height=440,
    )

    labels_e, mwh = data.energie_evolution(user, n_periodes=n_mois)
    fig_energie = go.Figure(
        go.Bar(x=labels_e, y=mwh, marker_color=BLUE, hovertemplate="%{x}<br><b>%{y:,.0f} MWh</b><extra></extra>")
    )
    apply_compact_layout(fig_energie, yaxis_title="MWh", angle_ticks=True)

    nb_immeubles_gu = data.kpi_nb_immeubles_prospectes(user)
    kpi_gu_immeubles = stat_card("Immeubles suivis (Guichet Unique)", f"{nb_immeubles_gu:,}".replace(",", " "), "fa-building", "primary")

    taux_conv_gu = data.kpi_taux_conversion_cie(user)
    kpi_gu_conversion = stat_card("Taux de conversion → demande CIE", f"{taux_conv_gu * 100:.0f}%" if taux_conv_gu is not None else "—", "fa-bullseye", "warning")

    return (
        kpi_ca, kpi_clients, kpi_energie, kpi_recouvr, fig_ca, fig_entite, fig_recouvr, fig_bc, fig_carte, fig_energie,
        kpi_gu_immeubles, kpi_gu_conversion,
    )
