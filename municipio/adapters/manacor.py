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

WEB_BASE = "https://manacor.org"
SEDE_BASE = "https://manacor.eadministracio.cat"
BOARD_URL = f"{SEDE_BASE}/board"
TRANSPARENCY_URBAN = f"{SEDE_BASE}/transparency/32805cd0-06d5-40e5-8879-2e8304830f35/"
URBANISMO_URL = f"{WEB_BASE}/es/urbanismo"
URBANISME_URL = f"{WEB_BASE}/ca/urbanisme"
PGOU_URL = "https://plageneral.manacor.org/"
SITMUN_URL = "https://sitmun.idelma.cat/urb_manacor"
CITIZEN_URBANISME = f"{SEDE_BASE}/citizen-service/9958a625-760e-4915-b506-f0e4acae37d8"
NOTICIAS_RSS = f"{WEB_BASE}/es/noticias/rss.xml"
MUNICIPIO = "Manacor"
ID_PREFIX = "manacor"

DEFAULT_LICENCIA_PAGES: list[dict[str, str]] = [
    {
        "url": f"{WEB_BASE}/es/archivos-y-documentos/modelo-de-comunicacion-previa-de-obras-castellano",
        "tipo": "comunicación previa",
        "titulo": "Modelo comunicación previa de obras (castellano)",
    },
    {
        "url": f"{WEB_BASE}/es/archivos-y-documentos/modelo-de-comunicacion-previa-de-obras-catalan",
        "tipo": "comunicación previa",
        "titulo": "Modelo comunicació prèvia d'obres (català)",
    },
    {
        "url": f"{WEB_BASE}/es/archivos-y-documentos/modelo-de-comunicacion-previa-de-obras-para-actividades-menores-o-inocuas",
        "tipo": "comunicación previa",
        "titulo": "Comunicación previa obras actividades menores o inocuas",
    },
    {
        "url": CITIZEN_URBANISME,
        "tipo": "trámites urbanismo",
        "titulo": "Urbanisme — sede electrónica (llicències, comunicacions prèvies)",
    },
    {
        "url": f"{WEB_BASE}/es/enlaces/41-clicar-aqui-para-contactar-con-el-departamento-de-urbanismo-y-obras-del-ayuntamiento-de",
        "tipo": "contacto urbanismo",
        "titulo": "Contacto departamento de urbanismo y obras",
    },
]

DEFAULT_PROYECTO_SEEDS: list[dict[str, str]] = [
    {
        "url": PGOU_URL,
        "titulo": "Pla General d'Ordenació Urbanística de Manacor",
        "tipo": "PGOU",
    },
    {
        "url": SITMUN_URL,
        "titulo": "SITMUN — visor d'informació urbanística Manacor",
        "tipo": "visor GIS",
    },
    {
        "url": TRANSPARENCY_URBAN,
        "titulo": "Transparència — documents urbanisme (portal sede)",
        "tipo": "documentación urbanística",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licen|licèn|llic[eè]ncia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autoritz|autoriz|obra[s]? (?:major|menor)|certificat|modelo de comunicaci)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|planej|plan (?:parcial|especial|general)|pgou|pla general|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|projecte|modificaci[oó]n|reparcel|"
    r"sector|pol[ií]gon|unitat d.actuaci|obres?|ampliaci[oó]|urbanitz|visor|sitmun|"
    r"ordenan|normes urban|iee\b|epcu|decret urb|planol|cam[ií]ns)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocat[oò]ria.*empleo|"
    r"subvencion|subvenci[oó]|jurado|mercadet|conserge|policia|ple\b|"
    r"habitatges municipals|serveis socials)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://manacor\.eadministracio\.cat)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_URBANISMO_NEWS = re.compile(
    r'href="((?:https://manacor\.org)?/(?:ca/noticies|es/noticias)/[^"]+)"[^>]*>([^<]{8,})',
    re.I,
)
RE_FILE_LINK = re.compile(
    r'href="((?:https://manacor\.org)?/sites/cilma_manacor/files/[^"]+\.pdf[^"]*)"[^>]*>([^<]{4,})',
    re.I,
)
RE_TRANSPARENCY_ROW = re.compile(r"<tr[^>]*>.*?</tr>", re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_NEWS = re.compile(
    r"(\d{1,2})[-/](enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre|gener|febrer|març|abril|maig|juny|"
    r"juliol|agost|setembre|octubre|novembre|desembre)[-/](\d{4})",
    re.I,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

_MONTH = {
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
    "gener": 1,
    "febrer": 2,
    "març": 3,
    "maig": 5,
    "juny": 6,
    "juliol": 7,
    "agost": 8,
    "setembre": 9,
    "desembre": 12,
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_NEWS.search(text or "")
    if m:
        mo = _MONTH.get(m.group(2).lower())
        if mo:
            try:
                return datetime(int(m.group(3)), mo, int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return _parse_fecha_dmy(text)


def _proyecto_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "pgou" in n or "pla general" in n:
        return "PGOU"
    if "plan parcial" in n or "pla parcial" in n:
        return "plan parcial"
    if "polígon" in n or "poligon" in n:
        return "desarrollo urbanístico"
    if "visor" in n or "sitmun" in n:
        return "visor GIS"
    if "ordenança" in n or "ordenanza" in n:
        return "normativa urbanística"
    if "iee" in n:
        return "informe evaluación edificios"
    if "obres" in n or "obra" in n:
        return "obra pública / urbanismo"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    return "urbanismo"


def _licencia_tipo(text: str) -> str:
    n = (text or "").lower()
    if "comunicaci" in n:
        return "comunicación previa"
    if "llic" in n or "licen" in n:
        return "licencia urbanística"
    if "certificat" in n:
        return "certificado urbanístico"
    return "trámite urbanismo"


class ManacorAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal manacor.org + sede espublico (eadministracio.cat) + PGOU/SITMUN (sin WFS público)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.transparency_url = str(
            self.config.get("transparency_urban_url") or TRANSPARENCY_URBAN
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-manacor/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

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
            if not documento or documento in ("Document", "Documento"):
                continue

            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            url = self._abs_sede(url)

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
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if "urban" in proc or "obra" in proc:
            return True
        return bool(RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob))

    def _collect_transparency(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TRANSPARENCY_ROW.finditer(html):
            row_html = m.group(0)
            if "preview-document" not in row_html:
                continue
            preview_m = RE_PREVIEW_LINK.search(row_html)
            if not preview_m:
                continue
            url = self._abs_sede(preview_m.group(1))
            if url in seen:
                continue
            seen.add(url)
            titulo = _strip_html(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            if title_m and len(title_m.group(1).strip()) > 8:
                titulo = title_m.group(1).strip()
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(titulo),
                    "url": url,
                    "origen": "sede_transparencia",
                    "blob": titulo,
                }
            )
        return rows

    def _collect_urbanismo_page(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in (URBANISMO_URL, URBANISME_URL):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_URBANISMO_NEWS.finditer(html):
                url = self._abs_web(m.group(1))
                titulo = _strip_html(m.group(2))
                if len(titulo) < 12:
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _parse_fecha_dmy(titulo),
                        "url": url,
                        "origen": "web_urbanismo_noticia",
                        "blob": titulo,
                    }
                )
            for m in RE_FILE_LINK.finditer(html):
                url = self._abs_web(m.group(1))
                titulo = _strip_html(m.group(2)) or url.split("/")[-1]
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _parse_fecha_dmy(titulo + " " + url),
                        "url": url,
                        "origen": "web_urbanismo_pdf",
                        "blob": titulo,
                    }
                )
        return rows

    def _collect_rss_urban(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(NOTICIAS_RSS)
            root = ET.fromstring(raw)
        except (urllib.error.URLError, ET.ParseError):
            return []
        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = _strip_html(item.findtext("description") or "")
            pub = _parse_rss_date(item.findtext("pubDate") or "")
            blob = f"{title} {desc}"
            if not RE_PROYECTO.search(blob):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": pub,
                    "url": link or URBANISMO_URL,
                    "origen": "web_rss",
                    "blob": blob,
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in DEFAULT_LICENCIA_PAGES:
            rows.append(
                {
                    "id": _stable_id("lic", seed["url"]),
                    "fecha_concesion": None,
                    "tipo": seed.get("tipo") or _licencia_tipo(seed["titulo"]),
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "source": "ayuntamiento",
                    "titulo": seed["titulo"],
                    "url": seed["url"],
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _collect_proyecto_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in DEFAULT_PROYECTO_SEEDS:
            rows.append(
                {
                    "id": _stable_id("proy", seed["url"]),
                    "municipio": MUNICIPIO,
                    "titulo": seed["titulo"],
                    "fecha": None,
                    "tipo": seed.get("tipo") or _proyecto_tipo(seed["titulo"]),
                    "url": seed["url"],
                    "source": "ayuntamiento",
                    "origen": "semilla",
                }
            )
        return rows

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        url = item.get("url") or URBANISMO_URL
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": item.get("titulo") or blob[:200],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": item.get("origen"),
            "expte": item.get("expediente"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        proc = (row.get("procedimiento") or "").lower()
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) and "urban" not in proc:
            return None
        rec = self._item_to_proyecto(
            {
                "titulo": row.get("titulo") or row.get("documento"),
                "fecha": row.get("fecha"),
                "url": row.get("url"),
                "blob": blob,
                "origen": "tablon",
                "expediente": row.get("expediente"),
            }
        )
        return rec

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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats["rows"]
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_proyecto_seeds():
            add(rec)
        for item in self._collect_urbanismo_page():
            add(self._item_to_proyecto(item))
        for item in self._collect_rss_urban():
            add(self._item_to_proyecto(item))
        for item in self._collect_transparency():
            add(self._item_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "sede_transparencia"),
            "with_geometry": 0,
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
