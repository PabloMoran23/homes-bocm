"""
Upsert de ingesta → Supabase (esquema homes).

Los scrapers llaman a estas funciones al terminar (o fila a fila en boletines).
Requiere SUPABASE_DB_URL o DATABASE_URL.

Uso:
  from ingest import IngestSession, available

  with IngestSession("municipio", municipio_slug="mostoles") as ses:
      ses.save_municipio({...})
      ses.save_proyectos([...])
      ses.save_licencias([...])
      ses.save_documentos([...])
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

import psycopg2
from psycopg2.extras import Json, execute_values

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = Path(__file__).resolve().parent
if str(POC_ROOT) not in sys.path:
    sys.path.insert(0, str(POC_ROOT))
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

from municipio.geometry import geometry_bbox, record_geometry  # noqa: E402

SCHEMA = "homes"

_GEOM_TYPES = {
    "Polygon",
    "MultiPolygon",
    "LineString",
    "MultiLineString",
    "Point",
    "MultiPoint",
}


def _load_dotenv() -> None:
    path = POC_ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        val = val.strip().strip("'").strip('"')
        os.environ[key] = val


def available() -> bool:
    _load_dotenv()
    return bool(os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL"))


def pg_url() -> str:
    _load_dotenv()
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta SUPABASE_DB_URL o DATABASE_URL")
    return url


def connect():
    return psycopg2.connect(pg_url())


def _now() -> datetime:
    return datetime.now(UTC)


def _blank(s: Any) -> str | None:
    t = str(s or "").strip()
    return t or None


def _float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _bool(v: Any) -> bool | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "sí", "si")


def _jsonish(v: Any, *, default: Any = None) -> Any:
    if v is None:
        v = default
    if v is None:
        return None
    if isinstance(v, Json):
        return v
    if isinstance(v, (dict, list)):
        return Json(v)
    return v


def _latlng(rec: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = _float(rec.get("lat"))
    lng = rec.get("lon") if rec.get("lon") is not None else rec.get("lng")
    return lat, _float(lng)


@contextmanager
def _owned_conn(conn) -> Iterator[Any]:
    if conn is not None:
        yield conn
        return
    with connect() as owned:
        yield owned
        owned.commit()


def _next_licencia_ids(cur, keys: list[str]) -> dict[str, int]:
    if not keys:
        return {}
    cur.execute(
        f"SELECT licencia_key, id FROM {SCHEMA}.licencia WHERE licencia_key = ANY(%s)",
        (keys,),
    )
    out = {str(r[0]): int(r[1]) for r in cur.fetchall()}
    cur.execute(f"SELECT COALESCE(MAX(id), 0) FROM {SCHEMA}.licencia")
    nxt = int(cur.fetchone()[0]) + 1
    for k in keys:
        if k not in out:
            out[k] = nxt
            nxt += 1
    return out


# ---------------------------------------------------------------------------
# Municipio
# ---------------------------------------------------------------------------

def save_municipio(row: dict[str, Any], *, conn=None) -> str:
    slug = str(row["slug"]).strip()
    if not slug:
        raise ValueError("municipio.slug vacío")
    now = _now()
    with _owned_conn(conn) as c, c.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {SCHEMA}.municipio (
              slug, nombre, provincia, comunidad_autonoma, ine, lat, lng,
              portal_url, adapter, last_ingest_at, raw, inserted_at, updated_at
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (slug) DO UPDATE SET
              nombre = EXCLUDED.nombre,
              provincia = COALESCE(EXCLUDED.provincia, {SCHEMA}.municipio.provincia),
              comunidad_autonoma = COALESCE(EXCLUDED.comunidad_autonoma, {SCHEMA}.municipio.comunidad_autonoma),
              ine = COALESCE(EXCLUDED.ine, {SCHEMA}.municipio.ine),
              lat = COALESCE(EXCLUDED.lat, {SCHEMA}.municipio.lat),
              lng = COALESCE(EXCLUDED.lng, {SCHEMA}.municipio.lng),
              portal_url = COALESCE(EXCLUDED.portal_url, {SCHEMA}.municipio.portal_url),
              adapter = COALESCE(EXCLUDED.adapter, {SCHEMA}.municipio.adapter),
              last_ingest_at = COALESCE(EXCLUDED.last_ingest_at, {SCHEMA}.municipio.last_ingest_at),
              raw = EXCLUDED.raw,
              updated_at = EXCLUDED.updated_at
            """,
            (
                slug,
                str(row.get("nombre") or slug),
                _blank(row.get("provincia")),
                _blank(row.get("comunidad_autonoma")),
                _blank(row.get("ine")),
                _float(row.get("lat")),
                _float(row.get("lng")),
                _blank(row.get("portal_url")),
                _blank(row.get("adapter")),
                row.get("last_ingest_at"),
                Json(row.get("raw") if isinstance(row.get("raw"), dict) else {}),
                now,
                now,
            ),
        )
    return slug


def touch_last_ingest_at(slug: str, *, conn=None) -> None:
    """Marca el municipio como refrescado ahora (solo tras ingest OK)."""
    slug = str(slug or "").strip()
    if not slug:
        return
    now = _now()
    with _owned_conn(conn) as c, c.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {SCHEMA}.municipio
            SET last_ingest_at = %s, updated_at = %s
            WHERE slug = %s
            """,
            (now, now, slug),
        )


def fetch_last_ingest_at(*, conn=None) -> dict[str, datetime]:
    """slug → última ingest OK (UTC)."""
    if not available() and conn is None:
        return {}
    with _owned_conn(conn) as c, c.cursor() as cur:
        cur.execute(
            f"SELECT slug, last_ingest_at FROM {SCHEMA}.municipio WHERE last_ingest_at IS NOT NULL"
        )
        out: dict[str, datetime] = {}
        for slug, ts in cur.fetchall():
            if slug and ts:
                if getattr(ts, "tzinfo", None) is None:
                    ts = ts.replace(tzinfo=UTC)
                out[str(slug)] = ts
        return out


def save_municipio_from_manifest(manifest: Any, *, conn=None) -> str:
    portal = getattr(manifest, "portal", None)
    return save_municipio(
        {
            "slug": manifest.slug,
            "nombre": manifest.nombre,
            "provincia": getattr(manifest, "provincia", None),
            "comunidad_autonoma": getattr(manifest, "comunidad_autonoma", None),
            "portal_url": getattr(portal, "base_url", None) if portal else None,
            "adapter": getattr(portal, "adapter", None) if portal else None,
            "raw": {"path": str(getattr(manifest, "path", "") or "")},
        },
        conn=conn,
    )


# ---------------------------------------------------------------------------
# Proyecto
# ---------------------------------------------------------------------------

_PROYECTO_UPSERT_COLS = [
    "id",
    "expediente_grupo",
    "exp_numero_original",
    "denominacion",
    "fecha_aprob",
    "enlace",
    "catalog_source",
    "sigma_layer_kind",
    "infopublica_inicio",
    "infopublica_fin",
    "figura_codigo",
    "tipo_figura",
    "organo_tramitador",
    "object_id",
    "sigma_synced_at",
    "has_geometry",
    "geom_geojson",
    "bbox_min_lng",
    "bbox_min_lat",
    "bbox_max_lng",
    "bbox_max_lat",
    "centroid_lat",
    "centroid_lng",
    "area_approx_m2",
    "raw_features_json",
    "sin_datos_visor",
    "visor_url",
    "visor_cabecera",
    "visor_ficha",
    "tramitacion",
    "documentacion_urls",
    "nti_documentos_total",
    "nti_documentos_muestra",
    "nti_listado_url",
    "visor_fetched_at",
    "visor_raw_json",
    "resumen_contenido",
    "tipo_legal",
    "escala",
    "contenido_principal",
    "fase",
    "fase_normalizada",
    "categoria_proyecto",
    "tipo_obra",
    "clasificacion_confianza",
    "clasificacion_fuentes",
    "bocm_primary_id",
    "bocm_source_id",
    "bocm_pub_date",
    "bocm_art_num",
    "bocm_title",
    "bocm_pdf_url",
    "bocm_municipio",
    "bocm_tipo_instrumento",
    "bocm_resumen",
    "bocm_es_relevante",
    "bocm_sigma_match_type",
    "bocm_sigma_match_score",
    "municipio",
    "municipio_slug",
    "fuente",
    "id_origen",
    "lat",
    "lng",
    "coord_source",
    "sector_key",
    "num_viviendas_max",
    "sup_total_m2",
    "sup_edificable_m2",
    "inserted_at",
    "updated_at",
]


def portal_proyecto_row(rec: dict[str, Any], *, slug: str, nombre: str) -> dict[str, Any] | None:
    pid = _blank(rec.get("id"))
    if not pid:
        return None
    now = _now()
    titulo = str(rec.get("titulo") or rec.get("denominacion") or "").strip()
    tipo = str(rec.get("tipo") or rec.get("tipo_figura") or rec.get("figura_codigo") or "").strip()
    fecha = _blank(rec.get("fecha") or rec.get("fecha_aprob"))
    pub_date = fecha[:10] if fecha and len(fecha) >= 10 else None
    lat, lng = _latlng(rec)
    url = _blank(rec.get("url") or rec.get("enlace") or rec.get("visor_url"))
    docs: list[str] = []
    if rec.get("pdf_url"):
        docs.append(str(rec["pdf_url"]))
    if isinstance(rec.get("pdf_urls"), list):
        docs.extend(str(u) for u in rec["pdf_urls"][:40])
    if isinstance(rec.get("documentacion_urls"), list):
        docs.extend(str(u) for u in rec["documentacion_urls"][:40])
    docs = list(dict.fromkeys(d for d in docs if d))
    geom = record_geometry(rec)
    bbox = geometry_bbox(geom) if geom else None
    has_geom = bool(geom and str(geom.get("type") or "") in _GEOM_TYPES)
    fuente_raw = str(rec.get("fuente") or rec.get("source") or "ayuntamiento").strip().lower()
    if fuente_raw in ("sigma", "madrid-sigma"):
        fuente = "sigma"
    elif fuente_raw in ("bocm", "bocm_legacy"):
        fuente = "bocm"
    else:
        fuente = fuente_raw or "ayuntamiento"
    catalog_source = _blank(rec.get("catalog_source")) or (
        "sigma" if fuente == "sigma" else "ayuntamiento-portal"
    )
    fase = _blank(rec.get("fase")) or _blank(tipo)
    visor_url = _blank(rec.get("visor_url")) or url
    nti_muestra = rec.get("nti_documentos_muestra")
    if not isinstance(nti_muestra, list):
        nti_muestra = docs[:5]
    tramitacion = rec.get("tramitacion") if isinstance(rec.get("tramitacion"), list) else []
    doc_urls = rec.get("documentacion_urls") if isinstance(rec.get("documentacion_urls"), list) else docs
    return {
        "id": pid,
        "expediente_grupo": _blank(rec.get("expediente_grupo")),
        "exp_numero_original": _blank(rec.get("exp_numero_original")),
        "denominacion": _blank(titulo),
        "fecha_aprob": pub_date,
        "enlace": url,
        "catalog_source": catalog_source,
        "sigma_layer_kind": _blank(rec.get("sigma_layer_kind")),
        "infopublica_inicio": _blank(rec.get("infopublica_inicio")),
        "infopublica_fin": _blank(rec.get("infopublica_fin")),
        "figura_codigo": _blank(rec.get("figura_codigo")),
        "tipo_figura": _blank(rec.get("tipo_figura")),
        "organo_tramitador": _blank(rec.get("organo_tramitador")),
        "object_id": _int(rec.get("object_id")),
        "sigma_synced_at": rec.get("sigma_synced_at"),
        "has_geometry": has_geom,
        "geom_geojson": Json(geom) if geom else None,
        "bbox_min_lng": rec.get("bbox_min_lng") if rec.get("bbox_min_lng") is not None else (bbox[0] if bbox else None),
        "bbox_min_lat": rec.get("bbox_min_lat") if rec.get("bbox_min_lat") is not None else (bbox[1] if bbox else None),
        "bbox_max_lng": rec.get("bbox_max_lng") if rec.get("bbox_max_lng") is not None else (bbox[2] if bbox else None),
        "bbox_max_lat": rec.get("bbox_max_lat") if rec.get("bbox_max_lat") is not None else (bbox[3] if bbox else None),
        "centroid_lat": rec.get("centroid_lat") if rec.get("centroid_lat") is not None else lat,
        "centroid_lng": rec.get("centroid_lng") if rec.get("centroid_lng") is not None else lng,
        "area_approx_m2": _float(rec.get("area_approx_m2")),
        "raw_features_json": Json({k: v for k, v in rec.items() if k != "id"}),
        "sin_datos_visor": bool(rec.get("sin_datos_visor")) if rec.get("sin_datos_visor") is not None else False,
        "visor_url": visor_url,
        "visor_cabecera": _jsonish(rec.get("visor_cabecera")),
        "visor_ficha": _jsonish(rec.get("visor_ficha")),
        "tramitacion": _jsonish(tramitacion, default=[]),
        "documentacion_urls": _jsonish(doc_urls, default=[]),
        "nti_documentos_total": _int(rec.get("nti_documentos_total")) or (len(docs) if docs else None),
        "nti_documentos_muestra": _jsonish(nti_muestra, default=[]),
        "nti_listado_url": _blank(rec.get("nti_listado_url")) or url,
        "visor_fetched_at": rec.get("visor_fetched_at"),
        "visor_raw_json": _jsonish(rec.get("visor_raw") or rec.get("visor_raw_json"), default={}),
        "resumen_contenido": _blank(rec.get("resumen_contenido")) or _blank(titulo),
        "tipo_legal": _blank(rec.get("tipo_legal")) or _blank(tipo),
        "escala": _blank(rec.get("escala")),
        "contenido_principal": _blank(rec.get("contenido_principal")) or _blank(titulo),
        "fase": fase,
        "fase_normalizada": _blank(rec.get("fase_normalizada")),
        "categoria_proyecto": _blank(rec.get("categoria_proyecto")),
        "tipo_obra": _blank(rec.get("tipo_obra")),
        "clasificacion_confianza": _blank(rec.get("clasificacion_confianza")),
        "clasificacion_fuentes": _jsonish(
            rec.get("clasificacion_fuentes"),
            default={"source": fuente, "slug": slug},
        ),
        "bocm_primary_id": _blank(rec.get("bocm_primary_id")),
        "bocm_source_id": _blank(rec.get("bocm_source_id")) or ("sigma" if fuente == "sigma" else "ayuntamiento-portal"),
        "bocm_pub_date": _blank(rec.get("bocm_pub_date")) or pub_date,
        "bocm_art_num": _blank(rec.get("bocm_art_num")),
        "bocm_title": _blank(rec.get("bocm_title")) or _blank(titulo),
        "bocm_pdf_url": _blank(rec.get("bocm_pdf_url")) or (docs[0] if docs else None),
        "bocm_municipio": _blank(rec.get("bocm_municipio")) or nombre,
        "bocm_tipo_instrumento": _blank(rec.get("bocm_tipo_instrumento")) or _blank(tipo),
        "bocm_resumen": _blank(rec.get("bocm_resumen")) or _blank(titulo[:800] if titulo else ""),
        "bocm_es_relevante": rec.get("bocm_es_relevante") if rec.get("bocm_es_relevante") is not None else True,
        "bocm_sigma_match_type": _blank(rec.get("bocm_sigma_match_type")),
        "bocm_sigma_match_score": _float(rec.get("bocm_sigma_match_score")),
        "municipio": nombre,
        "municipio_slug": slug,
        "fuente": fuente,
        "id_origen": _blank(rec.get("id_origen")) or pid,
        "lat": lat,
        "lng": lng,
        "coord_source": _blank(rec.get("coord_source"))
        or ("sigma_ambito" if fuente == "sigma" and lat is not None else None)
        or ("ayuntamiento-portal" if lat is not None else None),
        "sector_key": _blank(rec.get("sector_key")) or slug,
        "num_viviendas_max": _int(rec.get("num_viviendas_max")),
        "sup_total_m2": _float(rec.get("sup_total_m2")),
        "sup_edificable_m2": _float(rec.get("sup_edificable_m2")),
        "inserted_at": now,
        "updated_at": now,
        "_docs": docs,
        "_titulo": titulo,
        "_hijas": {
            "tramitacion": tramitacion,
            "nti_docs": nti_muestra if isinstance(rec.get("nti_documentos_muestra"), list) else [],
            "bocm_publicaciones": rec.get("bocm_publicaciones")
            if isinstance(rec.get("bocm_publicaciones"), list)
            else [],
            "documentacion_urls": doc_urls if isinstance(doc_urls, list) else [],
        },
    }


def save_proyectos(rows: list[dict[str, Any]], *, conn=None) -> int:
    ready = [r for r in rows if r and r.get("id")]
    if not ready:
        return 0
    cols = [c for c in _PROYECTO_UPSERT_COLS]
    tuples = [tuple(r.get(c) for c in cols) for r in ready]
    sql = f"""
        INSERT INTO {SCHEMA}.proyecto ({", ".join(cols)}) VALUES %s
        ON CONFLICT (id) DO UPDATE SET
          denominacion = EXCLUDED.denominacion,
          enlace = EXCLUDED.enlace,
          visor_url = COALESCE(EXCLUDED.visor_url, {SCHEMA}.proyecto.visor_url),
          visor_cabecera = COALESCE(EXCLUDED.visor_cabecera, {SCHEMA}.proyecto.visor_cabecera),
          visor_ficha = COALESCE(EXCLUDED.visor_ficha, {SCHEMA}.proyecto.visor_ficha),
          visor_fetched_at = COALESCE(EXCLUDED.visor_fetched_at, {SCHEMA}.proyecto.visor_fetched_at),
          visor_raw_json = CASE
            WHEN EXCLUDED.visor_raw_json IS NOT NULL AND EXCLUDED.visor_raw_json <> '{{}}'::jsonb
            THEN EXCLUDED.visor_raw_json
            ELSE COALESCE({SCHEMA}.proyecto.visor_raw_json, EXCLUDED.visor_raw_json)
          END,
          tramitacion = CASE
            WHEN EXCLUDED.tramitacion IS NOT NULL AND EXCLUDED.tramitacion <> '[]'::jsonb
            THEN EXCLUDED.tramitacion
            ELSE COALESCE({SCHEMA}.proyecto.tramitacion, EXCLUDED.tramitacion)
          END,
          resumen_contenido = EXCLUDED.resumen_contenido,
          tipo_legal = COALESCE(EXCLUDED.tipo_legal, {SCHEMA}.proyecto.tipo_legal),
          escala = COALESCE(EXCLUDED.escala, {SCHEMA}.proyecto.escala),
          contenido_principal = EXCLUDED.contenido_principal,
          fase = COALESCE(EXCLUDED.fase, {SCHEMA}.proyecto.fase),
          fase_normalizada = COALESCE(EXCLUDED.fase_normalizada, {SCHEMA}.proyecto.fase_normalizada),
          categoria_proyecto = COALESCE(EXCLUDED.categoria_proyecto, {SCHEMA}.proyecto.categoria_proyecto),
          tipo_obra = COALESCE(EXCLUDED.tipo_obra, {SCHEMA}.proyecto.tipo_obra),
          clasificacion_confianza = COALESCE(EXCLUDED.clasificacion_confianza, {SCHEMA}.proyecto.clasificacion_confianza),
          documentacion_urls = CASE
            WHEN EXCLUDED.documentacion_urls IS NOT NULL AND EXCLUDED.documentacion_urls <> '[]'::jsonb
            THEN EXCLUDED.documentacion_urls
            ELSE COALESCE({SCHEMA}.proyecto.documentacion_urls, EXCLUDED.documentacion_urls)
          END,
          nti_listado_url = COALESCE(EXCLUDED.nti_listado_url, {SCHEMA}.proyecto.nti_listado_url),
          nti_documentos_total = COALESCE(EXCLUDED.nti_documentos_total, {SCHEMA}.proyecto.nti_documentos_total),
          nti_documentos_muestra = CASE
            WHEN EXCLUDED.nti_documentos_muestra IS NOT NULL AND EXCLUDED.nti_documentos_muestra <> '[]'::jsonb
            THEN EXCLUDED.nti_documentos_muestra
            ELSE COALESCE({SCHEMA}.proyecto.nti_documentos_muestra, EXCLUDED.nti_documentos_muestra)
          END,
          expediente_grupo = COALESCE(EXCLUDED.expediente_grupo, {SCHEMA}.proyecto.expediente_grupo),
          exp_numero_original = COALESCE(EXCLUDED.exp_numero_original, {SCHEMA}.proyecto.exp_numero_original),
          sigma_layer_kind = COALESCE(EXCLUDED.sigma_layer_kind, {SCHEMA}.proyecto.sigma_layer_kind),
          infopublica_inicio = COALESCE(EXCLUDED.infopublica_inicio, {SCHEMA}.proyecto.infopublica_inicio),
          infopublica_fin = COALESCE(EXCLUDED.infopublica_fin, {SCHEMA}.proyecto.infopublica_fin),
          figura_codigo = COALESCE(EXCLUDED.figura_codigo, {SCHEMA}.proyecto.figura_codigo),
          tipo_figura = COALESCE(EXCLUDED.tipo_figura, {SCHEMA}.proyecto.tipo_figura),
          organo_tramitador = COALESCE(EXCLUDED.organo_tramitador, {SCHEMA}.proyecto.organo_tramitador),
          object_id = COALESCE(EXCLUDED.object_id, {SCHEMA}.proyecto.object_id),
          sigma_synced_at = COALESCE(EXCLUDED.sigma_synced_at, {SCHEMA}.proyecto.sigma_synced_at),
          area_approx_m2 = COALESCE(EXCLUDED.area_approx_m2, {SCHEMA}.proyecto.area_approx_m2),
          sin_datos_visor = EXCLUDED.sin_datos_visor OR {SCHEMA}.proyecto.sin_datos_visor,
          municipio = EXCLUDED.municipio,
          municipio_slug = COALESCE(EXCLUDED.municipio_slug, {SCHEMA}.proyecto.municipio_slug),
          fuente = COALESCE(EXCLUDED.fuente, {SCHEMA}.proyecto.fuente),
          id_origen = COALESCE(EXCLUDED.id_origen, {SCHEMA}.proyecto.id_origen),
          bocm_primary_id = COALESCE(EXCLUDED.bocm_primary_id, {SCHEMA}.proyecto.bocm_primary_id),
          bocm_municipio = EXCLUDED.bocm_municipio,
          bocm_pub_date = COALESCE(EXCLUDED.bocm_pub_date, {SCHEMA}.proyecto.bocm_pub_date),
          bocm_art_num = COALESCE(EXCLUDED.bocm_art_num, {SCHEMA}.proyecto.bocm_art_num),
          bocm_title = EXCLUDED.bocm_title,
          bocm_pdf_url = COALESCE(EXCLUDED.bocm_pdf_url, {SCHEMA}.proyecto.bocm_pdf_url),
          bocm_tipo_instrumento = EXCLUDED.bocm_tipo_instrumento,
          bocm_resumen = EXCLUDED.bocm_resumen,
          bocm_source_id = EXCLUDED.bocm_source_id,
          bocm_es_relevante = EXCLUDED.bocm_es_relevante,
          bocm_sigma_match_type = COALESCE(EXCLUDED.bocm_sigma_match_type, {SCHEMA}.proyecto.bocm_sigma_match_type),
          bocm_sigma_match_score = COALESCE(EXCLUDED.bocm_sigma_match_score, {SCHEMA}.proyecto.bocm_sigma_match_score),
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
          num_viviendas_max = COALESCE(EXCLUDED.num_viviendas_max, {SCHEMA}.proyecto.num_viviendas_max),
          sup_total_m2 = COALESCE(EXCLUDED.sup_total_m2, {SCHEMA}.proyecto.sup_total_m2),
          sup_edificable_m2 = COALESCE(EXCLUDED.sup_edificable_m2, {SCHEMA}.proyecto.sup_edificable_m2),
          raw_features_json = EXCLUDED.raw_features_json,
          clasificacion_fuentes = EXCLUDED.clasificacion_fuentes,
          catalog_source = EXCLUDED.catalog_source,
          updated_at = EXCLUDED.updated_at
    """
    with _owned_conn(conn) as c, c.cursor() as cur:
        execute_values(cur, sql, tuples, page_size=100)
    return len(tuples)


# ---------------------------------------------------------------------------
# Licencia
# ---------------------------------------------------------------------------

def save_licencias(rows: list[dict[str, Any]], *, conn=None) -> int:
    ready = [r for r in rows if r and (r.get("id") or r.get("licencia_key") or r.get("id_origen"))]
    if not ready:
        return 0
    keys = [str(r.get("id") or r.get("licencia_key") or r.get("id_origen")) for r in ready]
    now = _now()
    with _owned_conn(conn) as c, c.cursor() as cur:
        id_map = _next_licencia_ids(cur, keys)
        tuples = []
        for rec, key in zip(ready, keys):
            lat, lng = _latlng(rec)
            fecha = _blank(rec.get("fecha_concesion") or rec.get("fecha"))
            anio = int(fecha[:4]) if fecha and len(fecha) >= 4 and fecha[:4].isdigit() else None
            slug = _blank(rec.get("municipio_slug"))
            tuples.append(
                (
                    id_map[key],
                    key,
                    rec.get("inmueble_id"),
                    anio if anio is not None else _int(rec.get("anio_dataset")),
                    _blank(rec.get("fecha_alta")),
                    fecha,
                    _blank(rec.get("procedimiento")),
                    _blank(rec.get("tipo") or rec.get("tipo_expediente")),
                    _blank(rec.get("uso")),
                    _blank(rec.get("interesado")),
                    _blank(rec.get("titulo") or rec.get("objeto")),
                    _blank(rec.get("unidad") or rec.get("distrito")),
                    lat,
                    lng,
                    Json({**rec, "source": rec.get("source") or rec.get("fuente") or "ayuntamiento"}),
                    rec.get("proyecto_id"),
                    slug,
                    rec.get("fuente") or rec.get("source") or "ayuntamiento",
                    key,
                    now,
                    now,
                )
            )
        sql = f"""
            INSERT INTO {SCHEMA}.licencia (
              id, licencia_key, inmueble_id, anio_dataset, fecha_alta, fecha_concesion,
              procedimiento, tipo_expediente, uso, interesado, objeto, unidad,
              lat, lng, raw_json, proyecto_id, municipio_slug, fuente, id_origen,
              inserted_at, updated_at
            ) VALUES %s
            ON CONFLICT (licencia_key) DO UPDATE SET
              anio_dataset = COALESCE(EXCLUDED.anio_dataset, {SCHEMA}.licencia.anio_dataset),
              fecha_concesion = COALESCE(EXCLUDED.fecha_concesion, {SCHEMA}.licencia.fecha_concesion),
              tipo_expediente = COALESCE(EXCLUDED.tipo_expediente, {SCHEMA}.licencia.tipo_expediente),
              objeto = COALESCE(EXCLUDED.objeto, {SCHEMA}.licencia.objeto),
              unidad = COALESCE(EXCLUDED.unidad, {SCHEMA}.licencia.unidad),
              lat = COALESCE(EXCLUDED.lat, {SCHEMA}.licencia.lat),
              lng = COALESCE(EXCLUDED.lng, {SCHEMA}.licencia.lng),
              raw_json = EXCLUDED.raw_json,
              inmueble_id = COALESCE(EXCLUDED.inmueble_id, {SCHEMA}.licencia.inmueble_id),
              municipio_slug = COALESCE(EXCLUDED.municipio_slug, {SCHEMA}.licencia.municipio_slug),
              fuente = COALESCE(EXCLUDED.fuente, {SCHEMA}.licencia.fuente),
              id_origen = COALESCE(EXCLUDED.id_origen, {SCHEMA}.licencia.id_origen),
              updated_at = EXCLUDED.updated_at
        """
        execute_values(cur, sql, tuples, page_size=200)
    return len(tuples)


def save_inmuebles(rows: list[dict[str, Any]], *, conn=None) -> dict[str, int]:
    """Upsert inmuebles por ndp_edificio. Devuelve ndp → id."""
    ready: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rec in rows:
        ndp = _blank(rec.get("ndp_edificio"))
        if not ndp or ndp in seen:
            continue
        seen.add(ndp)
        ready.append(rec)
    if not ready:
        return {}
    now = _now()
    with _owned_conn(conn) as c, c.cursor() as cur:
        tuples = []
        for rec in ready:
            lat, lng = _latlng(rec)
            tuples.append(
                (
                    str(rec["ndp_edificio"]),
                    _blank(rec.get("direccion")),
                    _blank(rec.get("distrito")),
                    _blank(rec.get("barrio")),
                    lat,
                    lng,
                    _blank(rec.get("coord_source")),
                    now,
                    now,
                )
            )
        sql = f"""
            INSERT INTO {SCHEMA}.inmueble (
              ndp_edificio, direccion, distrito, barrio, lat, lng, coord_source,
              inserted_at, updated_at
            ) VALUES %s
            ON CONFLICT (ndp_edificio) DO UPDATE SET
              direccion = COALESCE(EXCLUDED.direccion, {SCHEMA}.inmueble.direccion),
              distrito = COALESCE(EXCLUDED.distrito, {SCHEMA}.inmueble.distrito),
              barrio = COALESCE(EXCLUDED.barrio, {SCHEMA}.inmueble.barrio),
              lat = COALESCE(EXCLUDED.lat, {SCHEMA}.inmueble.lat),
              lng = COALESCE(EXCLUDED.lng, {SCHEMA}.inmueble.lng),
              coord_source = COALESCE(EXCLUDED.coord_source, {SCHEMA}.inmueble.coord_source),
              updated_at = EXCLUDED.updated_at
        """
        execute_values(cur, sql, tuples, page_size=200)
        ndps = [str(r["ndp_edificio"]) for r in ready]
        cur.execute(
            f"SELECT ndp_edificio, id FROM {SCHEMA}.inmueble WHERE ndp_edificio = ANY(%s)",
            (ndps,),
        )
        return {str(r[0]): int(r[1]) for r in cur.fetchall()}


def save_proyecto_hijas(items: list[dict[str, Any]], *, conn=None) -> dict[str, int]:
    """Trámites visor, docs NTI y vínculos BOCM (particularidad Madrid)."""
    tramite_rows: list[tuple] = []
    doc_rows: list[tuple] = []
    bocm_rows: list[tuple] = []
    now = _now()
    for item in items:
        pid = _blank(item.get("id"))
        hijas = item.get("_hijas") or {}
        if not pid:
            continue
        tram = hijas.get("tramitacion") or []
        if isinstance(tram, list):
            for i, t in enumerate(tram):
                if not isinstance(t, dict):
                    continue
                tramite_rows.append(
                    (
                        pid,
                        i,
                        _blank(t.get("fecha")),
                        _blank(t.get("tramite") or t.get("texto")),
                        _blank(t.get("organo")),
                        _blank(t.get("visorUrl") or t.get("visor_url")),
                        now,
                    )
                )
        nti_docs = hijas.get("nti_docs") or []
        if isinstance(nti_docs, list):
            for i, d in enumerate(nti_docs[:40]):
                if not isinstance(d, dict):
                    continue
                url = _blank(d.get("url"))
                if not url:
                    continue
                doc_rows.append(
                    (
                        pid,
                        i,
                        url,
                        _blank(d.get("titulo")),
                        _blank(d.get("tooltip")),
                        _blank(d.get("rutaCarpetas")),
                        _blank(d.get("tipodocNti") or d.get("tipodoc_nti")),
                        _blank(d.get("fechaDocumento") or d.get("fecha_documento")),
                        "nti",
                    )
                )
        for i, url in enumerate(hijas.get("documentacion_urls") or []):
            if not url:
                continue
            doc_rows.append((pid, 10000 + i, str(url), None, None, None, None, None, "visor"))
        for pub in hijas.get("bocm_publicaciones") or []:
            if not isinstance(pub, dict) or not pub.get("bocm_id"):
                continue
            bocm_rows.append(
                (
                    pid,
                    str(pub["bocm_id"]),
                    bool(pub.get("es_principal")),
                    _blank(pub.get("bocm_source_id")) or "bocm",
                    _blank(pub.get("pub_date") or pub.get("bocm_date")),
                    _blank(pub.get("art_num")),
                    _blank(pub.get("title")),
                    pub.get("es_relevante"),
                    _blank(pub.get("tipo_instrumento")),
                    _blank(pub.get("nombre_sector")),
                    _blank(pub.get("procedimiento_expediente")),
                    _blank(pub.get("resumen")),
                    _blank(pub.get("match_type")),
                    _float(pub.get("match_score")),
                    now,
                )
            )
    stats = {"proyecto_tramite": 0, "proyecto_documento": 0, "proyecto_bocm_publicacion": 0}
    if not tramite_rows and not doc_rows and not bocm_rows:
        return stats
    pids = list({r[0] for r in tramite_rows + doc_rows + bocm_rows})
    with _owned_conn(conn) as c, c.cursor() as cur:
        cur.execute(
            f"DELETE FROM {SCHEMA}.proyecto_tramite WHERE proyecto_id = ANY(%s)",
            (pids,),
        )
        cur.execute(
            f"DELETE FROM {SCHEMA}.proyecto_documento WHERE proyecto_id = ANY(%s)",
            (pids,),
        )
        if tramite_rows:
            execute_values(
                cur,
                f"""
                INSERT INTO {SCHEMA}.proyecto_tramite (
                  proyecto_id, orden, fecha, tramite, organo, visor_url, fetched_at
                ) VALUES %s
                """,
                tramite_rows,
                page_size=500,
            )
            stats["proyecto_tramite"] = len(tramite_rows)
        if doc_rows:
            execute_values(
                cur,
                f"""
                INSERT INTO {SCHEMA}.proyecto_documento (
                  proyecto_id, orden, url, titulo, tooltip, ruta_carpetas,
                  tipodoc_nti, fecha_documento, fuente
                ) VALUES %s
                ON CONFLICT (proyecto_id, url) DO UPDATE SET
                  titulo = COALESCE(EXCLUDED.titulo, {SCHEMA}.proyecto_documento.titulo),
                  fuente = EXCLUDED.fuente
                """,
                doc_rows,
                page_size=500,
            )
            stats["proyecto_documento"] = len(doc_rows)
        if bocm_rows:
            execute_values(
                cur,
                f"""
                INSERT INTO {SCHEMA}.proyecto_bocm_publicacion (
                  proyecto_id, bocm_id, es_principal, bocm_source_id, pub_date,
                  art_num, title, es_relevante, tipo_instrumento, nombre_sector,
                  procedimiento_expediente, resumen, match_type, match_score, inserted_at
                ) VALUES %s
                ON CONFLICT (bocm_id) DO UPDATE SET
                  proyecto_id = EXCLUDED.proyecto_id,
                  es_principal = EXCLUDED.es_principal,
                  pub_date = COALESCE(EXCLUDED.pub_date, {SCHEMA}.proyecto_bocm_publicacion.pub_date),
                  match_type = COALESCE(EXCLUDED.match_type, {SCHEMA}.proyecto_bocm_publicacion.match_type)
                """,
                bocm_rows,
                page_size=500,
            )
            stats["proyecto_bocm_publicacion"] = len(bocm_rows)
    return stats


# ---------------------------------------------------------------------------
# Publicación (boletín)
# ---------------------------------------------------------------------------

def publicacion_id(*, boletin: str, fecha: str, art_num: str, fingerprint: str | None) -> str:
    fp = (fingerprint or "na").strip() or "na"
    return f"{boletin}:{fecha}:{art_num}:{fp}"[:200]


def publicacion_from_boletin_row(row: dict[str, Any], *, boletin: str) -> dict[str, Any]:
    fecha = str(row.get("bocm_date") or row.get("fecha") or "")[:10]
    art = str(row.get("art_num") or "")
    fp = _blank(row.get("proyecto_fingerprint"))
    return {
        "id": publicacion_id(boletin=boletin, fecha=fecha, art_num=art, fingerprint=fp),
        "boletin": boletin,
        "fecha": fecha or None,
        "art_num": art or None,
        "titulo": str(row.get("title") or row.get("titulo") or "")[:2000],
        "pdf_url": _blank(row.get("pdf_url")),
        "pdf_path": _blank(row.get("pdf_path")),
        "municipio_nombre": _blank(row.get("municipio")),
        "resumen": _blank(row.get("resumen")),
        "num_viviendas_max": _int(row.get("num_viviendas_max")),
        "fingerprint": fp,
        "proyecto_id": _blank(row.get("proyecto_id")),
        "es_relevante": row.get("es_relevante"),
        "raw": {k: v for k, v in row.items() if k not in {"id"}},
    }


def save_publicaciones(rows: list[dict[str, Any]], *, conn=None) -> int:
    ready = [r for r in rows if r and r.get("id")]
    if not ready:
        return 0
    now = _now()
    tuples = []
    for r in ready:
        es_rel = r.get("es_relevante")
        if isinstance(es_rel, str):
            es_rel = es_rel.strip().lower() in {"1", "true", "yes", "si", "sí"}
        tuples.append(
            (
                r["id"],
                str(r.get("boletin") or "desconocido"),
                r.get("fecha") or None,
                _blank(r.get("art_num")),
                str(r.get("titulo") or ""),
                _blank(r.get("pdf_url")),
                _blank(r.get("pdf_path")),
                _blank(r.get("municipio_slug")),
                _blank(r.get("municipio_nombre")),
                _blank(r.get("resumen")),
                _int(r.get("num_viviendas_max")),
                _blank(r.get("fingerprint")),
                _blank(r.get("proyecto_id")),
                es_rel if isinstance(es_rel, bool) else None,
                Json(r.get("raw") if isinstance(r.get("raw"), dict) else r),
                now,
                now,
            )
        )
    sql = f"""
        INSERT INTO {SCHEMA}.publicacion (
          id, boletin, fecha, art_num, titulo, pdf_url, pdf_path,
          municipio_slug, municipio_nombre, resumen, num_viviendas_max,
          fingerprint, proyecto_id, es_relevante, raw, inserted_at, updated_at
        ) VALUES %s
        ON CONFLICT (id) DO UPDATE SET
          titulo = EXCLUDED.titulo,
          pdf_url = COALESCE(EXCLUDED.pdf_url, {SCHEMA}.publicacion.pdf_url),
          municipio_slug = COALESCE(EXCLUDED.municipio_slug, {SCHEMA}.publicacion.municipio_slug),
          municipio_nombre = COALESCE(EXCLUDED.municipio_nombre, {SCHEMA}.publicacion.municipio_nombre),
          resumen = COALESCE(EXCLUDED.resumen, {SCHEMA}.publicacion.resumen),
          num_viviendas_max = COALESCE(EXCLUDED.num_viviendas_max, {SCHEMA}.publicacion.num_viviendas_max),
          fingerprint = COALESCE(EXCLUDED.fingerprint, {SCHEMA}.publicacion.fingerprint),
          proyecto_id = COALESCE(EXCLUDED.proyecto_id, {SCHEMA}.publicacion.proyecto_id),
          es_relevante = COALESCE(EXCLUDED.es_relevante, {SCHEMA}.publicacion.es_relevante),
          raw = EXCLUDED.raw,
          updated_at = EXCLUDED.updated_at
    """
    with _owned_conn(conn) as c, c.cursor() as cur:
        execute_values(cur, sql, tuples, page_size=200)
    return len(tuples)


# ---------------------------------------------------------------------------
# Documento
# ---------------------------------------------------------------------------

def save_documentos(rows: list[dict[str, Any]], *, conn=None) -> int:
    ready = [r for r in rows if r and r.get("url")]
    if not ready:
        return 0
    now = _now()
    seen: set[str] = set()
    tuples = []
    for r in ready:
        url = str(r["url"]).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        tuples.append(
            (
                _blank(r.get("proyecto_id")),
                _blank(r.get("publicacion_id")),
                url,
                _blank(r.get("titulo")),
                str(r.get("fuente") or "portal"),
                Json(r.get("extraido") if isinstance(r.get("extraido"), dict) else {}),
                now,
                now,
            )
        )
    if not tuples:
        return 0
    sql = f"""
        INSERT INTO {SCHEMA}.documento (
          proyecto_id, publicacion_id, url, titulo, fuente, extraido,
          inserted_at, updated_at
        ) VALUES %s
        ON CONFLICT (url) DO UPDATE SET
          proyecto_id = COALESCE(EXCLUDED.proyecto_id, {SCHEMA}.documento.proyecto_id),
          publicacion_id = COALESCE(EXCLUDED.publicacion_id, {SCHEMA}.documento.publicacion_id),
          titulo = COALESCE(EXCLUDED.titulo, {SCHEMA}.documento.titulo),
          fuente = EXCLUDED.fuente,
          extraido = EXCLUDED.extraido,
          updated_at = EXCLUDED.updated_at
    """
    with _owned_conn(conn) as c, c.cursor() as cur:
        execute_values(cur, sql, tuples, page_size=200)
    return len(tuples)


# ---------------------------------------------------------------------------
# ingest_run
# ---------------------------------------------------------------------------

def start_ingest_run(scraper: str, municipio_slug: str | None = None, *, conn=None) -> int:
    with _owned_conn(conn) as c, c.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {SCHEMA}.ingest_run (scraper, municipio_slug, status)
            VALUES (%s, %s, 'running')
            RETURNING id
            """,
            (scraper, _blank(municipio_slug)),
        )
        return int(cur.fetchone()[0])


def finish_ingest_run(
    run_id: int,
    *,
    status: str = "ok",
    rows_upserted: dict[str, Any] | None = None,
    error: str | None = None,
    conn=None,
) -> None:
    with _owned_conn(conn) as c, c.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {SCHEMA}.ingest_run
            SET finished_at = now(),
                status = %s,
                rows_upserted = %s,
                error = %s
            WHERE id = %s
            """,
            (status, Json(rows_upserted or {}), _blank(error), run_id),
        )


class IngestSession:
    """Una ejecución de scraper: abre conexión, registra ingest_run y hace upserts."""

    def __init__(self, scraper: str, municipio_slug: str | None = None):
        self.scraper = scraper
        self.municipio_slug = municipio_slug
        self.conn = None
        self.run_id: int | None = None
        self.counts: dict[str, int] = {}

    def __enter__(self) -> "IngestSession":
        self.conn = connect()
        self.run_id = start_ingest_run(
            self.scraper, self.municipio_slug, conn=self.conn
        )
        self.conn.commit()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self.run_id is not None:
                finish_ingest_run(
                    self.run_id,
                    status="error" if exc else "ok",
                    rows_upserted=self.counts,
                    error=str(exc) if exc else None,
                    conn=self.conn,
                )
            if self.conn is not None:
                self.conn.commit()
        finally:
            if self.conn is not None:
                self.conn.close()
                self.conn = None

    def _bump(self, key: str, n: int) -> int:
        self.counts[key] = self.counts.get(key, 0) + n
        return n

    def save_municipio(self, row: dict[str, Any]) -> str:
        return save_municipio(row, conn=self.conn)

    def save_municipio_from_manifest(self, manifest: Any) -> str:
        return save_municipio_from_manifest(manifest, conn=self.conn)

    def save_proyectos(self, rows: list[dict[str, Any]]) -> int:
        return self._bump("proyecto", save_proyectos(rows, conn=self.conn))

    def save_licencias(self, rows: list[dict[str, Any]]) -> int:
        return self._bump("licencia", save_licencias(rows, conn=self.conn))

    def save_publicaciones(self, rows: list[dict[str, Any]]) -> int:
        return self._bump("publicacion", save_publicaciones(rows, conn=self.conn))

    def save_documentos(self, rows: list[dict[str, Any]]) -> int:
        return self._bump("documento", save_documentos(rows, conn=self.conn))

    def save_inmuebles(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        ids = save_inmuebles(rows, conn=self.conn)
        self._bump("inmueble", len(ids))
        return ids

    def save_proyecto_hijas(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        stats = save_proyecto_hijas(rows, conn=self.conn)
        for key, n in stats.items():
            self._bump(key, n)
        return stats

    def commit(self) -> None:
        if self.conn is not None:
            self.conn.commit()


def optional_ingest_session(scraper: str, municipio_slug: str | None = None):
    """IngestSession si hay DB configurada; si no, context manager que devuelve None."""
    from contextlib import nullcontext

    if not available():
        return nullcontext(None)
    if os.getenv("SKIP_SUPABASE_INGEST", "").strip().lower() in ("1", "true", "yes"):
        return nullcontext(None)
    return IngestSession(scraper, municipio_slug)


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


def persist_boletin_row(session: IngestSession | None, row: dict[str, Any], *, boletin: str) -> None:
    """Guarda una fila de parseo de boletín. No lanza: el CSV es la fuente de verdad local."""
    if session is None:
        return
    try:
        pub = publicacion_from_boletin_row(row, boletin=boletin)
        session.save_publicaciones([pub])
        url = pub.get("pdf_url")
        if url:
            session.save_documentos(
                [
                    {
                        "publicacion_id": pub["id"],
                        "url": url,
                        "titulo": pub.get("titulo"),
                        "fuente": "boletin",
                    }
                ]
            )
        session.commit()
    except Exception as exc:
        print(f"  aviso supabase: {exc}", flush=True)


def sync_municipio_output(slug: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Lee output/municipios/<slug>/*.jsonl y hace upsert. Lo usa el post-merge de cada PR."""
    from municipio.manifest import load_manifest

    manifest = load_manifest(slug)
    out_dir = manifest.output_dir
    proyectos_raw = _read_jsonl(out_dir / "proyectos.jsonl")
    licencias_raw = _read_jsonl(out_dir / "licencias.jsonl")
    stats: dict[str, Any] = {
        "slug": slug,
        "nombre": manifest.nombre,
        "proyectos": len(proyectos_raw),
        "licencias": len(licencias_raw),
        "dry_run": dry_run,
    }
    if not proyectos_raw and not licencias_raw:
        stats["status"] = "skipped"
        stats["reason"] = "sin datos en output/municipios"
        return stats

    proy_rows = []
    hijas_rows = []
    doc_rows = []
    for rec in proyectos_raw:
        mapped = portal_proyecto_row(rec, slug=manifest.slug, nombre=manifest.nombre)
        if not mapped:
            continue
        docs = mapped.pop("_docs", [])
        mapped.pop("_titulo", None)
        hijas = mapped.pop("_hijas", None)
        if hijas:
            hijas_rows.append({"id": mapped["id"], "_hijas": hijas})
        proy_rows.append(mapped)
        doc_fuente = "nti" if mapped.get("fuente") == "sigma" else "portal"
        for url in docs:
            doc_rows.append(
                {
                    "proyecto_id": mapped["id"],
                    "url": url,
                    "titulo": mapped.get("denominacion"),
                    "fuente": doc_fuente,
                }
            )
        if rec.get("url") and rec.get("url") not in docs:
            doc_rows.append(
                {
                    "proyecto_id": mapped["id"],
                    "url": rec["url"],
                    "titulo": mapped.get("denominacion"),
                    "fuente": doc_fuente,
                }
            )

    lic_rows = []
    for rec in licencias_raw:
        if not rec.get("id"):
            continue
        row = dict(rec)
        row["municipio_slug"] = manifest.slug
        row["fuente"] = rec.get("fuente") or rec.get("source") or "ayuntamiento"
        lic_rows.append(row)
        if rec.get("pdf_url"):
            doc_rows.append(
                {
                    "url": rec["pdf_url"],
                    "titulo": rec.get("titulo"),
                    "fuente": "portal",
                }
            )

    stats["proyectos_mapped"] = len(proy_rows)
    stats["licencias_mapped"] = len(lic_rows)
    stats["documentos"] = len(doc_rows)
    stats["hijas"] = len(hijas_rows)
    if dry_run:
        stats["status"] = "dry_run"
        return stats
    if not available():
        stats["status"] = "skipped"
        stats["reason"] = "sin SUPABASE_DB_URL"
        return stats

    with IngestSession("municipio", municipio_slug=manifest.slug) as ses:
        ses.save_municipio_from_manifest(manifest)
        ses.save_proyectos(proy_rows)
        if hijas_rows:
            for key, n in save_proyecto_hijas(hijas_rows, conn=ses.conn).items():
                ses._bump(key, n)
        inm_ids = save_inmuebles(lic_rows, conn=ses.conn)
        if inm_ids:
            ses._bump("inmueble", len(inm_ids))
            for row in lic_rows:
                ndp = str(row.get("ndp_edificio") or "")
                if ndp and ndp in inm_ids:
                    row["inmueble_id"] = inm_ids[ndp]
        ses.save_licencias(lic_rows)
        ses.save_documentos(doc_rows)
        touch_last_ingest_at(manifest.slug, conn=ses.conn)
        stats["upserted"] = dict(ses.counts)
    stats["status"] = "ok"
    return stats


def ingest_madrid_after_proyectos(cur, *, docs: list, bocm_pub: list) -> dict[str, int]:
    """Marca origen SIGMA sin tocar filas de ayuntamiento; copia docs/BOCM al esquema de ingesta."""
    cur.execute(
        f"""
        INSERT INTO {SCHEMA}.municipio (slug, nombre, provincia, comunidad_autonoma)
        VALUES ('madrid', 'Madrid', 'Madrid', 'comunidad-madrid')
        ON CONFLICT (slug) DO NOTHING
        """
    )
    cur.execute(
        f"""
        UPDATE {SCHEMA}.proyecto
        SET municipio_slug = COALESCE(municipio_slug, 'madrid'),
            fuente = COALESCE(fuente, 'sigma'),
            id_origen = COALESCE(id_origen, id)
        WHERE COALESCE(catalog_source, '') <> 'ayuntamiento-portal'
          AND COALESCE(fuente, '') <> 'ayuntamiento'
        """
    )
    doc_rows = []
    for row in docs or []:
        if len(row) < 3 or not row[2]:
            continue
        doc_rows.append(
            {
                "proyecto_id": row[0],
                "url": row[2],
                "titulo": row[3] if len(row) > 3 else None,
                "fuente": (row[8] if len(row) > 8 else None) or "nti",
            }
        )
    n_docs = save_documentos(doc_rows, conn=cur.connection) if doc_rows else 0
    pubs = []
    for row in bocm_pub or []:
        if len(row) < 7:
            continue
        fecha = row[4]
        fecha_s = fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha or "")[:10]
        art = str(row[5] or "")
        boletin = str(row[3] or "bocm")
        pubs.append(
            {
                "id": publicacion_id(
                    boletin=boletin, fecha=fecha_s, art_num=art, fingerprint=str(row[1] or "")
                ),
                "boletin": boletin,
                "fecha": fecha_s or None,
                "art_num": art or None,
                "titulo": str(row[6] or ""),
                "proyecto_id": row[0],
                "es_relevante": row[7] if len(row) > 7 else None,
                "resumen": row[11] if len(row) > 11 else None,
                "raw": {"bocm_id": row[1], "match_type": row[12] if len(row) > 12 else None},
            }
        )
    n_pub = save_publicaciones(pubs, conn=cur.connection) if pubs else 0
    return {"documento": n_docs, "publicacion": n_pub}
