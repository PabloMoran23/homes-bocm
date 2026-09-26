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
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.ayuntamientodemanzanilla.es"
SEDE_BASE = "https://manzanilla.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
DOSSIER_URL = f"{SEDE_BASE}/dossier/"
URBANISMO_URL = f"{WEB_BASE}/es/servicios/urbanismo/"
PGOU_URL = f"{WEB_BASE}/es/pgou/"
ORDENANZAS_URL = f"{WEB_BASE}/es/ayuntamiento/ordenanzas/"
TRANSPARENCIA_PGOU_URL = (
    f"{WEB_BASE}/es/gobierno-abierto/portal-transparencia/resultados-de-transparencia/"
    "Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00040/"
)
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Manzanilla"
ID_PREFIX = "manzanilla"
INE_CODE = "21051"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    PGOU_URL,
    ORDENANZAS_URL,
    TRANSPARENCIA_PGOU_URL,
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|ocupaci[oó]n de v[ií]a p[uú]blica|aprovechamiento)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|catalogo|catálogo|normativa urban|edificaci[oó]n|"
    r"clasificaci[oó]n del suelo|usos pormenorizados|afecciones|rat\b|visor)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|subvenci[oó]n|bolsa de empleo)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://manzanilla\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_HEADING = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SKIP_HREF = re.compile(
    r"(?i)(facebook|twitter|linkedin|google\.com/share|javascript:|#|"
    r"reglamento-deportes|Reciclar\.pdf|/system/modules/)",
)


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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "catalogo" in b or "catálogo" in b:
        return "catálogo urbanístico"
    if "ordenanza" in b and "edificaci" in b:
        return "ordenanza de edificación"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "planeamiento vigente" in b or "clasificaci" in b and "suelo" in b:
        return "planeamiento"
    if "usos pormenorizados" in b or "edificabilidades" in b:
        return "normativa urbanística"
    if "rat" in b and "manzanilla" in b:
        return "reglamento de accesibilidad"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class ManzanillaAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS Saga Suite (Diputación Huelva) + sede espublico gestiona."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.dossier_url = str(self.config.get("dossier_url") or DOSSIER_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-manzanilla/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        if "emptyTable" in html or "emptyRow" in html:
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
                    "origen": "sede_tablon",
                }
            )
        return rows

    def _collect_dossier_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, inner in RE_LINK.findall(html):
            text = _strip_html(inner)
            if not text or not re.search(r"(?i)urban|licencia|obra|planeam|vivienda", text):
                continue
            url = self._abs_sede(href)
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": text[:500],
                    "url": url,
                    "blob": f"{text} {url}",
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _collect_web_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_pdf(page_url: str, href: str, title: str, origen: str) -> None:
            if RE_SKIP_HREF.search(href):
                return
            pdf_url = self._abs_web(href)
            if pdf_url in seen:
                return
            blob = f"{title} {pdf_url}"
            if not RE_PROYECTO.search(blob) and "pgou" not in origen:
                return
            seen.add(pdf_url)
            rows.append(
                {
                    "titulo": title[:500] or Path(urllib.parse.urlparse(pdf_url).path).stem,
                    "fecha": _fecha_from_blob(blob, pdf_url),
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "blob": blob,
                    "origen": origen,
                }
            )

        for seed in self.seed_pages:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue

            for href, inner in RE_LINK.findall(html):
                if not href.lower().endswith(".pdf") and ".pdf" not in href.lower():
                    continue
                add_pdf(seed, href, _strip_html(inner) or Path(href).stem, f"web_{Path(seed).name or 'page'}")

            for m in RE_PDF_HREF.finditer(html):
                add_pdf(seed, m.group(1), Path(m.group(1)).stem, f"web_{Path(seed).name or 'page'}")

            for m in RE_HEADING.finditer(html):
                title = _strip_html(m.group(1))
                if len(title) < 8 or not RE_PROYECTO.search(title):
                    continue
                key = f"{seed}#{title}"
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _fecha_from_blob(title, seed),
                        "url": seed,
                        "blob": f"{title} {seed}",
                        "origen": "web_seccion",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Sede espublico gestiona; tablón vacío a sept 2026",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.dossier_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": self.dossier_url,
                "source": "ayuntamiento",
                "nota": "Licencias, comunicaciones previas y planeamiento vía sede (sin histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", URBANISMO_URL),
                "fecha_concesion": None,
                "tipo": "información urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Servicio de Urbanismo — web municipal",
                "url": URBANISMO_URL,
                "source": "ayuntamiento",
                "nota": "Concejalía de Urbanismo; enlace a PGOU y normativa",
                "origen": "web_tramite",
            },
        ]
        for item in self._collect_dossier_tramites():
            if not RE_LICENCIA.search(item.get("blob") or item.get("titulo") or ""):
                continue
            url = item["url"]
            pages.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite sede electrónica",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Catálogo espublico gestiona",
                    "origen": item.get("origen"),
                }
            )
        return pages

    def _board_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item.get("titulo") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = item.get("url") or item.get("titulo") or ""
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": item.get("fecha"),
            "tipo": item.get("procedimiento") or "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item.get("titulo"),
            "url": item.get("url"),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _board_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item.get("titulo") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = item.get("url") or item.get("titulo") or ""
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": item.get("titulo"),
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url"),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _web_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        pdf = item.get("pdf_url") or item.get("url") or ""
        blob = item.get("blob") or item.get("titulo") or ""
        key = pdf or item.get("url") or item.get("titulo") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url") or PGOU_URL,
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
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
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": 0, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_web_docs():
            add(self._web_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Manzanilla — consulta SITUA (Junta de Andalucía)",
                "fecha": "2014-05-07",
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": f"Visor regional planeamiento INE {INE_CODE}; aprobación definitiva PGOU 2014",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pdfs": sum(1 for r in rows if r.get("pdf_url")),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
