"""Regex y utilidades para métricas urbanísticas en PDFs NTI/SIGMA."""

from __future__ import annotations

import re
from typing import Any

from sector_geometry.madrid_nti_doc_roles import (
    DOC_TYPE_PRIORITY,
    infer_doc_type,
    infer_familia_expediente,
    infer_genera_vivienda_nueva,
    metric_role_priority,
    role_extract_priority,
)

__all__ = [
    "DOC_TYPE_PRIORITY",
    "METRIC_KEYS",
    "infer_doc_type",
    "extract_regex_metrics",
    "merge_metrics",
    "merge_expediente_metrics",
    "_metric_sane",
]

METRIC_KEYS = (
    "num_viviendas_max",
    "sup_total_m2",
    "sup_edificable_m2",
    "tipo_vivienda",
    "uso_principal",
    "promotor_o_propietario",
    "nombre_ambito",
    "sistema_actuacion",
)

_RE_VIVIENDAS = re.compile(
    r"""
    (?:
        n[uú]mero\s+(?:m[aá]ximo\s+)?de\s+viviendas[^:]*?:\s*(\d[\d.,\s]*)
      | construcci[oó]n\s+de\s+(\d[\d.,\s]*)\s+viviendas?
      | (\d[\d.,\s]*)\s+viviendas?\s*(?:previstas?|m[aá]x(?:imas?)?|totales?|nuevas?)?
      | viviendas?\s*(?:m[aá]x(?:imo)?|totales?|previstas?)[^:]*?:\s*(\d[\d.,\s]*)
      | nº\s*(?:m[aá]x\s*)?viviendas?[^:]*?:\s*(\d[\d.,\s]*)
      | de\s+(\d[\d.,\s]*)\s+viviendas\s+a\s+(\d[\d.,\s]*)
      | supon[ií]a\s+unas\s+(\d[\d.,\s]*)\s+viviendas?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_RE_SUP_AMBITO_STRICT = re.compile(
    r"""
    superficie\s+del\s+(?:ámbito|ambito)[^.\n]{0,50}
    (?:asciende\s+a|es\s+de|,?\s*con\s+una\s+superficie\s+de|,?\s*destinada)[^.\n]{0,30}
    (\d[\d.,\s]*)\s*m\s*[²2]
    """,
    re.IGNORECASE | re.VERBOSE,
)

_RE_SUP_AMBITO = re.compile(
    r"""
    superficie\s+(?:del\s+)?(?:ámbito|ambito|afectada|territorial)[^.\n]{0,40}
    (?:asciende\s+a|es\s+de|de|,?\s*con)\s*:?\s*(\d[\d.,\s]*)\s*m\s*[²2]
    | superficie\s+de\s+(?:la\s+)?parcela[^.\n]{0,30}(\d[\d.,\s]*)\s*m
    """,
    re.IGNORECASE | re.VERBOSE,
)

_RE_SUP_SIMPLE = re.compile(
    r"superficie[^.\n]{0,35}(\d[\d.,\s]*)\s*m\s*[²2]",
    re.IGNORECASE,
)

_RE_EDIFICABILIDAD = re.compile(
    r"""
    edificabilidad\s+(?:m[aá]xima\s+)?(?:asignada|del\s+ámbito)?[^.\n]{0,50}
    (?:asciende\s+a|es\s+de|cifra\s+en|:)\s*(\d[\d.,\s]*)\s*m\s*[²2]
    | edificabilidad\s+asignada\s*:\s*(\d[\d.,\s]*)\s*m\s*[²2]
    | edificabilidad\s+(?:m[aá]xima\s+)?(?:es\s+de\s+)?(\d[\d.,\s]*)\s*m\s*[²2]
    """,
    re.IGNORECASE | re.VERBOSE,
)

_RE_TIPO_VIVIENDA = re.compile(
    r"(vivienda\s+(?:libre|protegida|pública|publica|colectiva|unifamiliar)|VPO|VPPL|VPPB)",
    re.IGNORECASE,
)

_RE_USO = re.compile(
    r"uso\s+(?:principal\s+)?(?:del\s+suelo\s+)?(?:es\s+)?([A-Za-zÁÉÍÓÚáéíóúñ\s]{3,40})",
    re.IGNORECASE,
)


def parse_spanish_number(raw: str | None) -> float | None:
    if not raw:
        return None
    s = re.sub(r"\s+", "", str(raw).strip())
    if not s or not re.search(r"\d", s):
        return None
    # 36.467,00 o 1.615.996
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    else:
        # miles con punto: 15.253 o 10.510
        parts = s.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            s = "".join(parts)
        elif len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 4:
            s = "".join(parts)
    try:
        return float(s)
    except ValueError:
        return None


def _first_number(groups: tuple) -> float | None:
    for g in groups:
        if g is None:
            continue
        if isinstance(g, tuple):
            for sub in g:
                v = parse_spanish_number(sub)
                if v is not None:
                    return v
        else:
            v = parse_spanish_number(g)
            if v is not None:
                return v
    return None


def extract_regex_metrics(text: str) -> dict[str, Any]:
    """Extracción heurística sin LLM."""
    out: dict[str, Any] = {k: None for k in METRIC_KEYS}
    if not text or len(text.strip()) < 40:
        out["texto_util"] = False
        return out
    out["texto_util"] = True

    viv_nums: list[float] = []
    for m in _RE_VIVIENDAS.finditer(text):
        for g in m.groups():
            if g is None:
                continue
            if isinstance(g, str) and " a " in g.lower():
                continue
            v = parse_spanish_number(g)
            if v is not None and 1 <= v <= 25_000:
                viv_nums.append(v)
    if viv_nums:
        out["num_viviendas_max"] = int(max(viv_nums))

    strict_sups: list[float] = []
    for m in _RE_SUP_AMBITO_STRICT.finditer(text):
        v = parse_spanish_number(m.group(1))
        if v is not None and 200 <= v <= 2_000_000:
            strict_sups.append(v)
    if strict_sups:
        out["sup_total_m2"] = max(strict_sups)
        out["sup_ambito_strict"] = True
    else:
        sups: list[float] = []
        for pat in (_RE_SUP_AMBITO, _RE_SUP_SIMPLE):
            for m in pat.finditer(text):
                g = m.group(1) if m.lastindex else None
                v = parse_spanish_number(g)
                if v is not None and 200 <= v <= 2_000_000:
                    sups.append(v)
        if sups:
            sups_sorted = sorted(sups)
            out["sup_total_m2"] = (
                sups_sorted[len(sups_sorted) // 2] if len(sups) > 3 else max(sups)
            )

    edifs: list[float] = []
    for m in _RE_EDIFICABILIDAD.finditer(text):
        v = _first_number(m.groups())
        if v is not None and 100 <= v <= 80_000:
            edifs.append(v)
    if edifs:
        out["sup_edificable_m2"] = max(edifs)

    tv = _RE_TIPO_VIVIENDA.search(text)
    if tv:
        out["tipo_vivienda"] = tv.group(1).strip()[:80]

    uso = _RE_USO.search(text)
    if uso:
        out["uso_principal"] = uso.group(1).strip()[:80]

    return out


def _metric_sane(key: str, val: Any) -> bool:
    if val is None or val == "":
        return False
    try:
        n = float(val)
    except (TypeError, ValueError):
        return key in ("tipo_vivienda", "uso_principal", "promotor_o_propietario", "nombre_ambito", "sistema_actuacion")
    if key == "num_viviendas_max":
        return 1 <= n <= 25_000
    if key == "sup_total_m2":
        return 200 <= n <= 2_000_000
    if key == "sup_edificable_m2":
        return 100 <= n <= 80_000
    return True


def merge_metrics(
    rows: list[dict[str, Any]],
    *,
    prefer_llm: bool = True,
) -> dict[str, Any]:
    """Fusiona métricas (modo legacy). Preferir merge_expediente_metrics."""
    return merge_expediente_metrics(rows, prefer_llm=prefer_llm).get("metrics") or {}


def _row_confidence(row: dict[str, Any], key: str) -> str:
    role = row.get("doc_role") or "otro"
    method = row.get("method") or "regex"
    if method.startswith("llm"):
        return "llm"
    if role in metric_role_priority(key)[:3]:
        return "alta"
    if role in metric_role_priority(key):
        return "media"
    return "baja"


def merge_expediente_metrics(
    rows: list[dict[str, Any]],
    *,
    prefer_llm: bool = True,
    denominacion: str = "",
    tipo_instrumento: str = "",
    familia_hint: str = "",
) -> dict[str, Any]:
    """Agrega métricas por expediente con trazabilidad y roles documentales."""
    if not rows:
        return {"metrics": {}, "hechos": [], "fuentes_pdf": []}

    roles_present = [str(r.get("doc_role") or "otro") for r in rows]
    grupo = str(rows[0].get("expediente_grupo") or "") if rows else ""
    familia = infer_familia_expediente(
        denominacion, tipo_instrumento, roles_present, expediente_grupo=grupo
    )
    if familia_hint and familia == "planeamiento_otro":
        familia = familia_hint

    def role_rank(row: dict[str, Any], key: str) -> int:
        role = str(row.get("doc_role") or "otro")
        prefs = metric_role_priority(key)
        try:
            return prefs.index(role)
        except ValueError:
            return role_extract_priority(role) + 20

    metrics: dict[str, Any] = {}
    hechos: list[dict[str, Any]] = []
    fuentes: list[str] = []
    metodos: list[str] = []

    for key in METRIC_KEYS:
        candidates = [r for r in rows if _metric_sane(key, r.get(key))]
        if not candidates:
            continue
        # Superficie: preferir valor más alto solo si hay patrón estricto de ámbito
        if key == "sup_total_m2":
            strict = [r for r in candidates if r.get("sup_ambito_strict")]
            pool = strict if strict else candidates
        else:
            pool = candidates
        pool.sort(
            key=lambda r: (
                role_rank(r, key),
                0 if (prefer_llm and str(r.get("method", "")).startswith("llm")) else 1,
            )
        )
        best = pool[0]
        val = best.get(key)
        metrics[key] = val
        hechos.append(
            {
                "metrica": key,
                "valor": val,
                "confianza": _row_confidence(best, key),
                "doc_role": best.get("doc_role"),
                "pdf_name": best.get("pdf_name"),
                "pdf_path": best.get("pdf_path"),
                "method": best.get("method"),
            }
        )

    for r in rows:
        name = r.get("pdf_name")
        if name and name not in fuentes:
            fuentes.append(name)
        m = r.get("method")
        if m and m not in metodos:
            metodos.append(m)

    metrics["genera_vivienda_nueva"] = infer_genera_vivienda_nueva(familia, metrics, rows=rows)
    metrics["familia_expediente"] = familia

    # Resumen y tipo instrumento del mejor doc
    best_doc = min(
        rows,
        key=lambda r: role_extract_priority(str(r.get("doc_role") or "otro")),
        default=None,
    )
    if best_doc:
        if best_doc.get("resumen"):
            metrics["resumen"] = best_doc.get("resumen")
        if best_doc.get("tipo_instrumento"):
            metrics["tipo_instrumento"] = best_doc.get("tipo_instrumento")

    return {
        "metrics": metrics,
        "hechos": hechos,
        "fuentes_pdf": fuentes,
        "metodos": metodos,
        "doc_role_principal": best_doc.get("doc_role") if best_doc else None,
        "pdfs_procesados": len(rows),
    }
