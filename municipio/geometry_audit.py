from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from municipio.geometry import has_area_geometry
from municipio.gis.sitcm import resolve_municipio_wfs, sitcm_municipio_available
from municipio.manifest import MUNICIPIOS_DIR, POC_ROOT, load_manifest

AUDIT_PATH = MUNICIPIOS_DIR / "geometry-audit.yaml"
REPORT_PATH = MUNICIPIOS_DIR / "geometry-audit.md"

GEOPORTAL_HINTS = re.compile(
    r"https?://[^\s\)`\"']+(?:geoportal|geospatial|nexus|arcgis|gis|sig)[^\s\)`\"']*",
    re.I,
)

ARCgis_PATHS = (
    "/arcgis/rest/services?f=json",
    "/server/rest/services?f=json",
)

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def _read_research(slug: str) -> str:
    path = MUNICIPIOS_DIR / slug / "RESEARCH.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _parse_geometry_status(research: str) -> str | None:
    m = re.search(r"geometry_status:\s*(available|partial|unavailable)", research, re.I)
    return m.group(1).lower() if m else None


def _probe_url(url: str, timeout: float = 10.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "poc-bocm-geometry-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as resp:
            body = resp.read(8000)
            ct = resp.headers.get("Content-Type", "")
            is_json = "json" in ct or body[:1] in (b"{", b"[")
            services = 0
            if is_json:
                try:
                    data = json.loads(body)
                    if isinstance(data, dict) and "services" in data:
                        services = len(data.get("services") or [])
                except json.JSONDecodeError:
                    pass
            return {
                "ok": True,
                "status": resp.status,
                "content_type": ct,
                "arcgis_services": services,
                "is_arcgis_catalog": services > 0,
            }
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "error": str(e.reason)}
    except Exception as e:
        return {"ok": False, "error": type(e).__name__, "detail": str(e)[:200]}


def _probe_arcgis_bases(urls: list[str]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for raw in urls:
        base = raw.split("?")[0].rstrip("/")
        for suffix in ("", "/geoportal", "/portal"):
            root = base + suffix if suffix else base
            if root in seen:
                continue
            seen.add(root)
            for path in ARCgis_PATHS:
                probe = _probe_url(root + path)
                if probe.get("is_arcgis_catalog"):
                    out.append({"base": root, "catalog_url": root + path, **probe})
                    break
    return out


def _count_local_geometry(slug: str) -> dict[str, int]:
    out_dir = POC_ROOT / "output" / "municipios" / slug
    counts = {"proyectos": 0, "proyectos_with_geometry": 0, "licencias_with_geometry": 0}
    proy = out_dir / "proyectos.jsonl"
    if proy.is_file():
        with proy.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                counts["proyectos"] += 1
                try:
                    if has_area_geometry(json.loads(line)):
                        counts["proyectos_with_geometry"] += 1
                except json.JSONDecodeError:
                    pass
    lic = out_dir / "licencias.jsonl"
    if lic.is_file():
        with lic.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    if has_area_geometry(json.loads(line)):
                        counts["licencias_with_geometry"] += 1
                except json.JSONDecodeError:
                    pass
    return counts


def audit_municipio(slug: str) -> dict[str, Any]:
    manifest = load_manifest(slug)
    research = _read_research(slug)
    urls = sorted(set(GEOPORTAL_HINTS.findall(research)))
    portal_cfg = manifest.portal.config or {}
    for key in ("geoportal_url", "geoportal_base", "gis_base", "sig_url"):
        val = portal_cfg.get(key)
        if isinstance(val, str) and val.startswith("http"):
            urls.append(val)

    geometry_status = _parse_geometry_status(research)
    sitcm_wfs = resolve_municipio_wfs(manifest.nombre)
    arcgis = _probe_arcgis_bases(urls[:6])

    if arcgis:
        portal_gis = "arcgis_rest"
    elif sitcm_wfs:
        portal_gis = "sitcm_fallback"
    elif urls:
        portal_gis = "viewer_html_only"
    else:
        portal_gis = "none_found"

    recommendation = "unavailable"
    if arcgis:
        recommendation = "arcgis_config"
    elif sitcm_wfs:
        recommendation = "sitcm_ambito"

    return {
        "slug": slug,
        "nombre": manifest.nombre,
        "provincia": manifest.provincia,
        "geometry_status_research": geometry_status,
        "geoportal_urls": urls[:8],
        "arcgis_probes": arcgis,
        "sitcm_available": sitcm_municipio_available(manifest.nombre),
        "sitcm_municipio_wfs": sitcm_wfs,
        "portal_gis_class": portal_gis,
        "recommended_enricher": recommendation,
        "local_counts": _count_local_geometry(slug),
    }


def audit_slugs(slugs: list[str]) -> dict[str, Any]:
    entries = [audit_municipio(slug) for slug in slugs]
    summary = {
        "arcgis_rest": sum(1 for e in entries if e["portal_gis_class"] == "arcgis_rest"),
        "sitcm_fallback": sum(1 for e in entries if e["portal_gis_class"] == "sitcm_fallback"),
        "viewer_html_only": sum(1 for e in entries if e["portal_gis_class"] == "viewer_html_only"),
        "none_found": sum(1 for e in entries if e["portal_gis_class"] == "none_found"),
        "with_local_geometry": sum(
            1 for e in entries if e["local_counts"]["proyectos_with_geometry"] > 0
        ),
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "municipio_count": len(entries),
        "summary": summary,
        "municipios": entries,
    }


def write_audit(slugs: list[str]) -> Path:
    payload = audit_slugs(slugs)
    AUDIT_PATH.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    _write_markdown_report(payload)
    return AUDIT_PATH


def _write_markdown_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Auditoría GIS — portales municipales CM",
        "",
        f"Generado: {payload.get('generated_at', '')}",
        "",
        "## Resumen",
        "",
        f"- Municipios auditados: {payload.get('municipio_count', 0)}",
    ]
    summary = payload.get("summary") or {}
    for key, label in (
        ("arcgis_rest", "ArcGIS REST consultable"),
        ("sitcm_fallback", "Sin visor REST; SITCM WFS disponible"),
        ("viewer_html_only", "Visor HTML/SPA sin REST"),
        ("none_found", "Sin geoportal documentado"),
        ("with_local_geometry", "Con polígonos en output local"),
    ):
        lines.append(f"- {label}: {summary.get(key, 0)}")

    lines.extend(["", "## Detalle por municipio", ""])
    for e in payload.get("municipios") or []:
        lc = e.get("local_counts") or {}
        lines.append(f"### {e.get('nombre')} (`{e.get('slug')}`)")
        lines.append(f"- Clase GIS: **{e.get('portal_gis_class')}**")
        lines.append(f"- Enriquecedor recomendado: `{e.get('recommended_enricher')}`")
        lines.append(
            f"- SITCM: {'sí' if e.get('sitcm_available') else 'no'}"
            + (f" (`{e.get('sitcm_municipio_wfs')}`)" if e.get("sitcm_municipio_wfs") else "")
        )
        if e.get("geoportal_urls"):
            lines.append("- URLs geoportal:")
            for u in e["geoportal_urls"][:4]:
                lines.append(f"  - {u}")
        lines.append(
            f"- Output local: {lc.get('proyectos_with_geometry', 0)}/{lc.get('proyectos', 0)} proyectos con polígono"
        )
        lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def load_queue_done_slugs() -> list[str]:
    queue_path = MUNICIPIOS_DIR / "queue.yaml"
    if not queue_path.is_file():
        return []
    data = yaml.safe_load(queue_path.read_text(encoding="utf-8"))
    return [
        str(m["slug"])
        for m in (data.get("municipios") or [])
        if m.get("status") == "done" and m.get("slug")
    ]
