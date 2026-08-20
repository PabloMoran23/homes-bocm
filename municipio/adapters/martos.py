from __future__ import annotations

import hashlib
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

WP_BASE = "https://martos.es"
TRANSP_BASE = "https://transparencia.martos.es"
SEDE_BASE = "https://sedeelectronica.martos.es"
MUNICIPIO = "Martos"
ID_PREFIX = "martos"

TABLON_DEFAULT = f"{SEDE_BASE}/eAdmin/Tablon.do?action=verAnuncios"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"

DEFAULT_WEB_SEEDS: list[str] = [
    f"{WP_BASE}/urbanismo-y-obras/",
    f"{WP_BASE}/urbanismo-y-obras/page/2/",
    f"{WP_BASE}/urbanismo-y-obras/page/3/",
    f"{WP_BASE}/urbanismo-y-obras/instrumentos-de-ordenacion-urbanistica-general",
    f"{WP_BASE}/urbanismo-y-obras/ordenanzas/",
    f"{WP_BASE}/urbanismo-y-obras/modelos-y-solicitudes/",
    f"{WP_BASE}/tu-ciudad/plan-especial-del-casco-antiguo/",
]

DEFAULT_TRANSP_SEEDS: list[str] = [
    f"{TRANSP_BASE}/procedimientos-en-exposicion-publica/",
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{WP_BASE}/urbanismo-y-obras/modelos-y-solicitudes/",
    f"{WP_BASE}/urbanismo-y-obras/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|"
    r"calificaci[oó]n ambiental|apertura de (?:actividad|local)|"
    r"hosteler[ií]a|establecimiento|taller|obra (?:mayor|menor)|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|"
    r"edicto|aprobaci[oó]n (?:inicial|definitiva)|consulta p[uú]blica|"
    r"mejora urbana|ordenaci[oó]n|interpretaci[oó]n|ordenanza|casco antiguo|"
    r"calificaci[oó]n ambiental|exposici[oó]n p[uú]blica|fibra [oó]ptica|"
    r"parcela|suelo|sector|actuaci[oó]n)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(precio p[uú]blico|tasa basura|periodo voluntario iae|"
    r"suplemento de cr[eé]dito|cr[eé]dito[- ]extra|cuenta general|"
    r"escuela (?:danza|pintura)|edm 2026|teletrabajo|cluster del pl[aá]stico|"
    r"consejo local agrario|ciclo integral del agua)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[./_-](\d{2})[./_-]")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DOWNLOAD_HREF = re.compile(
    r'href="((?:https://(?:martos\.es|transparencia\.martos\.es))?/download/[^"]+\.pdf)"',
    re.I,
)
RE_TABLON_ROW = re.compile(
    r'verAnuncio&id=([A-F0-9]+).*?width="40%"[^>]*>\s*(.*?)\s*<br>.*?'
    r"Periodo:</span>\s*(\d{1,2}/\d{1,2}/\d{4})",
    re.I | re.S,
)
RE_TABLON_LINK = re.compile(
    r'verAnuncio[^"\']*id=([A-F0-9]+)',
    re.I,
)
RE_TABLON_DESC = re.compile(
    r"(?i)Descripci[oó]n\s*</[^>]+>\s*</[^>]+>\s*<[^>]+>\s*([^<]+)",
)
RE_TABLON_FECHA = re.compile(
    r"(?i)Fecha inicio publicaci[oó]n\s*</[^>]+>\s*</[^>]+>\s*<[^>]+>\s*"
    r"(\d{1,2}/\d{1,2}/\d{4})",
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


def _fecha_from_pdf_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(Path(url).name) if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r"<title>([^<]+)",
        r"<h1[^>]*>([^<]+)",
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _pdf_tipo(name: str, section: str = "") -> str:
    blob = f"{name} {section}".lower()
    if "interpretacion" in blob or "interpretación" in blob:
        return "interpretación PGOU"
    if "pgou" in blob or "plan general" in blob or "ordenacion" in blob:
        return "PGOU"
    if "plan especial" in blob or "casco antiguo" in blob:
        return "plan especial"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "mejora urbana" in blob or "ordenacion" in blob:
        return "mejora urbana"
    if "calificacion ambiental" in blob or "calificación ambiental" in blob:
        return "calificación ambiental"
    if "informacion publica" in blob or "información pública" in blob:
        return "información pública"
    if "consulta publica" in blob:
        return "consulta pública"
    if "licencia" in blob or "declaracion responsable" in blob:
        return "licencia / trámite"
    return "documento urbanismo"


class MartosAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress martos.es + tablón sede propia + transparencia WPFD."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_DEFAULT)
        self.web_seeds = [str(u) for u in (self.config.get("web_seeds") or DEFAULT_WEB_SEEDS)]
        self.transp_seeds = [str(u) for u in (self.config.get("transparencia_seeds") or DEFAULT_TRANSP_SEEDS)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, use_sede_ssl: bool = False, latin1: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-martos/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sedeelectronica.martos.es" in url else None
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            raw = resp.read()
        encoding = "iso-8859-1" if latin1 or "sedeelectronica.martos.es" in url else "utf-8"
        return raw.decode(encoding, errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or f"{self.wp_base}/", unescape(href))

    def _abs_sede(self, href: str) -> str:
        return self._abs_url(href, f"{self.sede_base}/eAdmin/")

    def _extract_downloads(self, html: str, page_url: str, base: str | None = None) -> list[dict[str, Any]]:
        page_title = _page_title(html, page_url.rstrip("/").rsplit("/", 1)[-1].replace("-", " "))
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_DOWNLOAD_HREF.finditer(html):
            pdf = self._abs_url(m.group(1), base or f"{self.wp_base}/")
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            titulo = name.replace("-", " ").replace("_", " ")
            rows.append(
                {
                    "id": _stable_id("proy", pdf),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_pdf_url(pdf),
                    "tipo": _pdf_tipo(name, page_title),
                    "url": page_url,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "origen": "wpfd",
                }
            )
        return rows

    def _collect_web_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.web_seeds:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for rec in self._extract_downloads(html, page_url):
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        return rows

    def _collect_transp_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.transp_seeds:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for rec in self._extract_downloads(html, page_url, self.transp_base):
                blob = f"{rec['titulo']} {rec.get('pdf_url', '')}"
                if RE_BOARD_NON_URBAN.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and "urban" not in blob.lower():
                    continue
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        return rows

    def _parse_tablon_list(self, html: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, title_raw, fecha_raw = m.group(1), m.group(2), m.group(3)
            if ann_id in seen:
                continue
            seen.add(ann_id)
            title = _strip_html(title_raw)
            items.append(
                {
                    "ann_id": ann_id,
                    "titulo": title[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": f"{self.sede_base}/eAdmin/Tablon.do?action=verAnuncio&id={ann_id}",
                }
            )
        if items:
            return items
        for m in RE_TABLON_LINK.finditer(html):
            ann_id = m.group(1)
            if ann_id in seen:
                continue
            seen.add(ann_id)
            items.append(
                {
                    "ann_id": ann_id,
                    "titulo": "",
                    "fecha": None,
                    "url": f"{self.sede_base}/eAdmin/Tablon.do?action=verAnuncio&id={ann_id}",
                }
            )
        return items

    def _fetch_tablon_detail(self, item: dict[str, Any]) -> dict[str, Any]:
        if item.get("titulo"):
            return item
        try:
            html = self._fetch(item["url"], use_sede_ssl=True, latin1=True)
        except urllib.error.URLError:
            return item
        title_m = re.search(r"<h2[^>]*>([^<]+)", html, re.I)
        title = unescape(title_m.group(1).strip()) if title_m else ""
        if not title:
            desc_m = RE_TABLON_DESC.search(html)
            title = unescape(desc_m.group(1).strip()) if desc_m else ""
        fecha_m = RE_TABLON_FECHA.search(html)
        fecha = _parse_fecha_dmy(fecha_m.group(1)) if fecha_m else item.get("fecha")
        pdfs = [
            self._abs_sede(x)
            for x in re.findall(r"abrirOriginal\('([^']+)'\)", html, re.I)
        ]
        pdf_urls = [self._abs_sede(x) for x in re.findall(r'href="([^"]+\.pdf[^"]*)"', html, re.I)]
        return {
            **item,
            "titulo": (title or item.get("titulo") or "")[:500],
            "fecha": fecha,
            "pdf_url": pdf_urls[0] if pdf_urls else None,
            "pdf_urls": pdf_urls[:10],
            "pdf_token": pdfs[0] if pdfs else None,
        }

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url, use_sede_ssl=True, latin1=True)
        except urllib.error.URLError:
            return []
        items = self._parse_tablon_list(html)
        rows: list[dict[str, Any]] = []
        for item in items:
            detail = self._fetch_tablon_detail(item)
            if detail.get("titulo"):
                rows.append(detail)
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title = str(row.get("titulo") or "")
        if RE_BOARD_NON_URBAN.search(title) and not RE_LICENCIA.search(title):
            return None
        if not RE_LICENCIA.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row.get("ann_id") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / actividad",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title = str(row.get("titulo") or "")
        if RE_BOARD_NON_URBAN.search(title) and not RE_PROYECTO.search(title):
            return None
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("ann_id") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": row.get("fecha"),
            "tipo": _pdf_tipo(title),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = _page_title(html, "Modelos y solicitudes urbanismo")
            rec_id = _stable_id("lic", page_url)
            if rec_id not in seen:
                seen.add(rec_id)
                rows.append(
                    {
                        "id": rec_id,
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": page_title[:500],
                        "url": page_url,
                        "source": "ayuntamiento",
                        "origen": "tramite_info",
                        "nota": "Formularios DR/comunicación previa; tramitación vía sede",
                    }
                )
            for rec in self._extract_downloads(html, page_url):
                blob = f"{rec['titulo']} {rec.get('pdf_url', '')}"
                if not RE_LICENCIA.search(blob) and "/obras/" not in rec.get("pdf_url", ""):
                    if "/actividades/" not in rec.get("pdf_url", ""):
                        continue
                lic_id = _stable_id("lic", rec.get("pdf_url") or rec["id"])
                if lic_id in seen:
                    continue
                seen.add(lic_id)
                rows.append(
                    {
                        "id": lic_id,
                        "fecha_concesion": rec.get("fecha"),
                        "tipo": "formulario licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": rec["titulo"][:500],
                        "url": page_url,
                        "pdf_url": rec.get("pdf_url"),
                        "source": "ayuntamiento",
                        "origen": "tramite_doc",
                    }
                )
        return rows

    def _situa_metadata(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", SITUA_SEARCH),
            "municipio": MUNICIPIO,
            "titulo": "Planeamiento urbanístico — consulta SITUA (Junta de Andalucía)",
            "fecha": None,
            "tipo": "PGOU / planeamiento",
            "url": SITUA_SEARCH,
            "source": "ayuntamiento",
            "origen": "situa",
            "nota": "Visor regional PDF; sin geometría GeoJSON por expediente",
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
        for rec in self._collect_licencias_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if str(r.get("origen", "")).startswith("tramite")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        new_rows = 0
        for rec in self._collect_licencias_tramites():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                new_rows += 1
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in existing:
                existing[rec["id"]] = rec
                new_rows += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "new": new_rows, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        situa = self._situa_metadata()
        rows.append(situa)
        seen.add(situa["id"])
        for rec in self._collect_web_proyectos():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for rec in self._collect_transp_proyectos():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wpfd": sum(1 for r in rows if r.get("origen") == "wpfd"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transp": sum(1 for r in rows if r.get("origen") == "wpfd" and TRANSP_BASE in str(r.get("pdf_url", ""))),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        new_rows = 0
        for rec in self._collect_web_proyectos():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                new_rows += 1
        for rec in self._collect_transp_proyectos():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                new_rows += 1
        for item in self._collect_tablon():
            rec = self._tablon_to_proyecto(item)
            if rec and rec["id"] not in existing:
                existing[rec["id"]] = rec
                new_rows += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "new": new_rows, "status": "ok"}
