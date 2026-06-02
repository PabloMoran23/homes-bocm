#!/usr/bin/env python3
"""
Genera web/public/data/* desde tablas de dominio en Supabase (post sync_dominio).

Uso:
  export SUPABASE_DB_URL=...
  python3 db/export_web_data_from_supabase.py [out_dir]

Requiere haber ejecutado sync_dominio_to_supabase.py antes.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

DB_DIR = Path(__file__).resolve().parent
POC_ROOT = DB_DIR.parent
sys.path.insert(0, str(DB_DIR))
sys.path.insert(0, str(POC_ROOT))

from export_sigma_ambito_web import fecha_aprob_ms  # noqa: E402
from sector_geometry.madrid_nti_vivienda_sanity import sanitize_viviendas_en_metrics  # noqa: E402
from sync_madrid_public_to_supabase import pg_url  # noqa: E402
from sync_programas_dominio import sync_programas  # noqa: E402

SCHEMA = "homes"
DEFAULT_OUT = POC_ROOT / "web" / "public" / "data"
LICENCIAS_MIN_YEAR_PUBLIC = 2022

# Orden de «última licencia» (misma lógica que export_ubicaciones_web.py / actuacion_edificacion).
_ULTIMA_LICENCIA_ORDER = """
  ORDER BY
    CASE WHEN l.fecha_concesion IS NULL OR TRIM(l.fecha_concesion) = '' THEN 1 ELSE 0 END,
    l.fecha_concesion DESC NULLS LAST,
    l.fecha_alta DESC NULLS LAST
  LIMIT 1
"""


def fecha_es_a_iso(raw: str | None) -> str | None:
    """Convierte D/M/YYYY o ISO a YYYY-MM-DD para el cliente."""
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    parts = s.split("/")
    if len(parts) == 3:
        try:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 100:
                y += 2000 if y < 50 else 1900
            return f"{y:04d}-{m:02d}-{d:02d}"
        except ValueError:
            return None
    return None


STRIP_PROYECTO_JSON = (
    "visor_raw_json",
    "raw_features_json",
    "metrics_json",
    "hechos_json",
    "fuentes_pdf_json",
    "geom_geojson",
    "tramitacion",
    "documentacion_urls",
    "nti_documentos_muestra",
    "visor_ficha",
    "visor_cabecera",
    "clasificacion_fuentes",
)

LAYER_GEO_FILES = {
    "informacion_publica": "madrid-sigma-ip.geojson",
    "tramitados_ad": "madrid-sigma-ad.geojson",
    "gestion": "madrid-sigma-gestion.geojson",
    "urbanizacion": "madrid-sigma-urbanizacion.geojson",
}

LAYER_KIND_ALIASES = {
    "tramitados_gestion": "gestion",
    "tramitados_urbanizacion": "urbanizacion",
}

MADRID_MUNICIPIO_SQL = """
  lower(trim(coalesce(p.bocm_municipio, p.municipio, ''))) IN (
    'madrid', 'madrid capital', 'madrid, capital'
  )
"""


def log(msg: str) -> None:
    print(msg, flush=True)


def _iso_date(v: Any) -> str:
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        return str(v)[:10]
    return str(v)[:10]


def proyecto_to_portal(row: dict[str, Any]) -> dict[str, Any]:
    enlace = row.get("enlace") or row.get("sigma_enlace_snapshot")
    return {
        "id": row.get("bocm_primary_id") or row.get("id"),
        "sourceId": row.get("bocm_source_id") or "bocm",
        "sourceLabel": "Homes",
        "territorioId": "comunidad-madrid",
        "territorioLabel": "Comunidad de Madrid",
        "bocmDate": _iso_date(row.get("bocm_pub_date")),
        "artNum": row.get("bocm_art_num") or "",
        "title": row.get("bocm_title") or "",
        "pdfUrl": row.get("bocm_pdf_url"),
        "municipio": row.get("bocm_municipio") or row.get("municipio") or "",
        "tipoInstrumento": row.get("bocm_tipo_instrumento") or "",
        "nombreSector": row.get("bocm_nombre_sector") or "",
        "estadoTramitacion": row.get("bocm_estado_tramitacion") or "",
        "fechaAcuerdo": row.get("bocm_fecha_acuerdo"),
        "organo": row.get("bocm_organo") or "",
        "promotor": row.get("bocm_promotor"),
        "numViviendas": row.get("num_viviendas_max"),
        "supTotalM2": row.get("sup_total_m2"),
        "supEdificableM2": row.get("sup_edificable_m2"),
        "tipoVivienda": row.get("tipo_vivienda"),
        "resumen": row.get("bocm_resumen") or "",
        "municipioProvincia": row.get("bocm_municipio_provincia") or "",
        "categoriasTematicas": row.get("bocm_categorias_tematicas"),
        "economicoResumen": row.get("bocm_economico_resumen"),
        "procedimientoExpediente": row.get("bocm_procedimiento_expediente"),
        "procedimientoTipo": row.get("bocm_procedimiento_tipo"),
        "importeTotalEur": row.get("importe_total_eur"),
        "requiereSegundaPasada": bool(row.get("bocm_requiere_segunda_pasada")),
        "charsTextoTotal": row.get("bocm_chars_texto_total"),
        "lat": row.get("lat"),
        "lng": row.get("lng"),
        "sectorKey": row.get("sector_key"),
        "sectorGeoKey": row.get("sector_geo_key"),
        "coordSource": row.get("coord_source"),
        "esRelevante": row.get("bocm_es_relevante"),
        "parseError": row.get("bocm_parse_error"),
        "sigmaMatchType": row.get("bocm_sigma_match_type"),
        "sigmaMatchScore": row.get("bocm_sigma_match_score"),
        "sigmaExpediente": row.get("expediente_grupo"),
        "sigmaDenominacion": row.get("denominacion"),
        "sigmaFase": row.get("fase"),
        "sigmaEnlace": enlace or None,
        "sigmaEnIp": row.get("sigma_layer_kind") == "informacion_publica",
        "sigmaCatalogSyncedAt": row.get("sigma_synced_at").isoformat()
        if row.get("sigma_synced_at")
        else None,
        "sigmaFiguraCodigo": row.get("figura_codigo"),
        "sigmaTipoFigura": row.get("tipo_figura"),
        "sigmaOrganoTramitador": row.get("organo_tramitador"),
        "sigmaCatalogSource": row.get("catalog_source"),
        "sigmaSigmaLayerKind": row.get("sigma_layer_kind"),
        "sigmaObjectId": row.get("object_id"),
        "sigmaFechaAprobacion": row.get("fecha_aprob"),
        "sigmaInfopublicaInicio": row.get("infopublica_inicio"),
        "sigmaInfopublicaFin": row.get("infopublica_fin"),
        "sigmaHasGeometrySigma": row.get("has_geometry") is True,
        "sigmaVisorFetchedAt": row.get("visor_fetched_at").isoformat()
        if row.get("visor_fetched_at")
        else None,
        "sigmaVisorUrl": row.get("visor_url"),
        "sigmaVisorCabecera": row.get("visor_cabecera"),
        "sigmaVisorTramitacion": row.get("tramitacion"),
        "sigmaVisorDocumentacionUrls": row.get("documentacion_urls"),
        "sigmaVisorNtiListadoUrl": row.get("nti_listado_url"),
        "sigmaVisorNtiDocumentosTotal": row.get("nti_documentos_total"),
        "sigmaVisorNtiDocumentosMuestra": row.get("nti_documentos_muestra"),
    }


def _fetch_proyectos_bocm(cur) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        SELECT *
        FROM {SCHEMA}.proyecto p
        WHERE p.bocm_primary_id IS NOT NULL AND {MADRID_MUNICIPIO_SQL}
        ORDER BY p.bocm_pub_date DESC NULLS LAST, p.bocm_primary_id
        """
    )
    return list(cur.fetchall())


def _fetch_proyectos_sigma(cur) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        SELECT *
        FROM {SCHEMA}.proyecto p
        WHERE p.expediente_grupo IS NOT NULL
           OR p.sigma_layer_kind IS NOT NULL
        ORDER BY p.expediente_grupo NULLS LAST, p.id
        """
    )
    return list(cur.fetchall())


def export_projects(out_dir: Path, rows: list[dict[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    projects = [proyecto_to_portal(r) for r in rows]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "projects.json").write_text(json.dumps(projects, ensure_ascii=False), encoding="utf-8")
    log(f"OK: projects.json ({len(projects)} proyectos Madrid)")

    by_exp: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in projects:
        exp = p.get("sigmaExpediente")
        if not exp or "/" not in str(exp):
            continue
        by_exp[str(exp)].append(
            {
                "id": p["id"],
                "title": str(p.get("title") or "")[:220],
                "bocmDate": p.get("bocmDate") or "",
                "artNum": p.get("artNum") or "",
                "esRelevante": p.get("esRelevante"),
            }
        )
    bocm_payload = {
        "generatedAt": generated_at,
        "expedienteKeys": len(by_exp),
        "byExpediente": {k: v[:25] for k, v in by_exp.items()},
    }
    (out_dir / "madrid-sigma-bocm-projects.json").write_text(
        json.dumps(bocm_payload, ensure_ascii=False),
        encoding="utf-8",
    )
    log(f"OK: madrid-sigma-bocm-projects.json ({len(by_exp)} expedientes)")

    summary = _build_summary(projects, generated_at)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    log("OK: summary.json")
    return projects


def _build_summary(projects: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    by_municipio: dict[str, int] = defaultdict(int)
    by_tipo: dict[str, int] = defaultdict(int)
    by_year: dict[str, int] = defaultdict(int)
    total_relevant = total_not = total_unknown = 0
    with_coords = 0
    date_min, date_max = "9999", "0000"

    for p in projects:
        if p.get("lat") is not None and p.get("lng") is not None:
            with_coords += 1
        rel = p.get("esRelevante")
        if rel is True:
            total_relevant += 1
        elif rel is False:
            total_not += 1
        else:
            total_unknown += 1
        if p.get("municipio"):
            by_municipio[str(p["municipio"])] += 1
        by_tipo[str(p.get("tipoInstrumento") or "Sin clasificar")] += 1
        d = str(p.get("bocmDate") or "")[:4]
        if d.isdigit():
            by_year[d] += 1
            if d < date_min:
                date_min = d
            if d > date_max:
                date_max = d

    sort_entries = lambda m: sorted(m.items(), key=lambda x: -x[1])  # noqa: E731

    return {
        "generatedAt": generated_at,
        "total": len(projects),
        "buildScope": "madrid-public",
        "source": "supabase-dominio",
        "totalRelevant": total_relevant,
        "totalNotRelevant": total_not,
        "totalRelevanceUnknown": total_unknown,
        "withCoords": with_coords,
        "dateRange": {
            "min": None if date_min == "9999" else date_min,
            "max": None if date_max == "0000" else date_max,
        },
        "byMunicipio": [{"name": k, "count": v} for k, v in sort_entries(by_municipio)[:50]],
        "byTipo": [{"name": k, "count": v} for k, v in sort_entries(by_tipo)[:30]],
        "byYear": [{"year": y, "count": c} for y, c in sorted(by_year.items())],
        "byTerritorio": [{"name": "Comunidad de Madrid", "count": len(projects)}],
        "byTerritorioRelevant": [{"name": "Comunidad de Madrid", "count": total_relevant}],
        "bySource": [{"name": "bocm", "count": len(projects)}],
        "portal": {
            "name": "Homes · Urbanismo",
            "tagline": "Proyectos urbanísticos en tu zona",
        },
    }


def export_madrid_sigma(out_dir: Path, rows: list[dict[str, Any]], generated_at: str) -> None:
    expedientes = []
    for r in rows:
        if not r.get("expediente_grupo") and not r.get("sigma_layer_kind"):
            continue
        expedientes.append(
            {
                "source": r.get("catalog_source") or r.get("sigma_layer_kind") or "tramitados_ad",
                "EXP_TX_NUMERO": r.get("exp_numero_original") or r.get("expediente_grupo") or r.get("id"),
                "EXP_TX_DENOM": r.get("denominacion"),
                "FAS_TX_DENOM": r.get("fase"),
                "FEX_DT_INFOPUB_INI": r.get("infopublica_inicio"),
                "FEX_DT_INFOPUB_FIN": r.get("infopublica_fin"),
                "FEX_DT_APROB": r.get("fecha_aprob"),
                "FIG_TX_ETIQ": r.get("figura_codigo"),
                "TFIG_TX_ABREV": r.get("tipo_figura"),
                "ORG_TX_DESC": r.get("organo_tramitador"),
                "EXP_ID": r.get("object_id"),
                "Enlace": r.get("enlace"),
                "sigma_layer_kind": r.get("sigma_layer_kind"),
                "has_geometry": r.get("has_geometry") is True,
            }
        )
    with_geom = sum(1 for e in expedientes if e.get("has_geometry"))
    payload = {
        "generatedAt": generated_at,
        "source": "supabase-dominio",
        "expedientes": expedientes,
        "counts": {
            "total": len(expedientes),
            "with_geometry": with_geom,
            "expedientes_unicos": len({e["EXP_TX_NUMERO"] for e in expedientes}),
        },
    }
    (out_dir / "madrid-sigma.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    log(f"OK: madrid-sigma.json ({len(expedientes)} expedientes)")


def export_clasificacion(out_dir: Path, rows: list[dict[str, Any]], generated_at: str) -> None:
    by_exp: dict[str, dict[str, Any]] = {}
    for r in rows:
        g = r.get("expediente_grupo")
        if not g or not r.get("categoria_proyecto"):
            continue
        by_exp[str(g)] = {
            "tipoLegal": r.get("tipo_legal"),
            "escala": r.get("escala"),
            "contenidoPrincipal": r.get("contenido_principal"),
            "faseNormalizada": r.get("fase_normalizada"),
            "categoriaProyecto": r.get("categoria_proyecto"),
            "tipoObra": r.get("tipo_obra"),
            "confianza": r.get("clasificacion_confianza"),
        }
    (out_dir / "madrid-sigma-clasificacion.json").write_text(
        json.dumps({"generatedAt": generated_at, "byExpediente": by_exp}, ensure_ascii=False),
        encoding="utf-8",
    )
    log(f"OK: madrid-sigma-clasificacion.json ({len(by_exp)} expedientes)")


def export_visor_slim(out_dir: Path, rows: list[dict[str, Any]], generated_at: str) -> None:
    slim: dict[str, Any] = {}
    con_visor = 0
    for r in rows:
        g = r.get("expediente_grupo")
        if not g:
            continue
        nti = r.get("nti_documentos_muestra")
        if isinstance(nti, list) and len(nti) > 15:
            nti = nti[:15]
        if r.get("visor_ficha") or r.get("tramitacion"):
            con_visor += 1
        slim[str(g)] = {
            "expedienteGrupo": g,
            "sinDatosVisor": r.get("sin_datos_visor"),
            "visorUrlUsada": r.get("visor_url"),
            "visorCabecera": r.get("visor_cabecera"),
            "visorFicha": r.get("visor_ficha"),
            "tramitacion": r.get("tramitacion"),
            "documentacionUrls": r.get("documentacion_urls"),
            "ntiListadoUrl": r.get("nti_listado_url"),
            "ntiDocumentosTotal": r.get("nti_documentos_total"),
            "ntiDocumentosMuestra": nti if isinstance(nti, list) else [],
        }
    payload = {
        "generatedAt": generated_at,
        "conVisorFicha": con_visor,
        "byGrupoExpediente": slim,
    }
    (out_dir / "madrid-sigma-visor-slim.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    log(f"OK: madrid-sigma-visor-slim.json ({len(slim)} expedientes)")


def export_metrics(out_dir: Path, rows: list[dict[str, Any]], generated_at: str) -> None:
    by: dict[str, dict[str, Any]] = {}
    for r in rows:
        g = r.get("expediente_grupo")
        if not g:
            continue
        hechos: list = []
        if r.get("hechos_json"):
            raw = r["hechos_json"]
            if isinstance(raw, list):
                hechos = raw[:6]
            elif isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                    hechos = parsed[:6] if isinstance(parsed, list) else []
                except json.JSONDecodeError:
                    pass
        tipo_vivienda = None
        mj = r.get("metrics_json")
        if isinstance(mj, dict):
            tipo_vivienda = mj.get("tipo_vivienda")
        elif isinstance(mj, str):
            try:
                parsed = json.loads(mj)
                if isinstance(parsed, dict):
                    tipo_vivienda = parsed.get("tipo_vivienda")
            except json.JSONDecodeError:
                pass
        row = sanitize_viviendas_en_metrics(
            {
                "num_viviendas_max": r.get("num_viviendas_max"),
                "sup_total_m2": r.get("sup_total_m2"),
                "sup_edificable_m2": r.get("sup_edificable_m2"),
                "tipo_vivienda": tipo_vivienda,
                "genera_vivienda_nueva": r.get("genera_vivienda_nueva"),
                "familia_expediente": r.get("familia_expediente"),
                "pdfs_procesados": r.get("pdfs_procesados"),
                "doc_role_principal": r.get("doc_role_principal"),
                "hechos": hechos,
            }
        )
        by[str(g)] = row
    payload = {"generatedAt": generated_at, "count": len(by), "byExpediente": by}
    (out_dir / "madrid-sigma-metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    log(f"OK: madrid-sigma-metrics.json ({len(by)} expedientes)")


def _feature_from_proyecto(r: dict[str, Any], licencias_linked: int = 0) -> dict[str, Any] | None:
    geom_raw = r.get("geom_geojson")
    if not geom_raw:
        return None
    if isinstance(geom_raw, str):
        try:
            geom = json.loads(geom_raw)
        except json.JSONDecodeError:
            return None
    else:
        geom = geom_raw
    if not geom or not geom.get("type"):
        return None
    ms_aprob = fecha_aprob_ms(r.get("fecha_aprob"))
    props: dict[str, Any] = {
        "EXP_TX_NUMERO": r.get("exp_numero_original") or r.get("expediente_grupo"),
        "EXP_TX_DENOM": r.get("denominacion"),
        "FIG_TX_ETIQ": r.get("figura_codigo"),
        "FAS_TX_DENOM": r.get("fase"),
        "ENLACE": r.get("enlace"),
        "sigma_layer_kind": r.get("sigma_layer_kind"),
        "licencias_linked": licencias_linked,
    }
    if ms_aprob is not None:
        props["FEX_DT_APROB"] = ms_aprob
    ip_ini = fecha_aprob_ms(r.get("infopublica_inicio"))
    ip_fin = fecha_aprob_ms(r.get("infopublica_fin"))
    if ip_ini is not None:
        props["FEX_DT_INFOPUB_INI"] = ip_ini
    if ip_fin is not None:
        props["FEX_DT_INFOPUB_FIN"] = ip_fin
    return {"type": "Feature", "geometry": geom, "properties": props}


def export_sigma_geojson(out_dir: Path, rows: list[dict[str, Any]], cur) -> None:
    cur.execute(
        f"""
        SELECT p.expediente_grupo, COUNT(*)::int AS n
        FROM {SCHEMA}.licencia l
        JOIN {SCHEMA}.proyecto p ON p.id = l.proyecto_id
        WHERE p.expediente_grupo IS NOT NULL
        GROUP BY p.expediente_grupo
        """
    )
    lic_by_exp = {r["expediente_grupo"]: r["n"] for r in cur.fetchall() if r.get("expediente_grupo")}

    by_layer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ambitos: list[dict[str, Any]] = []
    skipped = 0

    for r in rows:
        if not r.get("has_geometry") or not r.get("geom_geojson"):
            continue
        feat = _feature_from_proyecto(r, lic_by_exp.get(r.get("expediente_grupo"), 0))
        if not feat:
            skipped += 1
            continue
        ambitos.append(feat)
        kind = LAYER_KIND_ALIASES.get(r.get("sigma_layer_kind") or "", r.get("sigma_layer_kind") or "")
        if kind in LAYER_GEO_FILES:
            by_layer[kind].append(feat)

    for kind, fname in LAYER_GEO_FILES.items():
        fc = {"type": "FeatureCollection", "features": by_layer.get(kind, [])}
        (out_dir / fname).write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
        log(f"OK: {fname} ({len(fc['features'])} features)")

    ambitos_path = out_dir / "madrid-sigma-ambitos.geojson"
    ambitos_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": ambitos}, ensure_ascii=False),
        encoding="utf-8",
    )
    log(f"OK: madrid-sigma-ambitos.geojson ({len(ambitos)} features, skipped {skipped})")


def export_ubicaciones(out_dir: Path, cur) -> None:
    cur.execute(
        f"""
        SELECT
          i.ndp_edificio,
          i.direccion,
          i.distrito,
          i.barrio,
          i.lat,
          i.lng,
          (SELECT COUNT(*)::int FROM {SCHEMA}.licencia l WHERE l.inmueble_id = i.id) AS licencias_count,
          (SELECT COUNT(DISTINCT p.expediente_grupo)::int
             FROM {SCHEMA}.licencia l
             JOIN {SCHEMA}.proyecto p ON p.id = l.proyecto_id
            WHERE l.inmueble_id = i.id AND p.expediente_grupo IS NOT NULL) AS sigma_count,
          (SELECT l.tipo_expediente FROM {SCHEMA}.licencia l
            WHERE l.inmueble_id = i.id {_ULTIMA_LICENCIA_ORDER}) AS ultima_licencia_tipo,
          (SELECT l.objeto FROM {SCHEMA}.licencia l
            WHERE l.inmueble_id = i.id {_ULTIMA_LICENCIA_ORDER}) AS ultima_licencia_objeto,
          (SELECT l.uso FROM {SCHEMA}.licencia l
            WHERE l.inmueble_id = i.id {_ULTIMA_LICENCIA_ORDER}) AS ultima_licencia_uso,
          (SELECT l.procedimiento FROM {SCHEMA}.licencia l
            WHERE l.inmueble_id = i.id {_ULTIMA_LICENCIA_ORDER}) AS ultima_licencia_procedimiento,
          (SELECT COALESCE(NULLIF(TRIM(l.fecha_concesion), ''), l.fecha_alta)
             FROM {SCHEMA}.licencia l
            WHERE l.inmueble_id = i.id {_ULTIMA_LICENCIA_ORDER}) AS ultima_licencia_fecha
        FROM {SCHEMA}.inmueble i
        WHERE i.lat IS NOT NULL AND i.lng IS NOT NULL
        """
    )
    rows = cur.fetchall()
    features = []
    search = []
    for r in rows:
        lat, lng = float(r["lat"]), float(r["lng"])
        if not (39.5 <= lat <= 41.2 and -4.5 <= lng <= -3.0):
            continue
        ndp = r["ndp_edificio"]
        direccion = r.get("direccion")
        distrito = r.get("distrito")
        props = {
            "ndp": ndp,
            "direccion": direccion,
            "distrito": distrito,
            "barrio": r.get("barrio"),
            "licencias": r.get("licencias_count") or 0,
            "sigma": r.get("sigma_count") or 0,
            "ultimaLicenciaTipo": r.get("ultima_licencia_tipo"),
            "ultimaLicenciaObjeto": r.get("ultima_licencia_objeto"),
            "ultimaLicenciaUso": r.get("ultima_licencia_uso"),
            "ultimaLicenciaProcedimiento": r.get("ultima_licencia_procedimiento"),
            "ultimaLicenciaFecha": fecha_es_a_iso(r.get("ultima_licencia_fecha")),
        }
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": props,
            }
        )
        search.append(
            {
                "ndp": ndp,
                "direccion": direccion or "",
                "distrito": distrito or "",
                "barrio": r.get("barrio") or "",
                "label": " · ".join(p for p in [direccion, distrito, f"NDP {ndp}"] if p),
                "lat": lat,
                "lng": lng,
            }
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ubicaciones-map.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "ubicaciones-search.json").write_text(
        json.dumps(search, ensure_ascii=False),
        encoding="utf-8",
    )
    meta = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "total": len(search),
        "withCoords": len(search),
        "source": "supabase-dominio",
    }
    (out_dir / "ubicaciones-meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log(f"OK: ubicaciones ({len(features)} puntos)")


def _licencia_year(row: dict[str, Any]) -> int | None:
    y = row.get("anio_dataset")
    if isinstance(y, int) and y > 1900:
        return y
    for field in ("fecha_concesion", "fecha_alta"):
        raw = row.get(field)
        if not raw:
            continue
        s = str(raw).strip()
        if len(s) >= 4 and s[:4].isdigit():
            return int(s[:4])
    return None


def export_licencias(out_dir: Path, cur, min_year: int) -> None:
    cur.execute(
        f"""
        SELECT
          l.id,
          l.licencia_key,
          l.anio_dataset,
          l.fecha_alta,
          l.fecha_concesion,
          l.procedimiento,
          l.tipo_expediente,
          l.uso,
          l.interesado,
          l.objeto,
          l.unidad,
          COALESCE(l.lat, i.lat) AS lat,
          COALESCE(l.lng, i.lng) AS lng,
          i.ndp_edificio,
          i.direccion,
          i.distrito
        FROM {SCHEMA}.licencia l
        LEFT JOIN {SCHEMA}.inmueble i ON i.id = l.inmueble_id
        """
    )
    rows = cur.fetchall()
    by_year: dict[int, dict[str, list]] = defaultdict(lambda: {"features": [], "rows": []})
    total = with_coords = 0
    by_uso: dict[str, int] = defaultdict(int)
    by_distrito: dict[str, int] = defaultdict(int)

    for r in rows:
        year = _licencia_year(r)
        if year is None or year < min_year:
            continue
        total += 1
        lat, lng = r.get("lat"), r.get("lng")
        row_out = {
            "id": r["id"],
            "licenciaKey": r.get("licencia_key"),
            "anioDataset": year,
            "fechaAlta": r.get("fecha_alta"),
            "fechaConcesion": r.get("fecha_concesion"),
            "procedimiento": r.get("procedimiento"),
            "tipoExpediente": r.get("tipo_expediente"),
            "uso": r.get("uso"),
            "objeto": r.get("objeto"),
            "ndp": r.get("ndp_edificio"),
            "direccion": r.get("direccion"),
            "distrito": r.get("distrito"),
        }
        by_year[year]["rows"].append(row_out)
        if lat is not None and lng is not None:
            lat, lng = float(lat), float(lng)
            if 39.5 <= lat <= 41.2 and -4.5 <= lng <= -3.0:
                with_coords += 1
                by_year[year]["features"].append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lng, lat]},
                        "properties": {
                            "id": r["id"],
                            "tipoExpediente": r.get("tipo_expediente"),
                            "objeto": r.get("objeto"),
                            "uso": r.get("uso"),
                            "procedimiento": r.get("procedimiento"),
                            "distrito": r.get("distrito"),
                        },
                    }
                )
        if r.get("uso"):
            by_uso[str(r["uso"])] += 1
        if r.get("distrito"):
            by_distrito[str(r["distrito"])] += 1

    years = sorted(by_year.keys())
    by_year_count = {}
    for y in years:
        pack = by_year[y]
        by_year_count[str(y)] = len(pack["rows"])
        (out_dir / f"madrid-licencias-{y}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": pack["features"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (out_dir / f"madrid-licencias-{y}.json").write_text(
            json.dumps(pack["rows"], ensure_ascii=False),
            encoding="utf-8",
        )
        log(f"OK: madrid-licencias-{y} ({len(pack['rows'])} filas)")

    top = lambda m, n=20: sorted(m.items(), key=lambda x: -x[1])[:n]  # noqa: E731
    index = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "source": "supabase-dominio",
        "totalRows": total,
        "withCoords": with_coords,
        "byYear": by_year_count,
        "years": years,
        "topUso": [{"name": k, "count": v} for k, v in top(by_uso)],
        "topDistrito": [{"name": k, "count": v} for k, v in top(by_distrito)],
    }
    (out_dir / "madrid-licencias-index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log(f"OK: madrid-licencias-index.json ({total} filas desde {min_year})")


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).isoformat()
    log(f"export_web_data_from_supabase → {out_dir}")

    with psycopg2.connect(pg_url()) as con:
        with con.cursor(cursor_factory=RealDictCursor) as cur:
            bocm_rows = _fetch_proyectos_bocm(cur)
            sigma_rows = _fetch_proyectos_sigma(cur)
            export_projects(out_dir, bocm_rows, generated_at)
            export_madrid_sigma(out_dir, sigma_rows, generated_at)
            export_clasificacion(out_dir, sigma_rows, generated_at)
            export_visor_slim(out_dir, sigma_rows, generated_at)
            export_metrics(out_dir, sigma_rows, generated_at)
            export_sigma_geojson(out_dir, sigma_rows, cur)
            export_ubicaciones(out_dir, cur)
            export_licencias(out_dir, cur, LICENCIAS_MIN_YEAR_PUBLIC)
            stats_prog = sync_programas(cur, out_dir / "madrid-sigma-programas.json")
            log(
                f"OK: madrid-sigma-programas.json ({stats_prog['programas']} programas, "
                f"{stats_prog['proyecto_con_programa']} proyectos con programa_id)"
            )

    log("OK: exportación Supabase completada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
