"""Cadencia de scrapers municipales: due-queue sobre last_ingest_at.

No lanza los ~240 municipios de golpe (timeout de GitHub Actions y un fallo
bloquearía el resto). Un cron diario elige los más viejos / nunca ingestados
y corre un lote.

Fuente del timestamp: homes.municipio.last_ingest_at (Supabase), no queue.yaml.
Madrid capital se excluye: tiene refresh-web-data.yml.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from municipio.manifest import MUNICIPIOS_DIR, POC_ROOT, list_manifest_slugs, load_manifest, load_yaml
from municipio.orchestrator import run

DB_DIR = POC_ROOT / "db"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

DEFAULT_INTERVAL_DAYS = 15
DEFAULT_LIMIT = 16
DEFAULT_STEP = "update"
SKIP_SLUGS = {"madrid"}


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        ts = raw
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts
    text = str(raw).strip()
    if not text:
        return None
    try:
        ts = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts


def _schedule_config(slug: str) -> dict[str, Any]:
    path = MUNICIPIOS_DIR / slug / "manifest.yaml"
    if not path.is_file():
        return {}
    try:
        data = load_yaml(path)
    except Exception:
        return {}
    raw = data.get("schedule") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def _truthy(val: Any, default: bool = True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "sí", "si")


def _load_timestamps() -> dict[str, datetime]:
    try:
        from ingest import fetch_last_ingest_at
    except Exception:
        return {}
    try:
        return fetch_last_ingest_at()
    except Exception as exc:
        print(f"aviso schedule: no se pudo leer last_ingest_at ({exc})", flush=True)
        return {}


def _age_days(ts: datetime | None, *, now: datetime) -> float | None:
    if ts is None:
        return None
    return round((now - ts).total_seconds() / 86400.0, 2)


def due_plan(
    *,
    interval_days: int = DEFAULT_INTERVAL_DAYS,
    limit: int = DEFAULT_LIMIT,
    include_madrid: bool = False,
    slugs: list[str] | None = None,
    timestamps: dict[str, datetime] | None = None,
    now: datetime | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Municipios a refrescar: nunca ingestados primero, luego los más viejos."""
    now = now or datetime.now(UTC)
    available = slugs or list_manifest_slugs()
    stamps = timestamps if timestamps is not None else _load_timestamps()
    due: list[dict[str, Any]] = []
    fresh: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for slug in available:
        cfg = _schedule_config(slug)
        enabled = _truthy(cfg.get("enabled"), default=True)
        force_madrid = slug == "madrid" and include_madrid
        if slug in SKIP_SLUGS and not force_madrid:
            skipped.append({"slug": slug, "reason": cfg.get("notes") or "madrid_own_workflow"})
            continue
        if not enabled and not force_madrid:
            skipped.append({"slug": slug, "reason": cfg.get("notes") or "schedule.enabled=false"})
            continue
        interval = int(cfg.get("interval_days") or interval_days)
        ts = stamps.get(slug)
        age = _age_days(ts, now=now)
        row = {
            "slug": slug,
            "last_ingest_at": ts.isoformat() if ts else None,
            "age_days": age,
            "interval_days": interval,
        }
        cutoff = now - timedelta(days=interval)
        if force or ts is None or ts < cutoff:
            due.append(row)
        else:
            fresh.append(row)

    due.sort(key=lambda r: (r["last_ingest_at"] is not None, r["last_ingest_at"] or ""))
    picked = due[: max(0, int(limit))]
    return {
        "now": now.isoformat(),
        "interval_days": interval_days,
        "limit": limit,
        "manifests": len(available),
        "due_total": len(due),
        "fresh_total": len(fresh),
        "skipped": skipped,
        "picked": picked,
        "due_remaining": due[len(picked) :],
    }


def _step_errors(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for name, payload in (result.get("steps") or {}).items():
        if isinstance(payload, dict) and payload.get("error"):
            errors.append(name)
    return errors


def _step_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"status": "ok"}
    if payload.get("error"):
        return {"error": payload.get("error"), "type": payload.get("type")}
    out = {k: payload[k] for k in ("status", "rows", "proyectos", "licencias", "reason") if k in payload}
    return out or {"status": "ok"}


def run_due(
    *,
    interval_days: int = DEFAULT_INTERVAL_DAYS,
    limit: int = DEFAULT_LIMIT,
    step: str = DEFAULT_STEP,
    include_madrid: bool = False,
    slugs: list[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    plan = due_plan(
        interval_days=interval_days,
        limit=limit,
        include_madrid=include_madrid,
        slugs=slugs,
        force=force,
    )
    out: dict[str, Any] = {
        "plan": {
            k: plan[k]
            for k in (
                "now",
                "interval_days",
                "limit",
                "manifests",
                "due_total",
                "fresh_total",
                "skipped",
                "picked",
            )
        },
        "step": step,
        "dry_run": dry_run,
        "results": [],
        "ok": 0,
        "failed": 0,
    }
    if dry_run:
        out["status"] = "dry_run"
        return out

    for item in plan["picked"]:
        slug = item["slug"]
        print(f"==> schedule {slug}", flush=True)
        try:
            result = run(load_manifest(slug), step)
        except Exception as exc:
            row = {
                "slug": slug,
                "ok": False,
                "error": str(exc),
                "type": type(exc).__name__,
            }
            out["results"].append(row)
            out["failed"] += 1
            print(f"  FAIL {slug}: {exc}", flush=True)
            continue
        errors = _step_errors(result)
        ok = not errors
        row = {
            "slug": slug,
            "ok": ok,
            "failed_steps": errors,
            "steps": {
                name: _step_summary(payload)
                for name, payload in (result.get("steps") or {}).items()
            },
        }
        out["results"].append(row)
        if ok:
            out["ok"] += 1
            print(f"  OK {slug}", flush=True)
        else:
            out["failed"] += 1
            print(f"  FAIL {slug}: {errors}", flush=True)

    out["status"] = "ok" if out["failed"] == 0 else "partial"
    return out
