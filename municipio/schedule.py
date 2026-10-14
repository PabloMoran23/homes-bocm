"""Review cadence uses durable source review timestamps, not DB write times.

Madrid capital keeps its independent workflow. The hourly dispatcher leases and
checkpoints work in PostgreSQL; unavailable queue state fails closed.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from municipio.manifest import MUNICIPIOS_DIR, POC_ROOT, list_manifest_slugs, load_manifest, load_yaml

DB_DIR = POC_ROOT / "db"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

DEFAULT_INTERVAL_DAYS = 15
DEFAULT_LIMIT = 3
DEFAULT_STEP = "update"
SKIP_SLUGS = {"madrid"}


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
    from ingest import connect
    # Fail closed when durable state is unavailable; DB writes are not reviews.
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT slug,last_complete FROM homes.refresh_review WHERE enabled=1 AND last_complete IS NOT NULL")
            return {slug: datetime.fromtimestamp(ts, UTC) for slug, ts in cur.fetchall()}


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
    """Municipios a revisar: nunca revisados primero, luego los más viejos."""
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
            "last_review_at": ts.isoformat() if ts else None,
            "age_days": age,
            "interval_days": interval,
        }
        cutoff = now - timedelta(days=interval)
        if force or ts is None or ts < cutoff:
            due.append(row)
        else:
            fresh.append(row)

    due.sort(key=lambda r: (r["last_review_at"] is not None, r["last_review_at"] or ""))
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
    if step != "update" or force or include_madrid or slugs:
        raise ValueError("Durable automatic refresh supports update only; use municipio run for explicit maintenance")
    if interval_days != 15:
        raise ValueError("The product review cadence is 15 days")
    from municipio.refresh_dispatch import census, dispatch
    from municipio.refresh_queue import Queue
    from ingest import connect
    import time
    if dry_run:
        return {"status": "dry_run", "plan": due_plan(limit=limit)}
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO homes, public")
        conn.commit()
        queue = Queue(conn)
        queue.reconcile(census(),time.time())
        results = dispatch(queue,limit=limit)
        metrics = queue.metrics(time.time())
        return {"results":results,"metrics":metrics,
                "ok":sum(r.get("complete",False) for r in results),
                "failed":sum(not r.get("complete",False) for r in results),
                "status":"partial" if metrics["sla_violations"] else "ok"}
