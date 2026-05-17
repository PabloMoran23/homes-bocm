"""Filtros por fecha para expedientes y documentos VISOR/NTI."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def parse_es_date(raw: str | None) -> datetime | None:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip().split()[0]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def expediente_year(grupo: str) -> int | None:
    parts = (grupo or "").strip().split("/")
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return None


def any_tramite_since(rec: dict[str, Any], since_year: int) -> bool:
    for hito in rec.get("tramitacion") or []:
        if not isinstance(hito, dict):
            continue
        dt = parse_es_date(hito.get("fecha"))
        if dt and dt.year >= since_year:
            return True
    return False


def expediente_is_recent(
    rec: dict[str, Any],
    grupo: str,
    *,
    since_year: int,
) -> bool:
    """Expediente reciente si el año del número o algún hito de tramitación >= since_year."""
    ey = expediente_year(grupo)
    if ey is not None and ey >= since_year:
        return True
    return any_tramite_since(rec, since_year)


def document_date_year(meta: dict[str, Any]) -> int | None:
    for key in ("fechaDocumento", "fechaCreacion"):
        dt = parse_es_date(meta.get(key))
        if dt:
            return dt.year
    return None


def document_is_recent(
    meta: dict[str, Any],
    rec: dict[str, Any],
    grupo: str,
    *,
    since_year: int,
) -> bool:
    """
    Documento reciente si tiene fecha >= since_year.
    Sin fecha en listado IAM: incluir solo si el expediente es reciente.
    Sin fecha en listado HTM: excluir (no podemos datarlo).
    """
    dy = document_date_year(meta)
    if dy is not None:
        return dy >= since_year
    kind = meta.get("listadoKind") or rec.get("ntiListadoKind")
    if kind == "iam":
        return expediente_is_recent(rec, grupo, since_year=since_year)
    return False


def filter_nti_documents(
    docs: list[dict[str, Any]],
    rec: dict[str, Any],
    grupo: str,
    *,
    since_year: int | None,
) -> list[dict[str, Any]]:
    if since_year is None:
        return docs
    if not expediente_is_recent(rec, grupo, since_year=since_year):
        return []
    return [d for d in docs if document_is_recent(d, rec, grupo, since_year=since_year)]
