"""Selección de PDFs por expediente según rol documental (pipeline inteligente)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sector_geometry.madrid_nti_doc_roles import (
    ROLES_EXTRACT_DEFAULT,
    classify_doc_role,
    role_extract_priority,
    should_skip_role,
)


def build_job_from_path(
    grupo: str,
    pdf_path: Path,
    *,
    meta: dict[str, Any] | None = None,
    rec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = meta or {}
    titulo = (meta.get("titulo") or meta.get("tooltip") or pdf_path.name).strip()
    ruta = meta.get("rutaCarpetas") or ""
    role = classify_doc_role(titulo, ruta, pdf_path.name)
    from sector_geometry.madrid_nti_doc_roles import infer_doc_type

    return {
        "grupo": grupo,
        "rec": rec or {},
        "meta": meta,
        "local_path": pdf_path,
        "doc_role": role,
        "doc_type": infer_doc_type(titulo, ruta, pdf_path.name),
        "doc_titulo": titulo,
        "doc_ruta": ruta,
    }


def select_jobs_for_expediente(
    jobs: list[dict[str, Any]],
    *,
    max_pdfs: int = 8,
    roles: set[str] | None = None,
    include_skipped: bool = False,
) -> list[dict[str, Any]]:
    """
    Elige hasta max_pdfs documentos por expediente: uno por rol prioritario.
    jobs deben ser del mismo grupo.
    """
    allowed = roles or ROLES_EXTRACT_DEFAULT
    by_role: dict[str, dict[str, Any]] = {}

    for job in jobs:
        role = job.get("doc_role") or classify_doc_role(
            job.get("doc_titulo") or job["local_path"].name,
            job.get("doc_ruta") or "",
            job["local_path"].name,
        )
        job["doc_role"] = role
        if not include_skipped and should_skip_role(role):
            continue
        if role not in allowed and not include_skipped:
            continue
        prev = by_role.get(role)
        if prev is None or role_extract_priority(role) < role_extract_priority(
            prev.get("doc_role") or "otro"
        ):
            by_role[role] = job
        elif prev is not None:
            # mismo rol: preferir AD sobre AI en ruta
            ruta = (job.get("doc_ruta") or "").lower()
            prev_ruta = (prev.get("doc_ruta") or "").lower()
            if "definitiva" in ruta and "definitiva" not in prev_ruta:
                by_role[role] = job

    picked = sorted(by_role.values(), key=lambda j: role_extract_priority(j.get("doc_role") or "otro"))
    return picked[:max_pdfs]


def select_pipeline_jobs(
    all_jobs: list[dict[str, Any]],
    *,
    max_pdfs_per_exp: int = 8,
    roles: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Agrupa jobs por expediente y aplica selección."""
    by_g: dict[str, list[dict[str, Any]]] = {}
    for job in all_jobs:
        by_g.setdefault(job["grupo"], []).append(job)

    out: list[dict[str, Any]] = []
    for grupo in sorted(by_g):
        out.extend(
            select_jobs_for_expediente(
                by_g[grupo],
                max_pdfs=max_pdfs_per_exp,
                roles=roles,
            )
        )
    return out
