"""Deterministic territorial policy, shared by ingestion and historical export/replay.

Never derive jurisdiction from coordinates, identifiers, filenames or a missing source.
The origin record remains intact; only the derived _territory result is replaceable.
"""
from __future__ import annotations

from typing import Any

VERSION = "license-territory-v1"
MADRID_CODE = "28079"
DATASET_URL = "https://datos.madrid.es/dataset/300193-0-licencias-urbanisticas"
SOURCE_SCOPES = {"madrid-opendata": "madrid"}
CODES = {"madrid": MADRID_CODE, "valladolid": "47186"}


def resolve_territory(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("raw_json")
    raw = raw if isinstance(raw, dict) else row
    # Derived results are deliberately ignored, so new rules also replay historical rows.
    source = row.get("fuente") or row.get("source") or raw.get("fuente") or raw.get("source")
    slug = row.get("municipio_slug") or raw.get("municipio_slug")
    slug = str(slug).strip().lower() if slug else None
    source = str(source).strip().lower() if source else None
    evidence = raw.get("_territorial_origin") or {}
    origin_slug = evidence.get("municipio_slug") if isinstance(evidence, dict) else None
    if origin_slug and evidence.get("adapter") and evidence.get("url"):
        origin_slug = str(origin_slug).strip().lower()
    else:
        origin_slug = None
    scoped = SOURCE_SCOPES.get(source)
    candidates = {s for s in (slug, origin_slug, scoped) if s}
    reason = None
    if len(candidates) > 1:
        reason = "conflicting_municipality_evidence"
    elif not candidates or not (origin_slug or source):
        reason = "missing_municipality_provenance"
    municipality = next(iter(candidates)) if reason is None else None
    return {"version": VERSION, "municipio_slug": municipality,
            "municipioCode": CODES.get(municipality), "status": "quarantined" if reason else "accepted",
            "reason": reason, "evidence": {"source": source, "declaredMunicipio": slug,
                                          "adapterOrigin": evidence or None}}


def territorial_raw(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "_territory": resolve_territory(row)}
