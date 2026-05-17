#!/usr/bin/env python3
"""
Evalúa estrategias de cruce BOCM ↔ SIGMA (Madrid capital) sin llamar a la API.
Uso: python3 -m sector_geometry.madrid_ayto_match_eval
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

from . import madrid_ayto_sync as sync
from .madrid_ayto_match import expedientes_from_row as expedientes_v2

POC_ROOT = Path(__file__).resolve().parents[1]
BOCM_CSV = POC_ROOT / "output" / "history_parsed_incremental.csv"
INDEX_OUT = POC_ROOT / "output" / "madrid_ayto_expedientes_index.json"

# Casos conocidos que NO deben enlazarse (fingerprint → expediente sigma prohibido)
KNOWN_BAD: dict[str, set[str]] = {
    "5799ad4a008ab8a9": {"711/2014/04512"},  # Chamartín licencia ≠ Príncipe Pío
}

# Tokens demasiado genéricos para fuzzy (1 solo match → falso positivo)
GENERIC_TOKENS = {
    "estacion",
    "desarrollo",
    "general",
    "redes",
    "mejora",
    "urbanismo",
    "urbanizacion",
    "planeamiento",
    "parcela",
    "sector",
    "area",
    "ambito",
    "madrid",
    "norte",
    "este",
    "oeste",
    "sur",
    "parque",
    "centro",
    "licencia",
    "actividad",
    "temporal",
    "obra",
    "rehabilitacion",
    "ampliacion",
    "modificacion",
    "aprobacion",
    "informacion",
    "publica",
    "infraestructura",
    "equipamiento",
    "vivienda",
    "suelo",
    "terrenos",
    "terreno",
    "junta",
    "compensacion",
    "entidad",
    "coordinacion",
}

EXP_SLASH_RE = re.compile(r"\b(\d{1,4}/\d{4}/\d{1,8})\b")
EXP_DASH_RE = re.compile(r"\b(\d{1,4})-(\d{4})-(\d{1,8})\b")


def _relevant_madrid_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with BOCM_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("municipio") or "").strip().lower() != "madrid":
                continue
            if (row.get("es_relevante") or "").strip().lower() not in ("true", "1", "yes", "si", "sí"):
                continue
            rows.append(row)
    return rows


def _load_catalog() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    data = json.loads(INDEX_OUT.read_text(encoding="utf-8"))
    catalog = data.get("expedientes") or []
    by_exp: dict[str, dict[str, Any]] = {}
    for rec in catalog:
        num = sync._norm_exp(str(rec.get("EXP_TX_NUMERO") or ""))
        if num:
            for v in sync._exp_variants(num):
                if v not in by_exp:
                    by_exp[v] = rec
    return by_exp, catalog


def expedientes_v1(row: dict[str, str]) -> set[str]:
    """Extractor legacy (solo slash en regex)."""
    found: set[str] = set()
    blob = " ".join(
        [
            row.get("procedimiento_expediente") or "",
            row.get("title") or "",
            row.get("resumen") or "",
            row.get("nombre_sector") or "",
            row.get("organo_aprobador") or "",
        ]
    )
    for m in EXP_SLASH_RE.finditer(blob):
        for v in sync._exp_variants(m.group(1)):
            found.add(v)
    pe = (row.get("procedimiento_expediente") or "").strip()
    if pe and "/" in pe:
        for v in sync._exp_variants(pe):
            found.add(v)
    return found


def _street_tokens_legacy(s: str) -> set[str]:
    t = sync._fold(s)
    stop = {
        "calle", "avenida", "paseo", "plaza", "madrid", "urbanismo", "licencia",
        "actividad", "estudio", "detalle", "plan", "especial", "modificacion",
        "aprobacion", "inicial", "definitiva", "informacion", "publica", "numero",
    }
    words = {w for w in t.split() if len(w) >= 3 and w not in stop and not w.isdigit()}
    return words


def _denom_score_legacy(bocm_text: str, sigma_denom: str) -> float:
    a = _street_tokens_legacy(bocm_text)
    b = _street_tokens_legacy(sigma_denom)
    if not a or not b:
        fa, fb = sync._fold(bocm_text), sync._fold(sigma_denom)
        if len(fa) >= 10 and len(fb) >= 10:
            if fa in fb or fb in fa:
                return 0.85
            return SequenceMatcher(None, fa, fb).ratio()
        return 0.0
    inter = a & b
    if len(inter) >= 2:
        return 0.5 + 0.5 * len(inter) / max(len(a), len(b))
    if len(inter) == 1 and len(max(inter, key=len)) >= 5:
        return 0.72
    fa, fb = sync._fold(bocm_text), sync._fold(sigma_denom)
    return SequenceMatcher(None, fa, fb).ratio() * 0.9


def _distinctive_tokens(s: str) -> set[str]:
    raw = _street_tokens_legacy(s)
    return {t for t in raw if t not in GENERIC_TOKENS and len(t) >= 4}


def denom_score_strict(bocm_text: str, sigma_denom: str) -> float:
    a = _distinctive_tokens(bocm_text)
    b = _distinctive_tokens(sigma_denom)
    if not a or not b:
        return 0.0
    inter = a & b
    if len(inter) >= 2:
        return 0.55 + 0.45 * len(inter) / max(len(a), len(b))
    if len(inter) == 1:
        tok = next(iter(inter))
        if len(tok) >= 8:
            return 0.78
        return 0.0
    fa, fb = sync._fold(bocm_text), sync._fold(sigma_denom)
    if len(fa) >= 12 and len(fb) >= 12:
        r = SequenceMatcher(None, fa, fb).ratio()
        if r >= 0.82:
            return r
    return 0.0


def denom_score_nombre_only(row: dict[str, str], sigma_denom: str) -> float:
    blob = (row.get("nombre_sector") or "").strip()
    if len(blob) < 8:
        return 0.0
    return denom_score_strict(blob, sigma_denom)


def _bocm_kind(row: dict[str, str]) -> str:
    t = sync._fold(row.get("tipo_instrumento") or "")
    if "licencia" in t:
        return "licencia"
    if "estudio" in t and "detalle" in t:
        return "estudio_detalle"
    if "plan especial" in t or t == "plan especial":
        return "plan_especial"
    if "modificacion" in t or "pgou" in t:
        return "modificacion"
    if "urbanizacion" in t:
        return "urbanizacion"
    return "otro"


def _sigma_kind(rec: dict[str, Any]) -> str:
    fig = (rec.get("FIG_TX_ETIQ") or "").upper()
    if fig.startswith("MPE") or fig.startswith("PE"):
        return "planeamiento"
    if fig.startswith("ED"):
        return "estudio_detalle"
    return "otro"


def _type_compatible(row: dict[str, str], rec: dict[str, Any]) -> bool:
    bk, sk = _bocm_kind(row), _sigma_kind(rec)
    if bk == "licencia" and sk == "planeamiento":
        return False
    return True


@dataclass
class MatchResult:
    bocm_id: str
    match_type: str | None
    match_score: float | None
    sigma_exp: str | None


@dataclass
class Strategy:
    name: str
    match_fn: Callable[[dict[str, str], dict[str, dict[str, Any]], list[dict[str, Any]]], MatchResult | None]


def match_production(row, by_exp, catalog) -> MatchResult | None:
    from .madrid_ayto_match import match_row

    hit, mt, sc = match_row(row, by_exp)
    if hit:
        return MatchResult(sync._bocm_row_id(row), mt, sc, str(hit.get("EXP_TX_NUMERO") or ""))
    return None


def match_current(row, by_exp, catalog) -> MatchResult | None:
    exps = expedientes_v1(row)
    for e in exps:
        if e in by_exp:
            r = by_exp[e]
            return MatchResult(
                sync._bocm_row_id(row),
                "expediente_numero",
                1.0,
                str(r.get("EXP_TX_NUMERO") or ""),
            )
    blob = " ".join([row.get("nombre_sector") or "", row.get("title") or "", row.get("resumen") or ""])
    best_score, best_rec = 0.0, None
    for rec in catalog:
        sc = _denom_score_legacy(blob, str(rec.get("EXP_TX_DENOM") or ""))
        if sc > best_score:
            best_score, best_rec = sc, rec
    if best_rec and best_score >= 0.68:
        return MatchResult(
            sync._bocm_row_id(row),
            "denominacion_fuzzy",
            round(best_score, 3),
            str(best_rec.get("EXP_TX_NUMERO") or ""),
        )
    return None


def match_exp_only(row, by_exp, catalog) -> MatchResult | None:
    for e in expedientes_v2(row):
        if e in by_exp:
            r = by_exp[e]
            return MatchResult(sync._bocm_row_id(row), "expediente_numero", 1.0, str(r.get("EXP_TX_NUMERO") or ""))
    return None


def match_exp_strict_fuzzy(row, by_exp, catalog) -> MatchResult | None:
    for e in expedientes_v2(row):
        if e in by_exp:
            r = by_exp[e]
            return MatchResult(sync._bocm_row_id(row), "expediente_numero", 1.0, str(r.get("EXP_TX_NUMERO") or ""))
    blob = " ".join([row.get("nombre_sector") or "", row.get("resumen") or ""])
    if len(blob.strip()) < 10:
        return None
    best_score, best_rec = 0.0, None
    for rec in catalog:
        if not _type_compatible(row, rec):
            continue
        sc = denom_score_strict(blob, str(rec.get("EXP_TX_DENOM") or ""))
        if sc > best_score:
            best_score, best_rec = sc, rec
    if best_rec and best_score >= 0.78:
        return MatchResult(
            sync._bocm_row_id(row),
            "denominacion_estricta",
            round(best_score, 3),
            str(best_rec.get("EXP_TX_NUMERO") or ""),
        )
    return None


def match_exp_nombre_fuzzy(row, by_exp, catalog) -> MatchResult | None:
    for e in expedientes_v2(row):
        if e in by_exp:
            r = by_exp[e]
            return MatchResult(sync._bocm_row_id(row), "expediente_numero", 1.0, str(r.get("EXP_TX_NUMERO") or ""))
    ns = (row.get("nombre_sector") or "").strip()
    if len(ns) < 10:
        return None
    best_score, best_rec = 0.0, None
    for rec in catalog:
        if not _type_compatible(row, rec):
            continue
        sc = denom_score_nombre_only(row, str(rec.get("EXP_TX_DENOM") or ""))
        if sc > best_score:
            best_score, best_rec = sc, rec
    if best_rec and best_score >= 0.78:
        return MatchResult(
            sync._bocm_row_id(row),
            "denominacion_sector",
            round(best_score, 3),
            str(best_rec.get("EXP_TX_NUMERO") or ""),
        )
    return None


def match_exp_denom_confirm(row, by_exp, catalog) -> MatchResult | None:
    """Expediente normalizado; fuzzy solo si nombre_sector parece calle/ámbito concreto."""
    for e in expedientes_v2(row):
        if e in by_exp:
            r = by_exp[e]
            return MatchResult(sync._bocm_row_id(row), "expediente_numero", 1.0, str(r.get("EXP_TX_NUMERO") or ""))
    ns = (row.get("nombre_sector") or "").strip()
    if len(ns) < 12:
        return None
    generic_ns = {"licencia de actividad temporal", "licencia de obra", "plan especial", "estudio de detalle"}
    if sync._fold(ns) in generic_ns or len(_distinctive_tokens(ns)) < 2:
        return None
    best_score, best_rec = 0.0, None
    for rec in catalog:
        if not _type_compatible(row, rec):
            continue
        sc = denom_score_strict(ns, str(rec.get("EXP_TX_DENOM") or ""))
        if sc > best_score:
            best_score, best_rec = sc, rec
    if best_rec and best_score >= 0.78:
        return MatchResult(
            sync._bocm_row_id(row),
            "denominacion_sector",
            round(best_score, 3),
            str(best_rec.get("EXP_TX_NUMERO") or ""),
        )
    return None


STRATEGIES = [
    Strategy("A_actual_fuzzy", match_current),
    Strategy("B_solo_expediente", match_exp_only),
    Strategy("F_produccion", match_production),
    Strategy("C_exp_norm+fuzzy_estricto", match_exp_strict_fuzzy),
    Strategy("D_exp+nombre_sector", match_exp_nombre_fuzzy),
    Strategy("E_exp+denom_sector_concreto", match_exp_denom_confirm),
]


def _expected_exp_from_pe(row: dict[str, str]) -> str | None:
    """Expediente canónico si procedimiento_expediente es parseable."""
    exps = list(expedientes_v2(row))
    pe = (row.get("procedimiento_expediente") or "").strip()
    if not pe:
        return None
    for e in exps:
        if pe.replace("-", "/").replace(" ", "") in e.replace("/", ""):
            return sync._norm_exp(e)
    if exps:
        return sync._norm_exp(sorted(exps, key=len)[0])
    return None


def evaluate() -> None:
    rows = _relevant_madrid_rows()
    by_exp, catalog = _load_catalog()
    print(f"Filas relevantes Madrid: {len(rows)}")
    print(f"Catálogo SIGMA: {len(catalog)} | índice expediente: {len(by_exp)}\n")

    # Filas con PE parseable que está en catálogo (verdad operativa para match por número)
    pe_gold: list[tuple[dict[str, str], str]] = []
    for row in rows:
        exp = _expected_exp_from_pe(row)
        if not exp:
            continue
        variants = sync._exp_variants(exp)
        hit_key = next((v for v in variants if v in by_exp), None)
        if hit_key:
            pe_gold.append(
                (row, sync._norm_exp(str(by_exp[hit_key].get("EXP_TX_NUMERO") or exp)))
            )

    print(f"Gold PE→SIGMA (PE en catálogo): {len(pe_gold)}\n")
    print(f"{'Estrategia':<32} {'Total':>6} {'Exp#':>6} {'Fuzzy':>6} {'PE_OK':>6} {'PE_miss':>8} {'Bad':>4} {'Hub_max':>8} {'Score@72':>8}")
    print("-" * 100)

    best_name = ""
    best_score = -1.0

    for strat in STRATEGIES:
        matches: list[MatchResult] = []
        for row in rows:
            m = strat.match_fn(row, by_exp, catalog)
            if m:
                matches.append(m)

        by_type = Counter(m.match_type for m in matches)
        exp_n = by_type.get("expediente_numero", 0)
        fuzzy_n = len(matches) - exp_n

        pe_ok = 0
        pe_miss = 0
        for row, expected in pe_gold:
            rid = sync._bocm_row_id(row)
            hit = next((m for m in matches if m.bocm_id == rid), None)
            if hit and sync._norm_exp(hit.sigma_exp or "") == sync._norm_exp(expected):
                pe_ok += 1
            else:
                pe_miss += 1

        bad = 0
        for row in rows:
            fp = (row.get("proyecto_fingerprint") or "").strip()
            if fp not in KNOWN_BAD:
                continue
            rid = sync._bocm_row_id(row)
            hit = next((m for m in matches if m.bocm_id == rid), None)
            if hit and sync._norm_exp(hit.sigma_exp or "") in {sync._norm_exp(x) for x in KNOWN_BAD[fp]}:
                bad += 1

        hub = Counter(sync._norm_exp(m.sigma_exp or "") for m in matches if m.match_type != "expediente_numero")
        hub_max = hub.most_common(1)[0][1] if hub else 0
        score72 = sum(1 for m in matches if m.match_score == 0.72)

        # Puntuación: priorizar PE_OK, penalizar bad y hub y fuzzy 0.72
        quality = pe_ok - 3 * bad - 0.01 * score72 - 0.05 * hub_max - 2 * pe_miss
        if quality > best_score:
            best_score = quality
            best_name = strat.name

        print(
            f"{strat.name:<32} {len(matches):>6} {exp_n:>6} {fuzzy_n:>6} {pe_ok:>6} {pe_miss:>8} {bad:>4} {hub_max:>8} {score72:>8}"
        )

    print(f"\n→ Mejor balance: {best_name} (score={best_score:.1f})")

    # Muestra caso Chamartín por estrategia
    cham_row = next(r for r in rows if (r.get("proyecto_fingerprint") or "") == "5799ad4a008ab8a9")
    print("\nCaso Chamartín (licencia temporal):")
    for strat in STRATEGIES:
        m = strat.match_fn(cham_row, by_exp, catalog)
        if m:
            print(f"  {strat.name}: {m.match_type} {m.sigma_exp} score={m.match_score}")
        else:
            print(f"  {strat.name}: sin match")


if __name__ == "__main__":
    evaluate()
