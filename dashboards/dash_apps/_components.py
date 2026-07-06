"""Composants partagés entre les 4 dash apps, construits avec dash-bootstrap-
components (dbc) plutôt qu'avec des html.Div(className=...) à la main : dbc
connaît les vraies largeurs de colonnes Bootstrap (width/md/xl en arguments
typés), ce qui évite la classe de bugs qu'on a eue (col-xl- sans repli, fautes de
frappe dans une chaîne de classes...). dbc émet les mêmes classes CSS Bootstrap
standard que cie-admin-2.min.css attend déjà, pas besoin d'une feuille de style
dbc séparée.

Contient aussi la charte graphique commune des figures Plotly (palette CIE,
courbes lissées + degradé, hauteur compacte, transition animée, barre d'outils
masquée) pour que les 4 dashboards aient un rendu cohérent et plus dense, façon
BI, plutôt que des graphiques Plotly par défaut.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html

# Chargée dans chaque dash app pour que les classes Bootstrap (émises par dbc et
# par nos propres html.Div) soient stylées à l'intérieur de l'iframe (document
# séparé du reste de la page Django) avec notre thème CIE recoloré.
CIE_STYLESHEET = "/static/dashboards/css/cie-admin-2.min.css"

# Palette de marque (cf. cie-theme.css côté Django) réutilisée dans les figures.
ORANGE = "#F7941E"
GREEN = "#2E9E4F"
BLUE = "#36B9CC"
GRAY = "#858796"
PIE_SEQUENCE = [ORANGE, GREEN, BLUE, "#5A5C69", "#F6C23E"]

# responsive=False est volontaire : on fixe une hauteur exacte (COMPACT_HEIGHT) via
# fig.update_layout(height=...). Avec responsive=True, Plotly redimensionne le
# graphique sur la taille réelle de son conteneur, qui peut s'effondrer à presque
# rien selon le contexte flex/iframe, écrasant le graphique au lieu de l'afficher
# à la hauteur prévue (déjà observé une fois, cf. historique du fichier).
GRAPH_CONFIG = {"displayModeBar": False, "responsive": False}
COMPACT_HEIGHT = 280


def stat_card(label, value, icon="fa-chart-bar", color="primary", delta_pct=None):
    """Reproduit le motif `.card.border-left-{color}` de SB Admin 2, avec dbc.Card.

    L'aide contextuelle ("?" au survol) est cherchée par libellé dans
    dashboards.data.AIDE_PAR_LIBELLE (import local pour éviter tout souci d'import
    circulaire au chargement du module, cf. pattern déjà utilisé ailleurs dans
    l'app pour les imports cross-app) : ainsi un même libellé garde la même
    explication, qu'il soit affiché ici ou sur la page d'accueil (dashboards.views).

    delta_pct (variation vs la période précédente, demande utilisateur cf.
    rapport "Fonctionnalités proposées") est laissé à None par les appelants qui
    n'ont pas encore cette donnée plutôt que de l'imposer partout d'un coup."""
    from dashboards.data import AIDE_PAR_LIBELLE

    aide = AIDE_PAR_LIBELLE.get(label)
    libelle = [label]
    if aide:
        libelle.append(html.I(className="fas fa-question-circle ml-1", title=aide))

    contenu_valeur = [html.Div(value, className="h5 mb-0 font-weight-bold text-gray-800")]
    if delta_pct is not None:
        sens = "up" if delta_pct >= 0 else "down"
        couleur_delta = "text-success" if delta_pct >= 0 else "text-danger"
        contenu_valeur.append(
            html.Div(
                [html.I(className=f"fas fa-arrow-{sens} mr-1"), f"{delta_pct:+.1f}% vs mois précédent"],
                className=f"small {couleur_delta}",
            )
        )

    return dbc.Card(
        dbc.CardBody(
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(libelle, className=f"text-xs font-weight-bold text-{color} text-uppercase mb-1"),
                            *contenu_valeur,
                        ],
                        className="mr-2",
                    ),
                    dbc.Col(html.I(className=f"fas {icon} fa-2x text-gray-300"), width="auto"),
                ],
                align="center",
                className="no-gutters",
            ),
        ),
        className=f"border-left-{color} shadow h-100 py-2 mb-4",
    )


def chart_card(title, children, icon="fa-chart-area"):
    """Carte standard SB Admin 2 (icône + titre en en-tête, corps), avec dbc.Card,
    reproduit le motif "Area Chart Example"/"Bar Chart Example" du template."""
    return dbc.Card(
        [
            dbc.CardHeader(
                html.H6(
                    [html.I(className=f"fas {icon} mr-2"), title],
                    className="m-0 font-weight-bold text-primary",
                ),
                className="py-2",
            ),
            dbc.CardBody(children, className="py-2"),
        ],
        className="shadow mb-4 h-100",
    )


def graph(component_id):
    """dcc.Graph avec la barre d'outils Plotly masquée, un dashboard métier n'a pas
    besoin des boutons zoom/export par défaut, qui alourdissent visuellement."""
    return dcc.Graph(id=component_id, config=GRAPH_CONFIG)


def _hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def smoothed_area_trace(x, y, color, name=None, hover_suffix=""):
    """Courbe lissée (spline) avec aire en degradé sous la courbe : l'effet
    "lisser avec un degrade" demandé, réutilisable pour n'importe quelle série
    temporelle (CA, base clients...).

    fillgradient.colorscale est indexé sur la VALEUR de la donnée (0=basse,
    proche de l'axe ; 1=haute, proche de la courbe), pas sur le haut/bas de
    l'écran, la couleur pleine doit donc être en position 1 (près de la courbe)
    et le transparent en position 0 (près de la ligne de base), pas l'inverse."""
    import plotly.graph_objects as go

    return go.Scatter(
        x=x,
        y=y,
        mode="lines+markers",
        line={"color": color, "shape": "spline", "smoothing": 0.6, "width": 3},
        marker={"size": 6, "color": color},
        fill="tozeroy",
        fillgradient={
            "type": "vertical",
            "colorscale": [[0, _hex_to_rgba(color, 0.0)], [1, _hex_to_rgba(color, 0.4)]],
        },
        name=name or "",
        hovertemplate="%{x}<br><b>%{y:,.0f}" + hover_suffix + "</b><extra></extra>",
    )


def truncate_label(text, max_len=28):
    """Tronque un libellé de catégorie trop long pour l'affichage (l'intégralité
    reste visible au survol via customdata, cf. horizontal_bar_trace), sans ça,
    un quartier comme "COCODY ( DANGA, LYCÉE TECHNIQUE-AMBASSADE ETC..)" déborde
    de toute carte compacte quelle que soit l'orientation des barres."""
    text = str(text)
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


def horizontal_bar_trace(labels, values, color, hover_suffix="", max_len=28):
    """Barres horizontales : la bonne représentation quand les libellés de
    catégorie sont longs (quartiers, intitulés de rôle/portefeuille...) : passé
    une certaine longueur, incliner l'axe X (cf. apply_compact_layout) ne suffit
    plus, alors qu'un axe Y horizontal affiche le texte sans rotation ni risque de
    chevauchement entre barres voisines.

    max_len ajustable par appelant : des libellés courts mais avec un suffixe
    disambiguant (ex: "Conseiller Client Grands Comptes #1"/"#2", cf.
    dashboards.data.portefeuille_par_commercial) ont besoin d'un seuil plus haut
    que des quartiers très longs, sous peine de couper avant le "#1"/"#2" et de
    faire apparaître deux barres avec le même libellé affiché."""
    import plotly.graph_objects as go

    return go.Bar(
        x=values,
        y=[truncate_label(l, max_len=max_len) for l in labels],
        customdata=labels,
        orientation="h",
        marker_color=color,
        hovertemplate="%{customdata}<br><b>%{x:,.0f}" + hover_suffix + "</b><extra></extra>",
    )


# Légende horizontale compacte, ancrée en haut à droite du graphique (demande
# utilisateur : une légende sur TOUS les graphes). Réutilisée par les deux layouts.
_LEGEND = {
    "orientation": "h",
    "yanchor": "bottom",
    "y": 1.02,
    "xanchor": "right",
    "x": 1,
    "font": {"size": 10},
}


def _add_value_labels(fig, legend_name=""):
    """Ajoute les étiquettes de valeurs sur les données de chaque trace (demande
    utilisateur : « les étiquettes aux données »), avec un format SI compact et
    sans zéros inutiles (%{...:.3~s} → 133, 3,57k, 291k, 29,2G) pour rester
    lisible quelle que soit la grandeur (comptages, %, FCFA...). Donne aussi un
    nom de série aux traces anonymes pour que la légende soit parlante."""
    for tr in fig.data:
        ttype = getattr(tr, "type", None)
        if ttype == "bar":
            horizontal = getattr(tr, "orientation", "v") == "h"
            tr.texttemplate = "%{x:.3~s}" if horizontal else "%{y:.3~s}"
            tr.textposition = "auto"
            tr.textfont = {"size": 11}
            tr.cliponaxis = False
        elif ttype == "scatter":
            mode = getattr(tr, "mode", None) or "lines"
            if "text" not in mode:
                tr.mode = mode + "+text"
            tr.texttemplate = "%{y:.3~s}"
            tr.textposition = "top center"
            tr.textfont = {"size": 10}
        elif ttype == "pie":
            # Le libellé de chaque part est déjà porté par la légende (activée par
            # apply_compact_layout) : répéter "label" ICI en texte flottant à
            # l'extérieur du donut faisait chevaucher les étiquettes entre elles ET
            # avec la légende sur les cartes compactes (retour utilisateur, capture
            # à l'appui). On se limite donc au pourcentage, ancré à l'INTÉRIEUR de
            # chaque part (textposition="inside"), qui ne peut pas déborder sur ses
            # voisines ni sur la légende.
            if not getattr(tr, "textinfo", None):
                tr.textinfo = "percent"
            tr.textposition = "inside"
            tr.insidetextorientation = "radial"
            tr.textfont = {"size": 11, "color": "#fff"}
        if legend_name and not getattr(tr, "name", None):
            tr.name = legend_name
    return fig


def choropleth_dr(valeurs_par_dr, colorbar_titre="", colorscale="Oranges", hover_suffix="", height=420):
    """Carte choroplèthe des 14 Directions Régionales à partir d'un dict
    {code_DR: valeur}. Étiquette (code DR) au centre de chaque DR, barre de couleur
    en légende. Fond OpenStreetMap/Carto (sans jeton). Réutilisable par tous les
    dashboards pour la répartition spatiale (demande utilisateur : cartes partout)."""
    import plotly.graph_objects as go

    from dashboards.geo import dr_centroids, dr_geojson

    codes = list(valeurs_par_dr.keys())
    vals = [valeurs_par_dr[c] for c in codes]
    fig = go.Figure(
        go.Choroplethmap(
            geojson=dr_geojson(), locations=codes, z=vals, featureidkey="properties.DR",
            colorscale=colorscale, marker_line_color="white", marker_line_width=0.6,
            colorbar={"title": colorbar_titre},
            hovertemplate="<b>%{location}</b><br>%{z:,.0f}" + hover_suffix + "<extra></extra>",
        )
    )
    cents = dr_centroids()
    etiquettes = [c for c in codes if c in cents]
    if etiquettes:
        fig.add_trace(
            go.Scattermap(
                lon=[cents[c][0] for c in etiquettes], lat=[cents[c][1] for c in etiquettes],
                text=etiquettes, mode="text", textfont={"size": 9, "color": "#222"},
                hoverinfo="skip", showlegend=False,
            )
        )
    fig.update_layout(
        map_style="carto-positron", map_zoom=5.1, map_center={"lat": 7.6, "lon": -5.55},
        margin={"l": 0, "r": 0, "t": 0, "b": 0}, height=height,
    )
    return fig


def apply_horizontal_bar_layout(fig, xaxis_title="", height=COMPACT_HEIGHT):
    """Pendant de apply_compact_layout pour les barres horizontales
    (horizontal_bar_trace) : automargin laisse Plotly calculer lui-même la marge
    gauche nécessaire aux libellés tronqués plutôt que de deviner une valeur fixe,
    et autorange="reversed" affiche la première catégorie (donnée déjà triée par
    valeur décroissante côté requête) en haut plutôt qu'en bas."""
    _add_value_labels(fig, xaxis_title)
    fig.update_layout(
        height=height,
        margin={"t": 40, "r": 24, "b": 36, "l": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Nunito, sans-serif", "color": "#5a5c69", "size": 12},
        xaxis={"title": xaxis_title, "gridcolor": "#eaecf4", "zeroline": False, "tickformat": ",.0f"},
        yaxis={"showgrid": False, "automargin": True, "autorange": "reversed"},
        showlegend=True,
        legend=_LEGEND,
        hoverlabel={"bgcolor": "white", "font_size": 12, "font_family": "Nunito, sans-serif"},
        transition={"duration": 400, "easing": "cubic-in-out"},
    )
    return fig


def apply_compact_layout(fig, yaxis_title="", height=COMPACT_HEIGHT, angle_ticks=False):
    """Mise en page commune : compacte, fond transparent (laisse voir la carte
    Bootstrap blanche derrière), grille discrète, police Nunito cohérente avec le
    reste de l'app, transition animée entre deux mises à jour (callback), pour ne
    plus avoir un graphique Plotly "générique" qui change brutalement.

    angle_ticks=True incline les libellés de l'axe X ET plafonne leur nombre
    (nticks) : nécessaire dès qu'un axe catégoriel a des libellés un peu longs
    ("14 < Délai <= 30jrs"...) ou qu'une série temporelle a beaucoup de points
    (12-24 mois). C'est appliqué systématiquement sur tous les graphiques à
    barres/courbes de l'app, plus seulement les séries mensuelles (cf. historique)."""
    _add_value_labels(fig, yaxis_title)
    fig.update_layout(
        height=height,
        margin={"t": 40, "r": 16, "b": 80 if angle_ticks else 36, "l": 48},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Nunito, sans-serif", "color": "#5a5c69", "size": 12},
        yaxis={"title": yaxis_title, "gridcolor": "#eaecf4", "zeroline": False, "tickformat": ",.0f"},
        xaxis={
            "showgrid": False,
            "tickfont": {"size": 10} if angle_ticks else {"size": 12},
            "tickangle": -40 if angle_ticks else 0,
            "tickmode": "auto",
            "nticks": 7 if angle_ticks else None,
        },
        showlegend=True,
        legend=_LEGEND,
        hoverlabel={"bgcolor": "white", "font_size": 12, "font_family": "Nunito, sans-serif"},
        transition={"duration": 400, "easing": "cubic-in-out"},
    )
    return fig
