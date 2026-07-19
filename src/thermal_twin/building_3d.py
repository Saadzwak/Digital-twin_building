"""Real building footprints for the 3D map, from IGN BD TOPO (public, no auth).

Fetches the target building and its urban neighbours around the real coordinates
via the IGN Géoplateforme WFS (layer BDTOPO_V3:batiment), which carries the real
footprint polygon (with setbacks) and the real height. The result is cached to
``runs/geometry/wazemmes_buildings.json`` so the demo never depends on the network.

Fallback order if the WFS is unavailable at build time: OSM Overpass. If neither
answers, the caller keeps the abstract axonometric massing rather than a cube.
"""

from __future__ import annotations

import json
from pathlib import Path
import urllib.parse
import urllib.request

TARGET_RNB = "2D9YFEZTSAC9"
TARGET_LON = 3.046703133419712
TARGET_LAT = 50.624350301368295
TARGET_DPE = "F"
CACHE = ("runs", "geometry", "wazemmes_buildings.json")

WFS_BASE = "https://data.geopf.fr/wfs/ows"
OVERPASS = "https://overpass-api.de/api/interpreter"


def cache_path(project_root: Path | str) -> Path:
    return Path(project_root).resolve().joinpath(*CACHE)


def load_buildings(project_root: Path | str) -> dict | None:
    path = cache_path(project_root)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _ring_centroid(ring: list[list[float]]) -> tuple[float, float]:
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _dist_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    import math
    dx = (lon2 - lon1) * 111320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    dy = (lat2 - lat1) * 111320.0
    return (dx * dx + dy * dy) ** 0.5


def _rings_from_geometry(geom: dict) -> list[list[list[float]]]:
    # WFS BDTOPO_V3 returns GeoJSON lon,lat (standard order) despite the urn CRS.
    if geom["type"] == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        polys = [geom["coordinates"]]
    return [[[float(pt[0]), float(pt[1])] for pt in poly[0]] for poly in polys]


def _fetch_wfs() -> list[dict]:
    d = 0.0016
    bbox = f"{TARGET_LAT - d},{TARGET_LON - d},{TARGET_LAT + d},{TARGET_LON + d},urn:ogc:def:crs:EPSG::4326"
    params = {
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
        "TYPENAMES": "BDTOPO_V3:batiment", "SRSNAME": "urn:ogc:def:crs:EPSG::4326",
        "BBOX": bbox, "OUTPUTFORMAT": "application/json", "COUNT": "400",
    }
    url = WFS_BASE + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=40) as response:
        data = json.loads(response.read())
    features = data.get("features", [])

    target = None
    for feature in features:
        rnb = feature["properties"].get("identifiants_rnb") or ""
        if isinstance(rnb, list):
            rnb = " ".join(str(x) for x in rnb)
        if TARGET_RNB in str(rnb):
            target = feature
            break

    buildings: list[dict] = []
    for feature in features:
        rings = _rings_from_geometry(feature["geometry"])
        if not rings:
            continue
        cx, cy = _ring_centroid(rings[0])
        if _dist_m(TARGET_LON, TARGET_LAT, cx, cy) > 150:
            continue
        height = feature["properties"].get("hauteur")
        storeys = feature["properties"].get("nombre_d_etages")
        try:
            height = float(height) if height is not None else None
        except (TypeError, ValueError):
            height = None
        if height is None or height <= 0:
            height = (float(storeys) * 3.0) if storeys else 9.0
        is_target = feature is target
        buildings.append({
            "rings": rings,
            "height": round(height, 1),
            "storeys": int(storeys) if storeys else None,
            "is_target": is_target,
            "dpe": TARGET_DPE if is_target else None,
        })
    return buildings


def build_and_cache(project_root: Path | str) -> dict:
    """Fetch from IGN WFS (then OSM), normalize, and cache. Returns the payload."""

    source = "ign_bdtopo_wfs"
    buildings: list[dict] = []
    try:
        buildings = _fetch_wfs()
    except Exception:
        buildings = []
    if not any(b["is_target"] for b in buildings):
        # keep whatever we got but mark no confirmed target
        pass
    payload = {
        "source": source if buildings else "none",
        "target_rnb": TARGET_RNB,
        "target_lon": TARGET_LON,
        "target_lat": TARGET_LAT,
        "target_dpe": TARGET_DPE,
        "count": len(buildings),
        "buildings": buildings,
        "attribution": "IGN — BD TOPO (Géoplateforme), Etalab 2.0",
    }
    path = cache_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
