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

WP_BASE = "https://alhendin.es"
SEDE_BASE = "https://alhendin.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
PGOU_URL = f"{WP_BASE}/pgou/"
PGOU_PDF_URL = f"{WP_BASE}/wp-content/uploads/2016/05/Normas-Urbanisticas-ADefinitiva.pdf"
SITUA_SEARCH = (
    "http://ws041.juntadeandalucia.es/medioambiente/situadifusion/pages/search.jsf"
)
DIPGRA_PLANEAMIENTO = (
    "https://www.dipgra.es/municipios/asistencia-a-municipios/asistencia/"
    "asistencia-urbanistica/planeamiento-urbanistico/"
)
MUNICIPIO = "Alhendín"
ID_PREFIX = "alhendin"

PROYECTO_SEED_PAGES: list[str] = [
    PGOU_URL,
    f"{WP_BASE}/asimilado-fuera-de-ordenacion/",
    f"{WP_BASE}/vivienda-protegida/",
    f"{WP_BASE}/urbanismo/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|primera ocupaci[oó]n|segregaci[oó]n|parcelaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|sunp|supi|ordenanza|rectificaci[oó]n|divisi[oó]n|segregaci[oó]n|"
    r"innovaci[oó]n|actuaci[oó]n|vivienda protegida|fuera de ordenaci[oó]n|asimilad)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|modificaci[oó]n.*presupuest|cr[eé]dito extra|"
    r"juez de paz|juzgado de paz|certamen de teatro|teatro no profesional|"
    r"subvenci[oó]n|contrataci[oó]n|empleo@|auxiliar administrativo)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://alhendin\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://alhendin\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_WP_STRICT = re.compile(
    r"(?i)(pgou|planeam|innovaci[oó]n.*pgou|modificaci[oó]n.*pgou|"
    r"norma urban|informaci[oó]n p[uú]blica|sector sub|sector api|"
    r"vivienda protegida|fuera de ordenaci[oó]n|boja|normativa urban|"
    r"planta de biometano|base a[eé]rea.*normativa urban)",
)
RE_FORM_PDF = re.compile(
    r"(?i)(solicitud|autoliquidaci[oó]n|declaraci[oó]n responsable|"
    r"modelo de|formulario|instrucciones|anexo|bonificaci[oó]n tasa|"
    r"impuesto sobre|autorizaci[oó]n para|certificado de empadron)",
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
    m = RE_FECHA_ISO.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = re.search(r"/(\d{4})/(\d{2})/", url or text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
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
    if "innovaci" in b and "pgou" in b:
        return "innovación PGOU"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "planeamiento de desarrollo" in b or "actuaci" in b:
        return "actuación urbanística"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "vivienda protegida" in b:
        return "vivienda protegida"
    if "fuera de ordenaci" in b or "asimilad" in b:
        return "fuera de ordenación"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class AlhendinAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress alhendin.es + sede espublico gestiona (tablón) + PGOU/SITUA Junta Andalucía."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.proyecto_seed_pages = [
            str(u) for u in (self.config.get("proyecto_seed_pages") or PROYECTO_SEED_PAGES)
        ]
        self.wp_search_terms = list(
            self.config.get("wp_search_terms") or ("pgou", "planeamiento", "innovacion pgou")
        )
        self.wp_max_pages = int(self.config.get("wp_max_pages", 3))
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
                    "Mozilla/5.0 poc-bocm-alhendin/1.0",
                ),
            },
        )
        with self._opener.open(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", unescape(href))

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

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for term in self.wp_search_terms:
            for page in range(1, self.wp_max_pages + 1):
                q = urllib.parse.quote(term)
                url = (
                    f"{self.wp_base}/wp-json/wp/v2/posts"
                    f"?search={q}&per_page=100&page={page}"
                    f"&_fields=id,date,link,title,content"
                )
                try:
                    data = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(data, list) or not data:
                    break
                for post in data:
                    pid = int(post.get("id") or 0)
                    if pid in seen:
                        continue
                    title = _strip_html(post.get("title", {}).get("rendered", ""))
                    blob = f"{title} {_strip_html(post.get('content', {}).get('rendered', ''))}"
                    if not RE_WP_STRICT.search(blob):
                        continue
                    seen.add(pid)
                    rows.append(
                        {
                            "id": pid,
                            "titulo": title[:500],
                            "fecha": (post.get("date") or "")[:10] or None,
                            "url": post.get("link") or "",
                            "blob": blob[:2000],
                            "origen": "wp_search",
                        }
                    )
                if len(data) < 100:
                    break
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(url: str, titulo: str, fecha: str | None, origen: str) -> None:
            abs_url = self._abs_wp(url)
            if abs_url in seen:
                return
            seen.add(abs_url)
            rows.append(
                {
                    "url": abs_url,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(titulo),
                    "blob": f"{titulo} {abs_url}",
                    "origen": origen,
                }
            )

        add(
            PGOU_PDF_URL,
            "PGOU Alhendín — Normas urbanísticas (aprobación definitiva)",
            "2016-05-01",
            "pgou_pdf",
        )

        for page_url in self.proyecto_seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_wp(m.group(1))
                if pdf in seen:
                    continue
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                blob = f"{name} {page_url}"
                if RE_FORM_PDF.search(name) and not re.search(
                    r"(?i)pgou|planeam|norma urban|fuera de orden|vivienda protegida",
                    blob,
                ):
                    continue
                if not RE_PROYECTO.search(blob):
                    continue
                seen.add(pdf)
                rows.append(
                    {
                        "url": pdf,
                        "titulo": name.replace("-", " ").replace("_", " ")[:500],
                        "fecha": _fecha_from_blob(name, pdf),
                        "tipo": _proyecto_tipo(blob),
                        "blob": blob,
                        "origen": "wp_seed_pdf",
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
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y edictos publicados en espublico gestiona",
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
                "nota": "Licencias y comunicaciones previas vía sede (sin histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.wp_base}/impresos-urbanismo/licencias-de-obra-mayor-y-menor/"),
                "fecha_concesion": None,
                "tipo": "impresos licencias de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias de obra mayor y menor — formularios",
                "url": f"{self.wp_base}/impresos-urbanismo/licencias-de-obra-mayor-y-menor/",
                "source": "ayuntamiento",
                "nota": "Modelos solicitud, declaración responsable y tasas",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.wp_base}/impresos-urbanismo/licencias-de-actividad/"),
                "fecha_concesion": None,
                "tipo": "impresos licencias de actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias de actividad — formularios",
                "url": f"{self.wp_base}/impresos-urbanismo/licencias-de-actividad/",
                "source": "ayuntamiento",
                "nota": "Apertura, cambio titularidad y calificación ambiental",
                "origen": "web_tramite",
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
                "nota": "Requiere identificación Cl@ve; no hay listado público",
                "origen": "sede_tramite",
            },
        ]

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", PGOU_PDF_URL),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Alhendín — Normas urbanísticas (PDF)",
                "fecha": "2016-05-01",
                "tipo": "PGOU",
                "url": PGOU_PDF_URL,
                "source": "ayuntamiento",
                "origen": "pgou_pdf",
            },
            {
                "id": _stable_id("proy", PGOU_URL),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Alhendín — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": PGOU_URL,
                "source": "ayuntamiento",
                "origen": "web_pgou",
            },
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "Planeamiento aprobado — SituaDIFusión Junta de Andalucía",
                "fecha": None,
                "tipo": "planeamiento",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
            },
            {
                "id": _stable_id("proy", DIPGRA_PLANEAMIENTO),
                "municipio": MUNICIPIO,
                "titulo": "Planeamiento urbanístico — Diputación de Granada",
                "fecha": None,
                "tipo": "planeamiento",
                "url": DIPGRA_PLANEAMIENTO,
                "source": "ayuntamiento",
                "origen": "diputacion_planeamiento",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        proc = (row.get("procedimiento") or "").lower()
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "vivienda")):
            return True
        urban_blob = re.sub(r"(?i)\bexpediente\b", "", blob)
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(urban_blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
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
        urban_blob = re.sub(r"(?i)\bexpediente\b", "", blob)
        if not RE_PROYECTO.search(urban_blob) and "planeamiento" not in proc:
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

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = str(row.get("url") or row.get("id"))
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "wp_search"),
        }

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row.get("blob") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "wp_seed_pdf"),
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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")),
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

        for rec in self._collect_proyecto_info_pages():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._wp_to_proyecto(item))
        for item in self._collect_seed_pdfs():
            add(self._seed_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "static": sum(
                1
                for r in rows
                if r.get("origen")
                in ("web_pgou", "pgou_pdf", "situa", "diputacion_planeamiento")
            ),
            "wp": sum(
                1
                for r in rows
                if str(r.get("origen", "")).startswith(("wp_", "pgou_"))
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
