#!/usr/bin/env python3
"""Boletín de tu área: actividad reciente en un radio (licencias + SIGMA)."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = POC_ROOT / "db" / "poc_local.sqlite"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo_utils import (  # noqa: E402
    PolygonIndex,
    bbox_for_radius_m,
    haversine_m,
    is_valid_wgs84_madrid,
    point_in_geom,
)


def parse_fecha_es(raw: str | None) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s[:10], fmt)
        except ValueError:
            continue
    return None


def fecha_sort_key(raw: str | None) -> float:
    d = parse_fecha_es(raw)
    return d.timestamp() if d else 0.0


def query_boletin(
    con: sqlite3.Connection,
    lat: float,
    lng: float,
    radius_m: float = 600.0,
    months: int = 24,
    limit: int = 80,
) -> dict:
    if not is_valid_wgs84_madrid(lng, lat):
        return {"error": "Coordenadas fuera de Madrid"}

    radius_m = max(100.0, min(radius_m, 3000.0))
    months = max(6, min(months, 120))
    cutoff = datetime.now() - timedelta(days=months * 30)

    min_lng, min_lat, max_lng, max_lat = bbox_for_radius_m(lng, lat, radius_m)

    # Inmueble más cercano (referencia)
    center_row = None
    best_d = float("inf")
    for row in con.execute(
        """
        SELECT id, ndp_edificio, direccion, distrito, barrio, lat, lng
        FROM inmueble
        WHERE lat IS NOT NULL AND lng IS NOT NULL
          AND lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?
        """,
        (min_lat, max_lat, min_lng, max_lng),
    ):
        d = haversine_m(lng, lat, float(row["lng"]), float(row["lat"]))
        if d <= radius_m and d < best_d:
            best_d = d
            center_row = dict(row)

    licencias: list[dict] = []
    seen_lic: set[int] = set()
    for row in con.execute(
        """
        SELECT ae.id, ae.fecha_concesion, ae.fecha_alta, ae.tipo_expediente, ae.uso,
               ae.procedimiento, ae.lat, ae.lng,
               i.ndp_edificio, i.direccion, i.distrito
        FROM actuacion_edificacion ae
        LEFT JOIN inmueble i ON i.id = ae.inmueble_id
        WHERE ae.lat IS NOT NULL AND ae.lng IS NOT NULL
          AND ae.lat BETWEEN ? AND ? AND ae.lng BETWEEN ? AND ?
        """,
        (min_lat, max_lat, min_lng, max_lng),
    ):
        r = dict(row)
        la, ln = float(r["lat"]), float(r["lng"])
        if not is_valid_wgs84_madrid(ln, la):
            continue
        dist = haversine_m(lng, lat, ln, la)
        if dist > radius_m:
            continue
        fecha = r["fecha_concesion"] or r["fecha_alta"]
        fd = parse_fecha_es(fecha)
        if fd and fd < cutoff:
            continue
        if r["id"] in seen_lic:
            continue
        seen_lic.add(r["id"])
        licencias.append(
            {
                "tipo": "licencia",
                "fecha": fecha,
                "distanciaM": round(dist),
                "titulo": (r["tipo_expediente"] or "Licencia urbanística")[:120],
                "detalle": " · ".join(
                    x
                    for x in [r["uso"], r["procedimiento"], r["direccion"]]
                    if x
                )[:200],
                "ndp": r["ndp_edificio"],
                "direccion": r["direccion"],
                "distrito": r["distrito"],
                "lat": la,
                "lng": ln,
            }
        )

    licencias.sort(key=lambda x: fecha_sort_key(x.get("fecha")), reverse=True)

    # SIGMA: polígonos que contienen el punto o tienen centroide cerca
    index = PolygonIndex(cell_deg=0.004)
    sigma_by_grupo: dict[str, dict] = {}

    for row in con.execute(
        """
        SELECT g.expediente_grupo, g.geom_geojson, g.bbox_min_lng, g.bbox_min_lat,
               g.bbox_max_lng, g.bbox_max_lat, g.centroid_lng, g.centroid_lat,
               g.area_approx_m2, c.denominacion, c.fase, c.sigma_layer_kind, c.enlace,
               c.exp_numero_original
        FROM sigma_ambito_geom g
        JOIN sigma_catalog_expediente c ON c.expediente_grupo = g.expediente_grupo
        WHERE g.bbox_max_lng >= ? AND g.bbox_min_lng <= ?
          AND g.bbox_max_lat >= ? AND g.bbox_min_lat <= ?
        """,
        (min_lng, max_lng, min_lat, max_lat),
    ):
        try:
            geom = json.loads(row["geom_geojson"])
        except json.JSONDecodeError:
            continue
        grupo = row["expediente_grupo"]
        clng = row["centroid_lng"]
        clat = row["centroid_lat"]
        dist_centroid = (
            haversine_m(lng, lat, float(clng), float(clat))
            if clng is not None and clat is not None
            else None
        )
        contains = point_in_geom(lng, lat, geom)
        if not contains and (dist_centroid is None or dist_centroid > radius_m):
            continue

        dist = 0.0 if contains else (dist_centroid or radius_m)
        sigma_by_grupo[grupo] = {
            "expediente_grupo": grupo,
            "denominacion": row["denominacion"],
            "fase": row["fase"],
            "sigma_layer_kind": row["sigma_layer_kind"],
            "enlace": row["enlace"],
            "exp_numero_original": row["exp_numero_original"],
            "distanciaM": round(dist),
            "contienePunto": contains,
            "geom": geom,
            "bbox": (row["bbox_min_lng"], row["bbox_min_lat"], row["bbox_max_lng"], row["bbox_max_lat"]),
            "area": row["area_approx_m2"],
        }

    sigma_events: list[dict] = []
    for grupo, meta in sigma_by_grupo.items():
        tram_rows = con.execute(
            """
            SELECT fecha, tramite, organo FROM sigma_vis_tramite
            WHERE expediente_grupo = ?
            ORDER BY orden DESC
            LIMIT 1
            """,
            (grupo,),
        ).fetchall()
        ultima_fecha = None
        ultimo_tramite = None
        if tram_rows:
            ultima_fecha = tram_rows[0]["fecha"]
            ultimo_tramite = tram_rows[0]["tramite"]
        else:
            y = str(meta.get("exp_numero_original") or "").split("/")
            if len(y) >= 2 and y[1].isdigit():
                ultima_fecha = f"01/01/{y[1]}"

        fd = parse_fecha_es(ultima_fecha)
        if fd and fd < cutoff:
            continue

        sigma_events.append(
            {
                "tipo": "sigma",
                "fecha": ultima_fecha,
                "distanciaM": meta["distanciaM"],
                "titulo": (meta["denominacion"] or grupo)[:140],
                "detalle": " · ".join(
                    x
                    for x in [
                        meta.get("fase"),
                        "En tu parcela" if meta["contienePunto"] else f"A {meta['distanciaM']} m",
                    ]
                    if x
                ),
                "expedienteGrupo": grupo,
                "contienePunto": meta["contienePunto"],
                "sigmaLayerKind": meta["sigma_layer_kind"],
                "lat": float(clat) if clat is not None else None,
                "lng": float(clng) if clng is not None else None,
            }
        )

    sigma_events.sort(key=lambda x: fecha_sort_key(x.get("fecha")), reverse=True)

    timeline: list[dict] = []
    for item in licencias[:40]:
        timeline.append(item)
    for item in sigma_events[:40]:
        timeline.append(item)
    timeline.sort(key=lambda x: fecha_sort_key(x.get("fecha")), reverse=True)
    timeline = timeline[:limit]

    return {
        "center": {
            "lat": lat,
            "lng": lng,
            "ndp": center_row["ndp_edificio"] if center_row else None,
            "direccion": center_row["direccion"] if center_row else None,
            "distrito": center_row["distrito"] if center_row else None,
            "barrio": center_row["barrio"] if center_row else None,
        },
        "params": {
            "radiusM": int(radius_m),
            "months": months,
        },
        "stats": {
            "licencias": len(licencias),
            "expedientesSigma": len(sigma_events),
            "eventos": len(timeline),
        },
        "licencias": licencias[:25],
        "expedientesSigma": sigma_events[:20],
        "timeline": timeline,
    }


def resolve_ndp_center(con: sqlite3.Connection, ndp: str) -> tuple[float, float] | None:
    row = con.execute(
        "SELECT lat, lng FROM inmueble WHERE ndp_edificio = ? AND lat IS NOT NULL",
        (ndp,),
    ).fetchone()
    if not row:
        return None
    lat, lng = float(row["lat"]), float(row["lng"])
    if not is_valid_wgs84_madrid(lng, lat):
        return None
    return lat, lng


def main() -> None:
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db.is_file():
        print(json.dumps({"error": f"No existe {db}"}))
        sys.exit(1)

    # JSON stdin or argv: lat lng [radius_m] [months]  OR  ndp=...
    payload: dict = {}
    if not sys.stdin.isatty():
        try:
            payload = json.loads(sys.stdin.read())
        except json.JSONDecodeError:
            payload = {}

    ndp = payload.get("ndp") or (sys.argv[2] if len(sys.argv) > 2 and "/" not in sys.argv[2] else None)
    try:
        lat = float(payload.get("lat") if payload.get("lat") is not None else sys.argv[2])
        lng = float(payload.get("lng") if payload.get("lng") is not None else sys.argv[3])
    except (TypeError, ValueError, IndexError):
        lat = lng = 0.0

    radius_m = float(payload.get("radiusM") or payload.get("radius_m") or 600)
    months = int(payload.get("months") or 24)

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row

    if ndp and not payload.get("lat"):
        coords = resolve_ndp_center(con, str(ndp).strip())
        if not coords:
            print(json.dumps({"error": "NDP sin coordenadas válidas"}))
            sys.exit(2)
        lat, lng = coords

    result = query_boletin(con, lat, lng, radius_m=radius_m, months=months)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
