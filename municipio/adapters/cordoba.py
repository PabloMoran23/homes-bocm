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

WEB_BASE = "https://www.cordoba.es"
GMU_BASE = "https://www.gmucordoba.es"
SEDE_BASE = f"{WEB_BASE}/sede"
MUNICIPIO = "Córdoba"
ID_PREFIX = "cordoba"

TABLON_GMU_URL = f"{GMU_BASE}/novedades/itemlist/category/2-tablon-de-anuncios"
URBANISMO_HUB = f"{WEB_BASE}/transparencia/transparencia-municipal/urbanismo"
INFO_PUBLICA_INDEX = (
    f"{WEB_BASE}/transparencia/transparencia-municipal/urbanismo/"
    "urbanismo-documentos-info-publica"
)
DEFAULT_INFO_PUBLICA_YEARS = [2024, 2025, 2026]

DEFAULT_LICENCIA_PAGES = [
    f"{SEDE_BASE}/tramites/urbanismo/solicitud-licencia-urbanistica-obras-nueva-planta",
    f"{WEB_BASE}/sites/default/files/transparencia/urbanismo/informacion-urbanistica/"
    "INSTRUCCIÓN%203_25%20PARA-ORIENTAR-EL-PROCEDIMIENTO-DE-OTORGAMIENTO-DE-LICENCIAS-Y-DR-7.pdf",
    f"{WEB_BASE}/sites/default/files/transparencia/urbanismo/informacion-urbanistica/"
    "LICENCIAS_Y_AUTORIZACIONES_2023.pdf",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|calificaci[oó]n ambiental)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|urbanizaci[oó]n|peri|ue-|unidad de ejecuci[oó]n|pctm|"
    r"actuaci[oó]n|estatutos de la entidad)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(convocatoria.*empleo|selecci[oó]n de personal|subvenci[oó]n deportiv|"
    r"modificaci[oó]n presupuestaria|pleno.*convocatoria)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DAY_MONTH = re.compile(
    r"(\d{1,2})\s*/\s*(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)",
    re.I,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPDTE = re.compile(
    r"(?i)(?:expediente|expte\.?)\s+(\d{1,4}/\d{4})|"
    r"serie\s+[\d.]+\s+\(PCTM\s+([^)]+)\)",
)
RE_DETAILS = re.compile(
    r"<details>\s*<summary><strong>(.*?)</strong>\s*(.*?)</summary>(.*?)</details>",
    re.I | re.S,
)
RE_ACCORDION_DT = re.compile(
    r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>",
    re.I | re.S,
)
RE_TABLON_ITEM = re.compile(
    r'class="catItemTitle"[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
RE_ITEM_DATE = re.compile(r'class="itemDateCreated"[^>]*>\s*([^<]+)', re.I)
RE_CSV_LINK = re.compile(r'validar\?csv=([^"&]+)', re.I)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.cordoba\.es)?/sites/default/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
MESES = {
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
}


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


def _fecha_from_blob(text: str, default_year: int | None = None) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_DAY_MONTH.search(text or "")
    if m:
        month = MESES.get(m.group(2).lower())
        if month:
            year = default_year
            if year is None:
                years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
                year = max(years) if years else datetime.now().year
            try:
                return datetime(year, month, int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "urbanizaci" in b and "proyecto" in b:
        return "proyecto de urbanización"
    if "calificaci" in b and "ambiental" in b:
        return "calificación ambiental"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "convenio" in b:
        return "convenio urbanístico"
    if "licencia" in b:
        return "licencia publicada"
    if "edicto" in b:
        return "edicto urbanístico"
    if "instrucci" in b:
        return "instrucción urbanística"
    return "urbanismo"


def _licencia_tipo(title: str) -> str:
    n = title.lower()
    if "nueva planta" in n:
        return "licencia obra nueva planta"
    if "declaraci" in n and "responsable" in n:
        return "declaración responsable"
    if "calificaci" in n and "ambiental" in n:
        return "calificación ambiental (licencia actividad)"
    if "licencia" in n:
        return "licencia urbanística"
    return "trámite urbanístico"


class CordobaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal cordoba.es (transparencia IP) + Joomla GMU tablón + sede trámites."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.gmu_base = str(self.config.get("gmu_base") or GMU_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_GMU_URL)
        self.info_publica_years = [
            int(y) for y in (self.config.get("info_publica_years") or DEFAULT_INFO_PUBLICA_YEARS)
        ]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self.tablon_max_pages = int(self.config.get("tablon_max_pages", 4))
        self.fetch_item_details = bool(self.config.get("fetch_gmu_item_details", False))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, retries: int = 3) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cordoba/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=90, context=self._ssl_ctx) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_err = exc
                time.sleep(1.5 * (attempt + 1))
        raise last_err or RuntimeError(f"fetch failed: {url}")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _abs_gmu(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.gmu_base}/", href)

    def _parse_info_publica(self, html: str, page_url: str) -> list[dict[str, Any]]:
        year_m = re.search(r"/(\d{4})(?:\?|$)", page_url)
        default_year = int(year_m.group(1)) if year_m else None
        items: list[dict[str, Any]] = []
        for m in RE_DETAILS.finditer(html):
            head = _strip_html(m.group(1) + " " + m.group(2))
            body = m.group(3)
            if RE_EXCLUDE.search(head):
                continue
            titulo = head[:500]
            blob = f"{titulo} {_strip_html(body)}"
            if not RE_PROYECTO.search(blob):
                continue
            csvs = RE_CSV_LINK.findall(body)
            doc_url = (
                self._abs_web(f"/sede/servicios/verificacion-documentos/s1/validar?csv={csvs[0]}")
                if csvs
                else page_url
            )
            items.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_blob(head, default_year=default_year),
                    "url": doc_url if csvs else page_url,
                    "pdf_url": doc_url if csvs else None,
                    "origen": "drupal_info_publica",
                    "content": blob[:2000],
                }
            )
        return items

    def _parse_urbanismo_hub(self, html: str, page_url: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for m in RE_ACCORDION_DT.finditer(html):
            titulo = _strip_html(m.group(1))[:500]
            body = m.group(2)
            if not titulo or RE_EXCLUDE.search(titulo):
                continue
            blob = f"{titulo} {_strip_html(body)}"
            if not RE_PROYECTO.search(blob):
                continue
            csvs = RE_CSV_LINK.findall(body)
            doc_url = (
                self._abs_web(f"/sede/servicios/verificacion-documentos/s1/validar?csv={csvs[0]}")
                if csvs
                else page_url
            )
            items.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_blob(titulo),
                    "url": doc_url,
                    "pdf_url": doc_url if csvs else None,
                    "origen": "drupal_urbanismo_accordion",
                    "content": blob[:2000],
                }
            )
        for pdf in RE_PDF_HREF.findall(html):
            url = self._abs_web(pdf)
            name = unescape(urllib.parse.unquote(Path(url).name))
            if not RE_PROYECTO.search(name):
                continue
            items.append(
                {
                    "titulo": name,
                    "fecha": _fecha_from_blob(url),
                    "url": url,
                    "pdf_url": url,
                    "origen": "drupal_urbanismo_pdf",
                    "content": name,
                }
            )
        return items

    def _collect_gmu_tablon(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_idx in range(self.tablon_max_pages):
            start = page_idx * 14
            url = self.tablon_url if start == 0 else f"{self.tablon_url}?start={start}"
            try:
                html = self._fetch(url, retries=2)
            except Exception:
                break
            found = RE_TABLON_ITEM.findall(html)
            if not found:
                break
            for href, raw_title in found:
                titulo = _strip_html(raw_title)[:500]
                item_url = self._abs_gmu(href)
                fecha: str | None = None
                pdf_url: str | None = None
                if self.fetch_item_details:
                    try:
                        detail = self._fetch(item_url, retries=1)
                        dm = RE_ITEM_DATE.search(detail)
                        if dm:
                            fecha = _fecha_from_blob(dm.group(1))
                        pdfs = re.findall(r'href="([^"]+\.pdf[^"]*)"', detail, re.I)
                        if pdfs:
                            pdf_url = self._abs_gmu(pdfs[0])
                    except Exception:
                        pass
                if fecha is None:
                    fecha = _fecha_from_blob(titulo)
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": fecha,
                        "url": item_url,
                        "pdf_url": pdf_url,
                        "origen": "gmu_joomla_tablon",
                        "content": titulo,
                    }
                )
            if "start=" not in html and page_idx > 0:
                break
        return rows

    def _collect_info_publica(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for year in self.info_publica_years:
            url = f"{INFO_PUBLICA_INDEX}/{year}"
            try:
                html = self._fetch(url)
            except Exception:
                continue
            out.extend(self._parse_info_publica(html, url))
        return out

    def _collect_licencia_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self.licencia_pages:
            titulo = unescape(urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name))
            if url.endswith(".pdf"):
                rows.append(
                    {
                        "id": _stable_id("lic", url),
                        "fecha_concesion": _fecha_from_blob(url),
                        "tipo": _licencia_tipo(titulo),
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": titulo[:500],
                        "url": url,
                        "pdf_url": url,
                        "source": "ayuntamiento",
                        "nota": "Documento informativo; no concesión publicada en tablón",
                    }
                )
                continue
            try:
                html = self._fetch(url)
            except Exception:
                continue
            page_title = _strip_html(re.search(r"<title>([^<]+)", html, re.I).group(1) if re.search(r"<title>", html) else titulo)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": _licencia_tipo(page_title),
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": page_title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo sede electrónica",
                }
            )
        return rows

    def _post_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        if not RE_LICENCIA.search(titulo):
            return None
        key = item.get("pdf_url") or item.get("url") or titulo
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": item.get("fecha"),
            "tipo": _licencia_tipo(titulo),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            **({"pdf_url": item["pdf_url"]} if item.get("pdf_url") else {}),
        }

    def _post_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        blob = f"{titulo} {item.get('content', '')}"
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = item.get("pdf_url") or item.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        m = RE_EXPDTE.search(blob)
        if m:
            rec["expediente_ref"] = (m.group(1) or m.group(2) or "").strip()
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
        for rec in self._collect_licencia_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_gmu_tablon():
            rec = self._post_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_pages():
            existing[rec["id"]] = rec
        for item in self._collect_gmu_tablon():
            rec = self._post_to_licencia(item)
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

        try:
            hub_html = self._fetch(URBANISMO_HUB)
            for item in self._parse_urbanismo_hub(hub_html, URBANISMO_HUB):
                add(self._post_to_proyecto(item))
        except Exception:
            pass

        for item in self._collect_info_publica():
            add(self._post_to_proyecto(item))

        for item in self._collect_gmu_tablon():
            add(self._post_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info_publica_years": self.info_publica_years,
            "tablon_pages": self.tablon_max_pages,
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
