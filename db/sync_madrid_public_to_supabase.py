#!/usr/bin/env python3
"""
Sync directo de datos publicos Madrid -> Supabase, sin SQLite intermedio.

Alcance barato:
  - source
  - sigma_catalog_expediente
  - sigma_ambito_geom
  - inmueble
  - actuacion_edificacion

No calcula link_licencia_sigma: ese cruce punto-en-poligono es el proceso caro.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

import psycopg2
from psycopg2.extras import Json, execute_values

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DB_DIR))

from direccion import build_direccion  # noqa: E402
from geo_utils import (  # noqa: E402
    geom_area_approx_m2,
    geom_bbox,
    is_valid_wgs84_madrid,
    resolve_licencia_coords,
    ring_centroid,
)
from migrate_sqlite import expediente_grupo_from_num, ms_to_iso_date, null_if_empty  # noqa: E402

SCHEMA = "homes"
BATCH = 5000
JSONL_LIC = POC_ROOT / "output/madrid_licencias.jsonl"
SIGMA_INDEX = POC_ROOT / "output/madrid_ayto_expedientes_index.json"
GEOJSON_SOURCES = (
    POC_ROOT / "output/madrid_ayto_expedientes_ad.geojson",
    POC_ROOT / "output/madrid_ayto_expedientes_gestion.geojson",
    POC_ROOT / "output/madrid_ayto_expedientes_urbanizacion.geojson",
    POC_ROOT / "output/madrid_ayto_expedientes_ip.geojson",
)


def pg_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Falta SUPABASE_DB_URL o DATABASE_URL")
    return url


def chunks[T](rows: list[T], size: int = BATCH) -> Iterable[list[T]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def insert_values(cur, table: str, columns: list[str], rows: list[tuple], conflict: str = "") -> int:
    if not rows:
        return 0
    cols = ", ".join(columns)
    sql = f"INSERT INTO {SCHEMA}.{table} ({cols}) VALUES %s"
    if conflict:
        sql += f" ON CONFLICT {conflict}"
    for batch in chunks(rows):
        execute_values(cur, sql, batch, page_size=len(batch))
    return len(rows)


def sync_sources(cur) -> int:
    return insert_values(
        cur,
        "source",
        ["id", "territorio_id", "territorio_label"],
        [
            ("bocm", "comunidad-madrid", "Comunidad de Madrid"),
            ("madrid-ayto", "madrid", "Madrid"),
        ],
        conflict="(id) DO UPDATE SET territorio_id = EXCLUDED.territorio_id, territorio_label = EXCLUDED.territorio_label",
    )


def load_sigma_catalog() -> tuple[list[tuple], set[str]]:
    if not SIGMA_INDEX.is_file():
        return [], set()
    raw = json.loads(SIGMA_INDEX.read_text(encoding="utf-8"))
    synced_at = raw.get("generatedAt") or datetime.now(UTC).isoformat()
    rows_by_grupo: dict[str, tuple] = {}
    grupos: set[str] = set()
    for item in raw.get("expedientes") or []:
        num = str(item.get("EXP_TX_NUMERO") or "").strip()
        grupo = expediente_grupo_from_num(num)
        if not grupo:
            continue
        grupos.add(grupo)
        rows_by_grupo[grupo] = (
            grupo,
            num,
            item.get("sigma_layer_kind") or item.get("source"),
            null_if_empty(str(item.get("EXP_TX_DENOM") or "")),
            null_if_empty(str(item.get("FAS_TX_DENOM") or "")),
            ms_to_iso_date(item.get("FEX_DT_APROB")),
            ms_to_iso_date(item.get("FEX_DT_INFOPUB_INI")),
            ms_to_iso_date(item.get("FEX_DT_INFOPUB_FIN")),
            null_if_empty(str(item.get("FIG_TX_ETIQ") or "")),
            null_if_empty(str(item.get("TFIG_TX_ABREV") or "")),
            null_if_empty(str(item.get("ORG_TX_DESC") or "")),
            null_if_empty(str(item.get("Enlace") or "")),
            null_if_empty(str(item.get("source") or "")),
            int(item["EXP_ID"]) if item.get("EXP_ID") not in (None, "") else None,
            bool(item.get("has_geometry")),
            synced_at,
            Json(item),
        )
    return list(rows_by_grupo.values()), grupos


def sync_sigma_catalog(cur) -> int:
    rows, _ = load_sigma_catalog()
    return insert_values(
        cur,
        "sigma_catalog_expediente",
        [
            "expediente_grupo",
            "exp_numero_original",
            "sigma_layer_kind",
            "denominacion",
            "fase",
            "fecha_aprob",
            "infopublica_inicio",
            "infopublica_fin",
            "figura_codigo",
            "tipo_figura",
            "organo_tramitador",
            "enlace",
            "catalog_source",
            "object_id",
            "has_geometry",
            "synced_at",
            "raw_features_json",
        ],
        rows,
        conflict="""(expediente_grupo) DO UPDATE SET
          exp_numero_original = EXCLUDED.exp_numero_original,
          sigma_layer_kind = EXCLUDED.sigma_layer_kind,
          denominacion = EXCLUDED.denominacion,
          fase = EXCLUDED.fase,
          fecha_aprob = EXCLUDED.fecha_aprob,
          infopublica_inicio = EXCLUDED.infopublica_inicio,
          infopublica_fin = EXCLUDED.infopublica_fin,
          figura_codigo = EXCLUDED.figura_codigo,
          tipo_figura = EXCLUDED.tipo_figura,
          organo_tramitador = EXCLUDED.organo_tramitador,
          enlace = EXCLUDED.enlace,
          catalog_source = EXCLUDED.catalog_source,
          object_id = EXCLUDED.object_id,
          has_geometry = EXCLUDED.has_geometry,
          synced_at = EXCLUDED.synced_at,
          raw_features_json = EXCLUDED.raw_features_json""",
    )


def load_sigma_ambitos() -> list[tuple]:
    synced_at = datetime.now(UTC).isoformat()
    rows_by_grupo: dict[str, tuple] = {}
    for path in GEOJSON_SOURCES:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            grupo = expediente_grupo_from_num(str(props.get("EXP_TX_NUMERO") or ""))
            geom = feat.get("geometry")
            if not grupo or not geom:
                continue
            bbox = geom_bbox(geom)
            if not bbox:
                continue
            min_lng, min_lat, max_lng, max_lat = bbox
            if geom.get("type") == "Polygon":
                clng, clat = ring_centroid(geom["coordinates"][0])
            elif geom.get("type") == "MultiPolygon" and geom.get("coordinates"):
                clng, clat = ring_centroid(geom["coordinates"][0][0])
            else:
                clng, clat = (min_lng + max_lng) / 2, (min_lat + max_lat) / 2
            rows_by_grupo[grupo] = (
                grupo,
                Json(geom),
                min_lng,
                min_lat,
                max_lng,
                max_lat,
                clng,
                clat,
                geom_area_approx_m2(geom),
                synced_at,
            )
    return list(rows_by_grupo.values())


def sync_sigma_ambitos(cur) -> int:
    rows = load_sigma_ambitos()
    n = insert_values(
        cur,
        "sigma_ambito_geom",
        [
            "expediente_grupo",
            "geom_geojson",
            "bbox_min_lng",
            "bbox_min_lat",
            "bbox_max_lng",
            "bbox_max_lat",
            "centroid_lng",
            "centroid_lat",
            "area_approx_m2",
            "synced_at",
        ],
        rows,
        conflict="""(expediente_grupo) DO UPDATE SET
          geom_geojson = EXCLUDED.geom_geojson,
          bbox_min_lng = EXCLUDED.bbox_min_lng,
          bbox_min_lat = EXCLUDED.bbox_min_lat,
          bbox_max_lng = EXCLUDED.bbox_max_lng,
          bbox_max_lat = EXCLUDED.bbox_max_lat,
          centroid_lng = EXCLUDED.centroid_lng,
          centroid_lat = EXCLUDED.centroid_lat,
          area_approx_m2 = EXCLUDED.area_approx_m2,
          synced_at = EXCLUDED.synced_at""",
    )
    cur.execute(
        f"""UPDATE {SCHEMA}.sigma_catalog_expediente c
            SET has_geometry = true
            WHERE EXISTS (
              SELECT 1 FROM {SCHEMA}.sigma_ambito_geom g
              WHERE g.expediente_grupo = c.expediente_grupo
            )"""
    )
    return n


def licencia_key(row: dict[str, Any], *, anio: int | None) -> str:
    parts = [
        str(anio or row.get("anio_dataset") or row.get("anioDataset") or ""),
        str(row.get("ndp_edificio") or row.get("ndpEdificio") or ""),
        str(row.get("fecha_de_alta") or row.get("fechaAlta") or ""),
        str(row.get("tipo_de_expediente") or row.get("tipoExpediente") or ""),
        str(row.get("fecha_concesin") or row.get("fechaConcesion") or ""),
    ]
    return sha256("|".join(parts).encode()).hexdigest()[:32]


def iter_licencias_rows() -> Iterable[dict[str, Any]]:
    if not JSONL_LIC.is_file():
        return
    with JSONL_LIC.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_licencias() -> tuple[list[tuple], list[tuple], dict[str, int]]:
    inmuebles: dict[str, dict[str, Any]] = {}
    actuaciones_by_key: dict[str, tuple] = {}
    stats = {"rows": 0, "skipped": 0, "with_coords": 0}

    for row in iter_licencias_rows():
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
            if not is_valid_wgs84_madrid(lng, lat):
                lat = lng = None
            else:
                coord_src = "utm_jsonl"
                stats["with_coords"] += 1

        current = inmuebles.get(ndp, {})
        if ndp not in inmuebles or (current.get("lat") is None and lat is not None):
            inmuebles[ndp] = {
                "direccion": build_direccion(row) or current.get("direccion"),
                "distrito": null_if_empty(str(row.get("descripcin_distrito") or row.get("distrito") or ""))
                or current.get("distrito"),
                "barrio": null_if_empty(
                    str(row.get("descripcion_barrio_bdc") or row.get("barrio") or "")
                )
                or current.get("barrio"),
                "lat": lat if lat is not None else current.get("lat"),
                "lng": lng if lng is not None else current.get("lng"),
                "coord_source": coord_src or current.get("coord_source"),
            }

        anio = row.get("anio_dataset") or row.get("anioDataset")
        try:
            anio_i = int(anio) if anio is not None else None
        except (TypeError, ValueError):
            anio_i = None

        stats["rows"] += 1
        key = licencia_key(row, anio=anio_i)
        actuaciones_by_key[key] = (
            key,
            ndp,
            anio_i,
            null_if_empty(str(row.get("fecha_de_alta") or row.get("fechaAlta") or "")),
            null_if_empty(str(row.get("fecha_concesin") or row.get("fechaConcesion") or "")),
            null_if_empty(str(row.get("procedimiento") or "")),
            null_if_empty(str(row.get("tipo_de_expediente") or row.get("tipoExpediente") or "")),
            null_if_empty(str(row.get("uso") or "")),
            null_if_empty(str(row.get("interesado") or "")),
            null_if_empty(str(row.get("objeto_de_la_licencia") or row.get("objeto") or "")),
            null_if_empty(str(row.get("unidad_responsable") or row.get("unidad") or "")),
            lat,
            lng,
            Json(row),
        )

    inmueble_rows: list[tuple] = []
    inmueble_id_by_ndp: dict[str, int] = {}
    now = datetime.now(UTC).isoformat()
    for idx, (ndp, rec) in enumerate(sorted(inmuebles.items()), start=1):
        inmueble_id_by_ndp[ndp] = idx
        inmueble_rows.append(
            (
                idx,
                ndp,
                rec.get("direccion"),
                rec.get("distrito"),
                rec.get("barrio"),
                rec.get("lat"),
                rec.get("lng"),
                rec.get("coord_source"),
                now,
                now,
            )
        )

    actuacion_rows = [
        (
            i,
            key,
            inmueble_id_by_ndp[ndp],
            anio,
            fecha_alta,
            fecha_concesion,
            procedimiento,
            tipo_expediente,
            uso,
            interesado,
            objeto,
            unidad,
            lat,
            lng,
            raw,
            now,
        )
        for i, (
            key,
            ndp,
            anio,
            fecha_alta,
            fecha_concesion,
            procedimiento,
            tipo_expediente,
            uso,
            interesado,
            objeto,
            unidad,
            lat,
            lng,
            raw,
        ) in enumerate(actuaciones_by_key.values(), start=1)
        if ndp in inmueble_id_by_ndp
    ]

    stats["inmuebles"] = len(inmueble_rows)
    stats["duplicated_licencia_keys"] = stats["rows"] - len(actuaciones_by_key)
    return inmueble_rows, actuacion_rows, stats


def sync_licencias(cur) -> dict[str, int]:
    inmueble_rows, actuacion_rows, stats = load_licencias()

    cur.execute(f"TRUNCATE TABLE {SCHEMA}.link_licencia_sigma, {SCHEMA}.actuacion_edificacion, {SCHEMA}.inmueble RESTART IDENTITY CASCADE")

    insert_values(
        cur,
        "inmueble",
        ["id", "ndp_edificio", "direccion", "distrito", "barrio", "lat", "lng", "coord_source", "inserted_at", "updated_at"],
        inmueble_rows,
    )
    insert_values(
        cur,
        "actuacion_edificacion",
        [
            "id",
            "licencia_key",
            "inmueble_id",
            "anio_dataset",
            "fecha_alta",
            "fecha_concesion",
            "procedimiento",
            "tipo_expediente",
            "uso",
            "interesado",
            "objeto",
            "unidad",
            "lat",
            "lng",
            "raw_json",
            "inserted_at",
        ],
        actuacion_rows,
    )
    for table, column in (("inmueble", "id"), ("actuacion_edificacion", "id")):
        cur.execute(
            f"SELECT setval(pg_get_serial_sequence('{SCHEMA}.{table}', '{column}'), "
            f"COALESCE((SELECT MAX({column}) FROM {SCHEMA}.{table}), 1))"
        )
    stats["actuaciones"] = len(actuacion_rows)
    stats["links"] = 0
    return stats


def summarize(cur) -> dict[str, int | None]:
    tables = [
        "sigma_catalog_expediente",
        "sigma_ambito_geom",
        "inmueble",
        "actuacion_edificacion",
        "link_licencia_sigma",
    ]
    out: dict[str, int | None] = {}
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{table}")
        out[table] = int(cur.fetchone()[0])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Sync Madrid public datasets directly to Supabase.")
    ap.add_argument("--skip-licencias", action="store_true", help="Only sync SIGMA catalog/geometries.")
    args = ap.parse_args()

    with psycopg2.connect(pg_url()) as con:
        with con.cursor() as cur:
            out: dict[str, Any] = {}
            out["source"] = sync_sources(cur)
            out["sigma_catalog"] = sync_sigma_catalog(cur)
            out["sigma_ambito_geom"] = sync_sigma_ambitos(cur)
            if not args.skip_licencias:
                out["licencias"] = sync_licencias(cur)
            out["counts"] = summarize(cur)
            cur.execute(f"ANALYZE {SCHEMA}.sigma_catalog_expediente")
            cur.execute(f"ANALYZE {SCHEMA}.sigma_ambito_geom")
            if not args.skip_licencias:
                cur.execute(f"ANALYZE {SCHEMA}.inmueble")
                cur.execute(f"ANALYZE {SCHEMA}.actuacion_edificacion")
        con.commit()
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
