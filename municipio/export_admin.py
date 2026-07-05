from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from municipio.manifest import MUNICIPIOS_DIR, POC_ROOT, list_manifest_slugs
from municipio.queue import (
    QUEUE_PATH,
    TERRITORIO_BY_SOURCE,
    _load_yaml,
    _parse_entries,
    open_pr_by_slug,
    pick_next,
)
from municipio.validate import validate_manifest

CCAA_LABELS = {tid: label for tid, (_, label) in TERRITORIO_BY_SOURCE.items()}
CCAA_LABELS.update(
    {
        "comunidad-madrid": "Comunidad de Madrid",
        "andalucia": "Andalucía",
        "castilla-y-leon": "Castilla y León",
        "comunitat-valenciana": "Comunitat Valenciana",
        "canarias": "Canarias",
        "asturias": "Principado de Asturias",
        "galicia": "Galicia",
        "cantabria": "Cantabria",
        "illes-balears": "Illes Balears",
        "euskadi": "Euskadi",
        "murcia": "Región de Murcia",
        "catalunya": "Catalunya",
        "castilla-mancha": "Castilla-La Mancha",
    }
)

ADAPTER_PATH = POC_ROOT / "municipio" / "adapters"


def _iso_mtime(path: Path) -> str | None:
    if not path.is_file():
        return None
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _git_last_commit(path: Path) -> dict[str, str | None]:
    rel = path.relative_to(POC_ROOT).as_posix()
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%cI|%h|%s", "--", rel],
            cwd=POC_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return {"at": None, "sha": None, "subject": None}
    line = (proc.stdout or "").strip()
    if proc.returncode != 0 or not line:
        return {"at": None, "sha": None, "subject": None}
    parts = line.split("|", 2)
    return {
        "at": parts[0] if len(parts) > 0 else None,
        "sha": parts[1] if len(parts) > 1 else None,
        "subject": parts[2] if len(parts) > 2 else None,
    }


def _adapter_module_path(adapter_ref: str | None) -> Path | None:
    if not adapter_ref or ":" not in adapter_ref:
        return None
    mod = adapter_ref.split(":", 1)[0].strip()
    if not mod.startswith("municipio.adapters."):
        return None
    rel = mod.replace(".", "/") + ".py"
    path = POC_ROOT / rel
    return path if path.is_file() else None


def _count_jsonl(path: Path) -> int:
    if not path.is_file():
        return 0
    n = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def _entry_activity_at(entry: Any, manifest_mtime: str | None, git_at: str | None) -> str | None:
    candidates = [entry.last_run, git_at, manifest_mtime]
    parsed: list[datetime] = []
    for raw in candidates:
        if not raw:
            continue
        try:
            parsed.append(datetime.fromisoformat(str(raw).replace("Z", "+00:00")))
        except ValueError:
            continue
    if not parsed:
        return None
    return max(parsed).isoformat()


def build_municipio_admin_payload(*, include_pending: bool = True) -> dict[str, Any]:
    queue_raw = _load_yaml(QUEUE_PATH) if QUEUE_PATH.is_file() else {}
    entries = _parse_entries(queue_raw)
    manifest_slugs = set(list_manifest_slugs())
    open_prs = open_pr_by_slug()
    rows: list[dict[str, Any]] = []

    for entry in entries:
        slug = entry.slug
        manifest_path = MUNICIPIOS_DIR / slug / "manifest.yaml"
        research_path = MUNICIPIOS_DIR / slug / "RESEARCH.md"
        output_dir = POC_ROOT / "output" / "municipios" / slug

        has_manifest = manifest_path.is_file()
        has_research = research_path.is_file()
        git_manifest = _git_last_commit(manifest_path) if has_manifest else {"at": None, "sha": None, "subject": None}
        manifest_mtime = _iso_mtime(manifest_path)

        adapter_ref: str | None = None
        portal_url: str | None = None
        adapter_path: Path | None = None
        proyectos_rows = 0
        licencias_rows = 0
        with_coords = 0
        with_geometry = 0
        parity_overall: str | None = None

        if has_manifest:
            try:
                import yaml

                raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                portal = raw.get("portal") or {}
                adapter_ref = portal.get("adapter")
                portal_url = portal.get("base_url")
                adapter_path = _adapter_module_path(str(adapter_ref or ""))
            except Exception:
                pass

            try:
                from municipio.manifest import load_manifest

                manifest = load_manifest(slug)
                report = validate_manifest(manifest)
                parity_overall = report.get("overall")
                proy = report.get("datasets", {}).get("proyectos", {})
                lic = report.get("datasets", {}).get("licencias", {})
                proyectos_rows = int(proy.get("rows") or 0)
                licencias_rows = int(lic.get("rows") or 0)
                with_coords = int(proy.get("with_coords") or 0)
                with_geometry = int(proy.get("with_geometry") or 0)
            except Exception:
                proyectos_rows = _count_jsonl(output_dir / "proyectos.jsonl")
                licencias_rows = _count_jsonl(output_dir / "licencias.jsonl")

        ccaa_id = entry.comunidad_autonoma or "comunidad-madrid"
        open_pr = open_prs.get(slug)
        blocked_reason: str | None = None
        if entry.status == "pending" and open_pr:
            blocked_reason = "pr_abierta"
        elif entry.status == "pending" and has_manifest:
            blocked_reason = "manifest_en_main"

        rows.append(
            {
                "slug": slug,
                "nombre": entry.nombre,
                "status": entry.status,
                "bocmCount": entry.bocm_count,
                "boletinSourceId": entry.boletin_source_id or "bocm",
                "comunidadAutonoma": ccaa_id,
                "comunidadLabel": CCAA_LABELS.get(ccaa_id, ccaa_id),
                "provincia": entry.provincia or "",
                "attempts": entry.attempts,
                "lastRun": entry.last_run,
                "lastError": entry.last_error,
                "prUrl": entry.pr_url,
                "openPrUrl": open_pr,
                "blockedReason": blocked_reason,
                "notes": entry.notes,
                "hasManifest": has_manifest,
                "hasResearch": has_research,
                "hasAdapter": adapter_path is not None,
                "adapterRef": adapter_ref,
                "adapterPath": str(adapter_path.relative_to(POC_ROOT)) if adapter_path else None,
                "portalUrl": portal_url,
                "manifestUpdatedAt": manifest_mtime,
                "mergedAt": git_manifest.get("at"),
                "mergeCommit": git_manifest.get("sha"),
                "mergeSubject": git_manifest.get("subject"),
                "activityAt": _entry_activity_at(entry, manifest_mtime, git_manifest.get("at")),
                "proyectosRows": proyectos_rows,
                "licenciasRows": licencias_rows,
                "withCoords": with_coords,
                "withGeometry": with_geometry,
                "parityOverall": parity_overall,
                "boletinCounts": entry.boletin_counts or {},
            }
        )

    by_status = Counter(r["status"] for r in rows)
    by_ccaa = Counter(r["comunidadAutonoma"] for r in rows)
    merged = [r for r in rows if r["hasManifest"] and r["status"] in {"done", "skipped"}]
    with_adapter = sum(1 for r in rows if r["hasAdapter"])
    with_parity_ok = sum(1 for r in rows if r["parityOverall"] == "ok")
    with_geometry_count = sum(1 for r in rows if (r["withGeometry"] or 0) > 0)

    next_raw = pick_next()
    next_row = None
    if next_raw:
        slug = str(next_raw.get("slug") or "")
        next_row = next((r for r in rows if r["slug"] == slug), None)

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "queueUpdatedAt": queue_raw.get("updated_at"),
        "queueDescription": queue_raw.get("description"),
        "minBocmCount": queue_raw.get("min_bocm_count"),
        "summary": {
            "total": len(rows),
            "byStatus": dict(sorted(by_status.items())),
            "byComunidad": {
                k: by_ccaa[k] for k in sorted(by_ccaa.keys(), key=lambda x: (-by_ccaa[x], x))
            },
            "withManifest": len(manifest_slugs),
            "withAdapter": with_adapter,
            "mergedOrSkipped": len(merged),
            "parityOk": with_parity_ok,
            "withPortalGeometry": with_geometry_count,
            "openPrs": len(open_prs),
        },
        "next": next_row,
        "openPrsBySlug": open_prs,
        "municipios": rows if include_pending else [r for r in rows if r["status"] != "pending"],
    }


def main() -> int:
    print(json.dumps(build_municipio_admin_payload(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
