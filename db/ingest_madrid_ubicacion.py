#!/usr/bin/env python3
"""
Carga modelo v2 (inmueble, actuación edificatoria, geometría SIGMA) y enlaza licencias↔SIGMA por ubicación.

Requisitos previos:
  python3 db/migrate_sqlite.py          # BOCM + catálogo SIGMA + link_project_sigma
  output/madrid_licencias.jsonl         # o JSON web ya geocodificados

Uso:
  python3 db/ingest_madrid_ubicacion.py
  python3 db/ingest_madrid_ubicacion.py --db db/poc_local.sqlite --skip-licencias
  python3 db/ingest_madrid_ubicacion.py --only-link   # solo cruce espacial (tablas ya cargadas)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DB_DIR))

from direccion import build_direccion  # noqa: E402
from geo_utils import (  # noqa: E402
    PolygonIndex,
    geom_area_approx_m2,
    geom_bbox,
    is_valid_wgs84_madrid,
    resolve_licencia_coords,
    ring_centroid,
)
from migrate_sqlite import (  # noqa: E402
    DEFAULT_DB,
    expediente_grupo_from_num,
    null_if_empty,
)

SCHEMA_UBICACION = DB_DIR / "schema_ubicacion.sql"
JSONL_LIC = POC_ROOT / "output/madrid_licencias.jsonl"
WEB_LIC_GLOB = "madrid-licencias-20*.json"
GEOJSON_SOURCES = (
    ("ad", POC_ROOT / "output/madrid_ayto_expedientes_ad.geojson"),
    ("gestion", POC_ROOT / "output/madrid_ayto_expedientes_gestion.geojson"),
    ("urbanizacion", POC_ROOT / "output/madrid_ayto_expedientes_urbanizacion.geojson"),
    ("ip", POC_ROOT / "output/madrid_ayto_expedientes_ip.geojson"),
)


def apply_ubicacion_schema(con: sqlite3.Connection) -> None:
    cur = con.execute("SELECT 1 FROM schema_migrations WHERE version=2")
    if cur.fetchone():
        return
    sql = SCHEMA_UBICACION.read_text(encoding="utf-8")
    con.executescript(sql)
    con.execute("INSERT OR IGNORE INTO schema_migrations (version) VALUES (2)")


def licencia_key(row: dict, *, anio: int | None) -> str:
    parts = [
        str(anio or row.get("anio_dataset") or row.get("anioDataset") or ""),
        str(row.get("ndp_edificio") or row.get("ndpEdificio") or ""),
        str(row.get("fecha_de_alta") or row.get("fechaAlta") or ""),
        str(row.get("tipo_de_expediente") or row.get("tipoExpediente") or ""),
        str(row.get("fecha_concesin") or row.get("fechaConcesion") or ""),
    ]
    return sha256("|".join(parts).encode()).hexdigest()[:32]


def iter_licencias_rows() -> list[dict]:
    """Preferir JSON web (lat/lng ya calculados); fallback JSONL + UTM."""
    web_dir = POC_ROOT / "web/public/data"
    rows: list[dict] = []
    if web_dir.is_dir():
        for path in sorted(web_dir.glob(WEB_LIC_GLOB)):
            try:
                year = int(path.stem.split("-")[-1])
            except ValueError:
                year = None
            for item in json.loads(path.read_text(encoding="utf-8")):
                item = dict(item)
                if year is not None:
                    item.setdefault("anioDataset", year)
                rows.append(item)
    if rows:
        return rows
    if not JSONL_LIC.is_file():
        return []
    out: list[dict] = []
    for line in JSONL_LIC.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def cleanup_invalid_coords(con: sqlite3.Connection) -> dict[str, int]:
    """Elimina coordenadas fuera de Madrid o centinelas 0º0' / Atlántico."""
    n_inm = n_lic = 0
    for row in con.execute("SELECT id, lat, lng FROM inmueble WHERE lat IS NOT NULL AND lng IS NOT NULL"):
        iid, lat, lng = int(row[0]), float(row[1]), float(row[2])
        if not is_valid_wgs84_madrid(lng, lat):
            con.execute(
                "UPDATE inmueble SET lat=NULL, lng=NULL, coord_source=NULL WHERE id=?",
                (iid,),
            )
            n_inm += 1
    for row in con.execute(
        "SELECT id, lat, lng FROM actuacion_edificacion WHERE lat IS NOT NULL AND lng IS NOT NULL"
    ):
        lid, lat, lng = int(row[0]), float(row[1]), float(row[2])
        if not is_valid_wgs84_madrid(lng, lat):
            con.execute(
                "UPDATE actuacion_edificacion SET lat=NULL, lng=NULL WHERE id=?",
                (lid,),
            )
            n_lic += 1
    return {"inmuebles": n_inm, "licencias": n_lic}


def ingest_licencias(con: sqlite3.Connection) -> dict[str, int]:
    rows = iter_licencias_rows()
    stats = {"rows": 0, "inmuebles": 0, "with_coords": 0, "skipped": 0}

    sql_inm = """INSERT INTO inmueble (ndp_edificio, direccion, distrito, barrio, lat, lng, coord_source, updated_at)
        VALUES (?,?,?,?,?,?,?, datetime('now'))
        ON CONFLICT(ndp_edificio) DO UPDATE SET
          direccion=COALESCE(excluded.direccion, direccion),
          distrito=COALESCE(excluded.distrito, distrito),
          barrio=COALESCE(excluded.barrio, barrio),
          lat=COALESCE(excluded.lat, lat),
          lng=COALESCE(excluded.lng, lng),
          coord_source=COALESCE(excluded.coord_source, coord_source),
          updated_at=datetime('now')"""

    sql_lic = """INSERT OR REPLACE INTO actuacion_edificacion (
        licencia_key, inmueble_id, anio_dataset, fecha_alta, fecha_concesion,
        procedimiento, tipo_expediente, uso, interesado, objeto, unidad,
        lat, lng, raw_json
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""

    inmueble_id_cache: dict[str, int] = {}

    for row in rows:
        ndp_raw = row.get("ndp_edificio") or row.get("ndpEdificio")
        if ndp_raw is None or ndp_raw == "":
            stats["skipped"] += 1
            continue
        ndp = str(int(ndp_raw)) if str(ndp_raw).isdigit() else str(ndp_raw).strip()

        coords = resolve_licencia_coords(row)
        lat = lng = None
        coord_src = None
        if coords:
            lng, lat = coords
            coord_src = "web_json" if row.get("lat") is not None else "utm_jsonl"
            stats["with_coords"] += 1

        distrito = null_if_empty(
            str(row.get("descripcin_distrito") or row.get("distrito") or "")
        )
        barrio = null_if_empty(
            str(row.get("descripcion_barrio_bdc") or row.get("barrio") or "")
        )
        direccion = build_direccion(row)

        if ndp not in inmueble_id_cache:
            con.execute(
                sql_inm,
                (ndp, direccion, distrito, barrio, lat, lng, coord_src),
            )
            cur = con.execute("SELECT id FROM inmueble WHERE ndp_edificio=?", (ndp,))
            inmueble_id_cache[ndp] = int(cur.fetchone()[0])
            stats["inmuebles"] += 1

        inm_id = inmueble_id_cache[ndp]
        anio = row.get("anio_dataset") or row.get("anioDataset")
        try:
            anio_i = int(anio) if anio is not None else None
        except (TypeError, ValueError):
            anio_i = None

        key = licencia_key(row, anio=anio_i)
        con.execute(
            sql_lic,
            (
                key,
                inm_id,
                anio_i,
                null_if_empty(str(row.get("fecha_de_alta") or row.get("fechaAlta") or "")),
                null_if_empty(
                    str(row.get("fecha_concesin") or row.get("fechaConcesion") or "")
                ),
                null_if_empty(str(row.get("procedimiento") or "")),
                null_if_empty(
                    str(row.get("tipo_de_expediente") or row.get("tipoExpediente") or "")
                ),
                null_if_empty(str(row.get("uso") or "")),
                null_if_empty(str(row.get("interesado") or "")),
                null_if_empty(
                    str(row.get("objeto_de_la_licencia") or row.get("objeto") or "")
                ),
                null_if_empty(
                    str(row.get("unidad_responsable") or row.get("unidad") or "")
                ),
                lat,
                lng,
                json.dumps(row, ensure_ascii=False),
            ),
        )
        stats["rows"] += 1
        if stats["rows"] % 10000 == 0:
            con.commit()
            print(f"  licencias: {stats['rows']}…", flush=True)

    return stats


def ingest_sigma_geometries(con: sqlite3.Connection) -> dict[str, int]:
    synced = datetime.now(UTC).isoformat()
    stats = {"features": 0, "inserted": 0, "catalog_flags": 0}
    sql = """INSERT OR REPLACE INTO sigma_ambito_geom (
        expediente_grupo, geom_geojson, bbox_min_lng, bbox_min_lat,
        bbox_max_lng, bbox_max_lat, centroid_lng, centroid_lat,
        area_approx_m2, synced_at
    ) VALUES (?,?,?,?,?,?,?,?,?,?)"""

    for _kind, path in GEOJSON_SOURCES:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for feat in data.get("features") or []:
            stats["features"] += 1
            props = feat.get("properties") or {}
            num = str(props.get("EXP_TX_NUMERO") or "").strip()
            grp = expediente_grupo_from_num(num)
            geom = feat.get("geometry")
            if not grp or not geom:
                continue
            bbox = geom_bbox(geom)
            if not bbox:
                continue
            min_lng, min_lat, max_lng, max_lat = bbox
            if geom.get("type") == "Polygon":
                clng, clat = ring_centroid(geom["coordinates"][0])
            elif geom.get("type") == "MultiPolygon" and geom["coordinates"]:
                clng, clat = ring_centroid(geom["coordinates"][0][0])
            else:
                clng, clat = (min_lng + max_lng) / 2, (min_lat + max_lat) / 2
            area = geom_area_approx_m2(geom)
            con.execute(
                sql,
                (
                    grp,
                    json.dumps(geom, ensure_ascii=False),
                    min_lng,
                    min_lat,
                    max_lng,
                    max_lat,
                    clng,
                    clat,
                    area,
                    synced,
                ),
            )
            con.execute(
                "UPDATE sigma_catalog_expediente SET has_geometry=1 WHERE expediente_grupo=?",
                (grp,),
            )
            stats["inserted"] += 1
            stats["catalog_flags"] += 1

    return stats


def link_licencias_sigma(con: sqlite3.Connection) -> dict[str, int]:
    """Punto-en-polígono: cada licencia con coords → expediente(s) SIGMA cuyo ámbito la contiene."""
    index = PolygonIndex(cell_deg=0.005)
    for row in con.execute(
        """SELECT g.expediente_grupo, g.geom_geojson, g.bbox_min_lng, g.bbox_min_lat,
                  g.bbox_max_lng, g.bbox_max_lat, g.area_approx_m2,
                  c.sigma_layer_kind, c.catalog_source
           FROM sigma_ambito_geom g
           JOIN sigma_catalog_expediente c ON c.expediente_grupo = g.expediente_grupo"""
    ):
        geom = json.loads(row[1])
        index.add(
            {
                "grupo": row[0],
                "geom": geom,
                "bbox": (row[2], row[3], row[4], row[5]),
                "area": row[6] or geom_area_approx_m2(geom),
                "layer": row[7] or row[8],
            }
        )

    licencias = list(
        con.execute(
            "SELECT id, lat, lng FROM actuacion_edificacion WHERE lat IS NOT NULL AND lng IS NOT NULL"
        )
    )

    con.execute("DELETE FROM link_licencia_sigma")
    sql_link = """INSERT OR IGNORE INTO link_licencia_sigma (
        licencia_id, expediente_grupo, match_method, match_score, sigma_layer_kind
    ) VALUES (?,?,?,?,?)"""

    stats = {
        "poligonos_indexados": len(index.polys),
        "licencias_con_coords": len(licencias),
        "links": 0,
        "licencias_con_al_menos_un_sigma": 0,
        "licencias_sin_match": 0,
    }
    licencias_con_match: set[int] = set()
    link_buf: list[tuple] = []

    for i, (lic_id, lat, lng) in enumerate(licencias):
        hits = index.query(lng, lat)
        if not hits:
            stats["licencias_sin_match"] += 1
            continue
        licencias_con_match.add(lic_id)
        hits.sort(key=lambda h: h["area"])
        for h in hits:
            score = 1.0 / len(hits) if len(hits) > 1 else 1.0
            link_buf.append(
                (lic_id, h["grupo"], "point_in_polygon", score, h["layer"])
            )
        if (i + 1) % 20000 == 0:
            print(f"  enlace: {i + 1}/{len(licencias)}…", flush=True)

    con.executemany(sql_link, link_buf)
    stats["links"] = len(link_buf)
    stats["licencias_con_al_menos_un_sigma"] = len(licencias_con_match)
    return stats


def sync_hitos_from_tramites(con: sqlite3.Connection) -> int:
    """Copia sigma_vis_tramite → hito (si existe tabla de visor)."""
    cur = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sigma_vis_tramite'"
    )
    if not cur.fetchone():
        return 0
    sql = """INSERT OR IGNORE INTO hito (entidad_tipo, entidad_id, fecha, tipo, organo, fuente, detalle_json)
        SELECT 'sigma', expediente_grupo, fecha, tramite, organo, 'sigma_vis_tramite', NULL
        FROM sigma_vis_tramite"""
    con.execute(sql)
    return con.execute("SELECT changes()").fetchone()[0]


def main() -> None:
    ap = argparse.ArgumentParser(description="Modelo ubicación Madrid + enlace licencias↔SIGMA.")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--skip-licencias", action="store_true")
    ap.add_argument("--skip-geom", action="store_true")
    ap.add_argument("--skip-link", action="store_true")
    ap.add_argument("--only-link", action="store_true")
    args = ap.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.db) as con:
        apply_ubicacion_schema(con)

        out: dict[str, object] = {"db": str(args.db)}

        if not args.only_link:
            if not args.skip_geom:
                out["sigma_geom"] = ingest_sigma_geometries(con)
            if not args.skip_licencias:
                out["licencias"] = ingest_licencias(con)
                out["cleanup_invalid_coords"] = cleanup_invalid_coords(con)
            out["hitos_from_tramites"] = sync_hitos_from_tramites(con)

        if not args.skip_link:
            out["link_licencia_sigma"] = link_licencias_sigma(con)

        con.commit()

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
