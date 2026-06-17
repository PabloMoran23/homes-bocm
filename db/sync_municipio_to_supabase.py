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
    fecha = null_if_empty(str(rec.get("fecha") or ""))
    pub_date = fecha[:10] if fecha and len(fecha) >= 10 else None
    lat = rec.get("lat")
    lng = rec.get("lon") if rec.get("lon") is not None else rec.get("lng")
    docs: list[str] = []
    if rec.get("pdf_url"):
        docs.append(str(rec["pdf_url"]))
    if isinstance(rec.get("pdf_urls"), list):
        docs.extend(str(u) for u in rec["pdf_urls"][:20])
    docs = list(dict.fromkeys(docs))

    p.update(
        {
            "id": str(rec["id"]),
            "denominacion": null_if_empty(str(rec.get("titulo") or "")),
            "fecha_aprob": pub_date,
            "enlace": null_if_empty(str(rec.get("url") or "")),
            "catalog_source": CATALOG_SOURCE,
            "raw_features_json": Json({k: v for k, v in rec.items() if k != "id"}),
            "sin_datos_visor": False,
            "visor_url": null_if_empty(str(rec.get("url") or "")),
            "tramitacion": Json([]),
            "documentacion_urls": Json(docs),
            "nti_documentos_total": len(docs) if docs else None,
            "nti_documentos_muestra": Json(docs[:5]),
            "visor_fetched_at": now,
            "visor_raw_json": Json(rec),
            "tipo_legal": null_if_empty(str(rec.get("tipo") or "")),
            "contenido_principal": null_if_empty(str(rec.get("titulo") or "")),
            "clasificacion_fuentes": Json({"source": "ayuntamiento", "slug": manifest.slug}),
            "municipio": manifest.nombre,
            "lat": float(lat) if lat is not None else None,
            "lng": float(lng) if lng is not None else None,
            "coord_source": "ayuntamiento-portal" if lat is not None and lng is not None else None,
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
    return (
        row_id,
        key,
        None,
        None,
        null_if_empty(str(rec.get("fecha_alta") or "")),
        null_if_empty(str(rec.get("fecha_concesion") or rec.get("fecha") or "")),
        null_if_empty(str(rec.get("procedimiento") or "")),
        null_if_empty(str(rec.get("tipo") or "")),
        null_if_empty(str(rec.get("uso") or "")),
        null_if_empty(str(rec.get("interesado") or "")),
        null_if_empty(str(rec.get("titulo") or rec.get("objeto") or "")),
        null_if_empty(str(rec.get("unidad") or rec.get("distrito") or "")),
        float(lat) if lat is not None else None,
        float(lng) if lng is not None else None,
        Json({**rec, "municipio_slug": manifest.slug, "municipio": manifest.nombre}),
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
                      tipo_legal = EXCLUDED.tipo_legal,
                      contenido_principal = EXCLUDED.contenido_principal,
                      documentacion_urls = EXCLUDED.documentacion_urls,
                      municipio = EXCLUDED.municipio,
                      lat = COALESCE(EXCLUDED.lat, {SCHEMA}.proyecto.lat),
                      lng = COALESCE(EXCLUDED.lng, {SCHEMA}.proyecto.lng),
                      coord_source = COALESCE(EXCLUDED.coord_source, {SCHEMA}.proyecto.coord_source),
                      raw_features_json = EXCLUDED.raw_features_json,
                      visor_raw_json = EXCLUDED.visor_raw_json,
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
