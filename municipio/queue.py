from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from municipio.manifest import MUNICIPIOS_DIR, POC_ROOT, list_manifest_slugs, slugify

QUEUE_PATH = MUNICIPIOS_DIR / "queue.yaml"
SUMMARY_JSON = POC_ROOT / "web" / "public" / "data" / "summary.json"

AUTOMATION_BRANCH_RE = re.compile(r"^automation/municipio-(.+)$")
MANIFEST_PATH_RE = re.compile(r"^data/municipios/([^/]+)/manifest\.yaml$")

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


def _gh_repo() -> str | None:
    env = os.environ.get("GITHUB_REPOSITORY")
    if env:
        return env
    try:
        out = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    url = (out.stdout or "").strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", url)
    return m.group(1) if m else None


def _gh_json(subcmd: list[str], *, fields: str) -> Any:
    repo = _gh_repo()
    cmd = ["gh", *subcmd, "--json", fields]
    if repo:
        cmd.extend(["--repo", repo])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout or "null")
    except json.JSONDecodeError:
        return None


@lru_cache(maxsize=1)
def open_pr_by_slug() -> dict[str, str]:
    """
    Slugs con PR abierta en GitHub → URL de la PR.
    Detecta ramas automation/municipio-<slug> o manifest en el diff.
    """
    prs = _gh_json(["pr", "list", "--state", "open"], fields="number,headRefName,title,url")
    if not isinstance(prs, list):
        return {}

    out: dict[str, str] = {}
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        number = pr.get("number")
        url = str(pr.get("url") or "")
        head = str(pr.get("headRefName") or "")
        m = AUTOMATION_BRANCH_RE.match(head)
        if m:
            out.setdefault(m.group(1), url)
            continue
        if number is None:
            continue
        files = _gh_json(["pr", "view", str(number)], fields="files")
        if not isinstance(files, dict):
            continue
        for item in files.get("files") or []:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            m2 = MANIFEST_PATH_RE.match(path)
            if m2:
                out.setdefault(m2.group(1), url)
                break
    return out


def _manifest_exists(slug: str) -> bool:
    return (MUNICIPIOS_DIR / slug / "manifest.yaml").is_file()


def _skip_reason(entry: QueueEntry, *, open_prs: dict[str, str]) -> str | None:
    if entry.status in {"done", "skipped"}:
        return f"status:{entry.status}"
    if _manifest_exists(entry.slug):
        return "manifest_en_main"
    pr_url = open_prs.get(entry.slug)
    if pr_url:
        return f"pr_abierta:{pr_url}"
    return None


def _candidate_entries(entries: list[QueueEntry]) -> list[QueueEntry]:
    open_prs = open_pr_by_slug()
    candidates: list[QueueEntry] = []
    for e in entries:
        if e.status == "pending" and _skip_reason(e, open_prs=open_prs) is None:
            candidates.append(e)
    if candidates:
        return candidates
    for e in entries:
        if e.status == "failed" and e.attempts < 3 and _skip_reason(e, open_prs=open_prs) is None:
            candidates.append(e)
    return candidates


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
    entries = _parse_entries(load_queue(path))
    candidates = _candidate_entries(entries)
    return candidates[0].to_dict() if candidates else None


def claim_next(path: Path = QUEUE_PATH) -> dict[str, Any] | None:
    data = load_queue(path)
    entries = _parse_entries(data)
    candidates = _candidate_entries(entries)
    if not candidates:
        return None
    target = candidates[0]
    now = datetime.now(timezone.utc).isoformat()
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
    open_prs = open_pr_by_slug()
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.status] = counts.get(e.status, 0) + 1

    skipped_open_pr = []
    for e in entries:
        if e.status != "pending":
            continue
        reason = _skip_reason(e, open_prs=open_prs)
        if reason and reason.startswith("pr_abierta:"):
            skipped_open_pr.append(
                {
                    "slug": e.slug,
                    "nombre": e.nombre,
                    "pr_url": reason.split(":", 1)[1],
                }
            )

    return {
        "updated_at": data.get("updated_at"),
        "total": len(entries),
        "by_status": counts,
        "next": pick_next(path),
        "open_prs": open_prs,
        "skipped_pending_with_open_pr": skipped_open_pr,
        "done": [e.to_dict() for e in entries if e.status == "done"],
        "pending": [e.to_dict() for e in entries if e.status == "pending"][:10],
    }
