"""Extrae campos estructurados de la ficha HTML del visor VSURB (Ayto. Madrid)."""

from __future__ import annotations

import html as html_module
import re
from typing import Any


def _html_text(fragment: str) -> str:
    s = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", fragment, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_module.unescape(s)
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", s)).strip()


def _parse_m2(raw: str | None) -> float | None:
    if not raw:
        return None
    t = _html_text(raw).replace(".", "").replace(",", ".")
    m = re.search(r"([\d]+(?:\.\d+)?)\s*m\s*2", t, re.I)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    m = re.search(r"([\d][\d.,]*)", t)
    if not m:
        return None
    try:
        return float(m.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _label_td(html: str, label: str) -> str | None:
    """Valor en la celda a la derecha de <b>Label:</b>."""
    pat = (
        rf"<b>\s*{re.escape(label)}\s*:?\s*</b>\s*</td>\s*"
        r"<td[^>]*>([\s\S]*?)</td>"
    )
    m = re.search(pat, html, re.I)
    if not m:
        return None
    v = _html_text(m.group(1))
    return v or None


def _section_after_header(html: str, header: str) -> str | None:
    """Texto de la fila siguiente a un bloque <b>HEADER</b> en wbvisor_bloque."""
    pat = (
        rf"<b>\s*{re.escape(header)}\s*</b>\s*</td>\s*</tr>\s*"
        r"<tr>\s*<td[^>]*colspan[^>]*>([\s\S]*?)</td>"
    )
    m = re.search(pat, html, re.I)
    if not m:
        return None
    v = _html_text(m.group(1))
    return v or None


def _section_descripcion_resumen(html: str) -> tuple[str | None, str | None]:
    """DESCRIPCIÓN ÁMBITO y RESUMEN CONTENIDO (toleran entidades HTML y tabuladores)."""
    desc = None
    resumen = None
    m = re.search(
        r"<b>\s*DESCRIPCI&Oacute;N\s+&Aacute;MBITO\s+PLANEAMIENTO\s*</b>\s*</td>\s*</tr>\s*"
        r"<tr>\s*<td[^>]*colspan[^>]*>([\s\S]*?)</td>",
        html,
        re.I,
    )
    if m:
        desc = _html_text(m.group(1)) or None
    m = re.search(
        r"<b>\s*RESUMEN\s+CONTENIDO\s*</b>\s*</td>\s*</tr>\s*"
        r"<tr>\s*<td[^>]*colspan[^>]*>([\s\S]*?)</td>",
        html,
        re.I,
    )
    if m:
        resumen = _html_text(m.group(1)) or None
    return desc, resumen


def _clean_expediente(raw: str | None) -> str | None:
    if not raw:
        return None
    m = re.search(r"\d{3}/\d{4}/\d{5}", raw.replace(" ", ""))
    if m:
        return m.group(0)
    return _html_text(raw).split()[0] if raw.strip() else None


def parse_visor_ficha(html: bytes | str) -> dict[str, Any] | None:
    """
    Devuelve dict con promotor, resumen, superficie, etc.
    None si no parece ficha de planeamiento (wbvisor).
    """
    hc = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else html
    if "wbvisor_bloque" not in hc and "wbvisor_contenedor" not in hc:
        return None

    out: dict[str, Any] = {}

    tit = re.search(
        r'<tr[^>]*class="wbvisor_titulo"[^>]*>\s*<td[^>]*><b>([^<]+)</b>'
        r"[\s\S]*?<td[^>]*colspan[^>]*><b>([^<]+)</b>",
        hc,
        re.I,
    )
    if tit:
        out["figuraCodigo"] = _html_text(tit.group(1))
        out["denominacionVisor"] = _html_text(tit.group(2))

    fig_row = re.search(
        r"<b>\s*Figura:\s*</b>\s*</td>\s*<td[^>]*colspan[^>]*><b>([^<]+)</b>",
        hc,
        re.I,
    )
    if fig_row:
        out["figuraTipo"] = _html_text(fig_row.group(1))

    tipo = re.search(
        r"<b>\s*Tipo\s+Planeamiento:\s*</b>\s*</td>\s*<td[^>]*>\s*<span>([^<]+)</span>",
        hc,
        re.I,
    )
    if tipo:
        out["tipoPlaneamiento"] = _html_text(tipo.group(1))

    exp_raw = _label_td(hc, "Expediente")
    if exp_raw:
        out["expedienteVisor"] = _clean_expediente(exp_raw)

    ambito = re.search(
        r"<b>\s*(?:&Aacute;|Á)mbito de\s+(?:Ordenaci&oacute;n|Ordenación):\s*</b>\s*</td>\s*"
        r"<td[^>]*colspan[^>]*>\s*(?:<div>)?([^<]+)",
        hc,
        re.I,
    )
    if ambito:
        out["ambitoOrdenacion"] = _html_text(ambito.group(1))

    archivo = re.search(
        r"<b>\s*Archivo\s+de\s+Planos:\s*</b>\s*</td>\s*<td[^>]*>([^<]+)",
        hc,
        re.I,
    )
    if archivo:
        v = _html_text(archivo.group(1))
        if v and v not in ("-", "-     "):
            out["archivoPlanos"] = v

    sistema = re.search(
        r"<b>\s*Sistema de\s+Actuaci&oacute;n:\s*</b>\s*</td>\s*<td[^>]*colspan[^>]*>([^<]+)",
        hc,
        re.I,
    )
    if sistema:
        out["sistemaActuacion"] = _html_text(sistema.group(1))

    unidad = re.search(
        r"<b>\s*Unidad\s+Tramitadora:\s*</b>\s*</td>\s*<td[^>]*colspan[^>]*>\s*([^<]+)",
        hc,
        re.I,
    )
    if unidad:
        out["unidadTramitadora"] = _html_text(unidad.group(1))

    for key, label in (
        ("distrito", "Ditrito"),
        ("iniciativa", "Iniciativa"),
        ("promotor", "Promotor"),
        ("equipoRedactor", "EQUIPO REDACTOR"),
        ("sugerencias", "SUGERENCIAS"),
        ("alegaciones", "ALEGACIONES"),
    ):
        v = _label_td(hc, label)
        if v:
            out[key] = v

    desc, resumen = _section_descripcion_resumen(hc)
    if desc:
        out["descripcionAmbito"] = desc
    if resumen:
        out["resumenContenido"] = resumen

    obs = _section_after_header(hc, "OBSERVACIONES")
    if obs:
        out["observaciones"] = obs

    sup_raw = re.search(
        r"<b>\s*Superfie\w*\s+del\s+&Aacute;mbito:\s*</b>\s*([^<]+)",
        hc,
        re.I,
    )
    if sup_raw:
        out["superficieAmbitoTexto"] = _html_text(sup_raw.group(1))
        out["superficieAmbitoM2"] = _parse_m2(sup_raw.group(1))

    # Quitar vacíos
    return {k: v for k, v in out.items() if v is not None and v != ""} or None


def ficha_resumen_corto(ficha: dict[str, Any] | None, *, max_len: int = 480) -> str | None:
    if not ficha:
        return None
    for key in ("resumenContenido", "descripcionAmbito", "observaciones"):
        t = ficha.get(key)
        if isinstance(t, str) and len(t.strip()) > 20:
            s = re.sub(r"\s+", " ", t.strip())
            if len(s) > max_len:
                return s[: max_len - 1].rstrip() + "…"
            return s
    return None
