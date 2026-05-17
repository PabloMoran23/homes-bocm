"""Utilidades geográficas sin dependencias opcionales (punto en polígono, UTM→WGS84)."""

from __future__ import annotations

import json
import math
import re
from typing import Any


MADRID_LAT_MIN = 39.5
MADRID_LAT_MAX = 41.2
MADRID_LNG_MIN = -4.5
MADRID_LNG_MAX = -3.0

_EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Distancia en metros entre dos puntos WGS84."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, a)))


def bbox_for_radius_m(lng: float, lat: float, radius_m: float) -> tuple[float, float, float, float]:
    """BBox aproximado (grados) para prefiltro SQL."""
    dlat = radius_m / 111_320.0
    dlng = radius_m / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return lng - dlng, lat - dlat, lng + dlng, lat + dlat


def is_valid_wgs84_madrid(lng: float, lat: float) -> bool:
    """Coordenadas plausibles para el municipio de Madrid (WGS84)."""
    if not math.isfinite(lng) or not math.isfinite(lat):
        return False
    if abs(lat) < 1e-6 and abs(lng) < 1e-6:
        return False
    return (
        MADRID_LAT_MIN <= lat <= MADRID_LAT_MAX
        and MADRID_LNG_MIN <= lng <= MADRID_LNG_MAX
    )


def is_placeholder_dms(raw: object) -> bool:
    """Valores centinela del open data cuando no hay georreferencia."""
    if raw is None:
        return True
    s = str(raw).strip()
    if not s or s in ("0", "0.0"):
        return True
    return bool(re.match(r"^0\s*[º°]\s*0\s*['\u2032]?\s*0", s, re.IGNORECASE))


def parse_dms_coord(raw: object) -> float | None:
    """Grados-minutos-segundos (BOCM Ayto.) → decimal; None si vacío o centinela."""
    if is_placeholder_dms(raw):
        return None
    s = str(raw).strip()
    m = re.match(
        r"([\d.]+)\s*[º°]\s*([\d.]+)\s*['\u2032]?\s*([\d.]*)\s*['\u2033]?\s*([NnSsEeWw])",
        s,
    )
    if not m:
        return None
    deg = float(m.group(1))
    minutes = float(m.group(2))
    sec = float(m.group(3)) if m.group(3) else 0.0
    if not all(math.isfinite(x) for x in (deg, minutes, sec)):
        return None
    v = deg + minutes / 60 + sec / 3600
    hemi = m.group(4).upper()
    if hemi in ("S", "W"):
        v = -v
    return v


def parse_utm_component(raw: object) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        n = float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n / 100.0


def utm30n_to_wgs84(easting: float, northing: float) -> tuple[float, float] | None:
    """UTM zona 30N (EPSG:25830 aprox.) → (lng, lat) en grados WGS84."""
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e = math.sqrt(2 * f - f * f)
    e2 = e * e / (1 - e * e)
    zone = 30
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)

    x = easting - 500000.0
    y = northing
    m = y / k0
    mu = m / (a * (1 - e**2 / 4 - 3 * e**4 / 64 - 5 * e**6 / 256))

    e1 = (1 - math.sqrt(1 - e**2)) / (1 + math.sqrt(1 - e**2))
    phi1 = mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
    phi1 += (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
    phi1 += (151 * e1**3 / 96) * math.sin(6 * mu)

    n1 = a / math.sqrt(1 - e**2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = e2 * math.cos(phi1) ** 2
    r1 = a * (1 - e**2) / (1 - e**2 * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * k0)

    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e2) * d**4 / 24
    )
    lon = lon0 + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e2 + 24 * t1**2) * d**5 / 120
    ) / math.cos(phi1)

    lng_deg = math.degrees(lon)
    lat_deg = math.degrees(lat)
    if lat_deg < 39.5 or lat_deg > 41.2 or lng_deg < -4.5 or lng_deg > -3.0:
        return None
    return lng_deg, lat_deg


def resolve_licencia_coords(row: dict[str, Any]) -> tuple[float, float] | None:
    lat_dms = parse_dms_coord(row.get("latitud"))
    lng_dms = parse_dms_coord(row.get("longitud"))
    if lat_dms is not None and lng_dms is not None:
        if is_valid_wgs84_madrid(lng_dms, lat_dms):
            return lng_dms, lat_dms

    lat = row.get("lat")
    lng = row.get("lng")
    if lat is not None and lng is not None:
        try:
            la, ln = float(lat), float(lng)
            if is_valid_wgs84_madrid(ln, la):
                return ln, la
        except (TypeError, ValueError):
            pass

    x = parse_utm_component(row.get("coordenadas_x") or row.get("coordenada_x"))
    y = parse_utm_component(row.get("coordenadas_y") or row.get("coordenada_y"))
    if x is None or y is None or x == 0 or y == 0:
        return None
    out = utm30n_to_wgs84(x, y)
    if out and is_valid_wgs84_madrid(out[0], out[1]):
        return out
    return None


def ring_bbox(ring: list[list[float]]) -> tuple[float, float, float, float]:
    lngs = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return min(lngs), min(lats), max(lngs), max(lats)


def geom_bbox(geom: dict[str, Any]) -> tuple[float, float, float, float] | None:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None
    if gtype == "Polygon":
        return ring_bbox(coords[0])
    if gtype == "MultiPolygon":
        boxes = [ring_bbox(poly[0]) for poly in coords if poly]
        if not boxes:
            return None
        return (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )
    return None


def ring_centroid(ring: list[list[float]]) -> tuple[float, float]:
    n = len(ring)
    if n == 0:
        return 0.0, 0.0
    lng = sum(p[0] for p in ring) / n
    lat = sum(p[1] for p in ring) / n
    return lng, lat


def point_in_ring(lng: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi
        ):
            inside = not inside
        j = i
    return inside


def point_in_geom(lng: float, lat: float, geom: dict[str, Any]) -> bool:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return False
    if gtype == "Polygon":
        if not point_in_ring(lng, lat, coords[0]):
            return False
        for hole in coords[1:]:
            if point_in_ring(lng, lat, hole):
                return False
        return True
    if gtype == "MultiPolygon":
        return any(
            point_in_geom(lng, lat, {"type": "Polygon", "coordinates": poly})
            for poly in coords
        )
    return False


def bbox_contains_point(
    bbox: tuple[float, float, float, float],
    lng: float,
    lat: float,
) -> bool:
    min_lng, min_lat, max_lng, max_lat = bbox
    return min_lng <= lng <= max_lng and min_lat <= lat <= max_lat


class PolygonIndex:
    """Índice por rejilla para candidatos punto-en-polígono."""

    def __init__(self, cell_deg: float = 0.005) -> None:
        self.cell_deg = cell_deg
        self._cells: dict[tuple[int, int], list[int]] = {}
        self.polys: list[dict[str, Any]] = []

    def _cell_key(self, lng: float, lat: float) -> tuple[int, int]:
        return (int(lng / self.cell_deg), int(lat / self.cell_deg))

    def _cells_for_bbox(
        self, bbox: tuple[float, float, float, float]
    ) -> list[tuple[int, int]]:
        min_lng, min_lat, max_lng, max_lat = bbox
        i0, j0 = self._cell_key(min_lng, min_lat)
        i1, j1 = self._cell_key(max_lng, max_lat)
        out: list[tuple[int, int]] = []
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                out.append((i, j))
        return out

    def add(self, poly: dict[str, Any]) -> None:
        idx = len(self.polys)
        self.polys.append(poly)
        for ck in self._cells_for_bbox(poly["bbox"]):
            self._cells.setdefault(ck, []).append(idx)

    def query(self, lng: float, lat: float) -> list[dict[str, Any]]:
        ck = self._cell_key(lng, lat)
        seen: set[int] = set()
        candidates: list[int] = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for pi in self._cells.get((ck[0] + di, ck[1] + dj), []):
                    if pi not in seen:
                        seen.add(pi)
                        candidates.append(pi)
        hits: list[dict[str, Any]] = []
        for pi in candidates:
            p = self.polys[pi]
            if not bbox_contains_point(p["bbox"], lng, lat):
                continue
            if point_in_geom(lng, lat, p["geom"]):
                hits.append(p)
        return hits


def geom_area_approx_m2(geom: dict[str, Any]) -> float:
    """Área aproximada en m² (proyección local) para desempatar polígonos."""
    bbox = geom_bbox(geom)
    if not bbox:
        return float("inf")
    min_lng, min_lat, max_lng, max_lat = bbox
    mid_lat = (min_lat + max_lat) / 2
    m_per_deg_lat = 111_320.0
    m_per_deg_lng = 111_320.0 * math.cos(math.radians(mid_lat))
    return (max_lng - min_lng) * m_per_deg_lng * (max_lat - min_lat) * m_per_deg_lat
