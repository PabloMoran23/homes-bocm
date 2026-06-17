from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from municipio.manifest import MUNICIPIOS_DIR, POC_ROOT, list_manifest_slugs, slugify

QUEUE_PATH = MUNICIPIOS_DIR / "queue.yaml"
SUMMARY_JSON = POC_ROOT / "web" / "public" / "data" / "summary.json"

# Municipios con pipeline propio (no portal genérico).
SKIP_NAMES = {
    "madrid",
}

# Ya implementados antes de la cola automática.
DONE_SLUGS = {
    "pozuelo-de-alarcon",
    "mostoles",
    "getafe",
}


@dataclass
class QueueEntry:
    slug: str
    nombre: str
    bocm_count: int
    status: str
    attempts: int = 0
    last_run: str | None = None
    last_error: str | None = None
    pr_url: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "nombre": self.nombre,
            "bocm_count": self.bocm_count,
            "status": self.status,
            "attempts": self.attempts,
            "last_run": self.last_run,
            "last_error": self.last_error,
            "pr_url": self.pr_url,
            "notes": self.notes,
        }


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as e:
        raise RuntimeError("PyYAML requerido: pip install -r requirements-municipio.txt") from e
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _dump_yaml(path: Path, data: dict[str, Any]) -> None:
    try:
        import yaml
    except ImportError as e:
        raise RuntimeError("PyYAML requerido: pip install -r requirements-municipio.txt") from e
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def _parse_entries(raw: dict[str, Any]) -> list[QueueEntry]:
    items = raw.get("municipios") or []
    out: list[QueueEntry] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            QueueEntry(
                slug=str(item.get("slug") or ""),
                nombre=str(item.get("nombre") or ""),
                bocm_count=int(item.get("bocm_count") or 0),
                status=str(item.get("status") or "pending"),
                attempts=int(item.get("attempts") or 0),
                last_run=item.get("last_run"),
                last_error=item.get("last_error"),
                pr_url=item.get("pr_url"),
                notes=str(item.get("notes") or ""),
            )
        )
    return out


def load_queue(path: Path = QUEUE_PATH) -> dict[str, Any]:
    if not path.is_file():
        return {"version": 1, "updated_at": None, "municipios": []}
    return _load_yaml(path)


def save_queue(data: dict[str, Any], path: Path = QUEUE_PATH) -> None:
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _dump_yaml(path, data)


def _entry_index(entries: list[QueueEntry], slug: str) -> int:
    for i, e in enumerate(entries):
        if e.slug == slug:
            return i
    return -1


def init_from_summary(
    *,
    min_bocm_count: int = 20,
    exclude_non_cm: bool = True,
    path: Path = QUEUE_PATH,
) -> dict[str, Any]:
    if not SUMMARY_JSON.is_file():
        raise FileNotFoundError(f"No existe {SUMMARY_JSON}")

    summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    by_municipio = summary.get("byMunicipio") or []
    existing_manifests = set(list_manifest_slugs())
    entries: list[QueueEntry] = []

    for item in by_municipio:
        nombre = str(item.get("name") or "").strip()
        count = int(item.get("count") or 0)
        if not nombre or count < min_bocm_count:
            continue
        slug = slugify(nombre)
        norm = slug.replace("-", " ")
        if norm in SKIP_NAMES or nombre.lower() == "madrid":
            entries.append(
                QueueEntry(
                    slug=slug,
                    nombre=nombre,
                    bocm_count=count,
                    status="skipped",
                    notes="Pipeline propio (Madrid capital / SIGMA)",
                )
            )
            continue
        if exclude_non_cm and nombre in {"Coín", "Cártama", "Mijas", "Valladolid"}:
            continue
        if slug in DONE_SLUGS or slug in existing_manifests:
            status = "done"
            notes = "Adapter ya implementado"
        else:
            status = "pending"
            notes = ""
        entries.append(
            QueueEntry(
                slug=slug,
                nombre=nombre,
                bocm_count=count,
                status=status,
                notes=notes,
            )
        )

    data = {
        "version": 1,
        "description": "Cola de onboarding de portales municipales (Comunidad de Madrid)",
        "min_bocm_count": min_bocm_count,
        "municipios": [e.to_dict() for e in entries],
    }
    save_queue(data, path)
    return data


def pick_next(path: Path = QUEUE_PATH) -> dict[str, Any] | None:
    data = load_queue(path)
    entries = _parse_entries(data)
    for e in entries:
        if e.status == "pending":
            return e.to_dict()
    for e in entries:
        if e.status == "failed" and e.attempts < 3:
            return e.to_dict()
    return None


def claim_next(path: Path = QUEUE_PATH) -> dict[str, Any] | None:
    data = load_queue(path)
    entries = _parse_entries(data)
    now = datetime.now(timezone.utc).isoformat()
    target: QueueEntry | None = None
    for e in entries:
        if e.status == "pending":
            target = e
            break
    if target is None:
        for e in entries:
            if e.status == "failed" and e.attempts < 3:
                target = e
                break
    if target is None:
        return None
    idx = _entry_index(entries, target.slug)
    entries[idx].status = "in_progress"
    entries[idx].attempts += 1
    entries[idx].last_run = now
    entries[idx].last_error = None
    data["municipios"] = [e.to_dict() for e in entries]
    save_queue(data, path)
    return entries[idx].to_dict()


def mark_status(
    slug: str,
    status: str,
    *,
    error: str | None = None,
    pr_url: str | None = None,
    notes: str | None = None,
    path: Path = QUEUE_PATH,
) -> dict[str, Any]:
    data = load_queue(path)
    entries = _parse_entries(data)
    idx = _entry_index(entries, slug)
    if idx < 0:
        raise KeyError(f"Municipio no está en la cola: {slug}")
    entries[idx].status = status
    entries[idx].last_run = datetime.now(timezone.utc).isoformat()
    if error is not None:
        entries[idx].last_error = error
    if pr_url is not None:
        entries[idx].pr_url = pr_url
    if notes is not None:
        entries[idx].notes = notes
    data["municipios"] = [e.to_dict() for e in entries]
    save_queue(data, path)
    return entries[idx].to_dict()


def queue_status(path: Path = QUEUE_PATH) -> dict[str, Any]:
    data = load_queue(path)
    entries = _parse_entries(data)
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.status] = counts.get(e.status, 0) + 1
    return {
        "updated_at": data.get("updated_at"),
        "total": len(entries),
        "by_status": counts,
        "next": pick_next(path),
        "done": [e.to_dict() for e in entries if e.status == "done"],
        "pending": [e.to_dict() for e in entries if e.status == "pending"][:10],
    }
