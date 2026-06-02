#!/usr/bin/env python3
"""
Sync Madrid → tablas de dominio (homes.proyecto, hijas, licencia, inmueble).

Fuentes: output/ tras madrid_ayto_sync, viso, licencias JSONL, BOCM CSV + links.
No escribe tablas legacy ni link_licencia_sigma.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json, execute_values

# Filas anchas (geom + visor JSON): lotes pequeños vía pooler remoto.
BATCH_PROYECTO = 80
BATCH_CHILD = 2500
MAX_DOCS_PER_PROYECTO = 40

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DB_DIR))

from migrate_sqlite import (  # noqa: E402
    csv_bool_int,
    expediente_grupo_from_num,
    float_or_none,
    int_or_none,
    null_if_empty,
    parse_relevante,
    row_to_stub,
)
from sync_madrid_public_to_supabase import (  # noqa: E402
    SCHEMA,
    SIGMA_METRICS,
    VISOR_JSON,
    collect_licencias,
    load_sigma_ambitos,
    load_sigma_catalog,
    load_sigma_visor,
    pg_url,
)

BOCM_CSV = POC_ROOT / "output/history_parsed_incremental.csv"
LINKS_JSONL = POC_ROOT / "output/madrid_ayto_bocm_links.jsonl"


def log(msg: str) -> None:
    print(msg, flush=True)


def insert_batch(
    cur,
    table: str,
    columns: list[str],
    rows: list[tuple],
    *,
    page_size: int = BATCH_CHILD,
    conflict: str = "",
) -> int:
    if not rows:
        return 0
    cols = ", ".join(columns)
    sql = f"INSERT INTO {SCHEMA}.{table} ({cols}) VALUES %s"
    if conflict:
        sql += f" ON CONFLICT {conflict}"
    step = max(1, min(page_size, 5000))
    for i in range(0, len(rows), step):
        batch = rows[i : i + step]
        execute_values(cur, sql, batch, page_size=len(batch))
    return len(rows)


GEOJSON_SOURCES = (
    POC_ROOT / "output/madrid_ayto_expedientes_ad.geojson",
    POC_ROOT / "output/madrid_ayto_expedientes_gestion.geojson",
    POC_ROOT / "output/madrid_ayto_expedientes_urbanizacion.geojson",
    POC_ROOT / "output/madrid_ayto_expedientes_ip.geojson",
)

PROYECTO_COLS = [
    "id",
    "expediente_grupo",
    "exp_numero_original",
    "bocm_primary_id",
    "bocm_sigma_match_type",
    "bocm_sigma_match_score",
    "sigma_enlace_snapshot",
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
    "sigma_synced_at",
    "raw_features_json",
    "geom_geojson",
    "bbox_min_lng",
    "bbox_min_lat",
    "bbox_max_lng",
    "bbox_max_lat",
    "centroid_lng",
    "centroid_lat",
    "area_approx_m2",
    "geom_synced_at",
    "metric_fase",
    "familia_expediente",
    "genera_vivienda_nueva",
    "metrics_json",
    "hechos_json",
    "fuentes_pdf_json",
    "doc_role_principal",
    "pdfs_procesados",
    "metrics_updated_at",
    "sin_datos_visor",
    "visor_url",
    "visor_cabecera",
    "visor_ficha",
    "resumen_contenido",
    "tramitacion",
    "documentacion_urls",
    "nti_listado_url",
    "nti_documentos_total",
    "nti_documentos_muestra",
    "visor_fetched_at",
    "visor_raw_json",
    "tipo_legal",
    "escala",
    "contenido_principal",
    "fase_normalizada",
    "categoria_proyecto",
    "tipo_obra",
    "clasificacion_confianza",
    "clasificacion_fuentes",
    "bocm_source_id",
    "bocm_pub_date",
    "bocm_art_num",
    "bocm_title",
    "bocm_pdf_path",
    "bocm_pdf_url",
    "bocm_txt_chars",
    "bocm_latency_s",
    "bocm_parse_error",
    "bocm_es_relevante",
    "bocm_municipio",
    "bocm_tipo_instrumento",
    "bocm_nombre_sector",
    "bocm_estado_tramitacion",
    "bocm_fecha_acuerdo",
    "bocm_organo",
    "bocm_promotor",
    "bocm_municipio_provincia",
    "bocm_resumen",
    "bocm_categorias_tematicas",
    "bocm_economico_resumen",
    "bocm_procedimiento_expediente",
    "bocm_procedimiento_tipo",
    "bocm_proyecto_fingerprint",
    "bocm_chars_texto_total",
    "bocm_llm_max_context_chars",
    "bocm_texto_truncado_llm",
    "bocm_requiere_segunda_pasada",
    "bocm_num_viviendas_max",
    "bocm_sup_total_m2",
    "bocm_sup_edificable_m2",
    "bocm_tipo_vivienda",
    "bocm_fecha_fin_estimada",
    "bocm_importe_total_eur",
    "metric_num_viviendas_max",
    "metric_sup_total_m2",
    "metric_sup_edificable_m2",
    "num_viviendas_max",
    "sup_total_m2",
    "sup_edificable_m2",
    "tipo_vivienda",
    "fecha_fin_estimada",
    "importe_total_eur",
    "municipio",
    "lat",
    "lng",
    "coord_source",
    "sector_key",
    "sector_geo_key",
    "inserted_at",
    "updated_at",
]


def _blank_proyecto() -> dict[str, Any]:
    p = {c: None for c in PROYECTO_COLS}
    p["pdfs_procesados"] = 0
    p["sin_datos_visor"] = False
    p["bocm_requiere_segunda_pasada"] = False
    p["has_geometry"] = False
    p["tramitacion"] = Json([])
    p["documentacion_urls"] = Json([])
    p["nti_documentos_muestra"] = Json([])
    p["visor_raw_json"] = Json({})
    p["clasificacion_fuentes"] = Json({})
    return p


def _norm_municipio(s: str | None) -> str:
    return (s or "").strip().lower()


def _is_madrid_capital(municipio: str | None) -> bool:
    return _norm_municipio(municipio) == "madrid"


def _parse_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        dialect = csv.Sniffer().sniff(text[:8192])
    except csv.Error:
        dialect = csv.excel
    return list(csv.DictReader(text.splitlines(), dialect=dialect))


def load_bocm_links() -> tuple[dict[str, tuple[str, dict]], dict[str, list[dict]]]:
    """bocm_id -> (expediente_grupo, link_rec); grupo -> [link_rec, ...]"""
    by_bocm: dict[str, tuple[str, dict]] = {}
    by_grupo: dict[str, list[dict]] = defaultdict(list)
    if not LINKS_JSONL.is_file():
        return by_bocm, by_grupo
    for line in LINKS_JSONL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        bid = rec.get("bocm_id")
        exp = rec.get("sigma_expediente")
        if not bid or not exp:
            continue
        grupo = expediente_grupo_from_num(str(exp))
        if not grupo:
            continue
        by_bocm[str(bid)] = (grupo, rec)
        by_grupo[grupo].append(rec)
    return by_bocm, by_grupo


def _bocm_fields_from_row(stub: dict, row: dict[str, str]) -> dict[str, Any]:
    rr = row
    es_rel = stub.get("es_relevante")
    if es_rel is not None and not isinstance(es_rel, bool):
        es_rel = bool(es_rel) if es_rel in (0, 1) else None
    return {
        "bocm_source_id": stub["source_id"],
        "bocm_pub_date": stub["pub_date"] or None,
        "bocm_art_num": stub["art_num"] or None,
        "bocm_title": (rr.get("title") or "")[:2000] or None,
        "bocm_pdf_path": null_if_empty(rr.get("pdf_path")),
        "bocm_pdf_url": null_if_empty(rr.get("pdf_url")),
        "bocm_txt_chars": int_or_none(rr.get("txt_chars")),
        "bocm_latency_s": float_or_none(rr.get("latency_s")),
        "bocm_parse_error": stub.get("parse_error"),
        "bocm_es_relevante": es_rel,
        "bocm_municipio": null_if_empty(rr.get("municipio")),
        "bocm_tipo_instrumento": null_if_empty(rr.get("tipo_instrumento")),
        "bocm_nombre_sector": null_if_empty(rr.get("nombre_sector")),
        "bocm_estado_tramitacion": null_if_empty(rr.get("estado_tramitacion")),
        "bocm_fecha_acuerdo": null_if_empty(rr.get("fecha_acuerdo")),
        "bocm_organo": null_if_empty(rr.get("organo_aprobador")),
        "bocm_promotor": null_if_empty(rr.get("promotor_o_propietario")),
        "bocm_municipio_provincia": null_if_empty(rr.get("municipio_provincia")),
        "bocm_resumen": null_if_empty(rr.get("resumen")),
        "bocm_categorias_tematicas": null_if_empty(rr.get("categorias_tematicas")),
        "bocm_economico_resumen": null_if_empty(rr.get("economico_resumen")),
        "bocm_procedimiento_expediente": null_if_empty(rr.get("procedimiento_expediente")),
        "bocm_procedimiento_tipo": null_if_empty(rr.get("procedimiento_tipo")),
        "bocm_proyecto_fingerprint": null_if_empty(rr.get("proyecto_fingerprint")),
        "bocm_chars_texto_total": int_or_none(rr.get("chars_texto_total")),
        "bocm_llm_max_context_chars": int_or_none(rr.get("llm_max_context_chars")),
        "bocm_texto_truncado_llm": bool(csv_bool_int(rr.get("texto_truncado_llm")))
        if csv_bool_int(rr.get("texto_truncado_llm")) is not None
        else None,
        "bocm_requiere_segunda_pasada": str(rr.get("requiere_segunda_pasada") or "").strip().lower()
        in ("true", "1"),
        "bocm_num_viviendas_max": int_or_none(rr.get("num_viviendas_max")),
        "bocm_sup_total_m2": float_or_none(rr.get("sup_total_m2")),
        "bocm_sup_edificable_m2": float_or_none(rr.get("sup_edificable_m2")),
        "bocm_tipo_vivienda": null_if_empty(rr.get("tipo_vivienda")),
        "bocm_fecha_fin_estimada": null_if_empty(rr.get("fecha_fin_estimada")),
        "bocm_importe_total_eur": float_or_none(rr.get("importe_total_eur_estimado")),
        "sector_key": stub.get("sector_key"),
        "sector_geo_key": stub.get("sector_geo_key"),
        "municipio": null_if_empty(rr.get("municipio")),
    }


def load_sigma_metrics_by_grupo() -> dict[str, dict]:
    if not SIGMA_METRICS.is_file():
        return {}
    raw = json.loads(SIGMA_METRICS.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for grupo, row in (raw.get("expedientes") or {}).items():
        if isinstance(row, dict):
            out[str(grupo)] = row
    return out


def build_proyectos() -> tuple[dict[str, dict], list, list, list, list]:
    """Retorna proyectos dict + filas hijas (bocm_pub, tramite, doc, pdf)."""
    now = datetime.now(UTC).isoformat()
    proyectos: dict[str, dict[str, Any]] = {}
    bocm_pub_rows: list[tuple] = []
    tramite_rows: list[tuple] = []
    doc_rows: list[tuple] = []
    pdf_rows: list[tuple] = []

    catalog_rows, _ = load_sigma_catalog()
    metrics_by_grupo = load_sigma_metrics_by_grupo()
    ambito_by_grupo = {r[0]: r for r in load_sigma_ambitos()}

    for row in catalog_rows:
        grupo = row[0]
        p = _blank_proyecto()
        p.update(
            {
                "id": grupo,
                "expediente_grupo": grupo,
                "exp_numero_original": row[1],
                "sigma_layer_kind": row[2],
                "denominacion": row[3],
                "fase": row[4],
                "fecha_aprob": row[5],
                "infopublica_inicio": row[6],
                "infopublica_fin": row[7],
                "figura_codigo": row[8],
                "tipo_figura": row[9],
                "organo_tramitador": row[10],
                "enlace": row[11],
                "catalog_source": row[12],
                "object_id": row[13],
                "has_geometry": row[14],
                "sigma_synced_at": row[15],
                "raw_features_json": row[16],
                "inserted_at": now,
                "updated_at": now,
            }
        )
        if grupo in ambito_by_grupo:
            g = ambito_by_grupo[grupo]
            p.update(
                {
                    "geom_geojson": g[1],
                    "bbox_min_lng": g[2],
                    "bbox_min_lat": g[3],
                    "bbox_max_lng": g[4],
                    "bbox_max_lat": g[5],
                    "centroid_lng": g[6],
                    "centroid_lat": g[7],
                    "area_approx_m2": g[8],
                    "geom_synced_at": g[9],
                    "has_geometry": True,
                    "lat": g[7],
                    "lng": g[6],
                    "coord_source": "sigma_ambito",
                }
            )
        mrow = metrics_by_grupo.get(grupo)
        if mrow:
            metrics = mrow.get("metrics") if isinstance(mrow.get("metrics"), dict) else mrow
            p.update(
                {
                    "metric_fase": null_if_empty(str(mrow.get("fase_sigma") or metrics.get("fase") or "")),
                    "familia_expediente": null_if_empty(str(mrow.get("familia_expediente") or "")),
                    "genera_vivienda_nueva": null_if_empty(str(mrow.get("genera_vivienda_nueva") or "")),
                    "metrics_json": Json(mrow.get("metrics") or metrics),
                    "hechos_json": Json(mrow.get("hechos")) if mrow.get("hechos") else None,
                    "fuentes_pdf_json": Json(mrow.get("fuentes_pdf")) if mrow.get("fuentes_pdf") else None,
                    "doc_role_principal": null_if_empty(str(mrow.get("doc_role_principal") or "")),
                    "pdfs_procesados": int(mrow.get("pdfs_procesados") or 0),
                    "metrics_updated_at": mrow.get("updated_at") or now,
                    "metric_num_viviendas_max": int_or_none(metrics.get("num_viviendas_max")),
                    "metric_sup_total_m2": float_or_none(metrics.get("sup_total_m2")),
                    "metric_sup_edificable_m2": float_or_none(metrics.get("sup_edificable_m2")),
                }
            )
            for pdf in mrow.get("pdfs") or []:
                if not isinstance(pdf, dict) or not pdf.get("pdf_path"):
                    continue
                pdf_rows.append(
                    (
                        grupo,
                        pdf.get("pdf_path"),
                        pdf.get("pdf_name"),
                        pdf.get("doc_type"),
                        pdf.get("doc_role"),
                        pdf.get("method"),
                        pdf.get("llm_model"),
                        pdf.get("processed_at") or now,
                        int_or_none(pdf.get("num_viviendas_max")),
                        float_or_none(pdf.get("sup_total_m2")),
                        float_or_none(pdf.get("sup_edificable_m2")),
                        null_if_empty(str(pdf.get("tipo_vivienda") or "")),
                        null_if_empty(str(pdf.get("uso_principal") or "")),
                        Json(pdf) if pdf else None,
                        null_if_empty(str(pdf.get("llm_error") or "")),
                        now,
                    )
                )
        proyectos[grupo] = p

    visor_rows, _ = load_sigma_visor()
    visor_raw = {}
    if VISOR_JSON.is_file():
        visor_raw = json.loads(VISOR_JSON.read_text(encoding="utf-8")).get("byGrupoExpediente") or {}

    for vrow in visor_rows:
        grupo = vrow[0]
        if grupo not in proyectos:
            p = _blank_proyecto()
            p.update({"id": grupo, "expediente_grupo": grupo, "inserted_at": now, "updated_at": now})
            proyectos[grupo] = p
        p = proyectos[grupo]
        p.update(
            {
                "sin_datos_visor": vrow[1],
                "visor_url": vrow[2],
                "visor_cabecera": vrow[3],
                "visor_ficha": vrow[4],
                "resumen_contenido": vrow[5],
                "tipo_legal": vrow[6],
                "escala": vrow[7],
                "contenido_principal": vrow[8],
                "fase_normalizada": vrow[9],
                "categoria_proyecto": vrow[10],
                "tipo_obra": vrow[11],
                "clasificacion_confianza": vrow[12],
                "clasificacion_fuentes": vrow[13],
                "tramitacion": vrow[14],
                "documentacion_urls": vrow[15],
                "nti_listado_url": vrow[16],
                "nti_documentos_total": vrow[17],
                "nti_documentos_muestra": vrow[18],
                "visor_fetched_at": vrow[19],
                "visor_raw_json": Json({}),
                "updated_at": now,
            }
        )
        tram_list = vrow[14]
        if isinstance(tram_list, Json):
            tram_list = tram_list.adapted
        if isinstance(tram_list, list):
            for i, t in enumerate(tram_list):
                if not isinstance(t, dict):
                    continue
                tramite_rows.append(
                    (
                        grupo,
                        i,
                        null_if_empty(str(t.get("fecha") or "")),
                        null_if_empty(str(t.get("tramite") or t.get("texto") or "")),
                        null_if_empty(str(t.get("organo") or "")),
                        null_if_empty(str(t.get("visorUrl") or t.get("visor_url") or "")),
                        vrow[19],
                    )
                )
        rec = visor_raw.get(grupo) if isinstance(visor_raw, dict) else None
        if isinstance(rec, dict):
            nti = rec.get("ntiArbol") if isinstance(rec.get("ntiArbol"), dict) else None
            docs: list[dict] = []
            if nti and isinstance(nti.get("documentos"), list):
                docs = [d for d in nti["documentos"] if isinstance(d, dict)]
            elif isinstance(rec.get("ntiDocumentosMuestra"), list):
                docs = [d for d in rec["ntiDocumentosMuestra"] if isinstance(d, dict)]
            for i, d in enumerate(docs[:MAX_DOCS_PER_PROYECTO]):
                url = null_if_empty(str(d.get("url") or ""))
                if not url:
                    continue
                doc_rows.append(
                    (
                        grupo,
                        i,
                        url,
                        null_if_empty(str(d.get("titulo") or "")),
                        null_if_empty(str(d.get("tooltip") or "")),
                        null_if_empty(str(d.get("rutaCarpetas") or "")),
                        null_if_empty(str(d.get("tipodocNti") or d.get("tipodoc_nti") or "")),
                        null_if_empty(str(d.get("fechaDocumento") or d.get("fecha_documento") or "")),
                        "nti",
                    )
                )
            for i, url in enumerate(rec.get("documentacionUrls") or []):
                if not url:
                    continue
                doc_rows.append((grupo, 10000 + i, str(url), None, None, None, None, None, "visor"))

    by_bocm, by_grupo = load_bocm_links()
    linked_bocm_ids = set(by_bocm.keys())
    primary_bocm: dict[str, str] = {}

    for grupo, links in by_grupo.items():
        if not links:
            continue
        links_sorted = sorted(links, key=lambda r: str(r.get("bocm_date") or ""), reverse=True)
        primary_bocm[grupo] = str(links_sorted[0].get("bocm_id") or "")

    for row in _parse_csv(BOCM_CSV):
        stub = row_to_stub(row, default_source="bocm")
        if not stub["pub_date"] or not stub["art_num"]:
            continue
        bid = str(stub["id"])
        municipio = (row.get("municipio") or "").strip()
        if bid not in linked_bocm_ids and not _is_madrid_capital(municipio):
            continue
        bfields = _bocm_fields_from_row(stub, row)
        link = by_bocm.get(bid)

        if link:
            grupo, lrec = link
            if grupo not in proyectos:
                p = _blank_proyecto()
                p.update({"id": grupo, "expediente_grupo": grupo, "inserted_at": now, "updated_at": now})
                proyectos[grupo] = p
            is_primary = primary_bocm.get(grupo) == bid
            bocm_pub_rows.append(
                (
                    grupo,
                    bid,
                    is_primary,
                    bfields["bocm_source_id"],
                    bfields["bocm_pub_date"],
                    bfields["bocm_art_num"],
                    bfields["bocm_title"],
                    bfields["bocm_es_relevante"],
                    bfields["bocm_tipo_instrumento"],
                    bfields["bocm_nombre_sector"],
                    bfields["bocm_procedimiento_expediente"],
                    (bfields["bocm_resumen"] or "")[:500] if bfields["bocm_resumen"] else None,
                    lrec.get("match_type"),
                    float(lrec["match_score"]) if lrec.get("match_score") is not None else None,
                    now,
                )
            )
            if is_primary:
                p = proyectos[grupo]
                p.update(bfields)
                p.update(
                    {
                        "bocm_primary_id": bid,
                        "bocm_sigma_match_type": lrec.get("match_type"),
                        "bocm_sigma_match_score": float(lrec["match_score"])
                        if lrec.get("match_score") is not None
                        else None,
                        "sigma_enlace_snapshot": null_if_empty(str(lrec.get("sigma_enlace") or "")),
                        "updated_at": now,
                    }
                )
        elif _is_madrid_capital(bfields.get("municipio")):
            oid = f"bocm:{bid}"
            p = _blank_proyecto()
            p.update(bfields)
            p.update(
                {
                    "id": oid,
                    "bocm_primary_id": bid,
                    "inserted_at": now,
                    "updated_at": now,
                }
            )
            proyectos[oid] = p
            bocm_pub_rows.append(
                (
                    oid,
                    bid,
                    True,
                    bfields["bocm_source_id"],
                    bfields["bocm_pub_date"],
                    bfields["bocm_art_num"],
                    bfields["bocm_title"],
                    bfields["bocm_es_relevante"],
                    bfields["bocm_tipo_instrumento"],
                    bfields["bocm_nombre_sector"],
                    bfields["bocm_procedimiento_expediente"],
                    (bfields["bocm_resumen"] or "")[:500] if bfields["bocm_resumen"] else None,
                    None,
                    None,
                    now,
                )
            )

    for p in proyectos.values():
        nv = p.get("metric_num_viviendas_max") or p.get("bocm_num_viviendas_max")
        st = p.get("metric_sup_total_m2") or p.get("bocm_sup_total_m2")
        se = p.get("metric_sup_edificable_m2") or p.get("bocm_sup_edificable_m2")
        p["num_viviendas_max"] = nv
        p["sup_total_m2"] = st
        p["sup_edificable_m2"] = se
        p["tipo_vivienda"] = p.get("bocm_tipo_vivienda")
        p["fecha_fin_estimada"] = p.get("bocm_fecha_fin_estimada")
        p["importe_total_eur"] = p.get("bocm_importe_total_eur")
        if not p.get("municipio") and p.get("bocm_municipio"):
            p["municipio"] = p["bocm_municipio"]

    return proyectos, bocm_pub_rows, tramite_rows, doc_rows, pdf_rows


def _proyecto_tuple(p: dict[str, Any]) -> tuple:
    return tuple(p.get(c) for c in PROYECTO_COLS)


def sync_proyectos(cur) -> dict[str, int]:
    t0 = time.perf_counter()
    log("Construyendo proyectos en memoria…")
    proyectos, bocm_pub, tramites, docs, pdfs = build_proyectos()
    log(
        f"  {len(proyectos)} proyectos, {len(bocm_pub)} BOCM, "
        f"{len(tramites)} trámites, {len(docs)} docs ({time.perf_counter() - t0:.1f}s)"
    )
    if not proyectos:
        return {"proyecto": 0}

    log("TRUNCATE proyecto + hijas (refresh semanal)…")
    cur.execute(f"TRUNCATE TABLE {SCHEMA}.proyecto CASCADE")

    rows = [_proyecto_tuple(proyectos[i]) for i in proyectos]
    t1 = time.perf_counter()
    log(f"INSERT {len(rows)} filas en proyecto (lotes de {BATCH_PROYECTO})…")
    n = insert_batch(cur, "proyecto", PROYECTO_COLS, rows, page_size=BATCH_PROYECTO)
    log(f"  proyecto OK ({time.perf_counter() - t1:.1f}s)")

    stats: dict[str, int] = {"proyecto": n}

    if bocm_pub:
        t2 = time.perf_counter()
        insert_batch(
            cur,
            "proyecto_bocm_publicacion",
            [
                "proyecto_id",
                "bocm_id",
                "es_principal",
                "bocm_source_id",
                "pub_date",
                "art_num",
                "title",
                "es_relevante",
                "tipo_instrumento",
                "nombre_sector",
                "procedimiento_expediente",
                "resumen",
                "match_type",
                "match_score",
                "inserted_at",
            ],
            bocm_pub,
        )
        stats["proyecto_bocm_publicacion"] = len(bocm_pub)
        log(f"  BOCM publicaciones ({time.perf_counter() - t2:.1f}s)")
    if tramites:
        t2 = time.perf_counter()
        insert_batch(
            cur,
            "proyecto_tramite",
            ["proyecto_id", "orden", "fecha", "tramite", "organo", "visor_url", "fetched_at"],
            tramites,
        )
        stats["proyecto_tramite"] = len(tramites)
        log(f"  trámites ({time.perf_counter() - t2:.1f}s)")
    if docs:
        seen_doc: set[tuple[str, str]] = set()
        docs_dedup: list[tuple] = []
        for row in docs:
            key = (row[0], row[2])
            if key in seen_doc:
                continue
            seen_doc.add(key)
            docs_dedup.append(row)
        t2 = time.perf_counter()
        insert_batch(
            cur,
            "proyecto_documento",
            [
                "proyecto_id",
                "orden",
                "url",
                "titulo",
                "tooltip",
                "ruta_carpetas",
                "tipodoc_nti",
                "fecha_documento",
                "fuente",
            ],
            docs_dedup,
            conflict="(proyecto_id, url) DO NOTHING",
        )
        docs = docs_dedup
        stats["proyecto_documento"] = len(docs)
        log(f"  documentos ({time.perf_counter() - t2:.1f}s)")
    if pdfs:
        t2 = time.perf_counter()
        insert_batch(
            cur,
            "proyecto_pdf_metric",
            [
                "proyecto_id",
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
                "row_json",
                "llm_error",
                "updated_at",
            ],
            pdfs,
        )
        stats["proyecto_pdf_metric"] = len(pdfs)
        log(f"  pdf metrics ({time.perf_counter() - t2:.1f}s)")

    log(f"Sync proyectos total: {time.perf_counter() - t0:.1f}s")
    return stats


INMUEBLE_UPSERT = (
    "(ndp_edificio) DO UPDATE SET "
    "direccion = COALESCE(EXCLUDED.direccion, homes.inmueble.direccion), "
    "distrito = COALESCE(EXCLUDED.distrito, homes.inmueble.distrito), "
    "barrio = COALESCE(EXCLUDED.barrio, homes.inmueble.barrio), "
    "lat = COALESCE(EXCLUDED.lat, homes.inmueble.lat), "
    "lng = COALESCE(EXCLUDED.lng, homes.inmueble.lng), "
    "coord_source = COALESCE(EXCLUDED.coord_source, homes.inmueble.coord_source), "
    "updated_at = EXCLUDED.updated_at"
)

LICENCIA_UPSERT = (
    "(licencia_key) DO UPDATE SET "
    "inmueble_id = EXCLUDED.inmueble_id, "
    "anio_dataset = EXCLUDED.anio_dataset, "
    "fecha_alta = EXCLUDED.fecha_alta, "
    "fecha_concesion = EXCLUDED.fecha_concesion, "
    "procedimiento = EXCLUDED.procedimiento, "
    "tipo_expediente = EXCLUDED.tipo_expediente, "
    "uso = EXCLUDED.uso, "
    "interesado = EXCLUDED.interesado, "
    "objeto = EXCLUDED.objeto, "
    "unidad = EXCLUDED.unidad, "
    "lat = EXCLUDED.lat, "
    "lng = EXCLUDED.lng, "
    "raw_json = EXCLUDED.raw_json, "
    "updated_at = EXCLUDED.updated_at"
)


def _next_licencia_ids(cur, keys: list[str]) -> dict[str, int]:
    if not keys:
        return {}
    cur.execute(f"SELECT licencia_key, id FROM {SCHEMA}.licencia WHERE licencia_key = ANY(%s)", (keys,))
    out = {str(r[0]): int(r[1]) for r in cur.fetchall()}
    cur.execute(f"SELECT COALESCE(MAX(id), 0) FROM {SCHEMA}.licencia")
    nxt = int(cur.fetchone()[0]) + 1
    for k in keys:
        if k not in out:
            out[k] = nxt
            nxt += 1
    return out


def sync_licencias_incremental(cur, years: set[int]) -> dict[str, Any]:
    inmuebles, actuaciones_by_key, stats = collect_licencias(years=years)
    now = datetime.now(UTC).isoformat()

    inmueble_rows = [
        (
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
        for ndp, rec in sorted(inmuebles.items())
    ]
    insert_batch(
        cur,
        "inmueble",
        ["ndp_edificio", "direccion", "distrito", "barrio", "lat", "lng", "coord_source", "inserted_at", "updated_at"],
        inmueble_rows,
        conflict=INMUEBLE_UPSERT,
    )

    ndps = list(inmuebles.keys())
    id_by_ndp: dict[str, int] = {}
    if ndps:
        cur.execute(f"SELECT id, ndp_edificio FROM {SCHEMA}.inmueble WHERE ndp_edificio = ANY(%s)", (ndps,))
        id_by_ndp = {str(row[1]): int(row[0]) for row in cur.fetchall()}

    keys = [k for k, t in actuaciones_by_key.items() if t[1] in id_by_ndp]
    id_by_key = _next_licencia_ids(cur, keys)

    lic_rows = []
    for key, tup in actuaciones_by_key.items():
        (
            _key,
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
        ) = tup
        if ndp not in id_by_ndp:
            continue
        lic_rows.append(
            (
                id_by_key[key],
                key,
                id_by_ndp[ndp],
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
                None,
                None,
                None,
                None,
                None,
                now,
                now,
            )
        )

    insert_batch(
        cur,
        "licencia",
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
            "proyecto_id",
            "proyecto_match_method",
            "proyecto_match_score",
            "proyecto_sigma_layer_kind",
            "proyecto_linked_at",
            "inserted_at",
            "updated_at",
        ],
        lic_rows,
        conflict="(licencia_key) DO UPDATE SET "
        "inmueble_id = EXCLUDED.inmueble_id, "
        "anio_dataset = EXCLUDED.anio_dataset, "
        "fecha_alta = EXCLUDED.fecha_alta, "
        "fecha_concesion = EXCLUDED.fecha_concesion, "
        "procedimiento = EXCLUDED.procedimiento, "
        "tipo_expediente = EXCLUDED.tipo_expediente, "
        "uso = EXCLUDED.uso, "
        "interesado = EXCLUDED.interesado, "
        "objeto = EXCLUDED.objeto, "
        "unidad = EXCLUDED.unidad, "
        "lat = EXCLUDED.lat, "
        "lng = EXCLUDED.lng, "
        "raw_json = EXCLUDED.raw_json, "
        "updated_at = EXCLUDED.updated_at",
    )
    stats["mode"] = "incremental"
    stats["licencias_upserted"] = len(lic_rows)
    return stats


def sync_licencias_full(cur) -> dict[str, Any]:
    inmuebles, actuaciones_by_key, stats = collect_licencias()
    now = datetime.now(UTC).isoformat()

    inmueble_rows: list[tuple] = []
    inmueble_id_by_ndp: dict[str, int] = {}
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

    lic_rows = []
    for i, tup in enumerate(actuaciones_by_key.values(), start=1):
        (
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
        ) = tup
        if ndp not in inmueble_id_by_ndp:
            continue
        lic_rows.append(
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
                None,
                None,
                None,
                None,
                None,
                now,
                now,
            )
        )

    cur.execute(f"TRUNCATE TABLE {SCHEMA}.licencia, {SCHEMA}.inmueble RESTART IDENTITY CASCADE")

    insert_batch(
        cur,
        "inmueble",
        ["id", "ndp_edificio", "direccion", "distrito", "barrio", "lat", "lng", "coord_source", "inserted_at", "updated_at"],
        inmueble_rows,
    )
    insert_batch(
        cur,
        "licencia",
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
            "proyecto_id",
            "proyecto_match_method",
            "proyecto_match_score",
            "proyecto_sigma_layer_kind",
            "proyecto_linked_at",
            "inserted_at",
            "updated_at",
        ],
        lic_rows,
    )
    for table, column in (("inmueble", "id"), ("licencia", "id")):
        cur.execute(
            f"SELECT setval(pg_get_serial_sequence('{SCHEMA}.{table}', '{column}'), "
            f"COALESCE((SELECT MAX({column}) FROM {SCHEMA}.{table}), 1))"
        )
    stats["licencias"] = len(lic_rows)
    stats["mode"] = "full"
    return stats


def summarize(cur) -> dict[str, int]:
    tables = [
        "proyecto",
        "proyecto_bocm_publicacion",
        "proyecto_tramite",
        "proyecto_documento",
        "proyecto_pdf_metric",
        "inmueble",
        "licencia",
    ]
    out: dict[str, int] = {}
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{table}")
        out[table] = int(cur.fetchone()[0])
    return out


def parse_years(raw: str) -> set[int]:
    years: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            years.add(int(part))
    if not years:
        raise SystemExit("--licencias-years requiere al menos un año")
    return years


def main() -> None:
    ap = argparse.ArgumentParser(description="Sync dominio (proyecto, licencia) a Supabase.")
    ap.add_argument("--skip-proyectos", action="store_true")
    ap.add_argument("--skip-licencias", action="store_true")
    ap.add_argument("--licencias-years", type=str, default="")
    ap.add_argument("--licencias-full", action="store_true")
    args = ap.parse_args()

    with psycopg2.connect(pg_url()) as con:
        with con.cursor() as cur:
            out: dict[str, Any] = {}
            if not args.skip_proyectos:
                out["proyectos"] = sync_proyectos(cur)
            if args.licencias_full:
                out["licencias"] = sync_licencias_full(cur)
            elif args.licencias_years.strip():
                out["licencias"] = sync_licencias_incremental(cur, parse_years(args.licencias_years))
            elif not args.skip_licencias:
                out["licencias"] = sync_licencias_full(cur)
            out["counts"] = summarize(cur)
            for t in out["counts"]:
                cur.execute(f"ANALYZE {SCHEMA}.{t}")
        con.commit()
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
