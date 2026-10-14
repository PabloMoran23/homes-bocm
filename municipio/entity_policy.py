"""Clasificación determinista de entidades; nunca convierte dudas en actividad.

La anotación es un derivado: los campos originales se conservan. Cambiar reglas
requiere aumentar RULE_VERSION; las categorías tienen además hash automático.
"""
from __future__ import annotations

import hashlib
from datetime import date
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

RULE_VERSION = "h01-v1"
_CATEGORIES_BYTES = (Path(__file__).parent / "policies/entity_categories.json").read_bytes()
CATEGORIES = json.loads(_CATEGORIES_BYTES)["outside_domain"]
POLICY_VERSION = RULE_VERSION + "-" + hashlib.sha256(_CATEGORIES_BYTES).hexdigest()[:12]
POLICY_KEY = "_entity_policy"
ELIGIBLE_TYPES = frozenset({"expediente", "actuacion"})


def norm(value: Any) -> str:
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower().strip()


def original(record: dict) -> dict:
    return {k: v for k, v in record.items() if k != POLICY_KEY}


def content_hash(record: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in original(record).items() if k != "_semantic_contract"}, sort_keys=True, ensure_ascii=False,
                                     default=str, separators=(",", ":")).encode()).hexdigest()


def classify(record: dict, *, kind: str = "proyecto") -> dict:
    fingerprint = content_hash(record)
    previous = record.get(POLICY_KEY)
    if isinstance(previous, dict) and previous.get("version") == POLICY_VERSION and previous.get("content_hash") == fingerprint and previous.get("kind") == kind:
        return previous
    title = norm(record.get("titulo") or record.get("denominacion") or record.get("objeto") or record.get("bocm_title"))
    text = " ".join([title, norm(record.get("tipo") or record.get("tipo_expediente") or record.get("tipo_figura")),
                     norm(record.get("categoria") or record.get("category"))])
    url = str(record.get("url") or record.get("enlace") or record.get("visor_url") or record.get("pdf_url") or record.get("bocm_pdf_url") or "")
    reference = record.get("expte") or record.get("expediente") or record.get("expediente_grupo") or record.get("exp_numero_original") or record.get("numero_expediente")
    reference = reference if reference and re.search(r"[0-9]", str(reference)) else None
    source = bool(urlparse(url).netloc) or bool(urlparse(str(record.get("source_dataset") or "")).netloc and record.get("id_origen"))
    structure = norm(record.get("entity_type") or record.get("source_entity_type"))
    state = norm(record.get("estado") or record.get("estado_tramitacion") or record.get("fase"))
    try:
        grant_date = date.fromisoformat(str(record.get("fecha_concesion") or "")[:10])
    except ValueError:
        grant_date = None
    granted = bool(grant_date) or state in {"concedida", "concedido", "otorgada", "otorgado"} or bool(re.search(r"\b(?:concesion de|se concede|se otorga|licencia concedida)\b", title))

    def result(entity_type: str, reason: str, eligible: bool = False) -> dict:
        return {"version": POLICY_VERSION, "content_hash": fingerprint, "kind": kind,
                "entity_type": entity_type, "reason_code": reason, "activity_eligible": eligible,
                "grant_evidenced": granted if kind == "licencia" else False}

    for category, phrases in CATEGORIES.items():
        if any(phrase in text for phrase in phrases):
            return result("fuera_dominio", "outside_domain:" + category)
    explicit_form = bool(re.search(r"^(?:formulario|impreso|modelo de solicitud|autoliquidacion|tasas? urbanisticas)\b", title))
    generic = bool(re.search(r"\b(?:como solicitar|requisitos para|solicitud de (?:licencia|aprobacion|permiso)|solicitud permiso obras)\b", title))
    if structure in {"tramite", "formulario", "service", "procedure"} or explicit_form or (generic and not (reference and source)):
        return result("tramite_reutilizable", "reusable_procedure")
    if structure in {"normativa", "regulation"} or re.search(r"^(?:ordenanza|normativa|reglamento)\b", title):
        return result("normativa", "regulation_resource")
    urban = bool(re.search(r"\b(?:urban\w*|planeamiento|viviendas?|edifica\w*|obras?|parcela\w*|sector|suelo|constru\w*|plan parcial|plan especial|plan general|pgou|modificacion puntual|estudio de detalle|reparcelacion)\b", text))
    official_sigma = record.get("sigma_layer_kind") or norm(record.get("fuente") or record.get("source")) in {"sigma", "madrid-sigma"}
    if reference and source and (urban or official_sigma):
        if kind == "licencia" and not granted:
            return result("expediente", "grant_not_evidenced")
        return result("expediente", "referenced_source_record", True)
    # Un acto publicado identificable también puede ser una actuación sin expte.
    bulletin = norm(record.get("fuente") or record.get("source") or record.get("bocm_source_id")) in {"bocm", "bocm_legacy"}
    official_host = (urlparse(url).hostname or "").lower()
    act = re.search(r"\b(?:aprobacion (?:inicial|definitiva|provisional)|se aprueba|se concede|se otorga)\b", title)
    municipality = record.get("municipio") or record.get("municipio_slug") or record.get("bocm_municipio")
    if bulletin and (official_host == "bocm.es" or official_host.endswith(".bocm.es")) and act and urban and municipality:
        return result("actuacion", "identified_published_act", kind != "licencia" or granted)
    # SIGMA: identificador del catálogo oficial, no un id arbitrario del scraper.
    if str(record.get("object_id") or "").isdigit() and record.get("sigma_layer_kind") and source:
        return result("actuacion", "official_catalog_identity", kind != "licencia" or granted)
    # Licencias de datos abiertos: procedencia y referencia estable de la fila.
    madrid_open_data = norm(record.get("fuente") or record.get("source")) == "madrid-opendata"
    if kind == "licencia" and granted and ((record.get("source_dataset") and record.get("id_origen") and urban) or (madrid_open_data and record.get("licencia_key"))):
        return result("actuacion", "granted_open_data_record", True)
    if structure in {"documento", "document"} or urlparse(url).path.lower().endswith(".pdf"):
        return result("documento", "document_without_activity_identity")
    if structure in {"anuncio", "notice"} or title.startswith("anuncio"):
        return result("anuncio", "notice_without_activity_identity")
    if "/catalog/" in urlparse(url).path.lower():
        return result("pendiente", "catalog_requires_evidence")
    return result("pendiente", "insufficient_identity_evidence")


def annotate(record: dict, *, kind: str = "proyecto") -> dict:
    return {**record, POLICY_KEY: classify(record, kind=kind)}


def annotate_jsonl(path: Path, *, kind: str) -> dict:
    """Punto común de todos los adaptadores; reemplazo atómico e idempotente."""
    if not path.is_file():
        return {"total": 0, "unknown": 0}
    rows = [annotate(json.loads(line), kind=kind) for line in path.read_text().splitlines() if line.strip()]
    unknown = sum(r[POLICY_KEY]["entity_type"] == "pendiente" for r in rows)
    report_path = path.with_suffix(".entities.json")
    prior = json.loads(report_path.read_text()) if report_path.is_file() else {}
    ratio = unknown / len(rows) if rows else 0
    spike = unknown >= 10 and ratio >= .25 and (not prior or ratio > prior.get("unknown_ratio", 0) + .15)
    spike = spike or (prior.get("status") == "adapter_incident" and unknown >= 10 and ratio >= .25)
    report = {"version": POLICY_VERSION, "total": len(rows), "unknown": unknown, "unknown_ratio": ratio,
              "status": "adapter_incident" if spike else "ok", "reason_code": "unknown_entity_spike" if spike else None}
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    if payload != path.read_text():
        tmp = path.with_suffix(".jsonl.entities.tmp")
        tmp.write_text(payload)
        tmp.replace(path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report
