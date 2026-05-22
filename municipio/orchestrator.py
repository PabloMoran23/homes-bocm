from __future__ import annotations

import json
from typing import Any, Callable

from municipio import licencias_runner, proyectos_runner, validate
from municipio.manifest import MunicipioManifest, load_manifest

Step = str  # licencias_backfill | licencias_update | proyectos_backfill | proyectos_update | validate | all

RUNNERS: dict[str, Callable[[MunicipioManifest], dict[str, Any]]] = {
    "licencias_backfill": licencias_runner.backfill,
    "licencias_update": licencias_runner.update,
    "proyectos_backfill": proyectos_runner.backfill,
    "proyectos_update": proyectos_runner.update,
}


def _steps_for(step: Step) -> list[str]:
    if step == "all":
        return [
            "proyectos_backfill",
            "licencias_backfill",
            "proyectos_update",
            "licencias_update",
            "validate",
        ]
    if step == "backfill":
        return ["proyectos_backfill", "licencias_backfill", "validate"]
    if step == "update":
        return ["proyectos_update", "licencias_update", "validate"]
    if step in RUNNERS:
        return [step]
    if step == "validate":
        return ["validate"]
    raise ValueError(f"Paso desconocido: {step}")


def run(manifest: MunicipioManifest, step: Step = "all") -> dict[str, Any]:
    results: dict[str, Any] = {"slug": manifest.slug, "steps": {}}
    for name in _steps_for(step):
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
    return results


def run_many(slugs: list[str], step: Step = "all") -> dict[str, Any]:
    out: dict[str, Any] = {"municipios": {}}
    for slug in slugs:
        manifest = load_manifest(slug)
        out["municipios"][slug] = run(manifest, step)
    global_path = validate.write_global_parity_report(slugs, load_manifest)
    out["global_parity_report"] = str(global_path)
    return out
