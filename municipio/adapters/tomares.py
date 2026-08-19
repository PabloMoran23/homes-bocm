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

WP_BASE = "https://www.tomares.es"
SEDE_BASE = "https://tomares.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
MUNICIPIO = "Tomares"
ID_PREFIX = "tomares"

DIPUSEVILLA_LICENCIAS = (
    "https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4109300F"
)
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/tu-alcaldia/organizacion-municipal/urbanismo/planeamiento-general/innovaciones-al-pgou",
    f"{WP_BASE}/tu-alcaldia/organizacion-municipal/urbanismo/planeamiento-general",
    f"{WP_BASE}/tu-alcaldia/organizacion-municipal/urbanismo/plan-general-de-ordenacion-urbanistica-municipal",
    f"{WP_BASE}/tu-alcaldia/organizacion-municipal/urbanismo/planes-de-desarrollo",
    f"{WP_BASE}/tu-alcaldia/organizacion-municipal/urbanismo/planes-de-desarrollo/estudios-de-detalle",
    f"{WP_BASE}/tu-alcaldia/organizacion-municipal/urbanismo/planes-de-desarrollo/planes-especiales",
    f"{WP_BASE}/tu-alcaldia/organizacion-municipal/urbanismo/planes-de-desarrollo/planes-parciales-de-ordenacion",
    f"{WP_BASE}/tu-alcaldia/organizacion-municipal/urbanismo/proyecto-delimitacion-de-ordenacion",
    f"{WP_BASE}/tu-alcaldia/organizacion-municipal/urbanismo",
    f"{WP_BASE}/circular-urbano-de-tomares",
    f"{WP_BASE}/servicios-de-interes/existe-en-este-ayuntamiento-pic-punto-de-informacion-catastral",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licytal)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|sunp|supi|ordenanza|rectificaci[oó]n|permuta|actuaci[oó]n|"
    r"delimitaci[oó]n|zaud[ií]n|aljamar|almenas|manch[oó]n|situa|vitua)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|tasas municipales|residuos s[oó]lidos urbanos|"
    r"anuncio cobranza|bop n)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://tomares\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.tomares\.es)?/sites/default/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_MP_CODE = re.compile(r"(?i)\b(MP-\d{2})")


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
    m = RE_FECHA_YM.search(url or text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(f"{text} {url}") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_wp_url(href: str) -> str:
    return urllib.parse.urljoin(WP_BASE, unescape(href))


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if re.search(r"(?i)\bmp-\d+", blob):
        return "modificación puntual PGOU"
    if "plan parcial" in blob or " pp " in blob:
        return "plan parcial"
    if "plan especial" in blob:
        return "plan especial"
    if "estudio de detalle" in blob or "estudio detalle" in blob:
        return "estudio de detalle"
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "delimitaci" in blob:
        return "delimitación de ordenación"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "permuta" in blob:
        return "modificación planeamiento"
    if "licencia" in blob:
        return "licencia publicada"
    return "urbanismo"


class TomaresAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 7 web + sede espublico gestiona (tablón y transparencia urbanismo)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency"
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

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get(
                    "user_agent",
                    "Mozilla/5.0 poc-bocm-tomares/1.0",
                ),
            },
        )
        with self._opener.open(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

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
                cls = cm.group(1)
                cells[cls] = _strip_html(cm.group(2))

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

    def _collect_drupal_innovaciones(self) -> list[dict[str, Any]]:
        url = f"{WP_BASE}/tu-alcaldia/organizacion-municipal/urbanismo/planeamiento-general/innovaciones-al-pgou"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(r"<li[^>]*>(.*?)</li>", html, re.I | re.S):
            text = _strip_html(m.group(1))
            if len(text) < 12 or text in seen:
                continue
            if any(skip in text.lower() for skip in ("taquilla eventos", "volver", "aviso legal")):
                continue
            if not RE_PROYECTO.search(text):
                continue
            seen.add(text)
            mp = RE_MP_CODE.search(text)
            titulo = text[:500]
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_blob(text),
                    "url": url,
                    "procedimiento": "innovación PGOU",
                    "blob": text,
                    "mp_code": mp.group(1).upper() if mp else None,
                }
            )
        return rows

    def _collect_drupal_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf_url = _abs_wp_url(m.group(1))
                if pdf_url in seen_urls or "icotomares" in pdf_url.lower():
                    continue
                seen_urls.add(pdf_url)
                name = Path(urllib.parse.unquote(pdf_url.split("?")[0])).stem.replace("-", " ")
                titulo = f"{name} ({page_url.split('/tomares.es/', 1)[-1]})"
                if not RE_PROYECTO.search(titulo) and not RE_PROYECTO.search(page_url):
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(name, pdf_url),
                        "url": pdf_url,
                        "procedimiento": "documentación urbanismo",
                        "blob": f"{titulo} {page_url}",
                        "page_url": page_url,
                    }
                )
        return rows

    def _collect_transparency_index(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        if RE_PROYECTO.search(html) or "URBANISMO" in html:
            rows.append(
                {
                    "titulo": "Portal transparencia — Urbanismo, Obras Públicas y Medio Ambiente (204 docs)",
                    "fecha": None,
                    "url": self.transparency_url,
                    "procedimiento": "transparencia urbanismo",
                    "blob": "URBANISMO OBRAS PÚBLICAS MEDIO AMBIENTE transparencia",
                }
            )

        seen: set[str] = set()
        for m in re.finditer(
            r'href="((?:https://tomares\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"'
            r'[^>]*>([^<]+)',
            html,
            re.I,
        ):
            doc_url = m.group(1)
            if doc_url.startswith("/"):
                doc_url = f"{self.sede_base}{doc_url}"
            if doc_url in seen:
                continue
            seen.add(doc_url)
            doc_title = _strip_html(m.group(2))
            if not doc_title or len(doc_title) < 4:
                continue
            if not RE_PROYECTO.search(doc_title):
                continue
            rows.append(
                {
                    "titulo": doc_title[:500],
                    "fecha": _fecha_from_blob(doc_title),
                    "url": doc_url,
                    "procedimiento": "transparencia urbanismo",
                    "blob": doc_title,
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
                "titulo": "Tablón de anuncios — licencias de obra y actividad",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en sede electrónica espublico gestiona",
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
                "id": _stable_id("lic", DIPUSEVILLA_LICENCIAS),
                "fecha_concesion": None,
                "tipo": "portal licencias Diputación de Sevilla",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta pública de licencias — Diputación de Sevilla (LicytalPub)",
                "url": DIPUSEVILLA_LICENCIAS,
                "source": "ayuntamiento",
                "nota": "Enlace oficial desde web municipal; portal provincial P4109300F",
                "origen": "dipusevilla",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id(
                    "lic",
                    f"{WP_BASE}/servicios-de-interes/existe-en-este-ayuntamiento-pic-punto-de-informacion-catastral",
                ),
                "fecha_concesion": None,
                "tipo": "P.I.C. catastral",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Punto de Información Catastral (PIC)",
                "url": (
                    f"{WP_BASE}/servicios-de-interes/"
                    "existe-en-este-ayuntamiento-pic-punto-de-informacion-catastral"
                ),
                "source": "ayuntamiento",
                "nota": "Consulta parcelas y referencias catastrales en el ayuntamiento",
                "origen": "web_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "genérico")):
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
            "expte": row.get("expediente") or None,
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
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "genérico" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _drupal_to_proyecto(self, row: dict[str, Any], origen: str) -> dict[str, Any]:
        titulo = row["titulo"]
        key = row.get("mp_code") or row["url"]
        return {
            "id": _stable_id("proy", f"{origen}:{key}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(titulo, row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": origen,
        }

    def _transparency_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        return {
            "id": _stable_id("proy", f"transparency:{titulo}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(titulo, row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "transparencia",
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
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "dipusevilla", "web_tramite")),
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
        for item in self._collect_drupal_innovaciones():
            add(self._drupal_to_proyecto(item, "drupal_innovacion"))
        for item in self._collect_drupal_pdfs():
            add(self._drupal_to_proyecto(item, "drupal_pdf"))
        for item in self._collect_transparency_index():
            add(self._transparency_to_proyecto(item))

        # PGOU vigente vía SITUA (enlace oficial en web municipal)
        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Tomares — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "drupal": sum(1 for r in rows if str(r.get("origen", "")).startswith("drupal")),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
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
