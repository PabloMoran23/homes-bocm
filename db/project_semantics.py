"""Versioned municipal record contract. No title/date/type inference.

Evidence paths address the original adapter record, stored with each derivation.
Descriptions are source prose, never treated as verified structured facts.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

CONTRACT_VERSION = "municipal-semantics/1"
TEMPLATE_VERSION = "municipal-facts/1"
DESCRIPTION_ALIASES = ("descripcion", "resumen", "resumen_contenido", "bocm_resumen")
PHASE_ALIASES = ("fase", "estado_tramitacion", "bocm_estado_tramitacion")
PHASES = {
    "aprobación inicial": "aprobacion_inicial", "aprobacion inicial": "aprobacion_inicial",
    "aprobación provisional": "aprobacion_provisional", "aprobacion provisional": "aprobacion_provisional",
    "aprobación definitiva": "aprobacion_definitiva", "aprobacion definitiva": "aprobacion_definitiva",
    "información pública": "informacion_publica", "informacion publica": "informacion_publica",
    "en tramitación": "en_tramitacion", "en tramitacion": "en_tramitacion",
    "aprobacion_inicial": "aprobacion_inicial", "aprobacion_definitiva": "aprobacion_definitiva",
    "aprobacion_provisional": "aprobacion_provisional", "informacion_publica": "informacion_publica",
    "en_tramitacion": "en_tramitacion",
}


def text(value: Any) -> str | None:
    return " ".join(value.split()) or None if isinstance(value, str) else None


def source_record(rec: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in rec.items() if k != "_semantic_contract"}


def source_hash(rec: dict[str, Any]) -> str:
    hashed = {k: v for k, v in source_record(rec).items() if k != "_entity_policy"}
    return hashlib.sha256(json.dumps(hashed, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), default=str).encode()).hexdigest()


def derive(rec: dict[str, Any]) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    unknown: dict[str, str] = {}
    url = next((text(rec.get(k)) for k in ("url", "enlace", "pdf_url", "visor_url") if text(rec.get(k))), None)

    def fact(name: str, value: str, field: str) -> str:
        facts.append({"name": name, "value": value, "evidence": {"field": field, "url": url}})
        return value

    def alias(name: str, fields: tuple[str, ...], *, dates: bool = False) -> str | None:
        candidates = [(k, text(rec.get(k))) for k in fields if text(rec.get(k))]
        if not candidates:
            unknown[name] = "missing_explicit_field"
            return None
        if dates:
            valid = []
            for k, v in candidates:
                try:
                    valid.append((k, date.fromisoformat(v).isoformat()))
                except ValueError:
                    unknown[name] = "invalid_calendar_date"
                    return None
            candidates = valid
        if len({v.casefold() for _, v in candidates}) > 1:
            unknown[name] = "conflicting_aliases"
            return None
        field, value = candidates[0]
        return fact(name, value, field)

    title = text(rec.get("titulo")) or text(rec.get("denominacion"))
    descriptions = [(k, text(rec.get(k))) for k in DESCRIPTION_ALIASES if text(rec.get(k))]
    descriptions = [(k, v) for k, v in descriptions if not title or v.casefold() != title.casefold()]
    description = None
    if descriptions:
        field, value = descriptions[0]
        description = {"value": value, "evidence": {"field": field, "url": url}}
    else:
        unknown["descripcion"] = "missing_description_or_title_copy"
    instrument = alias("tipo", ("tipo", "tipo_legal", "tipo_figura", "bocm_tipo_instrumento"))
    phase = alias("fase", PHASE_ALIASES)
    normalized = PHASES.get(phase.casefold()) if phase else None
    if phase and (phase.casefold() == (instrument or "").casefold() or not normalized):
        facts[:] = [f for f in facts if f["name"] != "fase"]
        unknown["fase"] = "instrument_is_not_phase" if phase.casefold() == (instrument or "").casefold() else "unrecognized_phase"
        phase = None
    publication = alias("fecha_publicacion", ("fecha_publicacion", "fecha_publicación", "bocm_pub_date"), dates=True)
    agreement = alias("fecha_acuerdo", ("fecha_acuerdo", "bocm_fecha_acuerdo"), dates=True)
    approval = alias("fecha_aprob", ("fecha_aprob", "fecha_aprobacion"), dates=True)
    if text(rec.get("fecha")):
        unknown["fecha"] = "generic_date_has_no_declared_meaning"
    # Only explicitly labelled values enter the factual template. No free-text metrics.
    clauses = []
    summary_facts = []
    for name, label in (("tipo", "Instrumento"), ("fase", "Fase administrativa"),
                        ("fecha_publicacion", "Publicado el"), ("fecha_acuerdo", "Acuerdo fechado el"),
                        ("fecha_aprob", "Aprobación fechada el")):
        f = next((f for f in facts if f["name"] == name), None)
        if f:
            clauses.append(f"{label}: {f['value']}")
            summary_facts.append(name)
    summary = "; ".join(clauses) + "." if clauses else None
    if summary and title and summary.casefold() == title.casefold():
        summary = None
        summary_facts = []
    return {"contract_version": CONTRACT_VERSION, "template_version": TEMPLATE_VERSION,
            "source_hash": source_hash(rec), "description": description, "facts": facts,
            "unknown": unknown, "fase": phase, "fase_normalizada": normalized,
            "fecha_publicacion": publication, "fecha_acuerdo": agreement, "fecha_aprob": approval,
            "summary": summary, "summary_facts": summary_facts,
            "status": "factual" if summary else "discovered"}


def apply(rec: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    derived = derive(rec)
    row.update(fase=derived["fase"], fase_normalizada=derived["fase_normalizada"],
               fecha_aprob=derived["fecha_aprob"], bocm_pub_date=derived["fecha_publicacion"],
               resumen_contenido=derived["summary"], bocm_resumen=derived["summary"])
    return derived
