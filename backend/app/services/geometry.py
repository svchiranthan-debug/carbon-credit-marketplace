"""Small geometry helpers for plantation boundaries (no external GIS dependency)."""
import math
from typing import List, Sequence

EARTH_RADIUS_M = 6_371_008.8


def polygon_area_hectares(latlngs: Sequence[Sequence[float]]) -> float:
    """Area of a small lat/lng polygon via a local equal-area (sinusoidal) projection + shoelace.

    Accurate to well under 1% for plantation-sized polygons.
    """
    if len(latlngs) < 3:
        return 0.0
    lat0 = math.radians(sum(p[0] for p in latlngs) / len(latlngs))
    pts = [(EARTH_RADIUS_M * math.radians(p[1]) * math.cos(lat0), EARTH_RADIUS_M * math.radians(p[0]))
           for p in latlngs]
    area = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0 / 10_000.0


def to_geojson_polygon(latlngs: Sequence[Sequence[float]]) -> dict:
    """[[lat, lng], ...] → closed GeoJSON Polygon with [lng, lat] order."""
    ring: List[List[float]] = [[float(p[1]), float(p[0])] for p in latlngs]
    if ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    return {"type": "Polygon", "coordinates": [ring]}


def latlngs_from_geojson(geojson) -> List[List[float]]:
    """GeoJSON Polygon → [[lat, lng], ...] without the closing point."""
    if not geojson or geojson.get("type") != "Polygon":
        return []
    ring = geojson["coordinates"][0]
    pts = [[p[1], p[0]] for p in ring]
    return pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts


def lonlat_ring(geojson) -> List[List[float]]:
    if not geojson or geojson.get("type") != "Polygon":
        return []
    return [list(p) for p in geojson["coordinates"][0]]


def point_in_polygon(lat: float, lng: float, latlngs: Sequence[Sequence[float]]) -> bool:
    inside = False
    n = len(latlngs)
    for i in range(n):
        y1, x1 = latlngs[i]
        y2, x2 = latlngs[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            x_cross = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lng < x_cross:
                inside = not inside
    return inside
