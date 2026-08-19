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

TRANSP_BASE = "https://transparencia.baeza.net"
SEDE_BASE = "https://baeza.sedelectronica.es"
WP_BASE = "https://www.baeza.net"
MUNICIPIO = "Baeza"
ID_PREFIX = "baeza"

REGISTRO_ROOT = "/transparencia/registro-de-instrumentos-de-ordenacion-urbanistica"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"

DEFAULT_TRANSP_SEEDS: list[str] = [
    f"{TRANSP_BASE}{REGISTRO_ROOT}",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/informacion-publica",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/convenios-urbanisticos",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/consultas-publicas-previas",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/planes-de-ordenacion-urbana",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/planes-de-ordenacion-urbana/plan-general-de-ordenacion-urbana--pgou-",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/planos",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/catalogo-del-centro-historico-de-baeza",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/planos/planos-i",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/planos/planos-iii",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/planos/planos-iv",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/planos/planos-v",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/planos/planos-vi",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/planos/planos-vii",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/planos/planos-viii",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/planos/planos-ix",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/catalogo-del-centro-historico-de-baeza/catalogo-i-y-ii",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/catalogo-del-centro-historico-de-baeza/catalogo-iii",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/catalogo-del-centro-historico-de-baeza/catalogo-iv",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/catalogo-del-centro-historico-de-baeza/ordenanzas-graficas",
    f"{TRANSP_BASE}{REGISTRO_ROOT}/proteccion-del-patrimonio/pepri/catalogo-del-centro-historico-de-baeza/ordenanzas-reguladoras",
]

PGOU_EXPEDIENTE_SUFFIXES: list[str] = [
    "28-pgou-97plano-de-ordenacion80-clasificacion-del-suelo-baeza",
    "33-pgou-97plano-de-ordenacion92-usos-en-suelo-urbano-la-yedra",
    "58-pgou-97plano-de-ordenacion16-alineaciones-y-rasantes-baeza",
]

DEFAULT_WEB_SEEDS: list[str] = [
    f"{WP_BASE}/urbanismo/",
    f"{WP_BASE}/urbanismo/page/2/",
    f"{WP_BASE}/el-ayuntamiento-auto/plan-especial-de-proteccion-reforma-interior-y-mejora-urbana/",
    f"{WP_BASE}/agenda-urbana-espanola/",
    f"{WP_BASE}/observatorio-urbano/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|primera utilizaci[oó]n|apertura de locales|cambio de titularidad)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pepri|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|cat[aá]logo|alineaci[oó]n|clasificaci[oó]n del suelo|"
    r"agenda urbana|patrimonio|reforma interior|mejora urbana)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"bolsa de trabajo|tribunal calificador|decreto.*pr/2026|listado.*bolsa|"
    r"disposiciones normativas.*circulaci[oó]n|consejo local de infancia)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://baeza\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_TRANSP_HREF = re.compile(
    r"href=['\"](/transparencia/(?:registro-de-instrumentos[^'\"]+|[^'\"]*expediente[^'\"]+))['\"]",
    re.I,
)
RE_TITLE = re.compile(r'class="tituloPagina"[^>]*>(.*?)</h2>', re.I | re.S)
RE_TEMPORAL_PDF = re.compile(r"(/Temporal/[a-f0-9-]+\.pdf)", re.I)
RE_WP_PDF = re.compile(
    r'href=["\'](https://www\.baeza\.net/wp-content/uploads/[^"\']+\.pdf)["\']',
    re.I,
)
RE_ARTICLE_LINK = re.compile(
    r'href="(https://www\.baeza\.net/[^"]+)"[^>]*class="[^"]*entry-title-link',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPDTE = re.compile(r"(?i)(?:expediente\s+)?([A-Z]{2,6}/[A-Z]{2,6}/\d+/\d{4})")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


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


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "pepri" in b or "patrimonio" in b or "catálogo" in b or "catalogo" in b:
        return "PEPRI"
    if "plan especial" in b or "reforma interior" in b:
        return "plan especial"
    if "convenio" in b:
        return "convenio urbanístico"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "agenda urbana" in b:
        return "agenda urbana"
    if "licencia" in b:
        return "licencia publicada"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    return "planeamiento"


class BaezaAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal transparencia ATM2 + sede espublico + web WordPress + SITUADIFUSION (PGOU)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.transp_seeds = list(self.config.get("transparencia_seeds") or DEFAULT_TRANSP_SEEDS)
        self.web_seeds = list(self.config.get("web_seeds") or DEFAULT_WEB_SEEDS)
        self.pgou_suffixes = list(self.config.get("pgou_expediente_suffixes") or PGOU_EXPEDIENTE_SUFFIXES)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-baeza/1.0")},
        )
        use_ssl = use_sede_ssl or "sedelectronica.es" in url
        if use_ssl:
            with self._opener.open(req, timeout=90) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _page_title(self, html: str, fallback: str = "") -> str:
        m = RE_TITLE.search(html)
        if m:
            return _strip_html(m.group(1))[:500]
        return fallback[:500]

    def _transp_links_from_html(self, html: str) -> set[str]:
        links: set[str] = set()
        for m in RE_TRANSP_HREF.finditer(html):
            path = m.group(1).split("#")[0].strip()
            if path.startswith("/transparencia/"):
                links.add(f"{self.transp_base}{path}")
        return links

    def _collect_transparencia_pages(self) -> list[dict[str, Any]]:
        urls: list[str] = list(self.transp_seeds)
        for suf in self.pgou_suffixes:
            urls.append(
                f"{self.transp_base}{REGISTRO_ROOT}/planes-de-ordenacion-urbana/"
                f"plan-general-de-ordenacion-urbana--pgou-/expediente-urb_plan_1_2023---{suf}"
            )
        seen_urls: set[str] = set()
        records: list[dict[str, Any]] = []

        for url in urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue

            title = self._page_title(html, fallback=url.split("/")[-1].replace("-", " "))
            if title.lower() in ("aviso", "inicio"):
                continue
            pdf_m = RE_TEMPORAL_PDF.search(html)
            pdf_url = f"{self.transp_base}{pdf_m.group(1)}" if pdf_m else None
            expte_m = RE_EXPDTE.search(title)
            blob = title
            if not RE_PROYECTO.search(blob) and not pdf_url:
                continue
            key = pdf_url or url
            rec = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": title,
                "fecha": _fecha_from_blob(blob),
                "tipo": _proyecto_tipo(blob),
                "url": url,
                "source": "ayuntamiento",
                "expte": expte_m.group(1) if expte_m else None,
                "origen": "transparencia",
            }
            if pdf_url:
                rec["pdf_url"] = pdf_url
            records.append(rec)

        # PGOU landing (SITUA iframe) as metadata row
        pgou_url = f"{self.transp_base}{REGISTRO_ROOT}/planes-de-ordenacion-urbana/plan-general-de-ordenacion-urbana--pgou-"
        records.append(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "Plan General de Ordenación Urbana (PGOU) — consulta SITUADIFUSION",
                "fecha": "1997-01-01",
                "tipo": "PGOU",
                "url": pgou_url,
                "source": "ayuntamiento",
                "expte": "URB/PLAN/1/2023",
                "origen": "situa",
                "nota": f"Visor regional embebido: {SITUA_SEARCH}",
            }
        )
        return records

    def _collect_web_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.web_seeds:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_WP_PDF.finditer(html):
                pdf_url = m.group(1)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                name = Path(urllib.parse.unquote(pdf_url.split("?")[0])).stem.replace("-", " ")
                titulo = name[:500]
                rows.append(
                    {
                        "id": _stable_id("proy", pdf_url),
                        "municipio": MUNICIPIO,
                        "titulo": titulo,
                        "fecha": _fecha_from_blob(pdf_url),
                        "tipo": _proyecto_tipo(titulo),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "source": "ayuntamiento",
                        "origen": "web_pdf",
                    }
                )
            for m in RE_ARTICLE_LINK.finditer(html):
                art_url = m.group(1)
                if "/urbanismo/" in art_url or "urban" in art_url.lower() or "obra" in art_url.lower():
                    slug = art_url.rstrip("/").split("/")[-1].replace("-", " ")[:500]
                    if art_url not in seen:
                        seen.add(art_url)
                        rows.append(
                            {
                                "id": _stable_id("proy", art_url),
                                "municipio": MUNICIPIO,
                                "titulo": slug,
                                "fecha": None,
                                "tipo": "urbanismo",
                                "url": art_url,
                                "source": "ayuntamiento",
                                "origen": "web_noticia",
                            }
                        )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, use_sede_ssl=True)
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
                "id": _stable_id("lic", f"{self.sede_base}/"),
                "fecha_concesion": None,
                "tipo": "trámites sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica Baeza (espublico gestiona)",
                "url": f"{self.sede_base}/",
                "source": "ayuntamiento",
                "nota": "Licencias y consulta de expedientes vía sede",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{TRANSP_BASE}/transparencia/relacion-ciudadana-y-sociedad/informacion-y-atencion-al-ciudadano/catalogo-de-procedi"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo procedimientos — licencias y urbanismo (transparencia)",
                "url": (
                    f"{TRANSP_BASE}/transparencia/relacion-ciudadana-y-sociedad/"
                    "informacion-y-atencion-al-ciudadano/catalogo-de-procedi"
                ),
                "source": "ayuntamiento",
                "origen": "transparencia_tramite",
            },
            {
                "id": _stable_id("lic", f"{WP_BASE}/urbanismo/"),
                "fecha_concesion": None,
                "tipo": "información urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sección urbanismo web municipal",
                "url": f"{WP_BASE}/urbanismo/",
                "source": "ayuntamiento",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", "https://sede.baeza.net/PortalCiudadano/Tablon/wfrTablon.aspx"),
                "fecha_concesion": None,
                "tipo": "tablón sede legacy",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón PortalCiudadano sede.baeza.net",
                "url": "https://sede.baeza.net/PortalCiudadano/Tablon/wfrTablon.aspx",
                "source": "ayuntamiento",
                "nota": "Portal legacy; contenido mínimo en CI",
                "origen": "sede_legacy",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "disposiciones normativas")):
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

        for rec in self._collect_transparencia_pages():
            add(rec)
        for rec in self._collect_web_pdfs():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web")),
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
