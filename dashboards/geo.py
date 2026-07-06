"""Référentiel géographique des Directions Régionales (DR) de la CIE.

Le fond de carte fourni (cie_dr/output.json) est un TopoJSON. Faute de bibliothèque
dédiée (topojson/geopandas non installées), on décode ici manuellement l'objet
"DR GEOJSON" (14 polygones, propriété `DR` = code DR) en GeoJSON exploitable par
Plotly (choroplèthe). Le résultat est mis en cache (chargé une seule fois)."""

import functools
import json

from django.conf import settings

CIE_DR_TOPOJSON = settings.BASE_DIR.parent / "cie_dr" / "DR GEOJSON.json"
DR_OBJECT = "DR GEOJSON"


def _centroid_lat(feature):
    """Latitude moyenne (approx.) de l'anneau extérieur d'une feature, pour
    départager les deux polygones d'Abidjan étiquetés à tort « DRABO »."""
    geom = feature["geometry"]
    ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
    return sum(p[1] for p in ring) / len(ring)


def _decode_arcs(topo):
    """Décode les arcs delta-encodés/quantifiés du TopoJSON en coordonnées lon/lat."""
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    decoded = []
    for arc in topo["arcs"]:
        x = y = 0
        points = []
        for dx, dy in arc:
            x += dx
            y += dy
            points.append([x * sx + tx, y * sy + ty])
        decoded.append(points)
    return decoded


@functools.lru_cache(maxsize=1)
def dr_geojson():
    """FeatureCollection GeoJSON des DR (chaque feature : properties.DR = code)."""
    topo = json.loads(CIE_DR_TOPOJSON.read_text(encoding="utf-8"))
    decoded = _decode_arcs(topo)

    def arc_coords(index):
        # Indice négatif => arc parcouru en sens inverse (convention TopoJSON).
        return decoded[index] if index >= 0 else list(reversed(decoded[~index]))

    def stitch_ring(arc_indices):
        coords = []
        for k, idx in enumerate(arc_indices):
            a = arc_coords(idx)
            coords.extend(a if k == 0 else a[1:])  # points de jonction dédupliqués
        return coords

    def polygon(rings):
        return [stitch_ring(r) for r in rings]

    features = []
    for geom in topo["objects"][DR_OBJECT]["geometries"]:
        code = (geom.get("properties") or {}).get("DR")
        gtype = geom.get("type")
        if gtype == "Polygon":
            coordinates = polygon(geom["arcs"])
        elif gtype == "MultiPolygon":
            coordinates = [polygon(poly) for poly in geom["arcs"]]
        else:
            continue
        features.append(
            {
                "type": "Feature",
                "id": code,
                "properties": {"DR": code},
                "geometry": {"type": gtype, "coordinates": coordinates},
            }
        )

    # Correction du fond fourni : DRAS (DR Abidjan Sud) est absent et DRABO
    # (Abobo) apparaît en double. Géographiquement, Abobo est au nord et Abidjan
    # Sud (Treichville, Marcory, Koumassi, Port-Bouët) au sud : on ré-étiquette
    # donc le polygone « DRABO » le plus méridional en DRAS, ce qui rétablit les
    # 14 DR distinctes sur la carte.
    drabo = [f for f in features if f["properties"]["DR"] == "DRABO"]
    if len(drabo) == 2 and not any(f["properties"]["DR"] == "DRAS" for f in features):
        sud = min(drabo, key=_centroid_lat)
        sud["id"] = "DRAS"
        sud["properties"]["DR"] = "DRAS"

    return {"type": "FeatureCollection", "features": features}


@functools.lru_cache(maxsize=1)
def dr_centroids():
    """Centroïde approximatif (lon, lat) de chaque DR, pour poser une étiquette
    (code DR + valeur) au centre de son polygone sur la carte choroplèthe."""
    cents = {}
    for f in dr_geojson()["features"]:
        geom = f["geometry"]
        ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
        lon = sum(p[0] for p in ring) / len(ring)
        lat = sum(p[1] for p in ring) / len(ring)
        cents[f["properties"]["DR"]] = (lon, lat)
    return cents
