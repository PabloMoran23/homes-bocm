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

SEDE_BASE = "https://escacenadelcampo.sedelectronica.es"
WEB_BASE = "https://www.escacenadelcampo.es"
BOARD_URL = f"{SEDE_BASE}/board/"
DOSSIER_URL = f"{SEDE_BASE}/dossier/"
SITUA_URL = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=21034"
BOJA_PGOU_MOD1_URL = "https://www.juntadeandalucia.es/boja/2022/134/32"
MUNICIPIO = "Escacena del Campo"
ID_PREFIX = "escacena-del-campo"

DEFAULT_WEB_SEEDS: list[str] = [
    f"{WEB_BASE}/es/Areas-tematicas/urbanismo/",
    f"{WEB_BASE}/es/ayuntamiento/ordenanzas/",
    f"{WEB_BASE}/es/ayuntamiento/publicaciones-oficiales/",
    f"{WEB_BASE}/es/gobierno-abierto/portal-transparencia/buscador-transparencia/",
    f"{WEB_BASE}/es/gobierno-abierto/portal-transparencia/marco-regulatorio/",
    f"{WEB_BASE}/es/noticias/",
]

RE_CATALOG = re.compile(
    r'href="((?:https://escacenadelcampo\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_PREVIEW = re.compile(
    r'href="((?:https://escacenadelcampo\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura| de ocupaci[oó]n)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|recepci[oó]n de obra|conexi[oó]n.*(?:abastecimiento|saneamiento))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|b[aá]sico)|pbom|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|certificado.*urban|informe urban|actuaci[oó]n urban|"
    r"amianto|censo.*amianto|segregaci[oó]n|parcelaci[oó]n)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*pleno|cobranza iae|"
    r"jurado|censo electoral|fiestas|mercadillo|carrera popular|taller de memoria)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(animales potencialmente peligrosos|inscripci[oó]n en actividades y cursos|"
    r"cobranza|iae|ivtm|cementerio|fiestas|cine|empleo|deporte)",
)
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
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "pbom" in b or "plan básico" in b or "plan basico" in b:
        return "PBOM"
    if "modificaci" in b and ("pgou" in b or "planeam" in b):
        return "modificación planeamiento"
    if "actuaci" in b and "urban" in b:
        return "actuación urbanística"
    if "certificado" in b or "informe urban" in b:
        return "certificado urbanístico"
    if "amianto" in b or "censo" in b:
        return "censo urbanístico"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "ordenanza" in b:
        return "normativa urbanística"
    if "licencia" in b:
        return "licencia publicada"
    if "planeamiento" in b or "situa" in b:
        return "planeamiento"
    return "urbanismo"


def _licencia_tipo(title: str) -> str:
    n = title.lower()
    if "obra mayor" in n:
        return "licencia de obra mayor"
    if "obra menor" in n or "declaraci" in n:
        return "declaración responsable / obra menor"
    if "actividad" in n or "espect" in n:
        return "licencia de actividad"
    if "ocupaci" in n:
        return "licencia de ocupación"
    if "recepci" in n and "obra" in n:
        return "recepción de obra"
    if "conexi" in n and ("abastecimiento" in n or "saneamiento" in n):
        return "licencia de conexión a redes"
    if "segregaci" in n or "parcelaci" in n:
        return "licencia de parcelación"
    return "trámite licencia urbanística"


class EscacenaDelCampoAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS Dip. Huelva + sede espublico gestiona (tablón + catálogo trámites) + SITUA."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.dossier_url = str(self.config.get("dossier_url") or DOSSIER_URL)
        self.situa_url = str(self.config.get("situa_url") or SITUA_URL)
        self.boja_pgou_url = str(self.config.get("boja_pgou_url") or BOJA_PGOU_MOD1_URL)
        self.web_seeds = [str(u) for u in (self.config.get("web_seeds") or DEFAULT_WEB_SEEDS)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._warmed_sede = False

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-escacena/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _warm_sede(self) -> None:
        if self._warmed_sede:
            return
        try:
            self._fetch(self.board_url)
        except urllib.error.URLError:
            pass
        self._warmed_sede = True

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _abs_sede(self, href: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        return urllib.parse.urljoin(f"{self.sede_base}/", href)

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

            preview_m = RE_PREVIEW.search(row_html)
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
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_tramites(self) -> list[dict[str, Any]]:
        self._warm_sede()
        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            href, titulo = m.group(1), unescape(m.group(2).strip())
            url = self._abs_sede(href)
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _collect_web_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(url: str, titulo: str, blob: str, origen: str) -> None:
            if url in seen:
                return
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                return
            seen.add(url)
            rows.append(
                {
                    "url": url,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(f"{titulo} {url}"),
                    "tipo": _proyecto_tipo(blob),
                    "blob": blob[:2000],
                    "origen": origen,
                }
            )

        for seed in self.web_seeds:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue

            for href in RE_HREF.findall(html):
                if any(x in href.lower() for x in (".pdf", "/export/sites/", "/export/")):
                    abs_url = self._abs_web(href)
                    name = urllib.parse.unquote(Path(abs_url).name.replace("-", " ").replace("_", " "))
                    add(abs_url, name or abs_url, f"{name} {abs_url} urbanismo Escacena", "web_pdf")

                if "/es/noticias/" in href and "index.html" not in href:
                    abs_url = self._abs_web(href)
                    if abs_url in seen:
                        continue
                    try:
                        article = self._fetch(abs_url)
                    except urllib.error.URLError:
                        continue
                    title_m = re.search(r"<title>([^<]+)</title>", article, re.I)
                    title = _strip_html(title_m.group(1)) if title_m else abs_url
                    blob = f"{title} {_strip_html(article)}"
                    if RE_PROYECTO.search(blob):
                        pdf = next(
                            (
                                self._abs_web(h)
                                for h in RE_HREF.findall(article)
                                if ".pdf" in h.lower() or "/export/" in h.lower()
                            ),
                            abs_url,
                        )
                        add(pdf, title, blob, "web_noticia")
        return rows

    def _collect_planeamiento_refs(self) -> list[dict[str, Any]]:
        return [
            {
                "url": self.situa_url,
                "titulo": "PGOU Escacena del Campo — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "blob": "planeamiento general SITUA Escacena del Campo INE 21034",
                "origen": "situa",
            },
            {
                "url": self.boja_pgou_url,
                "titulo": (
                    "Modificación núm. 1 del PGOU (adaptación NNSS a LOUA) — "
                    "aprobación definitiva BOJA 2022"
                ),
                "fecha": "2022-07-14",
                "tipo": "modificación planeamiento",
                "blob": "PGOU modificación Escacena del Campo BOJA 2022",
                "origen": "boja",
            },
        ]

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
                "nota": "Concesiones y edictos publicados en sede espublico gestiona",
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
                "nota": "Licencias, DR y comunicaciones previas vía sede (sin histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/es/Areas-tematicas/urbanismo/"),
                "fecha_concesion": None,
                "tipo": "información urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Área temática Urbanismo — web municipal",
                "url": f"{self.web_base}/es/Areas-tematicas/urbanismo/",
                "source": "ayuntamiento",
                "nota": "Sección urbanismo OpenCMS Diputación de Huelva (contacto y enlaces)",
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
                "nota": "Requiere identificación; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
        ]

    def _should_exclude(self, blob: str) -> bool:
        return bool(RE_EXCLUDE.search(blob))

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
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
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
            "origen": row.get("origen"),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if self._should_exclude(row["titulo"]):
            return None
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": _licencia_tipo(row["titulo"]),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite",
            "origen": row.get("origen"),
        }

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if self._should_exclude(row["titulo"]):
            return None
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        if RE_LICENCIA.search(row["titulo"]) and not re.search(
            r"(?i)planeam|urban|certificado|informe|actuaci", row["titulo"]
        ):
            return None
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite",
            "origen": row.get("origen"),
        }

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or row.get("titulo") or ""
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web",
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
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "info": sum(
                1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")
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
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
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

        for item in self._collect_planeamiento_refs():
            add(self._doc_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_tramites():
            add(self._tramite_to_proyecto(item))
        for item in self._collect_web_docs():
            add(self._doc_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
            "boja": sum(1 for r in rows if r.get("origen") == "boja"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web")),
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
