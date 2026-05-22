from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from municipio.manifest import MunicipioManifest, POC_ROOT

# Paridad mínima respecto a dashboard Madrid (licencias + proyectos BOCM)
PARITY_CHECKS = {
    "proyectos": {
        "file": "proyectos.jsonl",
        "min_rows": 1,
        "fields_any": ["id", "municipio", "titulo", "fecha"],
    },
    "licencias": {
        "file": "licencias.jsonl",
        "min_rows": 0,
        "fields_any": ["id", "fecha_concesion", "tipo", "distrito"],
        "optional": True,
    },
}


def _count_jsonl(path: Path) -> int:
    if not path.is_file() or path.stat().st_size == 0:
        return 0
    n = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def _sample_fields(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        return set(obj.keys())
                except json.JSONDecodeError:
                    pass
            break
    return set()


def _level(count: int, min_rows: int, optional: bool) -> str:
    if count >= min_rows and min_rows > 0:
        return "ok"
    if count > 0:
        return "partial"
    if optional:
        return "none"
    return "none" if count == 0 else "partial"


def validate_manifest(manifest: MunicipioManifest) -> dict[str, Any]:
    out_dir = manifest.output_dir
    report: dict[str, Any] = {
        "slug": manifest.slug,
        "nombre": manifest.nombre,
        "manifest": str(manifest.path),
        "licencias_configured": manifest.licencias.enabled,
        "proyectos_configured": manifest.proyectos.enabled,
        "datasets": {},
    }

    for name, spec in PARITY_CHECKS.items():
        path = out_dir / spec["file"]
        count = _count_jsonl(path)
        fields = _sample_fields(path)
        required = set(spec.get("fields_any") or [])
        has_fields = bool(fields & required) if required else count > 0
        optional = bool(spec.get("optional"))
        min_rows = int(spec.get("min_rows", 1))
        level = _level(count if has_fields else 0, min_rows, optional)
        if count >= min_rows and not has_fields and min_rows > 0:
            level = "partial"
        report["datasets"][name] = {
            "level": level,
            "rows": count,
            "path": str(path),
            "fields_present": sorted(fields)[:20],
        }

    levels = [d["level"] for d in report["datasets"].values()]
    if all(l == "ok" for l in levels):
        report["overall"] = "ok"
    elif any(l == "ok" for l in levels):
        report["overall"] = "partial"
    else:
        report["overall"] = "none"

    return report


def write_parity_report(manifest: MunicipioManifest) -> Path:
    manifest.ensure_output_dir()
    report = validate_manifest(manifest)
    path = manifest.output_dir / "parity-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_global_parity_report(slugs: list[str], loader) -> Path:
    reports = []
    for slug in slugs:
        m = loader(slug)
        reports.append(validate_manifest(m))
    path = POC_ROOT / "output" / "municipios" / "parity-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"municipios": reports}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
