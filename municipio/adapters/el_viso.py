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

WP_BASE = "https://ayto-elviso.com"
SEDE_BASE = "https://elviso.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
MODELOS_URL = f"{WP_BASE}/modelos-de-solicitudes-varias/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "El Viso"
ID_PREFIX = "el-viso"

WP_BANDOS_CATEGORY = 4

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|icio|construcciones.*instalaciones)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|actuaci[oó]n|expropiaci[oó]n|ampliaci[oó]n.*instalaciones|"
    r"inter[eé]s p[uú]blico|ganader)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza|padrones|presupuesto|estado de ejecuci[oó]n|acta.*pleno|"
    r"subvenci[oó]n.*deportista|residuos dom[eé]sticos|palomas|piscina|feria|"
    r"emproacsa|hidraulico|puesta al cobro)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://elviso\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://ayto-elviso\.com)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_BOP_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
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


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "ordenanza" in blob and ("obra" in blob or "icio" in blob or "construccion" in blob):
        return "ordenanza fiscal urbanística"
    if "actuaci" in blob and "inter[eé]s p[uú]blico" in blob:
        return "actuación de interés público"
    if "ampliaci" in blob and "instalaciones" in blob:
        return "proyecto de actuación"
    if "licencia" in blob:
        return "licencia publicada"
    if "bop" in blob or "boja" in blob:
        return "publicación oficial"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    return "urbanismo"


class ElVisoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Elementor (bandos + modelos) + sede espublico gestiona (tablón)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.modelos_url = str(self.config.get("modelos_url") or MODELOS_URL)
        self.wp_bandos_category = int(self.config.get("wp_bandos_category") or WP_BANDOS_CATEGORY)
        self.wp_max_pages = int(self.config.get("wp_max_pages", 5))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, use_opener: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-viso/1.0")},
        )
        if use_opener:
            with self._opener.open(req, timeout=90) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", unescape(href))

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, use_opener=True)
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
                    "fecha": _parse_fecha_dmy(fecha_raw) or _fecha_from_blob(titulo),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_wp_bandos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for page in range(1, self.wp_max_pages + 1):
            url = (
                f"{self.wp_base}/wp-json/wp/v2/posts"
                f"?categories={self.wp_bandos_category}&per_page=50&page={page}"
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
                seen.add(pid)
                title = _strip_html(post.get("title", {}).get("rendered", ""))
                content = post.get("content", {}).get("rendered", "") or ""
                blob = f"{title} {content}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                rows.append(
                    {
                        "id": pid,
                        "titulo": title[:500],
                        "fecha": (post.get("date") or "")[:10] or _fecha_from_blob(blob),
                        "url": post.get("link") or "",
                        "content": content,
                        "blob": blob,
                        "origen": "wp_bando",
                    }
                )
        return rows

    def _collect_wp_search(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for term in ("informacion publica", "ordenanza", "actuacion", "licencia obra", "planeamiento"):
            url = (
                f"{self.wp_base}/wp-json/wp/v2/posts"
                f"?search={urllib.parse.quote(term)}&per_page=20"
                f"&_fields=id,date,link,title,content"
            )
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(data, list):
                continue
            for post in data:
                pid = int(post.get("id") or 0)
                if pid in seen:
                    continue
                seen.add(pid)
                title = _strip_html(post.get("title", {}).get("rendered", ""))
                content = post.get("content", {}).get("rendered", "") or ""
                blob = f"{title} {content}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                rows.append(
                    {
                        "id": pid,
                        "titulo": title[:500],
                        "fecha": (post.get("date") or "")[:10] or _fecha_from_blob(blob),
                        "url": post.get("link") or "",
                        "content": content,
                        "blob": blob,
                        "origen": f"wp_search_{term.replace(' ', '_')}",
                    }
                )
        return rows

    def _collect_modelos_urbanismo(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.modelos_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            href = self._abs_wp(m.group(1))
            if href in seen:
                continue
            seen.add(href)
            name = unescape(urllib.parse.unquote(Path(href).name)).replace("-", " ").replace(".pdf", "")
            if not RE_LICENCIA.search(name) and not RE_PROYECTO.search(name):
                continue
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": None,
                    "url": self.modelos_url,
                    "pdf_url": href,
                    "blob": name,
                    "origen": "web_modelos",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Sede espublico gestiona; categoría «Licencias Urbanísticas»",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.modelos_url),
                "fecha_concesion": None,
                "tipo": "modelos solicitud licencia de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Modelos de solicitud — licencia de obras y DR urbanística",
                "url": self.modelos_url,
                "source": "ayuntamiento",
                "nota": "PDFs descargables en web municipal (WordPress)",
                "origen": "web_modelos",
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
                "nota": "Licencias y comunicaciones previas vía sede (sin histórico público estructurado)",
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
                "nota": "Requiere identificación Cl@ve/certificado; no hay listado abierto",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "información pública")):
            return True
        if "licencias urban" in cat or "urban" in cat:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        cat = (row.get("categoria") or "").lower()
        if not RE_LICENCIA.search(blob) and "licencias urban" not in cat:
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia urbanística"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif "licencias urban" in cat:
            tipo = "licencia urbanística"
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
        cat = (row.get("categoria") or "").lower()
        if (
            not RE_PROYECTO.search(blob)
            and "información pública" not in proc
            and "ordenanza" not in proc
            and "licencias urban" not in cat
        ):
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

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = f"wp:{row.get('id') or row['url']}"
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "wp"),
        }

    def _wp_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = f"wp:{row.get('id') or row['url']}"
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "wp"),
        }

    def _modelo_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", row.get("pdf_url") or row["titulo"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "modelo solicitud licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": "web_modelos",
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_licencia_info_pages():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_licencia(item))
        for item in self._collect_wp_bandos():
            add(self._wp_to_licencia(item))
        for item in self._collect_wp_search():
            add(self._wp_to_licencia(item))
        for item in self._collect_modelos_urbanismo():
            add(self._modelo_to_licencia(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_modelos")),
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
        for item in self._collect_wp_bandos():
            rec = self._wp_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_wp_search():
            rec = self._wp_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_modelos_urbanismo():
            existing[self._modelo_to_licencia(item)["id"]] = self._modelo_to_licencia(item)
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
        for item in self._collect_wp_bandos():
            add(self._wp_to_proyecto(item))
        for item in self._collect_wp_search():
            add(self._wp_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "Planeamiento urbanístico — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "planeamiento",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": "Visor regional de planeamiento; sin enlace a expedientes del ayuntamiento",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp")),
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
