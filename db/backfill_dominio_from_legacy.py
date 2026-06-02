#!/usr/bin/env python3
"""
Backfill homes.proyecto (+ hijas) y homes.licencia desde tablas legacy en el mismo Supabase.

Útil si ya hay datos en sigma_* / actuacion_edificacion y no se dispone de output/ local.
Preferir: python3 db/sync_dominio_to_supabase.py (desde artefactos frescos).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg2

SCHEMA = "homes"


def pg_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Falta SUPABASE_DB_URL")
    return url


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sql_proyecto = f"""
    INSERT INTO {SCHEMA}.proyecto (
      id, expediente_grupo, exp_numero_original,
      sigma_layer_kind, denominacion, fase, fecha_aprob,
      infopublica_inicio, infopublica_fin, figura_codigo, tipo_figura,
      organo_tramitador, enlace, catalog_source, object_id, has_geometry,
      sigma_synced_at, raw_features_json,
      geom_geojson, bbox_min_lng, bbox_min_lat, bbox_max_lng, bbox_max_lat,
      centroid_lng, centroid_lat, area_approx_m2, geom_synced_at,
      metric_fase, familia_expediente, genera_vivienda_nueva,
      metrics_json, hechos_json, fuentes_pdf_json, doc_role_principal,
      pdfs_procesados, metrics_updated_at,
      sin_datos_visor, visor_url, visor_cabecera, visor_ficha, resumen_contenido,
      tramitacion, documentacion_urls, nti_listado_url, nti_documentos_total,
      nti_documentos_muestra, visor_fetched_at, visor_raw_json,
      tipo_legal, escala, contenido_principal, fase_normalizada, categoria_proyecto,
      tipo_obra, clasificacion_confianza, clasificacion_fuentes,
      bocm_primary_id, bocm_sigma_match_type, bocm_sigma_match_score, sigma_enlace_snapshot,
      num_viviendas_max, sup_total_m2, sup_edificable_m2,
      lat, lng, inserted_at, updated_at
    )
    SELECT
      c.expediente_grupo,
      c.expediente_grupo,
      c.exp_numero_original,
      c.sigma_layer_kind, c.denominacion, c.fase, c.fecha_aprob,
      c.infopublica_inicio, c.infopublica_fin, c.figura_codigo, c.tipo_figura,
      c.organo_tramitador, c.enlace, c.catalog_source, c.object_id, c.has_geometry,
      c.synced_at, c.raw_features_json,
      g.geom_geojson, g.bbox_min_lng, g.bbox_min_lat, g.bbox_max_lng, g.bbox_max_lat,
      g.centroid_lng, g.centroid_lat, g.area_approx_m2, g.synced_at,
      m.fase_sigma, m.familia_expediente, m.genera_vivienda_nueva,
      m.metrics_json, m.hechos_json, m.fuentes_pdf_json, m.doc_role_principal,
      m.pdfs_procesados, m.updated_at,
      COALESCE(v.sin_datos_visor, false), v.visor_url, v.visor_cabecera, v.visor_ficha, v.resumen_contenido,
      COALESCE(v.tramitacion, '[]'::jsonb), COALESCE(v.documentacion_urls, '[]'::jsonb),
      v.nti_listado_url, v.nti_documentos_total, COALESCE(v.nti_documentos_muestra, '[]'::jsonb),
      v.fetched_at, COALESCE(v.raw_json, '{{}}'::jsonb),
      v.tipo_legal, v.escala, v.contenido_principal, v.fase_normalizada, v.categoria_proyecto,
      v.tipo_obra, v.clasificacion_confianza, COALESCE(v.clasificacion_fuentes, '{{}}'::jsonb),
      l.project_id, l.match_type, l.match_score, l.sigma_enlace_snapshot,
      COALESCE(m.num_viviendas_max, p.num_viviendas_max),
      COALESCE(m.sup_total_m2, p.sup_total_m2),
      COALESCE(m.sup_edificable_m2, p.sup_edificable_m2),
      COALESCE(g.centroid_lat, p.lat), COALESCE(g.centroid_lng, p.lng),
      now(), now()
    FROM {SCHEMA}.sigma_catalog_expediente c
    LEFT JOIN {SCHEMA}.sigma_ambito_geom g ON g.expediente_grupo = c.expediente_grupo
    LEFT JOIN {SCHEMA}.sigma_visor_expediente v ON v.expediente_grupo = c.expediente_grupo
    LEFT JOIN {SCHEMA}.sigma_expediente_metric m ON m.expediente_grupo = c.expediente_grupo
    LEFT JOIN {SCHEMA}.link_project_sigma l ON l.expediente_grupo = c.expediente_grupo
    LEFT JOIN {SCHEMA}.project_boletin p ON p.id = l.project_id
    ON CONFLICT (id) DO NOTHING
    """

    sql_licencia = f"""
    INSERT INTO {SCHEMA}.licencia (
      id, licencia_key, inmueble_id, anio_dataset, fecha_alta, fecha_concesion,
      procedimiento, tipo_expediente, uso, interesado, objeto, unidad,
      lat, lng, raw_json, inserted_at, updated_at
    )
    SELECT
      a.id, a.licencia_key, a.inmueble_id, a.anio_dataset, a.fecha_alta, a.fecha_concesion,
      a.procedimiento, a.tipo_expediente, a.uso, a.interesado, a.objeto, a.unidad,
      a.lat, a.lng, a.raw_json, a.inserted_at, now()
    FROM {SCHEMA}.actuacion_edificacion a
    ON CONFLICT (licencia_key) DO NOTHING
    """

    with psycopg2.connect(pg_url()) as con:
        with con.cursor() as cur:
            if args.dry_run:
                cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.sigma_catalog_expediente")
                n_sigma = cur.fetchone()[0]
                cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.actuacion_edificacion")
                n_lic = cur.fetchone()[0]
                print(json.dumps({"sigma_catalog": n_sigma, "actuacion_edificacion": n_lic}, indent=2))
                return
            cur.execute(sql_proyecto)
            n_p = cur.rowcount
            cur.execute(sql_licencia)
            n_l = cur.rowcount
        con.commit()
    print(json.dumps({"proyecto_inserted": n_p, "licencia_inserted": n_l}, indent=2))


if __name__ == "__main__":
    main()
