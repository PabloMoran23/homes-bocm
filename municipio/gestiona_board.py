"""Lector común del tablón de anuncios de las sedes Gestiona (*.sedelectronica.es).

El tablón solo muestra los anuncios en exposición. La primera página trae unos
10; el resto se carga con el botón «Mostrar más», que es una llamada AJAX de
Wicket ligada a la sesión (cookie). ``?page=N`` no pagina: devuelve la misma
página. Este módulo abre una sesión, lee la tabla y pulsa «Mostrar más» hasta
que no quedan más filas o se alcanza el tope.

No filtra nada: devuelve todos los anuncios. La clasificación es aparte
(``municipio.anuncio_clase``).
"""

from __future__ import annotations

import hashlib
import html
import http.cookiejar
import re
import ssl
import time
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Iterable
from urllib.parse import urljoin, urlparse

from municipio.http import fetch_text

GESTIONA_HOST = re.compile(r"https?://([a-z0-9-]+(?:\.[a-z0-9-]+)*\.sedelectronica\.es)", re.I)
_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
_CELL = re.compile(r'<td class="(class_[A-Za-z]+)"[^>]*>(.*?)</td>', re.I | re.S)
_PREVIEW = re.compile(r'href="([^"]*/preview-document/([0-9a-f-]{36})[^"]*)"', re.I)
_MORE = re.compile(r'class="more_results".*?wicketAjaxGet\(\s*[\'"]([^\'"]+)[\'"]', re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

DEFAULT_MAX_CLICKS = 60  # ~600 anuncios; ningún tablón probado pasaba de 90
DEFAULT_DELAY_S = 0.4
USER_AGENT = "homes-municipio-anuncios/1.0"

# Columnas conocidas del tablón; el resto se conserva en ``celdas``.
_FIELDS = {
    "class_name": "titulo",
    "class_folderCode": "expediente",
    "class_folderName": "procedimiento",
    "class_boardCategory": "categoria",
    "class_description": "descripcion",
    "class_dateFrom": "fecha_publicacion",
    "class_startDate": "fecha_publicacion",
    "class_endDate": "fecha_fin",
    "class_dateTo": "fecha_fin",
}


class GestionaBoardError(RuntimeError):
    """El tablón no respondió como un tablón Gestiona."""


@dataclass
class BoardResult:
    board_url: str
    anuncios: list[dict[str, Any]]
    clicks: int
    truncated: bool


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", fragment))).strip()


def _iso(value: str | None) -> str | None:
    m = _DMY.search(value or "")
    if not m:
        return None
    day, month, year = (int(x) for x in m.groups())
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def board_url_for(raw_manifest: dict[str, Any]) -> str | None:
    """URL del tablón Gestiona del municipio, o None si no tiene sede Gestiona.

    Usa ``portal.config.board_url`` si es Gestiona; si no, el primer host
    ``*.sedelectronica.es`` que aparezca en el manifest. ``anuncios.enabled:
    false`` lo desactiva.
    """
    anuncios = raw_manifest.get("anuncios") or {}
    if isinstance(anuncios, dict) and anuncios.get("enabled") is False:
        return None
    if isinstance(anuncios, dict) and anuncios.get("board_url"):
        return str(anuncios["board_url"])
    config = (raw_manifest.get("portal") or {}).get("config") or {}
    board = str(config.get("board_url") or "")
    m = GESTIONA_HOST.match(board)
    if m:
        return f"https://{m.group(1).lower()}/board/"
    for value in _strings(raw_manifest):
        m = GESTIONA_HOST.search(value)
        if m:
            return f"https://{m.group(1).lower()}/board/"
    return None


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def parse_rows(page: str, board_url: str) -> list[dict[str, Any]]:
    host = urlparse(board_url).netloc
    rows: list[dict[str, Any]] = []
    for m in _ROW.finditer(page):
        row_html = m.group(0)
        celdas: dict[str, str] = {}
        for cm in _CELL.finditer(row_html):
            celdas[cm.group(1)] = _text(cm.group(2))
        titulo = celdas.get("class_name", "")
        if not titulo:
            continue
        rec: dict[str, Any] = {}
        for css, key in _FIELDS.items():
            if celdas.get(css) and not rec.get(key):
                rec[key] = celdas[css]
        for key in ("fecha_publicacion", "fecha_fin"):
            if key in rec:
                rec[key] = _iso(rec[key])
        preview = _PREVIEW.search(row_html)
        doc_id = preview.group(2).lower() if preview else None
        url = urljoin(board_url, html.unescape(preview.group(1))) if preview else board_url
        identity = doc_id or "|".join(
            str(rec.get(k) or "") for k in ("expediente", "titulo", "fecha_publicacion")
        )
        rows.append(
            {
                "id": "gestiona-" + hashlib.sha1(f"{host}|{identity}".encode()).hexdigest()[:20],
                "fuente": "gestiona",
                "sede": host,
                "documento_id": doc_id,
                "url": url,
                **rec,
                "celdas": {k: v for k, v in celdas.items() if k not in _FIELDS},
            }
        )
    return rows


def _opener(insecure_ssl: bool) -> urllib.request.OpenerDirector:
    handlers: list[Any] = [urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())]
    if insecure_ssl:
        handlers.append(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    return urllib.request.build_opener(*handlers)


def read_board(
    board_url: str,
    *,
    max_clicks: int = DEFAULT_MAX_CLICKS,
    delay_s: float = DEFAULT_DELAY_S,
    timeout: float = 45,
    insecure_ssl: bool = False,
    user_agent: str = USER_AGENT,
    fetch: Callable[[urllib.request.Request], str] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> BoardResult:
    """Lee el tablón completo. ``fetch`` permite inyectar la red en tests."""
    opener = _opener(insecure_ssl)
    if fetch is None:
        def fetch(request: urllib.request.Request) -> str:
            return fetch_text(request, opener=opener.open, timeout=timeout)

    first = fetch(urllib.request.Request(board_url, headers={"User-Agent": user_agent}))
    if "Sede Electrónica Indeterminada" in first or "Sede Electr&oacute;nica Indeterminada" in first:
        raise GestionaBoardError(f"{board_url}: sede Gestiona no operativa (Sede Electrónica Indeterminada)")
    if "class_name" not in first and "more_results" not in first and "board" not in first.lower():
        raise GestionaBoardError(f"{board_url}: la respuesta no parece un tablón Gestiona")
    by_id: dict[str, dict[str, Any]] = {}
    for rec in parse_rows(first, board_url):
        by_id.setdefault(rec["id"], rec)
    more = _MORE.search(first)
    clicks = 0
    base_rel = urlparse(board_url).path.lstrip("/") or "board/"
    while more and clicks < max_clicks:
        sleep(delay_s)
        url = urljoin(board_url, html.unescape(more.group(1)))
        body = html.unescape(
            fetch(
                urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": user_agent,
                        "Wicket-Ajax": "true",
                        "Wicket-Ajax-BaseURL": base_rel,
                        "Accept": "text/xml",
                    },
                )
            )
        )
        clicks += 1
        rows = parse_rows(body, board_url)
        new = [r for r in rows if r["id"] not in by_id]
        for rec in new:
            by_id[rec["id"]] = rec
        if not new:
            more = None
            break
        more = _MORE.search(body)
    return BoardResult(
        board_url=board_url,
        anuncios=list(by_id.values()),
        clicks=clicks,
        truncated=bool(more) and clicks >= max_clicks,
    )


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
