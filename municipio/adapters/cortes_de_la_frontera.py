from __future__ import annotations

import base64
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

WEB_BASE = "https://www.cortesdelafrontera.es"
SEDE_BASE = "https://sede.malaga.es/cortesdelafrontera"
BOARD_URL = f"{SEDE_BASE}/tablon-de-anuncios/"
TRANSPARENCY_URL = (
    "http://www.malaga.es/gobiernoabierto/portal/entidad/ent-770/cortesdelafrontera"
)
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Cortes de la Frontera"
ID_PREFIX = "cortes-de-la-frontera"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/12046/planeamiento-urbanistico-pgou",
    f"{WEB_BASE}/12044/informacion-sobre-solicitudes-de-licencia-de-obra",
    f"{WEB_BASE}/12045/peticion-de-informe-a-adif-para-licencias-de-obra-con-limitacion-a-linea-ferrea",
    f"{WEB_BASE}/12050/informacion-para-las-peticiones-de-licencia-de-apertura",
    f"{WEB_BASE}/12051/solicitud-de-licencia-para-animales-peligrosos",
    (
        f"{WEB_BASE}/8233/com1_md-3/com1_md3_cd-62417/"
        "formularios-declaraciones-responsables"
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|anexo\s+\d+)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|rectificaci[oó]n|situa|vitua)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|bolsa de empleo|auxiliar administrativo)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://sede\.malaga\.es)?/[^"]*preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WEB_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _situa_planeamiento_url() -> str:
    params = {
        "municipiosseleccionados": "29046",
        "municipiosSelec": "CORTES DE LA FRONTERA",
        "codigosMunicipios": "29046",
        "checkBoxSel": "aprobado",
        "DataTables_Table_0_length": "10",
        "tituloNNSSPP": "Planeamiento general aprobado de CORTES DE LA FRONTERA",
        "codigosNombresMunicipios": '[{"id":"29046","nombre":"CORTES DE LA FRONTERA"}]',
    }
    encoded = base64.b64encode(urllib.parse.urlencode(params).encode()).decode()
    return (
        "https://ws132.juntadeandalucia.es/situadifusion/pages/"
        f"planeamientoGeneralCompartir.jsf?{encoded}"
    )


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "situa" in b or "planeamiento general" in b:
        return "planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "licencia" in b:
        return "licencia publicada"
    if "declaraci" in b and "responsable" in b:
        return "declaración responsable"
    return "urbanismo"


class CortesDeLaFronteraAyuntamientoAdapter(AyuntamientoAdapter):
    """Web Diputación Málaga (static.malaga.es) + sede.malaga.es + SITUA Junta de Andalucía."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)
        self.situa_url = str(self.config.get("situa_planeamiento_url") or _situa_planeamiento_url())
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

    def _user_agent(self, url: str) -> str:
        browser_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        if "cortesdelafrontera.es" in url or "static.malaga.es" in url:
            return browser_ua
        return str(self.config.get("user_agent") or browser_ua)

    def _fetch(self, url: str, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self._user_agent(url),
                "Accept-Language": "es-ES,es;q=0.9",
            },
        )
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "latin-1"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.web_base}/", href))

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, timeout=20)
        except (urllib.error.URLError, TimeoutError, OSError):
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
                url = f"https://sede.malaga.es{url}"

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

    def _collect_web_formularios(self) -> list[dict[str, Any]]:
        form_url = (
            f"{self.web_base}/8233/com1_md-3/com1_md3_cd-62417/"
            "formularios-declaraciones-responsables"
        )
        try:
            html = self._fetch(form_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_WEB_LINK.finditer(html):
            href = self._abs_web(m.group(1))
            text = _strip_html(m.group(2))
            if "static.malaga.es" not in href or ".pdf" not in href.lower():
                continue
            if href in seen:
                continue
            seen.add(href)
            rows.append(
                {
                    "url": href,
                    "titulo": text[:500] or Path(urllib.parse.urlparse(href).path).name,
                    "tipo": "declaración responsable",
                    "fecha": None,
                    "blob": f"{text} declaración responsable licencia obra Cortes de la Frontera",
                    "origen": "web_formulario",
                }
            )
        return rows

    def _collect_web_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url in self.seed_pages:
            if page_url in seen:
                continue
            seen.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            title_m = re.search(
                r'class="twelve columns contenido"><div class="tituloSeccion">([^<]+)</div>',
                html,
                re.I,
            )
            titulo = _strip_html(title_m.group(1)) if title_m else page_url.rsplit("/", 1)[-1]
            rows.append(
                {
                    "url": page_url,
                    "titulo": titulo[:500],
                    "tipo": _proyecto_tipo(titulo),
                    "fecha": None,
                    "blob": f"{titulo} urbanismo Cortes de la Frontera",
                    "origen": "web_tramite",
                }
            )

            for m in RE_WEB_LINK.finditer(html):
                href = self._abs_web(m.group(1))
                text = _strip_html(m.group(2))
                if "juntadeandalucia" in href and "situa" in href.lower():
                    rows.append(
                        {
                            "url": href,
                            "titulo": f"SITUA — consulta planeamiento ({text or 'Junta de Andalucía'})",
                            "tipo": "planeamiento",
                            "fecha": None,
                            "blob": f"SITUA PGOU Cortes de la Frontera {text}",
                            "origen": "situa",
                        }
                    )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede Diputación de Málaga",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos y anuncios en sede.malaga.es (timeout SSL posible en CI)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — Diputación de Málaga",
                "url": self.sede_base,
                "source": "ayuntamiento",
                "nota": "Trámites y presentación telemática vía sede.malaga.es",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/12044/informacion-sobre-solicitudes-de-licencia-de-obra"),
                "fecha_concesion": None,
                "tipo": "información licencia de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Información sobre solicitudes de licencia de obra",
                "url": f"{self.web_base}/12044/informacion-sobre-solicitudes-de-licencia-de-obra",
                "source": "ayuntamiento",
                "nota": "Trámite informativo en web municipal (Diputación Málaga)",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/12050/informacion-para-las-peticiones-de-licencia-de-apertura"),
                "fecha_concesion": None,
                "tipo": "licencias de apertura",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Información para peticiones de licencia de apertura",
                "url": f"{self.web_base}/12050/informacion-para-las-peticiones-de-licencia-de-apertura",
                "source": "ayuntamiento",
                "nota": "Formularios y requisitos de apertura de locales",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id(
                    "lic",
                    f"{self.web_base}/8233/com1_md-3/com1_md3_cd-62417/formularios-declaraciones-responsables",
                ),
                "fecha_concesion": None,
                "tipo": "declaraciones responsables (formularios PDF)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Formularios declaraciones responsables — urbanismo",
                "url": (
                    f"{self.web_base}/8233/com1_md-3/com1_md3_cd-62417/"
                    "formularios-declaraciones-responsables"
                ),
                "source": "ayuntamiento",
                "nota": "11 anexos PDF (obra, cambio de uso, comunicación previa, etc.)",
                "origen": "web_formulario",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
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
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _formulario_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "declaración responsable",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web_formulario",
        }

    def _web_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row.get("blob") or ""),
            "tipo": row.get("tipo") or _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web_tramite",
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
        for item in self._collect_web_formularios():
            rec = self._formulario_to_licencia(item)
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
            "formularios": sum(1 for r in rows if r.get("origen") == "web_formulario"),
            "info": sum(
                1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")
            ),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_web_formularios():
            existing[self._formulario_to_licencia(item)["id"]] = self._formulario_to_licencia(item)
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

        add(
            self._web_to_proyecto(
                {
                    "url": self.situa_url,
                    "titulo": "PGOU Cortes de la Frontera — consulta SITUA (Junta de Andalucía)",
                    "tipo": "PGOU",
                    "fecha": None,
                    "blob": "PGOU planeamiento SITUA Cortes de la Frontera INE 29046",
                    "origen": "situa",
                }
            )
        )

        for item in self._collect_web_seed_pages():
            if item.get("origen") == "situa":
                add(self._web_to_proyecto(item))
            elif RE_PROYECTO.search(item.get("blob") or item.get("titulo") or ""):
                add(self._web_to_proyecto(item))

        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
            "web": sum(1 for r in rows if r.get("origen") in ("web_tramite",)),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
