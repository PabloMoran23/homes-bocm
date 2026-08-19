"""Convierte volcados SIGMA/visor/licencias de Madrid → JSONL del pipeline municipio.

Lee `output/madrid_*` (lo que ya bajan `sector_geometry.madrid_*`) y escribe
`output/municipios/madrid/{proyectos,licencias}.jsonl` con el contrato común
más campos SIGMA (fase, visor, NTI, geometría).
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from municipio.geometry import geometry_centroid, record_geometry
from municipio.manifest import MunicipioManifest

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = POC_ROOT / "db"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

from geo_utils import geom_area_approx_m2, geom_bbox, ring_centroid  # noqa: E402
from migrate_sqlite import (  # noqa: E402
    expediente_grupo_from_num,
    ms_to_iso_date,
    null_if_empty,
    row_to_stub,
)
from sigma_classification import classify_sigma_project  # noqa: E402
from visor_resumen import resumen_contenido_from_visor_ficha  # noqa: E402

SIGMA_INDEX = POC_ROOT / "output/madrid_ayto_expedientes_index.json"
VISOR_JSON = POC_ROOT / "output/madrid_viso_expedientes.json"
SIGMA_METRICS = POC_ROOT / "output/madrid_sigma_expediente_metrics.json"
LINKS_JSONL = POC_ROOT / "output/madrid_ayto_bocm_links.jsonl"
BOCM_CSV = POC_ROOT / "output/history_parsed_incremental.csv"
JSONL_LIC = POC_ROOT / "output/madrid_licencias.jsonl"
GEOJSON_SOURCES = (
    POC_ROOT / "output/madrid_ayto_expedientes_ad.geojson",
    POC_ROOT / "output/madrid_ayto_expedientes_gestion.geojson",
    POC_ROOT / "output/madrid_ayto_expedientes_urbanizacion.geojson",
    POC_ROOT / "output/madrid_ayto_expedientes_ip.geojson",
)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


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


def _pdf_urls(rec: dict[str, Any], nti_docs: list[dict[str, Any]]) -> list[str]:
    urls: list[str] = []
    for url in rec.get("documentacionUrls") or []:
        if url:
            urls.append(str(url))
    for doc in nti_docs:
        url = doc.get("url")
        if url:
            urls.append(str(url))
    return list(dict.fromkeys(urls))


def _geom_payload(geom: dict[str, Any]) -> dict[str, Any] | None:
    bbox = geom_bbox(geom)
    if not bbox:
        return None
    min_lng, min_lat, max_lng, max_lat = bbox
    if geom.get("type") == "Polygon":
        clng, clat = ring_centroid(geom["coordinates"][0])
    elif geom.get("type") == "MultiPolygon" and geom.get("coordinates"):
        clng, clat = ring_centroid(geom["coordinates"][0][0])
    else:
        centroid = geometry_centroid(geom)
        if centroid:
            clat, clng = centroid
        else:
            clng, clat = (min_lng + max_lng) / 2, (min_lat + max_lat) / 2
    return {
        "geom_geojson": geom,
        "bbox_min_lng": min_lng,
        "bbox_min_lat": min_lat,
        "bbox_max_lng": max_lng,
        "bbox_max_lat": max_lat,
        "centroid_lng": clng,
        "centroid_lat": clat,
        "area_approx_m2": geom_area_approx_m2(geom),
        "lat": clat,
        "lon": clng,
        "lng": clng,
        "coord_source": "sigma_ambito",
    }


def load_geoms_by_grupo() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in GEOJSON_SOURCES:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            grupo = expediente_grupo_from_num(str(props.get("EXP_TX_NUMERO") or ""))
            geom = feat.get("geometry")
            if not grupo or not isinstance(geom, dict):
                continue
            payload = _geom_payload(geom)
            if payload:
                out[grupo] = payload
    return out


def load_metrics_by_grupo() -> dict[str, dict[str, Any]]:
    if not SIGMA_METRICS.is_file():
        return {}
    raw = json.loads(SIGMA_METRICS.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for grupo, row in (raw.get("expedientes") or {}).items():
        if isinstance(row, dict):
            out[str(grupo)] = row
    return out


def load_bocm_links() -> tuple[dict[str, tuple[str, dict]], dict[str, list[dict]]]:
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


def _catalog_row(item: dict[str, Any], synced_at: str) -> dict[str, Any] | None:
    num = str(item.get("EXP_TX_NUMERO") or "").strip()
    grupo = expediente_grupo_from_num(num)
    if not grupo:
        return None
    denom = null_if_empty(str(item.get("EXP_TX_DENOM") or ""))
    fase = null_if_empty(str(item.get("FAS_TX_DENOM") or ""))
    figura = null_if_empty(str(item.get("FIG_TX_ETIQ") or ""))
    tipo_figura = null_if_empty(str(item.get("TFIG_TX_ABREV") or ""))
    enlace = null_if_empty(str(item.get("Enlace") or ""))
    layer = item.get("sigma_layer_kind") or item.get("source")
    return {
        "id": grupo,
        "municipio": "Madrid",
        "titulo": denom or grupo,
        "fecha": ms_to_iso_date(item.get("FEX_DT_APROB")),
        "tipo": figura or tipo_figura or "planeamiento",
        "fase": fase,
        "url": enlace,
        "source": "sigma",
        "fuente": "sigma",
        "catalog_source": null_if_empty(str(item.get("source") or "")) or "sigma",
        "expediente_grupo": grupo,
        "exp_numero_original": num or grupo,
        "sigma_layer_kind": null_if_empty(str(layer or "")),
        "infopublica_inicio": ms_to_iso_date(item.get("FEX_DT_INFOPUB_INI")),
        "infopublica_fin": ms_to_iso_date(item.get("FEX_DT_INFOPUB_FIN")),
        "figura_codigo": figura,
        "tipo_figura": tipo_figura,
        "organo_tramitador": null_if_empty(str(item.get("ORG_TX_DESC") or "")),
        "object_id": int(item["EXP_ID"]) if item.get("EXP_ID") not in (None, "") else None,
        "sigma_synced_at": synced_at,
        "has_geometry": bool(item.get("has_geometry")),
        "raw": item,
    }


def _apply_visor(row: dict[str, Any], rec: dict[str, Any], *, catalog: dict[str, Any], area: float | None, viviendas: int | None) -> None:
    visor_ficha = rec.get("visorFicha") if isinstance(rec.get("visorFicha"), dict) else None
    visor_url = null_if_empty(str(rec.get("visorUrlUsada") or ""))
    layer_kind = null_if_empty(str(rec.get("sigmaLayerKind") or "")) or row.get("sigma_layer_kind")
    resumen = resumen_contenido_from_visor_ficha(visor_ficha)
    classification = classify_sigma_project(
        visor_ficha=visor_ficha,
        resumen_contenido=resumen,
        sigma_layer_kind=layer_kind or catalog.get("sigma_layer_kind") or catalog.get("source"),
        catalog=catalog,
        area_approx_m2=area,
        num_viviendas_max=viviendas,
    )
    nti_docs = _nti_docs(rec)
    nti_total = rec.get("ntiDocumentosTotal")
    nti = rec.get("ntiArbol") if isinstance(rec.get("ntiArbol"), dict) else None
    if not isinstance(nti_total, int) and nti and isinstance(nti.get("documentosTotal"), int):
        nti_total = nti.get("documentosTotal")
    pdfs = _pdf_urls(rec, nti_docs)
    tramitacion = rec.get("tramitacion") if isinstance(rec.get("tramitacion"), list) else []
    row.update(
        {
            "sin_datos_visor": bool(rec.get("sinDatosVisor")),
            "visor_url": visor_url or row.get("url"),
            "visor_cabecera": rec.get("visorCabecera") if isinstance(rec.get("visorCabecera"), dict) else None,
            "visor_ficha": visor_ficha,
            "resumen_contenido": resumen or row.get("titulo"),
            "tipo_legal": classification["tipo_legal"],
            "escala": classification["escala"],
            "contenido_principal": classification["contenido_principal"],
            "fase_normalizada": classification["fase_normalizada"],
            "categoria_proyecto": classification["categoria_proyecto"],
            "tipo_obra": classification["tipo_obra"],
            "clasificacion_confianza": classification["clasificacion_confianza"],
            "clasificacion_fuentes": classification["clasificacion_fuentes"],
            "tramitacion": tramitacion,
            "documentacion_urls": rec.get("documentacionUrls") if isinstance(rec.get("documentacionUrls"), list) else pdfs,
            "nti_listado_url": null_if_empty(str(rec.get("ntiListadoUrl") or "")),
            "nti_documentos_total": nti_total if isinstance(nti_total, int) else (len(nti_docs) or None),
            "nti_documentos_muestra": nti_docs[:80],
            "visor_fetched_at": rec.get("generatedAt"),
            "visor_raw": rec,
            "pdf_urls": pdfs,
        }
    )
    if visor_url and not row.get("url"):
        row["url"] = visor_url


def build_proyectos() -> list[dict[str, Any]]:
    if not SIGMA_INDEX.is_file():
        raise FileNotFoundError(
            f"Falta {SIGMA_INDEX.name}. Ejecuta sector_geometry.madrid_ayto_sync antes de exportar."
        )
    raw = json.loads(SIGMA_INDEX.read_text(encoding="utf-8"))
    synced_at = raw.get("generatedAt") or datetime.now(UTC).isoformat()
    geoms = load_geoms_by_grupo()
    metrics = load_metrics_by_grupo()
    visor_bundle = json.loads(VISOR_JSON.read_text(encoding="utf-8")) if VISOR_JSON.is_file() else {}
    visor_by_grupo = visor_bundle.get("byGrupoExpediente") or {}
    catalog_by_grupo: dict[str, dict[str, Any]] = {}
    rows: dict[str, dict[str, Any]] = {}

    for item in raw.get("expedientes") or []:
        rec = _catalog_row(item, synced_at)
        if not rec:
            continue
        grupo = rec["id"]
        catalog_by_grupo[grupo] = item
        geom = geoms.get(grupo)
        if geom:
            rec.update(geom)
            rec["has_geometry"] = True
        mrow = metrics.get(grupo)
        if isinstance(mrow, dict):
            m = mrow.get("metrics") if isinstance(mrow.get("metrics"), dict) else mrow
            rec["num_viviendas_max"] = m.get("num_viviendas_max")
            rec["sup_edificable_m2"] = m.get("sup_edificable_m2")
            rec["sup_total_m2"] = m.get("sup_total_m2")
            rec["metrics"] = mrow
        rows[grupo] = rec

    for grupo, rec_raw in visor_by_grupo.items():
        if not grupo or not isinstance(rec_raw, dict):
            continue
        if grupo not in rows:
            rows[grupo] = {
                "id": grupo,
                "municipio": "Madrid",
                "titulo": grupo,
                "tipo": "planeamiento",
                "source": "sigma",
                "fuente": "sigma",
                "catalog_source": "sigma",
                "expediente_grupo": grupo,
                "exp_numero_original": grupo,
            }
        area = (geoms.get(grupo) or {}).get("area_approx_m2")
        viviendas = rows[grupo].get("num_viviendas_max")
        try:
            viviendas_i = int(viviendas) if viviendas not in (None, "") else None
        except (TypeError, ValueError):
            viviendas_i = None
        _apply_visor(
            rows[grupo],
            rec_raw,
            catalog=catalog_by_grupo.get(grupo) or {},
            area=area,
            viviendas=viviendas_i,
        )
        if grupo in geoms and not record_geometry(rows[grupo]):
            rows[grupo].update(geoms[grupo])

    by_bocm, by_grupo = load_bocm_links()
    primary_bocm: dict[str, str] = {}
    for grupo, links in by_grupo.items():
        if not links:
            continue
        links_sorted = sorted(links, key=lambda r: str(r.get("bocm_date") or ""), reverse=True)
        primary_bocm[grupo] = str(links_sorted[0].get("bocm_id") or "")
        pubs = []
        for link in links_sorted:
            pubs.append(
                {
                    "bocm_id": link.get("bocm_id"),
                    "es_principal": str(link.get("bocm_id") or "") == primary_bocm[grupo],
                    "pub_date": link.get("bocm_date"),
                    "match_type": link.get("match_type"),
                    "match_score": link.get("match_score"),
                    "sigma_enlace": link.get("sigma_enlace"),
                }
            )
        if grupo in rows:
            rows[grupo]["bocm_publicaciones"] = pubs
            rows[grupo]["bocm_primary_id"] = primary_bocm[grupo]

    if BOCM_CSV.is_file():
        with BOCM_CSV.open(encoding="utf-8", newline="") as fh:
            for csv_row in csv.DictReader(fh):
                stub = row_to_stub(csv_row, default_source="bocm")
                bid = str(stub["id"])
                link = by_bocm.get(bid)
                if not link:
                    continue
                grupo, lrec = link
                rec = rows.get(grupo)
                if not rec:
                    continue
                if primary_bocm.get(grupo) != bid:
                    continue
                rec["bocm_source_id"] = stub["source_id"]
                rec["bocm_pub_date"] = stub["pub_date"] or None
                rec["bocm_art_num"] = stub["art_num"] or None
                rec["bocm_title"] = (csv_row.get("title") or "")[:2000] or rec.get("titulo")
                rec["bocm_pdf_url"] = null_if_empty(csv_row.get("pdf_url"))
                rec["bocm_es_relevante"] = stub.get("es_relevante")
                rec["bocm_municipio"] = "Madrid"
                rec["bocm_tipo_instrumento"] = null_if_empty(csv_row.get("tipo_instrumento"))
                rec["bocm_resumen"] = null_if_empty(csv_row.get("resumen"))
                rec["bocm_sigma_match_type"] = lrec.get("match_type")
                rec["bocm_sigma_match_score"] = lrec.get("match_score")
                if rec.get("bocm_pdf_url"):
                    rec.setdefault("pdf_urls", [])
                    if rec["bocm_pdf_url"] not in rec["pdf_urls"]:
                        rec["pdf_urls"].insert(0, rec["bocm_pdf_url"])

    return list(rows.values())


def build_licencias() -> list[dict[str, Any]]:
    from sync_madrid_public_to_supabase import collect_licencias

    if not JSONL_LIC.is_file():
        return []
    _inmuebles, actuaciones, _stats = collect_licencias()
    rows: list[dict[str, Any]] = []
    for key, tup in actuaciones.items():
        ndp = tup[1]
        inm = _inmuebles.get(ndp) or {}
        rows.append(
            {
                "id": key,
                "licencia_key": key,
                "ndp_edificio": ndp,
                "anio_dataset": tup[2],
                "fecha_alta": tup[3],
                "fecha_concesion": tup[4],
                "procedimiento": tup[5],
                "tipo": tup[6],
                "tipo_expediente": tup[6],
                "uso": tup[7],
                "interesado": tup[8],
                "titulo": tup[9],
                "objeto": tup[9],
                "unidad": tup[10],
                "distrito": inm.get("distrito"),
                "barrio": inm.get("barrio"),
                "direccion": inm.get("direccion"),
                "lat": tup[11] if tup[11] is not None else inm.get("lat"),
                "lon": tup[12] if tup[12] is not None else inm.get("lng"),
                "lng": tup[12] if tup[12] is not None else inm.get("lng"),
                "coord_source": inm.get("coord_source") or ("utm_jsonl" if tup[11] is not None else None),
                "source": "madrid-opendata",
                "fuente": "madrid-opendata",
            }
        )
    return rows


def export_proyectos(manifest: MunicipioManifest) -> dict[str, Any]:
    manifest.ensure_output_dir()
    proyectos = build_proyectos()
    proy_path = manifest.output_dir / "proyectos.jsonl"
    _write_jsonl(proy_path, proyectos)
    with_geom = sum(1 for r in proyectos if record_geometry(r))
    return {
        "status": "ok",
        "proyectos": len(proyectos),
        "proyectos_con_geometria": with_geom,
        "proyectos_path": str(proy_path),
    }


def export_licencias(manifest: MunicipioManifest) -> dict[str, Any]:
    manifest.ensure_output_dir()
    licencias = build_licencias()
    lic_path = manifest.output_dir / "licencias.jsonl"
    if licencias:
        _write_jsonl(lic_path, licencias)
    return {
        "status": "ok",
        "licencias": len(licencias),
        "licencias_path": str(lic_path) if licencias else None,
    }


def export_madrid(manifest: MunicipioManifest) -> dict[str, Any]:
    proy = export_proyectos(manifest)
    lic = export_licencias(manifest)
    return {**proy, **lic}
