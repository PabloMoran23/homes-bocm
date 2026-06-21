#!/usr/bin/env python3
"""
Sync datos del portal municipal (output/municipios/<slug>/) → Supabase homes.*.

Uso:
  python3 db/sync_municipio_to_supabase.py --municipio torrejon-de-ardoz
  python3 db/sync_municipio_to_supabase.py --all-done
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json, execute_values

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DB_DIR))

from migrate_sqlite import null_if_empty  # noqa: E402
from sync_dominio_to_supabase import PROYECTO_COLS, _blank_proyecto  # noqa: E402
from sync_madrid_public_to_supabase import SCHEMA, _next_row_ids, pg_url  # noqa: E402

sys.path.insert(0, str(POC_ROOT))
from municipio.geometry import geometry_bbox, record_geometry  # noqa: E402
from municipio.manifest import list_manifest_slugs, load_manifest  # noqa: E402

CATALOG_SOURCE = "ayuntamiento-portal"

LICENCIA_COLS = [
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
    "proyecto_id",
    "proyecto_match_method",
    "proyecto_match_score",
    "proyecto_sigma_layer_kind",
    "proyecto_linked_at",
    "inserted_at",
    "updated_at",
]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _proyecto_dict(rec: dict[str, Any], manifest) -> dict[str, Any]:
    now = datetime.now(UTC)
    p = _blank_proyecto()
    titulo = str(rec.get("titulo") or rec.get("denominacion") or "").strip()
    tipo = str(rec.get("tipo") or "").strip()
    fecha = null_if_empty(str(rec.get("fecha") or ""))
    pub_date = fecha[:10] if fecha and len(fecha) >= 10 else None
    lat = rec.get("lat")
    lng = rec.get("lon") if rec.get("lon") is not None else rec.get("lng")
    coord_source = null_if_empty(str(rec.get("coord_source") or ""))
    url = null_if_empty(str(rec.get("url") or ""))
    docs: list[str] = []
    if rec.get("pdf_url"):
        docs.append(str(rec["pdf_url"]))
    if isinstance(rec.get("pdf_urls"), list):
        docs.extend(str(u) for u in rec["pdf_urls"][:20])
    docs = list(dict.fromkeys(docs))
    pdf_url = docs[0] if docs else None
    geom = record_geometry(rec)
    bbox = geometry_bbox(geom) if geom else None
    has_geom = geom is not None and str(geom.get("type") or "") in {
        "Polygon",
        "MultiPolygon",
        "LineString",
        "MultiLineString",
        "Point",
        "MultiPoint",
    }

    p.update(
        {
            "id": str(rec["id"]),
            "denominacion": null_if_empty(titulo),
            "fecha_aprob": pub_date,
            "enlace": url,
            "catalog_source": CATALOG_SOURCE,
            "has_geometry": has_geom,
            "geom_geojson": Json(geom) if geom else None,
            "bbox_min_lng": bbox[0] if bbox else None,
            "bbox_min_lat": bbox[1] if bbox else None,
            "bbox_max_lng": bbox[2] if bbox else None,
            "bbox_max_lat": bbox[3] if bbox else None,
            "centroid_lat": float(lat) if lat is not None else None,
            "centroid_lng": float(lng) if lng is not None else None,
            "raw_features_json": Json({k: v for k, v in rec.items() if k != "id"}),
            "sin_datos_visor": False,
            "visor_url": url,
            "tramitacion": Json([]),
            "documentacion_urls": Json(docs),
            "nti_documentos_total": len(docs) if docs else None,
            "nti_documentos_muestra": Json(docs[:5]),
            "nti_listado_url": url,
            "visor_fetched_at": now,
            "visor_raw_json": Json(rec),
            "resumen_contenido": null_if_empty(titulo),
            "tipo_legal": null_if_empty(tipo),
            "contenido_principal": null_if_empty(titulo),
            "fase": null_if_empty(tipo),
            "clasificacion_fuentes": Json(
                {
                    "source": "ayuntamiento",
                    "slug": manifest.slug,
                    "origen": rec.get("origen"),
                }
            ),
            "bocm_source_id": "ayuntamiento-portal",
            "bocm_pub_date": pub_date,
            "bocm_title": null_if_empty(titulo),
            "bocm_pdf_url": pdf_url,
            "bocm_municipio": manifest.nombre,
            "bocm_tipo_instrumento": null_if_empty(tipo),
            "bocm_resumen": null_if_empty(titulo[:800] if titulo else ""),
            "bocm_es_relevante": True,
            "municipio": manifest.nombre,
            "lat": float(lat) if lat is not None else None,
            "lng": float(lng) if lng is not None else None,
            "coord_source": coord_source or ("ayuntamiento-portal" if lat is not None else None),
            "sector_key": manifest.slug,
            "inserted_at": now,
            "updated_at": now,
        }
    )
    return p


def _proyecto_tuple(p: dict[str, Any]) -> tuple:
    return tuple(p[c] for c in PROYECTO_COLS)


def _licencia_row(rec: dict[str, Any], *, row_id: int, manifest) -> tuple:
    now = datetime.now(UTC)
    lat = rec.get("lat")
    lng = rec.get("lon") if rec.get("lon") is not None else rec.get("lng")
    key = str(rec.get("id") or rec.get("licencia_key") or "")
    fecha_concesion = null_if_empty(str(rec.get("fecha_concesion") or rec.get("fecha") or ""))
    anio = None
    if fecha_concesion and len(fecha_concesion) >= 4 and fecha_concesion[:4].isdigit():
        anio = int(fecha_concesion[:4])
    return (
        row_id,
        key,
        None,
        anio,
        null_if_empty(str(rec.get("fecha_alta") or "")),
        fecha_concesion,
        null_if_empty(str(rec.get("procedimiento") or "")),
        null_if_empty(str(rec.get("tipo") or "")),
        null_if_empty(str(rec.get("uso") or "")),
        null_if_empty(str(rec.get("interesado") or "")),
        null_if_empty(str(rec.get("titulo") or rec.get("objeto") or "")),
        null_if_empty(str(rec.get("unidad") or rec.get("distrito") or "")),
        float(lat) if lat is not None else None,
        float(lng) if lng is not None else None,
        Json(
            {
                **rec,
                "municipio_slug": manifest.slug,
                "municipio": manifest.nombre,
                "coord_source": rec.get("coord_source"),
                "source": "ayuntamiento",
            }
        ),
        None,
        None,
        None,
        None,
        None,
        now,
        now,
    )


def sync_municipio(slug: str, *, dry_run: bool = False) -> dict[str, Any]:
    manifest = load_manifest(slug)
    out_dir = manifest.output_dir
    proyectos = _read_jsonl(out_dir / "proyectos.jsonl")
    licencias = _read_jsonl(out_dir / "licencias.jsonl")
    stats: dict[str, Any] = {
        "slug": slug,
        "nombre": manifest.nombre,
        "proyectos": len(proyectos),
        "licencias": len(licencias),
        "dry_run": dry_run,
    }
    if not proyectos and not licencias:
        stats["status"] = "skipped"
        stats["reason"] = "sin datos en output/municipios"
        return stats

    proyecto_rows = [_proyecto_tuple(_proyecto_dict(r, manifest)) for r in proyectos if r.get("id")]
    licencia_keys = [str(r["id"]) for r in licencias if r.get("id")]
    proy_with_coords = sum(
        1 for r in proyectos if r.get("lat") is not None and (r.get("lon") is not None or r.get("lng") is not None)
    )
    proy_with_geom = sum(1 for r in proyectos if record_geometry(r))
    lic_with_coords = sum(
        1 for r in licencias if r.get("lat") is not None and (r.get("lon") is not None or r.get("lng") is not None)
    )
    stats["proyectos_with_coords"] = proy_with_coords
    stats["proyectos_with_geometry"] = proy_with_geom
    stats["licencias_with_coords"] = lic_with_coords

    if dry_run:
        stats["status"] = "dry_run"
        return stats

    with psycopg2.connect(pg_url()) as conn:
        with conn.cursor() as cur:
            if proyecto_rows:
                cols = ", ".join(PROYECTO_COLS)
                sql = f"""
                    INSERT INTO {SCHEMA}.proyecto ({cols}) VALUES %s
                    ON CONFLICT (id) DO UPDATE SET
                      denominacion = EXCLUDED.denominacion,
                      enlace = EXCLUDED.enlace,
                      visor_url = EXCLUDED.visor_url,
                      resumen_contenido = EXCLUDED.resumen_contenido,
                      tipo_legal = EXCLUDED.tipo_legal,
                      contenido_principal = EXCLUDED.contenido_principal,
                      fase = EXCLUDED.fase,
                      documentacion_urls = EXCLUDED.documentacion_urls,
                      nti_listado_url = EXCLUDED.nti_listado_url,
                      municipio = EXCLUDED.municipio,
                      bocm_municipio = EXCLUDED.bocm_municipio,
                      bocm_pub_date = COALESCE(EXCLUDED.bocm_pub_date, {SCHEMA}.proyecto.bocm_pub_date),
                      bocm_title = EXCLUDED.bocm_title,
                      bocm_pdf_url = COALESCE(EXCLUDED.bocm_pdf_url, {SCHEMA}.proyecto.bocm_pdf_url),
                      bocm_tipo_instrumento = EXCLUDED.bocm_tipo_instrumento,
                      bocm_resumen = EXCLUDED.bocm_resumen,
                      bocm_source_id = EXCLUDED.bocm_source_id,
                      bocm_es_relevante = EXCLUDED.bocm_es_relevante,
                      lat = COALESCE(EXCLUDED.lat, {SCHEMA}.proyecto.lat),
                      lng = COALESCE(EXCLUDED.lng, {SCHEMA}.proyecto.lng),
                      coord_source = COALESCE(EXCLUDED.coord_source, {SCHEMA}.proyecto.coord_source),
                      has_geometry = EXCLUDED.has_geometry OR {SCHEMA}.proyecto.has_geometry,
                      geom_geojson = COALESCE(EXCLUDED.geom_geojson, {SCHEMA}.proyecto.geom_geojson),
                      bbox_min_lng = COALESCE(EXCLUDED.bbox_min_lng, {SCHEMA}.proyecto.bbox_min_lng),
                      bbox_min_lat = COALESCE(EXCLUDED.bbox_min_lat, {SCHEMA}.proyecto.bbox_min_lat),
                      bbox_max_lng = COALESCE(EXCLUDED.bbox_max_lng, {SCHEMA}.proyecto.bbox_max_lng),
                      bbox_max_lat = COALESCE(EXCLUDED.bbox_max_lat, {SCHEMA}.proyecto.bbox_max_lat),
                      centroid_lat = COALESCE(EXCLUDED.centroid_lat, {SCHEMA}.proyecto.centroid_lat),
                      centroid_lng = COALESCE(EXCLUDED.centroid_lng, {SCHEMA}.proyecto.centroid_lng),
                      sector_key = EXCLUDED.sector_key,
                      raw_features_json = EXCLUDED.raw_features_json,
                      visor_raw_json = EXCLUDED.visor_raw_json,
                      clasificacion_fuentes = EXCLUDED.clasificacion_fuentes,
                      catalog_source = EXCLUDED.catalog_source,
                      updated_at = EXCLUDED.updated_at
                """
                execute_values(cur, sql, proyecto_rows, page_size=100)

            if licencia_keys:
                id_map = _next_row_ids(cur, "licencia", licencia_keys)
                licencia_rows = [
                    _licencia_row(r, row_id=id_map[str(r["id"])], manifest=manifest)
                    for r in licencias
                    if r.get("id")
                ]
                cols = ", ".join(LICENCIA_COLS)
                sql = f"""
                    INSERT INTO {SCHEMA}.licencia ({cols}) VALUES %s
                    ON CONFLICT (licencia_key) DO UPDATE SET
                      anio_dataset = COALESCE(EXCLUDED.anio_dataset, {SCHEMA}.licencia.anio_dataset),
                      fecha_concesion = COALESCE(EXCLUDED.fecha_concesion, {SCHEMA}.licencia.fecha_concesion),
                      tipo_expediente = COALESCE(EXCLUDED.tipo_expediente, {SCHEMA}.licencia.tipo_expediente),
                      objeto = COALESCE(EXCLUDED.objeto, {SCHEMA}.licencia.objeto),
                      unidad = COALESCE(EXCLUDED.unidad, {SCHEMA}.licencia.unidad),
                      lat = COALESCE(EXCLUDED.lat, {SCHEMA}.licencia.lat),
                      lng = COALESCE(EXCLUDED.lng, {SCHEMA}.licencia.lng),
                      raw_json = EXCLUDED.raw_json,
                      updated_at = EXCLUDED.updated_at
                """
                execute_values(cur, sql, licencia_rows, page_size=200)
        conn.commit()

    stats["status"] = "ok"
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync portal municipal → Supabase")
    parser.add_argument("--municipio", "-m", action="append", dest="municipios")
    parser.add_argument("--all-done", action="store_true", help="Sync todos los manifests existentes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    slugs = args.municipios or []
    if args.all_done:
        slugs = list_manifest_slugs()
    if not slugs:
        parser.error("Indica --municipio <slug> o --all-done")

    results = []
    for slug in slugs:
        try:
            results.append(sync_municipio(slug, dry_run=args.dry_run))
        except Exception as e:
            results.append({"slug": slug, "status": "error", "error": str(e)})

    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0 if all(r.get("status") in ("ok", "dry_run", "skipped") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
