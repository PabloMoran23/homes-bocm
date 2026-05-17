#!/usr/bin/env python3
"""
Sincroniza expedientes SIGMA (Ayto. Madrid) y cruza con BOCM (solo municipio Madrid capital).

Salidas en output/:
  - madrid_ayto_raw/                         (volcados ArcGIS por capa)
  - madrid_ayto_expedientes_ip.geojson       (información pública, con geometría)
  - madrid_ayto_expedientes_ad.geojson       (~3k tramitados planeamiento AD)
  - madrid_ayto_expedientes_gestion.geojson  (~495 tramitados gestión, SEGUIMIENTO)
  - madrid_ayto_expedientes_urbanizacion.geojson (~495 tramitados urbanización)
  - madrid_ayto_expedientes_ad.json          (atributos AD)
  - madrid_ayto_expedientes_gestion.json
  - madrid_ayto_expedientes_urbanizacion.json
  - madrid_ayto_expedientes_full.jsonl       (catálogo plano, una línea/expediente)
  - madrid_ayto_expedientes_index.json       (índice unificado IP + AD completo)
  - madrid_ayto_bocm_match.json              (estadísticas + muestras admin)
  - madrid_ayto_bocm_links.jsonl             (cruce BOCM, solo por nº expediente)

  Tramitación + documentos NTI (post-sync opcional): python3 -m sector_geometry.madrid_viso_fetch
  Descarga PDF/documentos NTI (prueba o masiva): python3 -m sector_geometry.madrid_viso_docs_download

Uso:
  python3 -m sector_geometry.madrid_ayto_sync              # descarga SIGMA completa + cruce
  python3 -m sector_geometry.madrid_ayto_sync --skip-fetch # reusa raw/ + recalcula índice/cruce
  python3 -m sector_geometry.madrid_ayto_sync --no-match   # solo descarga/índice, sin cruce BOCM
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .madrid_ayto_match import expedientes_from_row, match_row

POC_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = POC_ROOT / "output"
BOCM_CSV = OUTPUT_DIR / "history_parsed_incremental.csv"
RAW_DIR = OUTPUT_DIR / "madrid_ayto_raw"
GEOJSON_OUT = OUTPUT_DIR / "madrid_ayto_expedientes_ip.geojson"
AD_FULL_OUT = OUTPUT_DIR / "madrid_ayto_expedientes_ad.json"
AD_GEOJSON_OUT = OUTPUT_DIR / "madrid_ayto_expedientes_ad.geojson"
GESTION_GEOJSON_OUT = OUTPUT_DIR / "madrid_ayto_expedientes_gestion.geojson"
URBANIZACION_GEOJSON_OUT = OUTPUT_DIR / "madrid_ayto_expedientes_urbanizacion.geojson"
GESTION_JSON_OUT = OUTPUT_DIR / "madrid_ayto_expedientes_gestion.json"
URBANIZACION_JSON_OUT = OUTPUT_DIR / "madrid_ayto_expedientes_urbanizacion.json"
FULL_JSONL_OUT = OUTPUT_DIR / "madrid_ayto_expedientes_full.jsonl"
INDEX_OUT = OUTPUT_DIR / "madrid_ayto_expedientes_index.json"
MATCH_OUT = OUTPUT_DIR / "madrid_ayto_bocm_match.json"
LINKS_OUT = OUTPUT_DIR / "madrid_ayto_bocm_links.jsonl"

SIGMA_IP_BASE = (
    "https://sigma.madrid.es/hosted/rest/services/"
    "DESARROLLO_URBANO_ACTUALIZADO/EXPEDIENTES_INFORMACION_PUBLICA/MapServer"
)
SIGMA_AD_BASE = (
    "https://sigma.madrid.es/hosted/rest/services/"
    "desarrollo_urbano_actualizado/EXPEDIENTES_PLANEAMIENTO_AD/MapServer"
)
SIGMA_SEGUIMIENTO_BASE = (
    "https://sigma.madrid.es/hosted/rest/services/"
    "DESARROLLO_URBANO_ACTUALIZADO/SEGUIMIENTO_EXPEDIENTES/MapServer"
)
IP_LAYERS = [(0, "planeamiento"), (1, "gestion"), (2, "urbanizacion")]
AD_LAYER_ID = 1
# Dataset 300119 — capas tramitadas adicionales (gestión + urbanización)
SEG_TRAMITADOS_LAYERS = [
    (3, "gestion", "tramitados_gestion"),
    (2, "urbanizacion", "tramitados_urbanizacion"),
]

def _http_get_json(url: str, timeout: float = 120.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "poc-bocm-madrid-ayto-sync/0.2 (+https://datos.madrid.es)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _norm_exp(num: str) -> str:
    return re.sub(r"\s+", "", (num or "").strip())


def _exp_variants(num: str) -> list[str]:
    """Genera variantes con último tramo zero-padded (135/2025/19 → 135/2025/00019)."""
    n = _norm_exp(num)
    if not n:
        return []
    out = {n}
    parts = n.split("/")
    if len(parts) == 3 and parts[2].isdigit():
        padded = parts[2].zfill(5)
        out.add(f"{parts[0]}/{parts[1]}/{padded}")
        out.add(f"{parts[0]}/{parts[1]}/{parts[2].zfill(4)}")
        if parts[2].startswith("0"):
            out.add(f"{parts[0]}/{parts[1]}/{parts[2].lstrip('0') or '0'}")
    return list(out)


def _props_summary(p: dict[str, Any], *, source: str, geometry: bool = False) -> dict[str, Any]:
    # Capas IP urbanización usan prefijos EXP_DT_* frente a FEX_DT_* del resto.
    fex_ini = p.get("FEX_DT_INFOPUB_INI") or p.get("EXP_DT_INFOPUB_INI")
    fex_fin = p.get("FEX_DT_INFOPUB_FIN") or p.get("EXP_DT_INFOPUB_FIN")
    fex_aprob = p.get("FEX_DT_APROB") or p.get("EXP_DT_APROB_INI")

    oid = p.get("EXP_ID")
    if oid is None:
        oid = p.get("OBJECTID")

    out = {
        "source": source,
        "EXP_ID": oid,
        "EXP_TX_NUMERO": p.get("EXP_TX_NUMERO"),
        "EXP_TX_DENOM": p.get("EXP_TX_DENOM"),
        "FAS_TX_DENOM": p.get("FAS_TX_DENOM"),
        "FEX_DT_INFOPUB_INI": fex_ini,
        "FEX_DT_INFOPUB_FIN": fex_fin,
        "FEX_DT_APROB": fex_aprob,
        "FIG_TX_ETIQ": p.get("FIG_TX_ETIQ"),
        "TFIG_TX_ABREV": p.get("TFIG_TX_ABREV"),
        "ORG_TX_DESC": p.get("ORG_TX_DESC"),
        "Enlace": p.get("Enlace") or p.get("ENLACE") or p.get("enlace"),
        "sigma_layer_kind": p.get("sigma_layer_kind"),
        "has_geometry": geometry,
    }
    if not out["Enlace"] and out.get("EXP_TX_NUMERO"):
        exp = str(out["EXP_TX_NUMERO"])
        fig = out.get("FIG_TX_ETIQ")
        if source == "tramitados_gestion" and fig:
            out["Enlace"] = (
                "https://www-s.madrid.es/VSURB_WBVISOR/seguimiento/expGestion.iam"
                f"?figura={urllib.parse.quote(str(fig))}"
            )
        elif source == "tramitados_urbanizacion" and fig:
            out["Enlace"] = (
                "https://www-s.madrid.es/VSURB_WBVISOR/seguimiento/expUrbanizacion.iam"
                f"?figura={urllib.parse.quote(str(fig))}"
            )
        else:
            out["Enlace"] = (
                "https://servpub.madrid.es/VSURB_WBVISOR/seguimiento/expPlaneamiento.iam"
                f"?exp={urllib.parse.quote(exp)}"
            )
    return out


def fetch_layer_json_paginated(
    base_url: str,
    layer_id: int,
    *,
    where: str = "1=1",
    out_fields: str = "*",
    return_geometry: bool = False,
    page_size: int = 1000,
) -> list[dict[str, Any]]:
    """Descarga una capa ArcGIS MapServer completa (formato JSON features/attributes)."""
    all_features: list[dict[str, Any]] = []
    offset = 0
    while True:
        qs = urllib.parse.urlencode(
            {
                "where": where,
                "outFields": out_fields,
                "returnGeometry": "true" if return_geometry else "false",
                "f": "json",
                "resultOffset": str(offset),
                "resultRecordCount": str(page_size),
            }
        )
        url = f"{base_url}/{layer_id}/query?{qs}"
        data = _http_get_json(url, timeout=180.0)
        if not isinstance(data, dict):
            break
        feats = data.get("features") or []
        if not feats:
            break
        all_features.extend(feats)
        print(f"    capa {layer_id}: +{len(feats)} (total {len(all_features)})", flush=True)
        if data.get("exceededTransferLimit") or len(feats) >= page_size:
            offset += len(feats)
            continue
        break
    return all_features


def fetch_expedientes_ip() -> dict[str, Any]:
    all_features: list[dict[str, Any]] = []
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for layer_id, layer_kind in IP_LAYERS:
        offset = 0
        page = 2000
        layer_feats: list[dict[str, Any]] = []
        while True:
            qs = urllib.parse.urlencode(
                {
                    "where": "1=1",
                    "outFields": "*",
                    "returnGeometry": "true",
                    "f": "geojson",
                    "outSR": "4326",
                    "resultOffset": str(offset),
                    "resultRecordCount": str(page),
                }
            )
            url = f"{SIGMA_IP_BASE}/{layer_id}/query?{qs}"
            data = _http_get_json(url)
            if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
                break
            feats = data.get("features") or []
            if not feats:
                break
            for f in feats:
                if not isinstance(f, dict):
                    continue
                props = f.setdefault("properties", {})
                if isinstance(props, dict):
                    props["sigma_layer_kind"] = layer_kind
                    props["sigma_layer_id"] = layer_id
            layer_feats.extend(feats)
            if len(feats) < page:
                break
            offset += page
        raw_path = RAW_DIR / f"ip_layer_{layer_id}_{layer_kind}.geojson"
        raw_path.write_text(
            json.dumps({"type": "FeatureCollection", "features": layer_feats}, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  IP layer {layer_id} ({layer_kind}): {len(layer_feats)} → {raw_path.name}", flush=True)
        all_features.extend(layer_feats)
    return {"type": "FeatureCollection", "features": all_features}


def fetch_tramitados_ad_geojson_paginated(
    *,
    page_size: int = 400,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Descarga Expedientes Planeamiento AD (layer 1) como GeoJSON con geometrías WGS84.
    Devuelve (features_fc, registros_sin_geometria_para_catalogo).
    """
    offset = 0
    feats_out: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    page_n = 0
    while True:
        page_n += 1
        qs = urllib.parse.urlencode(
            {
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
                "resultOffset": str(offset),
                "resultRecordCount": str(page_size),
            }
        )
        url = f"{SIGMA_AD_BASE}/{AD_LAYER_ID}/query?{qs}"
        data = _http_get_json(url, timeout=300.0)
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            print(f"  aviso: AD GeoJSON inválido (offset={offset})", flush=True)
            break
        feats = data.get("features") or []
        if not feats:
            break
        for f in feats:
            if not isinstance(f, dict):
                continue
            props_raw = f.get("properties")
            props_dict: dict[str, Any] = (
                props_raw if isinstance(props_raw, dict) else {}
            )
            merged = dict(props_dict)
            merged.setdefault("sigma_layer_kind", "tramitados_ad")
            f["properties"] = merged
            feats_out.append(f)
            records.append(_props_summary(merged, source="tramitados_ad"))
        print(f"    AD GeoJSON pág.{page_n}: +{len(feats)} (total {len(feats_out)})", flush=True)
        if len(feats) < page_size:
            break
        offset += len(feats)

    fc = {"type": "FeatureCollection", "features": feats_out}
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_geo = RAW_DIR / "ad_tramitados_layer1.geojson"
    raw_geo.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    AD_GEOJSON_OUT.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    print(f"  OK: {AD_GEOJSON_OUT.name} ({len(feats_out)} polígonos)", flush=True)
    print(f"  raw → {raw_geo.name}", flush=True)
    return feats_out, records


def fetch_tramitados_ad_full() -> list[dict[str, Any]]:
    """Descarga catálogo AD (~3k expedientes): GeoJSON + polígonos y lista de registros."""
    print("  AD layer 1 — tramitados (GeoJSON + geometría)…", flush=True)
    try:
        _, records = fetch_tramitados_ad_geojson_paginated()
        if records:
            return records
    except Exception as ex:
        print(f"  aviso: GeoJSON AD falló ({ex}); atributos sin geometría", flush=True)
    print("  AD layer 1 (fallback JSON solo atributos)…", flush=True)
    feats = fetch_layer_json_paginated(
        SIGMA_AD_BASE,
        AD_LAYER_ID,
        out_fields="*",
        return_geometry=False,
        page_size=1000,
    )
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / "ad_tramitados_layer1.json"
    raw_path.write_text(
        json.dumps(
            {
                "source": "EXPEDIENTES_PLANEAMIENTO_AD",
                "layer_id": AD_LAYER_ID,
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
                "count": len(feats),
                "features": feats,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    records = []
    for f in feats:
        attrs = f.get("attributes") or {}
        records.append(_props_summary(attrs, source="tramitados_ad"))
    print(f"  raw → {raw_path} ({len(feats)} features)", flush=True)
    return records


def fetch_seguimiento_tramitados_geojson(
    layer_id: int,
    layer_kind: str,
    source: str,
    *,
    page_size: int = 400,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Capas SEGUIMIENTO_EXPEDIENTES (dataset 300119): gestión (3) y urbanización (2).
    Devuelve FeatureCollection WGS84 + registros para catálogo.
    """
    offset = 0
    feats_out: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    page_n = 0
    while True:
        page_n += 1
        qs = urllib.parse.urlencode(
            {
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
                "resultOffset": str(offset),
                "resultRecordCount": str(page_size),
            }
        )
        url = f"{SIGMA_SEGUIMIENTO_BASE}/{layer_id}/query?{qs}"
        data = _http_get_json(url, timeout=300.0)
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            print(f"  aviso: SEG layer {layer_id} GeoJSON inválido (offset={offset})", flush=True)
            break
        feats = data.get("features") or []
        if not feats:
            break
        for f in feats:
            if not isinstance(f, dict):
                continue
            props_raw = f.get("properties")
            props_dict: dict[str, Any] = props_raw if isinstance(props_raw, dict) else {}
            merged = dict(props_dict)
            merged["sigma_layer_kind"] = layer_kind
            merged["sigma_layer_id"] = layer_id
            f["properties"] = merged
            feats_out.append(f)
            rec = _props_summary(merged, source=source, geometry=True)
            rec["geometry"] = f.get("geometry")
            records.append(rec)
        print(
            f"    SEG {layer_kind} pág.{page_n}: +{len(feats)} (total {len(feats_out)})",
            flush=True,
        )
        if len(feats) < page_size:
            break
        offset += len(feats)

    fc = {"type": "FeatureCollection", "features": feats_out}
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_name = f"seg_{layer_kind}_layer{layer_id}.geojson"
    (RAW_DIR / raw_name).write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    print(f"  raw → {raw_name}", flush=True)
    return fc, records


def fetch_tramitados_gestion_urbanizacion() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Descarga gestión + urbanización (SEGUIMIENTO_EXPEDIENTES)."""
    gestion_recs: list[dict[str, Any]] = []
    urban_recs: list[dict[str, Any]] = []

    for layer_id, layer_kind, source in SEG_TRAMITADOS_LAYERS:
        print(f"  SEGUIMIENTO layer {layer_id} ({layer_kind})…", flush=True)
        fc, records = fetch_seguimiento_tramitados_geojson(layer_id, layer_kind, source)
        if layer_kind == "gestion":
            GESTION_GEOJSON_OUT.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
            GESTION_JSON_OUT.write_text(
                json.dumps(
                    {
                        "source": f"SEGUIMIENTO_EXPEDIENTES/layer{layer_id}",
                        "layer_id": layer_id,
                        "fetchedAt": datetime.now(timezone.utc).isoformat(),
                        "count": len(records),
                        "records": records,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            gestion_recs = records
            print(f"  OK: {GESTION_GEOJSON_OUT.name} ({len(records)} polígonos)", flush=True)
        else:
            URBANIZACION_GEOJSON_OUT.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
            URBANIZACION_JSON_OUT.write_text(
                json.dumps(
                    {
                        "source": f"SEGUIMIENTO_EXPEDIENTES/layer{layer_id}",
                        "layer_id": layer_id,
                        "fetchedAt": datetime.now(timezone.utc).isoformat(),
                        "count": len(records),
                        "records": records,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            urban_recs = records
            print(f"  OK: {URBANIZACION_GEOJSON_OUT.name} ({len(records)} polígonos)", flush=True)

    return gestion_recs, urban_recs


def fetch_tramitados_by_expedientes(exp_numbers: list[str]) -> list[dict[str, Any]]:
    """Consulta EXPEDIENTES_PLANEAMIENTO_AD por lotes de números de expediente."""
    records: list[dict[str, Any]] = []
    batch_size = 15
    unique = []
    seen: set[str] = set()
    for e in exp_numbers:
        for v in _exp_variants(e):
            if v not in seen:
                seen.add(v)
                unique.append(v)

    for i in range(0, len(unique), batch_size):
        batch = unique[i : i + batch_size]
        clauses = [f"EXP_TX_NUMERO = '{_norm_exp(e).replace(chr(39), chr(39) * 2)}'" for e in batch]
        where = " OR ".join(clauses)
        qs = urllib.parse.urlencode(
            {
                "where": where,
                "outFields": "EXP_TX_NUMERO,EXP_TX_DENOM,FAS_TX_DENOM,FEX_DT_APROB,FIG_TX_ETIQ,Enlace,ENLACE",
                "returnGeometry": "false",
                "f": "json",
                "resultRecordCount": str(batch_size * 2),
            }
        )
        url = f"{SIGMA_AD_BASE}/{AD_LAYER_ID}/query?{qs}"
        try:
            data = _http_get_json(url)
        except Exception as ex:
            print(f"  aviso: lote tramitados falló ({ex})")
            continue
        for f in data.get("features") or []:
            attrs = f.get("attributes") or {}
            records.append(_props_summary(attrs, source="tramitados_ad"))
    return records


def _merge_sigma_record(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Combina entradas del mismo expediente (p. ej. planeamiento AD + gestión)."""
    out = dict(existing)
    for k, v in new.items():
        if k == "geometry" and v and not out.get("geometry"):
            out[k] = v
        elif v is not None and v != "" and (out.get(k) in (None, "")):
            out[k] = v
    src_a = str(out.get("source") or "")
    src_b = str(new.get("source") or "")
    if src_b and src_b not in src_a.split("+"):
        out["source"] = f"{src_a}+{src_b}" if src_a else src_b
    kinds = {x for x in str(out.get("sigma_layer_kind") or "").split("+") if x}
    nk = new.get("sigma_layer_kind")
    if nk:
        kinds.add(str(nk))
    if kinds:
        out["sigma_layer_kind"] = "+".join(sorted(kinds))
    out["has_geometry"] = bool(out.get("geometry")) or bool(new.get("geometry"))
    return out


def _index_record(rec: dict[str, Any], by_exp: dict[str, dict[str, Any]], catalog: list[dict[str, Any]]) -> None:
    catalog.append(rec)
    num = _norm_exp(str(rec.get("EXP_TX_NUMERO") or ""))
    if not num:
        return
    for v in _exp_variants(num):
        if v in by_exp:
            by_exp[v] = _merge_sigma_record(by_exp[v], rec)
        else:
            by_exp[v] = rec


def build_sigma_index(
    ip_fc: dict[str, Any],
    tramitados: list[dict[str, Any]],
    gestion: list[dict[str, Any]] | None = None,
    urbanizacion: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    by_exp: dict[str, dict[str, Any]] = {}
    catalog: list[dict[str, Any]] = []

    for f in ip_fc.get("features") or []:
        if not isinstance(f, dict):
            continue
        p = f.get("properties") or {}
        rec = _props_summary(p, source="informacion_publica", geometry=True)
        rec["geometry"] = f.get("geometry")
        _index_record(rec, by_exp, catalog)

    for rec in tramitados:
        _index_record(rec, by_exp, catalog)

    for rec in gestion or []:
        _index_record(rec, by_exp, catalog)

    for rec in urbanizacion or []:
        _index_record(rec, by_exp, catalog)

    return by_exp, catalog


def write_full_catalog(catalog: list[dict[str, Any]]) -> None:
    """JSONL plano + índice JSON (sin geometrías pesadas en el índice)."""
    with FULL_JSONL_OUT.open("w", encoding="utf-8") as lf:
        for rec in catalog:
            lf.write(json.dumps(rec, ensure_ascii=False) + "\n")

    index_rows = []
    for rec in catalog:
        row = {k: v for k, v in rec.items() if k != "geometry"}
        index_rows.append(row)

    INDEX_OUT.write_text(
        json.dumps(
            {
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "note": "Catálogo SIGMA: IP + planeamiento AD + gestión + urbanización (dataset 300119).",
                "counts": {
                    "total": len(catalog),
                    "informacion_publica": sum(
                        1 for r in catalog if str(r.get("source") or "").startswith("informacion_publica")
                    ),
                    "tramitados_ad": sum(
                        1 for r in catalog if "tramitados_ad" in str(r.get("source") or "")
                    ),
                    "tramitados_gestion": sum(
                        1 for r in catalog if "tramitados_gestion" in str(r.get("source") or "")
                    ),
                    "tramitados_urbanizacion": sum(
                        1 for r in catalog if "tramitados_urbanizacion" in str(r.get("source") or "")
                    ),
                    "with_geometry": sum(1 for r in catalog if r.get("geometry")),
                    "expedientes_unicos": len(
                        {_norm_exp(str(r.get("EXP_TX_NUMERO") or "")) for r in catalog if r.get("EXP_TX_NUMERO")}
                    ),
                },
                "expedientes": index_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _bocm_row_id(row: dict[str, str]) -> str:
    """Debe coincidir con build-data.mjs: fp completo o sectorKey[:12] o «na»."""
    fp = (row.get("proyecto_fingerprint") or "").strip()
    source_id = (row.get("boletin_source_id") or "bocm").strip().lower() or "bocm"
    pub = row.get("bocm_date") or row.get("date_pub") or row.get("fecha") or ""
    art = row.get("art_num") or row.get("id") or ""
    if fp:
        suffix = fp
    else:
        from .keys import stable_sector_key

        sk = stable_sector_key(
            municipio=row.get("municipio"),
            nombre_sector=row.get("nombre_sector"),
            municipio_provincia=row.get("municipio_provincia"),
            boletin_source_id=source_id,
        )
        suffix = sk[:12] if sk else "na"
    return f"{source_id}-{pub}-{art}-{suffix}"


def match_bocm_to_sigma(
    by_exp: dict[str, dict[str, Any]], catalog: list[dict[str, Any]]
) -> dict[str, Any]:
    bocm_rows: list[dict[str, str]] = []
    if BOCM_CSV.is_file():
        with BOCM_CSV.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if (row.get("municipio") or "").strip().lower() == "madrid":
                    bocm_rows.append(row)

    matched_by_exp: list[dict[str, Any]] = []
    unmatched_bocm: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    matched_sigma_nums: set[str] = set()

    for row in bocm_rows:
        hit, match_type, match_score = match_row(row, by_exp)

        entry: dict[str, Any] = {
            "bocm_id": _bocm_row_id(row),
            "bocm_date": row.get("bocm_date"),
            "art_num": row.get("art_num"),
            "title": (row.get("title") or "")[:220],
            "es_relevante": row.get("es_relevante"),
            "procedimiento_expediente": row.get("procedimiento_expediente"),
            "nombre_sector": row.get("nombre_sector"),
        }

        if hit:
            num = _norm_exp(str(hit.get("EXP_TX_NUMERO") or ""))
            if num:
                matched_sigma_nums.add(num)
            entry.update(
                {
                    "match_type": match_type,
                    "match_score": match_score,
                    "sigma_expediente": hit.get("EXP_TX_NUMERO"),
                    "sigma_denominacion": hit.get("EXP_TX_DENOM"),
                    "sigma_fase": hit.get("FAS_TX_DENOM"),
                    "sigma_enlace": hit.get("Enlace"),
                    "sigma_source": hit.get("source"),
                    "sigma_en_ip": hit.get("source") == "informacion_publica",
                }
            )
            links.append(entry)
            matched_by_exp.append(entry)
        else:
            unmatched_bocm.append(entry)

    sigma_only = [
        _props_summary(r, source=str(r.get("source") or ""))
        for r in catalog
        if _norm_exp(str(r.get("EXP_TX_NUMERO") or ""))
        and _norm_exp(str(r.get("EXP_TX_NUMERO") or "")) not in matched_sigma_nums
        and r.get("source") == "informacion_publica"
    ]

    relevant = [
        r
        for r in bocm_rows
        if (r.get("es_relevante") or "").strip().lower() in ("true", "1", "yes", "si", "sí")
    ]

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "note": "Solo municipio Madrid (capital). Cruce: IP + tramitados AD; match solo por nº expediente (sin fuzzy).",
        "sigma": {
            "expedientes_ip_total": sum(1 for r in catalog if r.get("source") == "informacion_publica"),
            "expedientes_index_total": len(catalog),
            "expedientes_tramitados_consultados": sum(
                1 for r in catalog if r.get("source") == "tramitados_ad"
            ),
            "expedientes_ip_sin_bocm": len(sigma_only),
            "samples_sin_bocm": sigma_only[:15],
        },
        "bocm_madrid_ciudad": {
            "filas_total": len(bocm_rows),
            "relevantes": len(relevant),
            "con_sector": sum(1 for r in relevant if (r.get("nombre_sector") or "").strip()),
            "match_expediente": len(matched_by_exp),
            "match_denominacion": 0,
            "match_total": len(matched_by_exp),
            "sin_match": len(unmatched_bocm),
            "pct_match_relevantes": round(len(matched_by_exp) / max(len(relevant), 1) * 1000) / 10,
            "samples_match_expediente": matched_by_exp[:10],
            "samples_match_denominacion": [],
            "samples_sin_match": unmatched_bocm[:8],
        },
        "links_written": len(links),
    }, links


def _load_json_records(path: Path, source: str) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("records"):
        return list(data["records"])
    return []


def _load_cached_sigma() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    ip_fc = json.loads(GEOJSON_OUT.read_text(encoding="utf-8"))
    tramitados = _load_json_records(AD_FULL_OUT, "tramitados_ad")
    if not tramitados and AD_FULL_OUT.is_file():
        ad_data = json.loads(AD_FULL_OUT.read_text(encoding="utf-8"))
        for f in ad_data.get("features") or []:
            attrs = f.get("attributes") or {}
            tramitados.append(_props_summary(attrs, source="tramitados_ad"))
    gestion = _load_json_records(GESTION_JSON_OUT, "tramitados_gestion")
    urban = _load_json_records(URBANIZACION_JSON_OUT, "tramitados_urbanizacion")
    return ip_fc, tramitados, gestion, urban


def main() -> None:
    ap = argparse.ArgumentParser(description="Sync SIGMA + cruce BOCM Madrid ciudad")
    ap.add_argument("--skip-fetch", action="store_true", help="Reusar volcados en output/ y raw/")
    ap.add_argument("--no-match", action="store_true", help="Solo descarga/índice; sin cruce BOCM")
    ap.add_argument(
        "--only-seg",
        action="store_true",
        help="Sólo descargar gestión+urbanización (reusa IP/AD locales si existen)",
    )
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    gestion_recs: list[dict[str, Any]] = []
    urban_recs: list[dict[str, Any]] = []

    if args.only_seg:
        print("Modo --only-seg: gestión + urbanización (SEGUIMIENTO)…", flush=True)
        if GEOJSON_OUT.is_file():
            ip_fc, tramitados, _, _ = _load_cached_sigma()
        else:
            ip_fc = {"type": "FeatureCollection", "features": []}
            tramitados = []
        gestion_recs, urban_recs = fetch_tramitados_gestion_urbanizacion()
    elif args.skip_fetch and GEOJSON_OUT.is_file() and AD_FULL_OUT.is_file():
        print("Reusando volcados locales…", flush=True)
        ip_fc, tramitados, gestion_recs, urban_recs = _load_cached_sigma()
        if not gestion_recs and GESTION_JSON_OUT.is_file():
            gestion_recs = _load_json_records(GESTION_JSON_OUT, "tramitados_gestion")
        if not urban_recs and URBANIZACION_JSON_OUT.is_file():
            urban_recs = _load_json_records(URBANIZACION_JSON_OUT, "tramitados_urbanizacion")
        print(
            f"  IP: {len(ip_fc.get('features') or [])} | AD: {len(tramitados)} | "
            f"Gestión: {len(gestion_recs)} | Urb: {len(urban_recs)}",
            flush=True,
        )
        if not gestion_recs or not urban_recs:
            print("  Faltan gestión/urbanización; descargando SEGUIMIENTO…", flush=True)
            g, u = fetch_tramitados_gestion_urbanizacion()
            gestion_recs = gestion_recs or g
            urban_recs = urban_recs or u
    else:
        print("Descargando EXPEDIENTES_INFORMACION_PUBLICA (todas las capas)…", flush=True)
        ip_fc = fetch_expedientes_ip()
        GEOJSON_OUT.write_text(json.dumps(ip_fc, ensure_ascii=False), encoding="utf-8")
        print(f"OK: {GEOJSON_OUT} ({len(ip_fc.get('features') or [])} features)")

        print("Descargando EXPEDIENTES_PLANEAMIENTO_AD (capa 1, geometrías + índice)…", flush=True)
        tramitados = fetch_tramitados_ad_full()
        AD_FULL_OUT.write_text(
            json.dumps(
                {
                    "source": "EXPEDIENTES_PLANEAMIENTO_AD",
                    "layer_id": AD_LAYER_ID,
                    "fetchedAt": datetime.now(timezone.utc).isoformat(),
                    "count": len(tramitados),
                    "records": tramitados,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"OK: {AD_FULL_OUT} ({len(tramitados)} expedientes)")

        print("Descargando SEGUIMIENTO_EXPEDIENTES (gestión + urbanización)…", flush=True)
        gestion_recs, urban_recs = fetch_tramitados_gestion_urbanizacion()

    by_exp, catalog = build_sigma_index(ip_fc, tramitados, gestion_recs, urban_recs)
    write_full_catalog(catalog)
    uniq = len({_norm_exp(str(r.get("EXP_TX_NUMERO") or "")) for r in catalog if r.get("EXP_TX_NUMERO")})
    print(
        f"OK: {INDEX_OUT} ({len(catalog)} filas catálogo, {uniq} expedientes únicos; "
        f"gestión {len(gestion_recs)}, urbanización {len(urban_recs)})"
    )
    print(f"OK: {FULL_JSONL_OUT}")

    if args.no_match:
        print("Omitido cruce BOCM (--no-match).")
        return

    report, links = match_bocm_to_sigma(by_exp, catalog)
    MATCH_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    with LINKS_OUT.open("w", encoding="utf-8") as lf:
        for link in links:
            lf.write(json.dumps(link, ensure_ascii=False) + "\n")
    print(f"OK: {LINKS_OUT} ({len(links)} enlaces con match)")

    bm = report["bocm_madrid_ciudad"]
    print(
        f"OK: {MATCH_OUT}\n"
        f"    Catálogo SIGMA: {len(catalog)} expedientes\n"
        f"    BOCM Madrid: {bm['filas_total']} filas | "
        f"match {bm['match_total']} (solo expediente {bm['match_expediente']}) "
        f"= {bm['pct_match_relevantes']}% relevantes\n"
        f"    SIGMA IP sin BOCM: {report['sigma']['expedientes_ip_sin_bocm']}"
    )


if __name__ == "__main__":
    main()
