from __future__ import annotations

import json
from typing import Any, Callable

from municipio import licencias_runner, proyectos_runner, validate
from municipio.enrich_geometry import enrich_manifest
from municipio.geocode import geocode_manifest
from municipio.manifest import MunicipioManifest, load_manifest
from municipio.sync_supabase import defer_manifest, sync_manifest

Step = str  # licencias_backfill | licencias_update | proyectos_backfill | proyectos_update | enrich_geometry | geocode | sync_supabase | validate | all

RUNNERS: dict[str, Callable[[MunicipioManifest], dict[str, Any]]] = {
    "licencias_backfill": licencias_runner.backfill,
    "licencias_update": licencias_runner.update,
    "proyectos_backfill": proyectos_runner.backfill,
    "proyectos_update": proyectos_runner.update,
    "enrich_geometry": enrich_manifest,
    "geocode": geocode_manifest,
    "sync_supabase": sync_manifest,
}


def _steps_for(step: Step) -> list[str]:
    if step == "all":
        return [
            "proyectos_backfill",
            "licencias_backfill",
            "proyectos_update",
            "licencias_update",
            "enrich_geometry",
            "geocode",
            "sync_supabase",
            "validate",
        ]
    if step == "backfill":
        return [
            "proyectos_backfill",
            "licencias_backfill",
            "enrich_geometry",
            "geocode",
            "sync_supabase",
            "validate",
        ]
    if step == "update":
        return [
            "proyectos_update",
            "licencias_update",
            "enrich_geometry",
            "geocode",
            "sync_supabase",
            "validate",
        ]
    if step in RUNNERS:
        return [step]
    if step == "validate":
        return ["validate"]
    raise ValueError(f"Paso desconocido: {step}")


def _is_timeout(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return "timeout" in text or "timed out" in text


def run(manifest: MunicipioManifest, step: Step = "all") -> dict[str, Any]:
    results: dict[str, Any] = {"slug": manifest.slug, "steps": {}}
    timed_out = False
    for name in _steps_for(step):
        if name == "sync_supabase" and timed_out:
            results["steps"][name] = {
                "status": "deferred",
                "reason": "timeout; se reintenta al día siguiente",
            }
            continue
        if name == "validate":
            path = validate.write_parity_report(manifest)
            results["steps"]["validate"] = {
                "parity_report": str(path),
                "report": json.loads(path.read_text(encoding="utf-8")),
            }
            continue
        try:
            results["steps"][name] = RUNNERS[name](manifest)
        except Exception as e:
            results["steps"][name] = {"error": str(e), "type": type(e).__name__}
            if _is_timeout(e):
                timed_out = True
    if timed_out:
        results["retry"] = "next_day"
        try:
            defer_manifest(manifest)
        except Exception as exc:
            results["defer_error"] = str(exc)
    return results


def run_many(slugs: list[str], step: Step = "all") -> dict[str, Any]:
    out: dict[str, Any] = {"municipios": {}}
    for slug in slugs:
        manifest = load_manifest(slug)
        out["municipios"][slug] = run(manifest, step)
    global_path = validate.write_global_parity_report(slugs, load_manifest)
    out["global_parity_report"] = str(global_path)
    return out
