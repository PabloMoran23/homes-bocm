"""Clasificación de documentos NTI por rol y utilidad para extracción de métricas."""

from __future__ import annotations

import re
from typing import Any

# Menor = más prioritario para merge de métricas
ROLE_EXTRACT_PRIORITY: dict[str, int] = {
    "informe_tecnico_ad": 1,
    "informe_propuesta_ad": 2,
    "memoria_propuesta": 3,
    "memoria_informacion": 4,
    "estudio_detalle": 5,
    "normas_urbanisticas": 6,
    "informe_tecnico_ai": 7,
    "documento_ambiental": 8,
    "informe_sectorial": 9,
    "resumen_ejecutivo": 10,
    "memoria_economica": 11,
    "informe_juridico": 12,
    "alegaciones": 13,
    "acuerdo_bocm": 90,
    "tramitacion": 91,
    "planos": 92,
    "otro": 50,
}

# Roles que se procesan por defecto en el pipeline inteligente
ROLES_EXTRACT_DEFAULT: frozenset[str] = frozenset(
    {
        "informe_tecnico_ad",
        "informe_propuesta_ad",
        "memoria_propuesta",
        "memoria_informacion",
        "estudio_detalle",
        "normas_urbanisticas",
        "informe_tecnico_ai",
        "documento_ambiental",
        "informe_sectorial",
        "resumen_ejecutivo",
        "memoria_economica",
    }
)

ROLES_SKIP_DEFAULT: frozenset[str] = frozenset(
    {"planos", "tramitacion", "acuerdo_bocm", "informe_juridico", "alegaciones", "otro"}
)

# Prioridad legacy (compat con madrid_nti_pdf_metrics.DOC_TYPE_PRIORITY)
DOC_TYPE_PRIORITY: dict[str, int] = {
    "resumen_ejecutivo": 10,
    "memoria": 4,
    "informe_tecnico": 1,
    "informe_juridico": 12,
    "normas_urbanisticas": 6,
    "documento_ambiental": 8,
    "acuerdo": 90,
    "planos": 92,
    "otro": 50,
}

_METRIC_ROLE_PRIORITY: dict[str, list[str]] = {
    "num_viviendas_max": [
        "informe_tecnico_ad",
        "informe_propuesta_ad",
        "estudio_detalle",
        "memoria_propuesta",
        "documento_ambiental",
        "memoria_informacion",
        "informe_tecnico_ai",
        "resumen_ejecutivo",
    ],
    "sup_total_m2": [
        "memoria_propuesta",
        "memoria_informacion",
        "normas_urbanisticas",
        "informe_tecnico_ad",
        "resumen_ejecutivo",
        "estudio_detalle",
    ],
    "sup_edificable_m2": [
        "normas_urbanisticas",
        "informe_tecnico_ad",
        "estudio_detalle",
        "memoria_propuesta",
        "planos",
    ],
    "tipo_vivienda": [
        "normas_urbanisticas",
        "memoria_propuesta",
        "informe_tecnico_ad",
        "resumen_ejecutivo",
    ],
    "uso_principal": [
        "normas_urbanisticas",
        "memoria_propuesta",
        "informe_tecnico_ad",
        "resumen_ejecutivo",
    ],
}


def classify_doc_role(titulo: str, ruta: str = "", pdf_name: str = "") -> str:
    """Rol fino del PDF según título, ruta NTI y nombre de fichero."""
    blob = f"{titulo} {ruta} {pdf_name}".lower()
    ruta_l = ruta.lower()

    if "plano" in blob and "resumen" not in blob:
        return "planos"
    if any(
        x in blob
        for x in (
            "anuncio",
            "justificante",
            "solicitud",
            "diligencia",
            "comunicación",
            "comunicacion",
            "remisión",
            "remision",
            "depósito registro",
            "deposito registro",
        )
    ):
        return "tramitacion"
    if "acuerdo" in blob or "bocm" in blob or "junta de gobierno" in blob or "pleno" in blob:
        if "informe" not in blob:
            return "acuerdo_bocm"
    if "alegacion" in blob:
        return "alegaciones"
    if "informe jur" in blob or "jurídico" in blob or "juridico" in blob:
        return "informe_juridico"

    if "estudio de detalle" in blob or "estudio_detalle" in blob or re.search(
        r"\bed[\s._-]", pdf_name.lower()
    ):
        return "estudio_detalle"

    if "aprobacion definitiva" in ruta_l or "aprobación definitiva" in ruta_l:
        if "informe propuesta" in blob or "informe técnico ad" in blob or "informe tecnico ad" in blob:
            return "informe_propuesta_ad"
        if "informe técnico" in blob or "informe tecnico" in blob or "inf tec" in blob:
            return "informe_tecnico_ad"

    if "informe técnico" in blob or "informe tecnico" in blob or "inf tec" in blob:
        if " a.i" in blob or " ai" in blob or "aprobación inicial" in ruta_l:
            return "informe_tecnico_ai"
        return "informe_tecnico_ad"

    if "normas urban" in blob or "normas_urb" in blob:
        return "normas_urbanisticas"

    if "resumen ejecutivo" in blob or "resumen_ejecutivo" in blob:
        return "resumen_ejecutivo"

    if any(
        x in blob
        for x in (
            "documento ambiental",
            "dae",
            "ambiental estratég",
            "ambiental estrateg",
            "declaracion ambiental",
            "declaración ambiental",
            "informe ambiental",
        )
    ):
        return "documento_ambiental"
    if "sostenibilidad" in blob and "informe" in blob:
        return "documento_ambiental"

    if "informe propuesta" in blob or "informe técnico ad" in blob or "informe tecnico ad" in blob:
        return "informe_propuesta_ad"

    if "memoria económica" in blob or "memoria economica" in blob or "viabilidad económica" in blob:
        return "memoria_economica"
    if "memoria de propuesta" in blob or "memoria propuesta" in blob:
        return "memoria_propuesta"
    if "memoria de información" in blob or "memoria de informacion" in blob:
        return "memoria_informacion"
    if "memoria" in blob:
        return "memoria_propuesta"

    if "informe" in blob and any(
        x in blob for x in ("dg ", "canal", "hacienda", "patrimonio", "confeder", "ecologistas")
    ):
        return "informe_sectorial"
    if blob.startswith("informe ") or "/informe " in blob or "informes recibidos" in ruta_l:
        return "informe_sectorial"

    return "otro"


def infer_doc_type(name: str, ruta: str = "", pdf_name: str = "") -> str:
    """Tipo documental legacy (compatibilidad con código existente)."""
    role = classify_doc_role(name, ruta, pdf_name)
    mapping = {
        "resumen_ejecutivo": "resumen_ejecutivo",
        "memoria_propuesta": "memoria",
        "memoria_informacion": "memoria",
        "memoria_economica": "memoria",
        "estudio_detalle": "memoria",
        "informe_tecnico_ad": "informe_tecnico",
        "informe_tecnico_ai": "informe_tecnico",
        "informe_propuesta_ad": "informe_tecnico",
        "informe_sectorial": "informe_tecnico",
        "informe_juridico": "informe_juridico",
        "normas_urbanisticas": "memoria",
        "documento_ambiental": "memoria",
        "planos": "planos",
        "acuerdo_bocm": "acuerdo",
        "tramitacion": "otro",
        "alegaciones": "otro",
        "otro": "otro",
    }
    return mapping.get(role, "otro")


def role_extract_priority(role: str) -> int:
    return ROLE_EXTRACT_PRIORITY.get(role, 50)


def should_skip_role(role: str, *, include_all: bool = False) -> bool:
    if include_all:
        return False
    return role in ROLES_SKIP_DEFAULT


def infer_familia_expediente(
    denominacion: str = "",
    tipo_instrumento: str = "",
    doc_roles_present: list[str] | None = None,
    expediente_grupo: str = "",
) -> str:
    """Familia urbanística para interpretar métricas."""
    blob = f"{denominacion} {tipo_instrumento} {expediente_grupo}".lower().replace("_", " ")
    if "pecuau" in blob or "control urbanístico" in blob or "control urbanistico" in blob:
        return "pecuau"
    if "catalogación" in blob or "catalogacion" in blob or "catálogo" in blob:
        return "catalogacion"
    if "estudio de detalle" in blob or (doc_roles_present and "estudio_detalle" in doc_roles_present):
        return "estudio_detalle"
    if "modificación puntual" in blob or "modificacion puntual" in blob or "mpg" in blob or "pgou" in blob:
        return "modificacion_pgou"
    if "plan parcial" in blob or "ppri" in blob or "reforma interior" in blob:
        return "plan_parcial"
    if "plan especial" in blob:
        return "plan_especial"
    if "gestión" in blob or "gestion" in blob:
        return "gestion"
    if "urbanización" in blob or "urbanizacion" in blob:
        return "urbanizacion"
    return "planeamiento_otro"


def infer_genera_vivienda_nueva(
    familia: str,
    metrics: dict[str, Any],
    *,
    rows: list[dict[str, Any]] | None = None,
) -> str:
    """
    Clasificación interpretativa:
      si | probable_sin_cifra | no | stock_existente | desconocido
    """
    if familia in ("pecuau", "catalogacion"):
        return "no"
    viv = metrics.get("num_viviendas_max")
    if familia == "plan_especial" and viv:
        return "stock_existente_o_rehabilitacion"
    if familia == "estudio_detalle" and viv:
        return "si"
    if rows:
        for r in rows:
            role = r.get("doc_role") or ""
            if role in ("informe_tecnico_ad", "memoria_propuesta") and r.get("num_viviendas_max"):
                return "probable_si"
    if viv and familia in ("plan_parcial", "modificacion_pgou"):
        return "probable_si"
    if metrics.get("sup_edificable_m2") and familia in ("plan_parcial", "modificacion_pgou"):
        return "probable_sin_cifra"
    if metrics.get("num_viviendas_max") and familia == "plan_parcial":
        return "probable_sin_cifra"
    if familia == "modificacion_pgou" and metrics.get("num_viviendas_max"):
        return "probable_si"
    if familia == "modificacion_pgou" and (metrics.get("sup_total_m2") or 0) > 500_000:
        return "probable_si"
    return "desconocido"


def metric_role_priority(metric_key: str) -> list[str]:
    return _METRIC_ROLE_PRIORITY.get(metric_key, list(ROLE_EXTRACT_PRIORITY.keys()))
