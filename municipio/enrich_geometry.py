from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from municipio.geometry import has_area_geometry, record_geometry
from municipio.gis.arcgis import query_mapserver_geojson
from municipio.gis.sitcm import resolve_ambito_geometry, resolve_municipio_wfs, sitcm_municipio_available
from municipio.manifest import MunicipioManifest

WFS_DELAY_S = 0.15


def _load_geometry_config(manifest: MunicipioManifest) -> dict[str, Any]:
    raw = manifest.path.parent / "manifest.yaml"
    try:
        from municipio.manifest import load_yaml

        data = load_yaml(raw)
    except Exception:
        return {}
    geom = data.get("geometry") or {}
    return dict(geom) if isinstance(geom, dict) else {}


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


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _record_title(rec: dict[str, Any]) -> str:
    return str(rec.get("titulo") or rec.get("denominacion") or rec.get("objeto") or "").strip()


def _enrichers_for(manifest: MunicipioManifest, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    explicit = cfg.get("enrichers")
    if isinstance(explicit, list):
        return [e for e in explicit if isinstance(e, dict)]

    if manifest.provincia.lower() == "madrid":
        return [{"kind": "sitcm_ambito"}]
    return []


def _apply_enricher(
    rec: dict[str, Any],
    enricher: dict[str, Any],
    *,
    manifest: MunicipioManifest,
    municipio_wfs: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    kind = str(enricher.get("kind") or "")
    title = _record_title(rec)

    if kind == "sitcm_ambito":
        muni = str(enricher.get("municipio_wfs") or municipio_wfs or "")
        if not muni or not title:
            return None, None
        geom, meta = resolve_ambito_geometry(muni, title)
        if geom:
            meta["geometry_source"] = "sitcm_vpla_ambito"
            meta["geometry_source_url"] = "https://idem.comunidad.madrid/geoserver3/ows"
        time.sleep(WFS_DELAY_S)
        return geom, meta

    if kind == "arcgis_mapserver":
        geom, meta = query_mapserver_geojson(enricher, rec)
        if geom:
            meta["geometry_source"] = "portal_visor_arcgis"
        return geom, meta

    return None, None


def enrich_records(
    records: list[dict[str, Any]],
    *,
    manifest: MunicipioManifest,
    cfg: dict[str, Any],
) -> dict[str, int]:
    enrichers = _enrichers_for(manifest, cfg)
    if not enrichers:
        return {"skipped_no_enricher": len(records), "already_had_geometry": 0, "enriched": 0, "no_match": 0}

    municipio_wfs = None
    if any(e.get("kind") == "sitcm_ambito" for e in enrichers):
        municipio_wfs = resolve_municipio_wfs(manifest.nombre)
        if not municipio_wfs:
            return {"skipped_no_sitcm": len(records), "already_had_geometry": 0, "enriched": 0, "no_match": 0}

    stats = {"already_had_geometry": 0, "enriched": 0, "no_match": 0, "skipped_empty_title": 0}

    for rec in records:
        if has_area_geometry(rec):
            stats["already_had_geometry"] += 1
            continue

        title = _record_title(rec)
        if not title:
            stats["skipped_empty_title"] += 1
            continue

        geom: dict[str, Any] | None = None
        meta: dict[str, Any] | None = None
        for enricher in enrichers:
            geom, meta = _apply_enricher(
                rec, enricher, manifest=manifest, municipio_wfs=municipio_wfs
            )
            if geom:
                break

        if not geom:
            stats["no_match"] += 1
            continue

        rec["geom_geojson"] = geom
        rec["geometry_source"] = (meta or {}).get("geometry_source") or "enrich_geometry"
        if meta and meta.get("geometry_source_url"):
            rec["geometry_source_url"] = meta["geometry_source_url"]
        if meta and meta.get("ambito_name"):
            rec["sector_key"] = meta["ambito_name"]
        rec["coord_source"] = rec.get("coord_source") or "portal_geometry_centroid"
        stats["enriched"] += 1

    return stats


def enrich_manifest(manifest: MunicipioManifest) -> dict[str, Any]:
    manifest.ensure_output_dir()
    cfg = _load_geometry_config(manifest)

    proyectos_path = manifest.output_dir / "proyectos.jsonl"
    licencias_path = manifest.output_dir / "licencias.jsonl"
    proyectos = _read_jsonl(proyectos_path)
    licencias = _read_jsonl(licencias_path)

    proy_stats = enrich_records(proyectos, manifest=manifest, cfg=cfg)
    lic_stats = enrich_records(licencias, manifest=manifest, cfg=cfg)

    if proyectos:
        _write_jsonl(proyectos_path, proyectos)
    if licencias:
        _write_jsonl(licencias_path, licencias)

    proy_with_geom = sum(1 for r in proyectos if has_area_geometry(r))
    lic_with_geom = sum(1 for r in licencias if has_area_geometry(r))

    return {
        "status": "ok",
        "slug": manifest.slug,
        "nombre": manifest.nombre,
        "sitcm_available": sitcm_municipio_available(manifest.nombre),
        "sitcm_municipio_wfs": resolve_municipio_wfs(manifest.nombre),
        "enrichers": _enrichers_for(manifest, cfg),
        "proyectos": {
            "rows": len(proyectos),
            "with_geometry": proy_with_geom,
            **proy_stats,
        },
        "licencias": {
            "rows": len(licencias),
            "with_geometry": lic_with_geom,
            **lic_stats,
        },
    }
