from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from municipio.adapters.registry import load_portal_adapter, resolve_portal_adapter_spec
from municipio.manifest import POC_ROOT, MunicipioManifest, municipio_matches

BOCM_CSV = POC_ROOT / "output" / "history_parsed_incremental.csv"
PROJECTS_JSON = POC_ROOT / "web" / "public" / "data" / "projects.json"


def _truthy(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val or "").strip().lower() in ("1", "true", "yes", "sí", "si")


def _row_to_record(row: dict[str, Any]) -> dict[str, Any]:
    fp = row.get("proyecto_fingerprint") or row.get("fp") or ""
    bocm_date = row.get("bocm_date") or row.get("bocmDate") or ""
    art_num = str(row.get("art_num") or row.get("artNum") or "")
    rid = row.get("id") or ""
    if not rid and bocm_date and art_num:
        rid = f"bocm-{bocm_date}-{art_num}-{str(fp)[:12] or 'na'}"
    return {
        "id": rid,
        "municipio": row.get("municipio") or "",
        "titulo": row.get("titulo") or row.get("title") or row.get("Title") or "",
        "fecha": row.get("fecha") or bocm_date or "",
        "tipo": row.get("tipo") or row.get("tipo_instrumento") or row.get("tipoInstrumento") or "",
        "es_relevante": (
            _truthy(row["es_relevante"])
            if row.get("es_relevante") not in (None, "")
            else _truthy(row.get("esRelevante", True))
        ),
        "url": row.get("url") or row.get("pdf_url") or row.get("pdfUrl") or "",
        "source": "bocm_legacy",
    }


def _read_bocm_csv() -> list[dict[str, str]]:
    with BOCM_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _read_projects_json() -> list[dict[str, Any]]:
    import json

    with PROJECTS_JSON.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"projects.json inválido: {PROJECTS_JSON}")
    rows = []
    for p in data:
        if str(p.get("sourceId") or p.get("source_id") or "") not in ("", "bocm"):
            continue
        if str(p.get("territorioId") or "") not in ("", "comunidad-madrid"):
            continue
        rows.append(p)
    return rows


def _read_bocm_rows() -> tuple[list[dict[str, Any]], str]:
    if BOCM_CSV.is_file():
        return _read_bocm_csv(), "csv"
    if PROJECTS_JSON.is_file():
        return _read_projects_json(), "projects_json"
    raise FileNotFoundError(
        f"Sin fuente BOCM: falta {BOCM_CSV} y {PROJECTS_JSON}"
    )


def _filter_rows(manifest: MunicipioManifest, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aliases = manifest.proyectos.municipio_aliases
    out: list[dict[str, Any]] = []
    for row in rows:
        if not municipio_matches(row.get("municipio"), aliases):
            continue
        rec = _row_to_record(row)
        if manifest.proyectos.source == "bocm_legacy" and not rec.get("es_relevante"):
            continue
        out.append(rec)
    return out


def _state_path(manifest: MunicipioManifest) -> Path:
    return manifest.output_dir / "proyectos.state.json"


def _out_path(manifest: MunicipioManifest) -> Path:
    return manifest.output_dir / "proyectos.jsonl"


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"seen_ids": [], "last_run": None}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _save_state(path: Path, state: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _backfill_ayuntamiento(manifest: MunicipioManifest) -> dict[str, Any]:
    adapter = load_portal_adapter(manifest)
    out = _out_path(manifest)
    result = adapter.backfill_proyectos(out)
    spec = resolve_portal_adapter_spec(manifest)
    state = {
        "seen_ids": [],
        "last_run": datetime.now(timezone.utc).isoformat(),
        "count": result.get("rows", 0),
        "input_source": "ayuntamiento",
        "adapter": spec,
        "portal_url": manifest.portal.base_url,
    }
    if out.is_file():
        with out.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rid = json.loads(line).get("id")
                        if rid:
                            state["seen_ids"].append(rid)
                    except json.JSONDecodeError:
                        pass
    _save_state(_state_path(manifest), state)
    return {
        **result,
        "path": str(out),
        "source": "ayuntamiento",
        "adapter": spec,
    }


def _update_ayuntamiento(manifest: MunicipioManifest) -> dict[str, Any]:
    adapter = load_portal_adapter(manifest)
    out = _out_path(manifest)
    state_path = _state_path(manifest)
    if not state_path.is_file():
        state_path.write_text("{}", encoding="utf-8")
    result = adapter.update_proyectos(out, state_path)
    spec = resolve_portal_adapter_spec(manifest)
    return {**result, "path": str(out), "source": "ayuntamiento", "adapter": spec}


def backfill(manifest: MunicipioManifest) -> dict[str, Any]:
    if not manifest.proyectos.enabled:
        return {"skipped": True, "reason": "proyectos.disabled"}
    manifest.ensure_output_dir()
    if manifest.proyectos.source == "ayuntamiento":
        return _backfill_ayuntamiento(manifest)
    rows, input_source = _read_bocm_rows()
    records = _filter_rows(manifest, rows)
    out = _out_path(manifest)
    _write_jsonl(out, records)
    state = {
        "seen_ids": [r["id"] for r in records if r.get("id")],
        "last_run": datetime.now(timezone.utc).isoformat(),
        "count": len(records),
        "input_source": input_source,
    }
    _save_state(_state_path(manifest), state)
    return {
        "rows": len(records),
        "path": str(out),
        "source": manifest.proyectos.source,
        "input_source": input_source,
    }


def update(manifest: MunicipioManifest) -> dict[str, Any]:
    if not manifest.proyectos.enabled:
        return {"skipped": True, "reason": "proyectos.disabled"}
    manifest.ensure_output_dir()
    if manifest.proyectos.source == "ayuntamiento":
        return _update_ayuntamiento(manifest)
    state_path = _state_path(manifest)
    state = _load_state(state_path)
    seen = set(state.get("seen_ids") or [])
    out = _out_path(manifest)

    existing: list[dict[str, Any]] = []
    if out.is_file():
        with out.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    existing.append(json.loads(line))

    rows, input_source = _read_bocm_rows()
    new_records = []
    for row in rows:
        rec = _row_to_record(row)
        rid = rec.get("id")
        if not rid or rid in seen:
            continue
        if not municipio_matches(rec.get("municipio"), aliases := manifest.proyectos.municipio_aliases):
            continue
        if manifest.proyectos.source == "bocm_legacy" and not rec.get("es_relevante"):
            continue
        new_records.append(rec)
        seen.add(rid)

    merged = existing + new_records
    _write_jsonl(out, merged)
    state["seen_ids"] = list(seen)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["count"] = len(merged)
    _save_state(state_path, state)
    return {
        "added": len(new_records),
        "total": len(merged),
        "path": str(out),
        "input_source": input_source,
    }
