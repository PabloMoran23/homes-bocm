"""Coherencia viviendas ↔ superficie (ámbito / edificabilidad) en métricas SIGMA."""

from __future__ import annotations

from typing import Any

# Madrid: parcela/edificio no admite densidades de gran sector (falsos positivos en memorias PGOUM).
M2_AMBITO_MIN_POR_VIVIENDA = 55
M2_EDIFICABLE_MIN_POR_VIVIENDA = 42
MAX_VIVIENDAS_SIN_SUPERFICIE = 400


def cap_viviendas_por_superficie(
    sup_total_m2: float | None,
    sup_edificable_m2: float | None = None,
) -> int | None:
    """Techo plausible de viviendas según m² de ámbito y/o edificabilidad."""
    caps: list[int] = []
    if sup_edificable_m2 is not None and sup_edificable_m2 >= 100:
        caps.append(int(sup_edificable_m2 / M2_EDIFICABLE_MIN_POR_VIVIENDA))
    if sup_total_m2 is not None and sup_total_m2 >= 200:
        caps.append(int(sup_total_m2 / M2_AMBITO_MIN_POR_VIVIENDA))
    if not caps:
        return None
    return max(1, min(caps))


def viviendas_coherentes_con_superficie(
    num_viviendas: int | float | None,
    sup_total_m2: float | None,
    sup_edificable_m2: float | None = None,
) -> bool:
    if num_viviendas is None:
        return True
    try:
        n = int(num_viviendas)
    except (TypeError, ValueError):
        return False
    if n < 1:
        return False

    cap = cap_viviendas_por_superficie(sup_total_m2, sup_edificable_m2)
    if cap is not None:
        return n <= cap
    return n <= MAX_VIVIENDAS_SIN_SUPERFICIE


def _adjust_genera_tras_descartar_viviendas(
    familia: str | None,
    genera: str | None,
) -> str | None:
    fam = familia or ""
    if fam in ("pecuau", "catalogacion"):
        return "no"
    if fam == "plan_especial":
        return "stock_existente_o_rehabilitacion"
    if genera in ("si", "probable_si"):
        if fam in ("plan_parcial", "modificacion_pgou"):
            return "probable_sin_cifra"
        return "desconocido"
    return genera


def sanitize_viviendas_en_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Anula num_viviendas_max y hechos asociados si no cuadra con la superficie."""
    viv = metrics.get("num_viviendas_max")
    if viv is None:
        return metrics

    sup = metrics.get("sup_total_m2")
    edif = metrics.get("sup_edificable_m2")
    try:
        sup_f = float(sup) if sup is not None else None
        edif_f = float(edif) if edif is not None else None
    except (TypeError, ValueError):
        sup_f, edif_f = None, None

    if viviendas_coherentes_con_superficie(viv, sup_f, edif_f):
        return metrics

    out = dict(metrics)
    out["num_viviendas_max"] = None
    out["genera_vivienda_nueva"] = _adjust_genera_tras_descartar_viviendas(
        out.get("familia_expediente"),
        out.get("genera_vivienda_nueva"),
    )
    hechos = out.get("hechos")
    if isinstance(hechos, list):
        out["hechos"] = [
            h
            for h in hechos
            if isinstance(h, dict)
            and h.get("metrica") != "num_viviendas_max"
            and h.get("metric") != "num_viviendas_max"
        ]
    return out
