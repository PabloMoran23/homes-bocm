from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

INFO_PUBLICA_BASE = "https://informacionpublica.marbella.es"
URBANISMO_WEB = "https://urbanismo.marbella.es"
SEDE_BASE = "https://marbella.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
MUNICIPIO = "Marbella"
ID_PREFIX = "marbella"

DEFAULT_RSS_FEEDS: list[str] = [
    f"{INFO_PUBLICA_BASE}/ambitos/urbanismo-y-ecologia.feed?type=rss",
    f"{INFO_PUBLICA_BASE}/feed?type=rss",
]

DEFAULT_LIST_PAGES: list[str] = [
    f"{INFO_PUBLICA_BASE}/ambitos/urbanismo-y-ecologia.html",
    f"{INFO_PUBLICA_BASE}/ambitos/urbanismo-y-ecologia/planeamiento.html",
    f"{INFO_PUBLICA_BASE}/ambitos/urbanismo-y-ecologia/infraestructuras.html",
    f"{URBANISMO_WEB}/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia apertura|apertura de local|"
    r"instrucci[oó]n.*licencias)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|atu|delimitaci[oó]n|"
    r"cambio de uso|ordenanza|urbanizaci[oó]n|infraestructura|reforma interior|"
    r"\burp[- ][a-z]{2}[- ]\d+|\bpa[- ][a-z]{2}[- ]\d+|\bpa-[a-z]{2}-\d+)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"modificaci[oó]n presupuestaria|cr[eé]dito extraordinario|transferencia de cr[eé]dito|"
    r"ejercicio presupuestario|subvenciones.*taxi|polic[ií]a local|aparcamiento)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://marbella\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_INFO_ARTICLE = re.compile(
    r'<a[^>]+href="(/ambitos/urbanismo-y-ecologia/[^"#?]+\.html)"[^>]*>'
    r'[\s\S]*?<span class="uk-link-heading">(.*?)</span>',
    re.I | re.S,
)
RE_URBANISMO_ARTICLE = re.compile(
    r'<a[^>]+href="(/[^"#?]+\.html)"[^>]*>'
    r'[\s\S]*?<h3[^>]*>.*?<span class="uk-link-heading">(.*?)</span>',
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_PUBLISHED = re.compile(
    r'Publicado el\s+(\d{1,2})\s+(\w+)\s+(\d{4})',
    re.I,
)
RE_EXPDTE = re.compile(
    r"(?i)(?:exp(?:ediente)?\.?|expte\.?)\s*([0-9]+/[0-9]{4})|\b(\d{1,6}/\d{4})\b",
)
MES_ES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text.strip()).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_PUBLISHED.search(text or "")
    if m:
        mes = MES_ES.get(m.group(2).lower())
        if mes:
            try:
                return datetime(int(m.group(3)), mes, int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    years = [
        int(x.group(1))
        for x in re.finditer(r"\b((?:19|20)\d{2})\b", text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _extract_expte(text: str) -> str | None:
    m = RE_EXPDTE.search(text or "")
    if not m:
        return None
    return m.group(1) or m.group(2)


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgom" in b or ("plan general" in b and "ordenaci" in b):
        return "PGOM"
    if "pgou" in b:
        return "PGOU"
    if "reparcel" in b:
        return "reparcelación"
    if "urbanizaci" in b and "proyecto" in b:
        return "proyecto de urbanización"
    if "delimitaci" in b or "atu" in b:
        return "delimitación ATU"
    if "modificaci" in b:
        return "modificación planeamiento"
    if "admisi" in b and "tr[aá]mite" in b:
        return "admisión a trámite"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "infraestructura" in b:
        return "infraestructuras urbanísticas"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class MarbellaAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal información pública Joomla + delegación urbanismo + tablón sede espublico."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or INFO_PUBLICA_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.info_base = str(self.config.get("info_publica_base") or INFO_PUBLICA_BASE).rstrip("/")
        self.urbanismo_web = str(self.config.get("urbanismo_web") or URBANISMO_WEB).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.rss_feeds = [str(u) for u in (self.config.get("rss_feeds") or DEFAULT_RSS_FEEDS)]
        self.list_pages = [str(u) for u in (self.config.get("list_pages") or DEFAULT_LIST_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-marbella/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_info(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.info_base}/", unescape(href))

    def _abs_urbanismo(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.urbanismo_web}/", unescape(href))

    def _collect_rss(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for feed_url in self.rss_feeds:
            try:
                xml_text = self._fetch(feed_url)
            except urllib.error.URLError:
                continue
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError:
                continue
            channel = root.find("channel")
            if channel is None:
                channel = root
            for item in channel.findall("item"):
                title = _strip_html(item.findtext("title") or "")
                link = (item.findtext("link") or "").strip()
                if not title or not link:
                    continue
                if "/urbanismo-y-ecologia/" not in link and "urbanismo" not in title.lower():
                    if not RE_PROYECTO.search(title) and not RE_LICENCIA.search(title):
                        continue
                if link in seen:
                    continue
                seen.add(link)
                fecha = _parse_rss_date(item.findtext("pubDate") or "")
                cat = item.findtext("category") or ""
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": link,
                        "fecha": fecha,
                        "categoria": cat[:120],
                        "blob": f"{title} {cat} {link}",
                        "origen": "info_publica_rss",
                    }
                )
        return rows

    def _collect_list_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.list_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            if "informacionpublica.marbella.es" in page_url:
                for m in RE_INFO_ARTICLE.finditer(html):
                    href, title = m.group(1), _strip_html(m.group(2))
                    url = self._abs_info(href)
                    if url in seen:
                        continue
                    seen.add(url)
                    ctx_start = max(0, m.start() - 400)
                    ctx = html[ctx_start : m.end() + 200]
                    rows.append(
                        {
                            "titulo": title[:500],
                            "url": url,
                            "fecha": _fecha_from_blob(ctx),
                            "blob": f"{title} {url}",
                            "origen": "info_publica_html",
                        }
                    )
            else:
                for m in RE_URBANISMO_ARTICLE.finditer(html):
                    href, title = m.group(1), _strip_html(m.group(2))
                    if not title or len(title) < 12:
                        continue
                    url = self._abs_urbanismo(href)
                    blob = f"{title} {url}"
                    if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                        continue
                    if url in seen:
                        continue
                    seen.add(url)
                    ctx_start = max(0, m.start() - 300)
                    ctx = html[ctx_start : m.end() + 200]
                    rows.append(
                        {
                            "titulo": title[:500],
                            "url": url,
                            "fecha": _fecha_from_blob(ctx),
                            "blob": blob,
                            "origen": "urbanismo_web",
                        }
                    )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento or documento in ("Documento",):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Marbella",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos y anuncios publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes (requiere identificación)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Consulta individual con certificado; no hay listado abierto de licencias concedidas",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id(
                    "lic",
                    f"{self.urbanismo_web}/documentos/instrucciones/instruccion-para-la-agilizacion-administrativa-en-la-tramitacion-de-licencias-de-obra.html",
                ),
                "fecha_concesion": None,
                "tipo": "instrucción tramitación licencias",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Instrucción agilización administrativa — licencias de obra",
                "url": (
                    f"{self.urbanismo_web}/documentos/instrucciones/"
                    "instruccion-para-la-agilizacion-administrativa-en-la-tramitacion-de-licencias-de-obra.html"
                ),
                "source": "ayuntamiento",
                "nota": "Normativa interna; sin registro público de concesiones",
                "origen": "urbanismo_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
            return True
        if "urban" in cat or "planeamiento" in cat:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or _extract_expte(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or _extract_expte(row["titulo"]),
            "origen": "tablon",
        }

    def _portal_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        titulo = row["titulo"]
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": _extract_expte(titulo),
            "origen": row.get("origen", "info_publica"),
        }

    def _portal_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(row.get("titulo", "")):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": _extract_expte(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "info_publica"),
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def _collect_portal_items(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for src in (self._collect_rss(), self._collect_list_pages()):
            for item in src:
                url = item.get("url") or ""
                if url and url not in seen:
                    seen.add(url)
                    merged.append(item)
        return merged

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_portal_items():
            rec = self._portal_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(
                1
                for r in rows
                if r.get("origen")
                in ("sede_tablon", "sede_tramite", "urbanismo_tramite", "info_publica_rss", "info_publica_html")
            ),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_portal_items():
            rec = self._portal_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_portal_items():
            add(self._portal_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info_publica": sum(
                1 for r in rows if r.get("origen") in ("info_publica_rss", "info_publica_html", "urbanismo_web")
            ),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": after,
                    "added": max(0, after - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
