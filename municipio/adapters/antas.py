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

SEDE_BASE = "https://antas.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
WEB_BASE = "https://www.antas.es"
URBANISMO_URL = f"{WEB_BASE}/urbanismo/"
ORDENANZAS_URL = f"{WEB_BASE}/reglamentos/"
TRANSPARENCY_URL = (
    f"{SEDE_BASE}/transparency/666d54b8-d709-4596-94e1-242f69de5fc7/"
)
WP_POSTS_API = f"{WEB_BASE}/wp-json/wp/v2/posts?per_page=100&_fields=id,link,title,date,content"
MUNICIPIO = "Antas"
ID_PREFIX = "antas"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|tasa.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|b[aá]sico)|pbom|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|pol[ií]gono|"
    r"cambio de uso|sunp|supi|ordenanza|rectificaci[oó]n|bando.*(?:solar|terreno)|"
    r"normativa urban|eae|evaluaci[oó]n ambiental|vivienda protegida|aljoroque|sr-\d)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|modificaci[oó]n.*presupuest|cr[eé]dito extraordinario|"
    r"jurado|fiestas locales|mercadillo|mercado semanal)",
)
RE_ORDENANZA_URBAN = re.compile(
    r"(?i)(licencia|urban|habitabilidad|intervenci[oó]n.*urban|edificaci[oó]n|"
    r"solar|terreno|construcci[oó]n|vpo|vivienda|icio|reconocimiento asimilado|"
    r"residuos.*construcci[oó]n|apertura.*establecimiento)",
)
RE_BOARD_ROW = re.compile(r'<tr[^>]*>\s*<td class="class_name".*?</tr>', re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://antas\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
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
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
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
    if "pbom" in b or "plan básico" in b or "plan basico" in b:
        return "PBOM"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "modificaci" in b and ("puntual" in b or "pgou" in b or "pbom" in b):
        return "modificación planeamiento"
    if "plan parcial" in b or "sector" in b or "polígono" in b or "poligono" in b:
        return "plan parcial"
    if "evaluaci" in b and "ambiental" in b:
        return "evaluación ambiental"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "bando" in b and ("solar" in b or "terreno" in b):
        return "bando urbanístico"
    if "ordenanza" in b or "normativa" in b:
        return "normativa urbanística"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class AntasAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress antas.es + sede espublico gestiona (tablón, transparencia PBOM)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.ordenanzas_url = str(self.config.get("ordenanzas_url") or ORDENANZAS_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-antas/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-antas/1.0"),
                "Accept": "application/json",
            },
        )
        with self._opener.open(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

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

    def _collect_transparency(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(
            r'href="((?:https://antas\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"[^>]*>([^<]{3,300})',
            html,
            re.I,
        ):
            href = self._abs_sede(m.group(1))
            titulo = _strip_html(m.group(2))
            if href in seen:
                continue
            seen.add(href)
            blob = f"{titulo} transparencia PBOM planeamiento Antas"
            if not RE_PROYECTO.search(blob):
                continue
            rows.append(
                {
                    "url": href,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "tipo": _proyecto_tipo(blob),
                    "blob": blob,
                    "origen": "transparencia",
                }
            )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        try:
            posts = self._fetch_json(self.config.get("wp_posts_api") or WP_POSTS_API)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []

        rows: list[dict[str, Any]] = []
        for post in posts:
            title = _strip_html(post.get("title", {}).get("rendered", ""))
            content = post.get("content", {}).get("rendered", "")
            blob = f"{title} {_strip_html(content)}"
            if not RE_PROYECTO.search(blob):
                continue
            link = post.get("link") or self.web_base
            fecha = (post.get("date") or "")[:10] or None
            pdf_links = [
                self._abs_web(h)
                for h in RE_HREF.findall(content)
                if ".pdf" in h.lower() or "wp-content/uploads" in h
            ]
            rows.append(
                {
                    "url": pdf_links[0] if pdf_links else link,
                    "titulo": title[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(blob),
                    "blob": blob[:2000],
                    "origen": "web_noticia",
                    "noticia_url": link,
                }
            )
        return rows

    def _collect_page_links(self, page_url: str, *, urban_filter: re.Pattern[str]) -> list[dict[str, Any]]:
        page_id = self.config.get("urbanismo_page_id", 404)
        ordenanzas_id = self.config.get("ordenanzas_page_id", 223)
        api_url = f"{self.web_base}/wp-json/wp/v2/pages/{page_id if page_url == self.urbanismo_url else ordenanzas_id}"
        try:
            page = self._fetch_json(api_url)
            content = page.get("content", {}).get("rendered", "")
        except (urllib.error.URLError, json.JSONDecodeError):
            try:
                content = self._fetch(page_url)
            except urllib.error.URLError:
                return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href in RE_HREF.findall(content):
            if not any(x in href.lower() for x in (".pdf", ".odt", ".doc", "wp-content")):
                continue
            abs_url = self._abs_web(href)
            if abs_url in seen:
                continue
            name = urllib.parse.unquote(Path(abs_url).name.replace("-", " ").replace("_", " "))
            blob = f"{name} {abs_url}"
            if not urban_filter.search(blob):
                continue
            seen.add(abs_url)
            rows.append(
                {
                    "url": abs_url,
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(name),
                    "tipo": _proyecto_tipo(blob) if urban_filter is RE_ORDENANZA_URBAN else "declaración responsable",
                    "blob": blob,
                    "origen": "web_urbanismo" if page_url == self.urbanismo_url else "web_ordenanzas",
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
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Bandos y anuncios publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "modelos declaración responsable",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — modelos normalizados y cita previa",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "DR obras, comunicación previa y cambio de uso (WordPress)",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/citaprevia.1"),
                "fecha_concesion": None,
                "tipo": "cita previa urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Cita previa — departamento de urbanismo",
                "url": f"{self.sede_base}/citaprevia.1",
                "source": "ayuntamiento",
                "nota": "Atención presencial urbanismo vía sede electrónica",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier.14"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier.14",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin histórico público)",
                "origen": "sede_tramite",
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
        ]
        for item in self._collect_page_links(self.urbanismo_url, urban_filter=RE_LICENCIA):
            pages.append(
                {
                    "id": _stable_id("lic", item["url"]),
                    "fecha_concesion": item.get("fecha"),
                    "tipo": item.get("tipo") or "modelo trámite urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "origen": "web_modelo",
                }
            )
        return pages

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
        if not RE_PROYECTO.search(blob):
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

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "noticia_url": row.get("noticia_url"),
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
            "info": sum(1 for r in rows if r.get("origen") != "tablon"),
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
        for item in self._collect_transparency():
            add(self._doc_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._doc_to_proyecto(item))
        for item in self._collect_page_links(self.ordenanzas_url, urban_filter=RE_ORDENANZA_URBAN):
            add(self._doc_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "web_noticia": sum(1 for r in rows if r.get("origen") == "web_noticia"),
            "web_ordenanzas": sum(1 for r in rows if r.get("origen") == "web_ordenanzas"),
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
