#!/usr/bin/env python3
"""
Sube datos de poc_local.sqlite → Supabase (esquema homes).

Requisitos:
  pip install -r db/requirements-supabase.txt
  export SUPABASE_DB_URL='postgresql://postgres.[ref]:[PASSWORD]@aws-0-eu-west-3.pooler.supabase.com:6543/postgres'

Uso:
  python3 db/sync_sqlite_to_supabase.py              # todas las tablas
  python3 db/sync_sqlite_to_supabase.py --only sigma,inmueble
  python3 db/sync_sqlite_to_supabase.py --truncate  # vacía homes.* antes (cuidado)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE = POC_ROOT / "db" / "poc_local.sqlite"
VISOR_JSON = POC_ROOT / "output" / "madrid_viso_expedientes.json"
SCHEMA = "homes"
BATCH = 4000

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sigma_classification import classify_sigma_project  # noqa: E402
from visor_resumen import resumen_contenido_from_visor_ficha  # noqa: E402


def pg_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print(
            "Falta SUPABASE_DB_URL (connection string Postgres del proyecto Supabase).\n"
            "Dashboard → Project Settings → Database → Connection string → URI",
            file=sys.stderr,
        )
        sys.exit(1)
    return url


def as_bool(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    return bool(int(v))


def as_json(v: Any) -> Any | None:
    if v is None or v == "":
        return None
    if isinstance(v, (dict, list)):
        return v
    return json.loads(v)


def as_ts(v: Any) -> str | None:
    if v is None or v == "":
        return None
    s = str(v).strip()
    if not s:
        return None
    if "T" in s:
        return s
    return s.replace(" ", "T") + "Z" if len(s) == 19 else s


def chunked(rows: list[tuple], size: int) -> Iterable[list[tuple]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def pg_json(v: Any) -> Any:
    if v is None:
        return None
    from psycopg2.extras import Json

    parsed = as_json(v) if isinstance(v, str) else v
    return Json(parsed) if parsed is not None else None


def insert_batch(cur, table: str, columns: list[str], rows: list[tuple], conflict: str | None = None) -> int:
    if not rows:
        return 0
    cols = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {SCHEMA}.{table} ({cols}) VALUES ({placeholders})"
    if conflict:
        sql += f" ON CONFLICT {conflict}"
    from psycopg2.extras import execute_batch

    for batch in chunked(rows, BATCH):
        execute_batch(cur, sql, batch, page_size=len(batch))
    return len(rows)


def truncate_all(cur) -> None:
    tables = [
        "link_licencia_sigma",
        "actuacion_edificacion",
        "inmueble",
        "sigma_pdf_metric",
        "sigma_expediente_metric",
        "sigma_visor_expediente",
        "sigma_ambito_geom",
        "link_project_sigma",
        "sigma_catalog_expediente",
        "project_boletin",
        "source",
    ]
    for t in tables:
        cur.execute(f"TRUNCATE TABLE {SCHEMA}.{t} CASCADE")


def sync_source(sqlite: sqlite3.Connection, cur) -> int:
    rows = [
        (r["id"], r["territorio_id"], r["territorio_label"])
        for r in sqlite.execute("SELECT id, territorio_id, territorio_label FROM source")
    ]
    return insert_batch(
        cur,
        "source",
        ["id", "territorio_id", "territorio_label"],
        rows,
        conflict="(id) DO NOTHING",
    )


def sync_sigma_catalog(sqlite: sqlite3.Connection, cur) -> int:
    rows = []
    for r in sqlite.execute("SELECT * FROM sigma_catalog_expediente"):
        rows.append(
            (
                r["expediente_grupo"],
                r["exp_numero_original"],
                r["sigma_layer_kind"],
                r["denominacion"],
                r["fase"],
                r["fecha_aprob"],
                r["infopublica_inicio"],
                r["infopublica_fin"],
                r["figura_codigo"],
                r["tipo_figura"],
                r["organo_tramitador"],
                r["enlace"],
                r["catalog_source"],
                r["object_id"],
                as_bool(r["has_geometry"]),
                as_ts(r["synced_at"]),
                pg_json(r["raw_features_json"]),
            )
        )
    return insert_batch(
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
        conflict="(expediente_grupo) DO NOTHING",
    )


def _json_array(value: Any, limit: int | None = None) -> Any:
    rows = value if isinstance(value, list) else []
    return rows[:limit] if limit is not None else rows


def _json_object(value: Any) -> Any | None:
    return value if isinstance(value, dict) else None


def _nti_docs(rec: dict[str, Any]) -> list[dict[str, Any]]:
    nti = rec.get("ntiArbol") if isinstance(rec.get("ntiArbol"), dict) else None
    if not nti:
        return []
    docs = nti.get("documentos")
    if isinstance(docs, list) and docs:
        return [d for d in docs if isinstance(d, dict)]
    sample = nti.get("documentosMuestra")
    if isinstance(sample, list):
        return [d for d in sample if isinstance(d, dict)]
    return []


def _sqlite_catalog_context(sqlite: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in sqlite.execute("SELECT * FROM sigma_catalog_expediente"):
        out[r["expediente_grupo"]] = {
            "sigma_layer_kind": r["sigma_layer_kind"],
            "source": r["catalog_source"],
            "tipo_figura": r["tipo_figura"],
            "figura_codigo": r["figura_codigo"],
            "fase": r["fase"],
            "FAS_TX_DENOM": r["fase"],
            "TFIG_TX_ABREV": r["tipo_figura"],
            "FIG_TX_ETIQ": r["figura_codigo"],
        }
    return out


def _sqlite_area_context(sqlite: sqlite3.Connection) -> dict[str, float]:
    out: dict[str, float] = {}
    try:
        rows = sqlite.execute("SELECT expediente_grupo, area_approx_m2 FROM sigma_ambito_geom")
    except sqlite3.OperationalError:
        return out
    for r in rows:
        if r["area_approx_m2"] is not None:
            out[r["expediente_grupo"]] = float(r["area_approx_m2"])
    return out


def _sqlite_viviendas_context(sqlite: sqlite3.Connection) -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        rows = sqlite.execute(
            "SELECT expediente_grupo, num_viviendas_max FROM sigma_expediente_metric"
        )
    except sqlite3.OperationalError:
        return out
    for r in rows:
        if r["num_viviendas_max"] is not None and int(r["num_viviendas_max"]) > 0:
            out[r["expediente_grupo"]] = int(r["num_viviendas_max"])
    return out


def sync_sigma_visor(sqlite: sqlite3.Connection, cur) -> int:
    if not VISOR_JSON.is_file():
        return 0
    raw = json.loads(VISOR_JSON.read_text(encoding="utf-8"))
    generated_at = raw.get("generatedAt") or datetime.now(UTC).isoformat()
    catalog_by_grupo = _sqlite_catalog_context(sqlite)
    area_by_grupo = _sqlite_area_context(sqlite)
    viviendas_by_grupo = _sqlite_viviendas_context(sqlite)
    rows = []
    stubs = []
    for grupo, rec_raw in (raw.get("byGrupoExpediente") or {}).items():
        if not grupo or not isinstance(rec_raw, dict):
            continue
        rec = dict(rec_raw)
        visor_ficha = rec.get("visorFicha") if isinstance(rec.get("visorFicha"), dict) else None
        visor_url = str(rec.get("visorUrlUsada") or "").strip() or None
        layer_kind = str(rec.get("sigmaLayerKind") or "").strip() or None
        resumen_contenido = resumen_contenido_from_visor_ficha(visor_ficha)
        catalog = catalog_by_grupo.get(grupo) or {}
        classification = classify_sigma_project(
            visor_ficha=visor_ficha,
            resumen_contenido=resumen_contenido,
            sigma_layer_kind=layer_kind or catalog.get("sigma_layer_kind") or catalog.get("source"),
            catalog=catalog,
            area_approx_m2=area_by_grupo.get(grupo),
            num_viviendas_max=viviendas_by_grupo.get(grupo),
        )
        nti = rec.get("ntiArbol") if isinstance(rec.get("ntiArbol"), dict) else None
        nti_total = (
            rec.get("ntiDocumentosTotal")
            if isinstance(rec.get("ntiDocumentosTotal"), int)
            else nti.get("documentosTotal")
            if nti and isinstance(nti.get("documentosTotal"), int)
            else None
        )
        stubs.append((grupo, grupo, layer_kind, visor_url, generated_at))
        rows.append(
            (
                grupo,
                bool(rec.get("sinDatosVisor")),
                visor_url,
                pg_json(_json_object(rec.get("visorCabecera"))),
                pg_json(_json_object(visor_ficha)),
                resumen_contenido,
                classification["tipo_legal"],
                classification["escala"],
                classification["contenido_principal"],
                classification["fase_normalizada"],
                classification["categoria_proyecto"],
                classification["clasificacion_confianza"],
                pg_json(classification["clasificacion_fuentes"]),
                pg_json(_json_array(rec.get("tramitacion"))),
                pg_json(_json_array(rec.get("documentacionUrls"))),
                str(rec.get("ntiListadoUrl") or "").strip() or None,
                nti_total,
                pg_json(_nti_docs(rec)[:80]),
                as_ts(generated_at),
                pg_json(rec),
                datetime.now(UTC).isoformat(),
            )
        )

    insert_batch(
        cur,
        "sigma_catalog_expediente",
        ["expediente_grupo", "exp_numero_original", "sigma_layer_kind", "enlace", "synced_at"],
        stubs,
        conflict="""(expediente_grupo) DO UPDATE SET
          sigma_layer_kind = COALESCE(homes.sigma_catalog_expediente.sigma_layer_kind, EXCLUDED.sigma_layer_kind),
          enlace = COALESCE(homes.sigma_catalog_expediente.enlace, EXCLUDED.enlace),
          synced_at = COALESCE(homes.sigma_catalog_expediente.synced_at, EXCLUDED.synced_at)""",
    )
    return insert_batch(
        cur,
        "sigma_visor_expediente",
        [
            "expediente_grupo",
            "sin_datos_visor",
            "visor_url",
            "visor_cabecera",
            "visor_ficha",
            "resumen_contenido",
            "tipo_legal",
            "escala",
            "contenido_principal",
            "fase_normalizada",
            "categoria_proyecto",
            "clasificacion_confianza",
            "clasificacion_fuentes",
            "tramitacion",
            "documentacion_urls",
            "nti_listado_url",
            "nti_documentos_total",
            "nti_documentos_muestra",
            "fetched_at",
            "raw_json",
            "updated_at",
        ],
        rows,
        conflict="""(expediente_grupo) DO UPDATE SET
          sin_datos_visor = EXCLUDED.sin_datos_visor,
          visor_url = EXCLUDED.visor_url,
          visor_cabecera = EXCLUDED.visor_cabecera,
          visor_ficha = EXCLUDED.visor_ficha,
          resumen_contenido = EXCLUDED.resumen_contenido,
          tipo_legal = EXCLUDED.tipo_legal,
          escala = EXCLUDED.escala,
          contenido_principal = EXCLUDED.contenido_principal,
          fase_normalizada = EXCLUDED.fase_normalizada,
          categoria_proyecto = EXCLUDED.categoria_proyecto,
          clasificacion_confianza = EXCLUDED.clasificacion_confianza,
          clasificacion_fuentes = EXCLUDED.clasificacion_fuentes,
          tramitacion = EXCLUDED.tramitacion,
          documentacion_urls = EXCLUDED.documentacion_urls,
          nti_listado_url = EXCLUDED.nti_listado_url,
          nti_documentos_total = EXCLUDED.nti_documentos_total,
          nti_documentos_muestra = EXCLUDED.nti_documentos_muestra,
          fetched_at = EXCLUDED.fetched_at,
          raw_json = EXCLUDED.raw_json,
          updated_at = EXCLUDED.updated_at""",
    )


def sync_sigma_ambito(sqlite: sqlite3.Connection, cur) -> int:
    rows = []
    for r in sqlite.execute("SELECT * FROM sigma_ambito_geom"):
        rows.append(
            (
                r["expediente_grupo"],
                pg_json(json.loads(r["geom_geojson"])),
                r["bbox_min_lng"],
                r["bbox_min_lat"],
                r["bbox_max_lng"],
                r["bbox_max_lat"],
                r["centroid_lng"],
                r["centroid_lat"],
                r["area_approx_m2"],
                as_ts(r["synced_at"]),
            )
        )
    return insert_batch(
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
        conflict="(expediente_grupo) DO NOTHING",
    )


def sync_project_boletin(sqlite: sqlite3.Connection, cur) -> int:
    rows = []
    for r in sqlite.execute("SELECT * FROM project_boletin"):
        rows.append(
            (
                r["id"],
                r["source_id"],
                r["pub_date"],
                r["art_num"],
                r["title"] or "",
                r["pdf_path"],
                r["pdf_url"],
                r["txt_chars"],
                r["latency_s"],
                r["parse_error"],
                as_bool(r["es_relevante"]),
                r["municipio"],
                r["tipo_instrumento"],
                r["nombre_sector"],
                r["estado_tramitacion"],
                r["fecha_acuerdo"],
                r["organo"],
                r["num_viviendas_max"],
                r["fecha_fin_estimada"],
                r["sup_total_m2"],
                r["sup_edificable_m2"],
                r["tipo_vivienda"],
                r["promotor"],
                r["municipio_provincia"],
                r["resumen"],
                r["categorias_tematicas"],
                r["economico_resumen"],
                r["procedimiento_expediente"],
                r["procedimiento_tipo"],
                r["importe_total_eur"],
                r["chars_texto_total"],
                r["llm_max_context_chars"],
                as_bool(r["texto_truncado_llm"]),
                as_bool(r["requiere_segunda_pasada"]),
                r["proyecto_fingerprint"],
                r["sector_key"],
                r["sector_geo_key"],
                r["lat"],
                r["lng"],
                r["coord_source"],
                as_ts(r["inserted_at"]),
                as_ts(r["updated_at"]),
            )
        )
    return insert_batch(
        cur,
        "project_boletin",
        [
            "id",
            "source_id",
            "pub_date",
            "art_num",
            "title",
            "pdf_path",
            "pdf_url",
            "txt_chars",
            "latency_s",
            "parse_error",
            "es_relevante",
            "municipio",
            "tipo_instrumento",
            "nombre_sector",
            "estado_tramitacion",
            "fecha_acuerdo",
            "organo",
            "num_viviendas_max",
            "fecha_fin_estimada",
            "sup_total_m2",
            "sup_edificable_m2",
            "tipo_vivienda",
            "promotor",
            "municipio_provincia",
            "resumen",
            "categorias_tematicas",
            "economico_resumen",
            "procedimiento_expediente",
            "procedimiento_tipo",
            "importe_total_eur",
            "chars_texto_total",
            "llm_max_context_chars",
            "texto_truncado_llm",
            "requiere_segunda_pasada",
            "proyecto_fingerprint",
            "sector_key",
            "sector_geo_key",
            "lat",
            "lng",
            "coord_source",
            "inserted_at",
            "updated_at",
        ],
        rows,
        conflict="(id) DO NOTHING",
    )


def sync_link_project_sigma(sqlite: sqlite3.Connection, cur) -> int:
    rows = [
        (
            r["project_id"],
            r["expediente_grupo"],
            r["match_type"],
            r["match_score"],
            r["sigma_enlace_snapshot"],
        )
        for r in sqlite.execute("SELECT * FROM link_project_sigma")
    ]
    return insert_batch(
        cur,
        "link_project_sigma",
        ["project_id", "expediente_grupo", "match_type", "match_score", "sigma_enlace_snapshot"],
        rows,
        conflict="(project_id) DO NOTHING",
    )


def sync_inmueble(sqlite: sqlite3.Connection, cur) -> int:
    rows = [
        (
            r["id"],
            r["ndp_edificio"],
            r["direccion"],
            r["distrito"],
            r["barrio"],
            r["lat"],
            r["lng"],
            r["coord_source"],
            as_ts(r["inserted_at"]),
            as_ts(r["updated_at"]),
        )
        for r in sqlite.execute("SELECT * FROM inmueble ORDER BY id")
    ]
    n = insert_batch(
        cur,
        "inmueble",
        [
            "id",
            "ndp_edificio",
            "direccion",
            "distrito",
            "barrio",
            "lat",
            "lng",
            "coord_source",
            "inserted_at",
            "updated_at",
        ],
        rows,
        conflict="(id) DO UPDATE SET ndp_edificio = EXCLUDED.ndp_edificio",
    )
    cur.execute(
        f"SELECT setval(pg_get_serial_sequence('{SCHEMA}.inmueble', 'id'), "
        f"COALESCE((SELECT MAX(id) FROM {SCHEMA}.inmueble), 1))"
    )
    return n


def sync_actuacion(sqlite: sqlite3.Connection, cur) -> int:
    rows = []
    for r in sqlite.execute("SELECT * FROM actuacion_edificacion ORDER BY id"):
        raw = r["raw_json"]
        rows.append(
            (
                r["id"],
                r["licencia_key"],
                r["inmueble_id"],
                r["anio_dataset"],
                r["fecha_alta"],
                r["fecha_concesion"],
                r["procedimiento"],
                r["tipo_expediente"],
                r["uso"],
                r["interesado"],
                r["objeto"],
                r["unidad"],
                r["lat"],
                r["lng"],
                pg_json(raw),
                as_ts(r["inserted_at"]),
            )
        )
    return insert_batch(
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
        rows,
        conflict="(id) DO NOTHING",
    )


def sync_link_licencia_sigma(sqlite: sqlite3.Connection, cur) -> int:
    rows = [
        (
            r["licencia_id"],
            r["expediente_grupo"],
            r["match_method"],
            r["match_score"],
            r["sigma_layer_kind"],
            as_ts(r["linked_at"]),
        )
        for r in sqlite.execute("SELECT * FROM link_licencia_sigma")
    ]
    return insert_batch(
        cur,
        "link_licencia_sigma",
        [
            "licencia_id",
            "expediente_grupo",
            "match_method",
            "match_score",
            "sigma_layer_kind",
            "linked_at",
        ],
        rows,
        conflict="(licencia_id, expediente_grupo) DO NOTHING",
    )


def sync_sigma_expediente_metric(sqlite: sqlite3.Connection, cur) -> int:
    rows = []
    for r in sqlite.execute("SELECT * FROM sigma_expediente_metric"):
        rows.append(
            (
                r["expediente_grupo"],
                r["denominacion"],
                r["fase_sigma"],
                r["familia_expediente"],
                r["genera_vivienda_nueva"],
                r["num_viviendas_max"],
                r["sup_total_m2"],
                r["sup_edificable_m2"],
                pg_json(r["metrics_json"]),
                pg_json(r["hechos_json"]),
                pg_json(r["fuentes_pdf_json"]),
                r["doc_role_principal"],
                r["pdfs_procesados"] or 0,
                as_ts(r["updated_at"]),
            )
        )
    return insert_batch(
        cur,
        "sigma_expediente_metric",
        [
            "expediente_grupo",
            "denominacion",
            "fase_sigma",
            "familia_expediente",
            "genera_vivienda_nueva",
            "num_viviendas_max",
            "sup_total_m2",
            "sup_edificable_m2",
            "metrics_json",
            "hechos_json",
            "fuentes_pdf_json",
            "doc_role_principal",
            "pdfs_procesados",
            "updated_at",
        ],
        rows,
        conflict="(expediente_grupo) DO NOTHING",
    )


def sync_sigma_pdf_metric(sqlite: sqlite3.Connection, cur) -> int:
    rows = []
    for r in sqlite.execute("SELECT * FROM sigma_pdf_metric"):
        rows.append(
            (
                r["expediente_grupo"],
                r["pdf_path"],
                r["pdf_name"],
                r["doc_type"],
                r["doc_role"],
                r["method"],
                r["llm_model"],
                as_ts(r["processed_at"]),
                r["num_viviendas_max"],
                r["sup_total_m2"],
                r["sup_edificable_m2"],
                r["tipo_vivienda"],
                r["uso_principal"],
                r["texto_util"],
                pg_json(r["row_json"]),
                r["llm_error"],
                as_ts(r["created_at"]),
                as_ts(r["updated_at"]),
            )
        )
    return insert_batch(
        cur,
        "sigma_pdf_metric",
        [
            "expediente_grupo",
            "pdf_path",
            "pdf_name",
            "doc_type",
            "doc_role",
            "method",
            "llm_model",
            "processed_at",
            "num_viviendas_max",
            "sup_total_m2",
            "sup_edificable_m2",
            "tipo_vivienda",
            "uso_principal",
            "texto_util",
            "row_json",
            "llm_error",
            "created_at",
            "updated_at",
        ],
        rows,
        conflict="(pdf_path) DO NOTHING",
    )


SYNC_STEPS: dict[str, Any] = {
    "source": sync_source,
    "sigma": sync_sigma_catalog,
    "visor": sync_sigma_visor,
    "ambito": sync_sigma_ambito,
    "projects": sync_project_boletin,
    "link_project": sync_link_project_sigma,
    "inmueble": sync_inmueble,
    "licencias": sync_actuacion,
    "links": sync_link_licencia_sigma,
    "metrics": sync_sigma_expediente_metric,
    "pdf_metrics": sync_sigma_pdf_metric,
}

ORDER = [
    "source",
    "sigma",
    "visor",
    "ambito",
    "projects",
    "link_project",
    "inmueble",
    "licencias",
    "links",
    "metrics",
    "pdf_metrics",
]


def main() -> None:
    ap = argparse.ArgumentParser(description="SQLite → Supabase (schema homes)")
    ap.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE)
    ap.add_argument("--truncate", action="store_true", help="Vacía tablas homes antes de insertar")
    ap.add_argument(
        "--only",
        type=str,
        default="",
        help="Subset comma-separated: source,sigma,visor,ambito,projects,link_project,inmueble,licencias,links,metrics,pdf_metrics",
    )
    args = ap.parse_args()

    if not args.sqlite.is_file():
        print(f"No existe SQLite: {args.sqlite}", file=sys.stderr)
        sys.exit(1)

    try:
        import psycopg2
    except ImportError:
        print("pip install -r db/requirements-supabase.txt", file=sys.stderr)
        sys.exit(1)

    only = [x.strip() for x in args.only.split(",") if x.strip()] if args.only else ORDER
    for key in only:
        if key not in SYNC_STEPS:
            print(f"Tabla desconocida: {key}", file=sys.stderr)
            sys.exit(1)

    sqlite = sqlite3.connect(args.sqlite)
    sqlite.row_factory = sqlite3.Row

    conn = psycopg2.connect(pg_url())
    conn.autocommit = False
    t0 = datetime.now(UTC)
    print(f"Sync → {SCHEMA} @ {t0.isoformat()}")

    try:
        with conn.cursor() as cur:
            if args.truncate:
                print("TRUNCATE homes.* …")
                truncate_all(cur)
            for key in only:
                if key not in ORDER:
                    continue
                step_t0 = datetime.now(UTC)
                n = SYNC_STEPS[key](sqlite, cur)
                conn.commit()
                print(f"  {key}: {n:,} filas ({(datetime.now(UTC) - step_t0).total_seconds():.1f}s)")
        print(f"OK en {(datetime.now(UTC) - t0).total_seconds():.1f}s")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        sqlite.close()


if __name__ == "__main__":
    main()
