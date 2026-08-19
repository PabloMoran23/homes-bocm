from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WP_BASE = "https://www.lavictoriadeacentejo.es"
SEDE_BASE = "http://sede.lavictoriadeacentejo.es"
MUNICIPIO = "La Victoria de Acentejo"
ID_PREFIX = "lvda"

PARTICIPACION_PARENT_ID = 5500
URBANISMO_PAGE_ID = 3311

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/servicios-municipales/urbanismo/",
    f"{WP_BASE}/servicios-municipales/urbanismo/participacion-ciudadana/",
    f"{WP_BASE}/servicios-municipales/urbanismo/normativa/",
    f"{WP_BASE}/servicios-municipales/urbanismo/licencias/",
    f"{WP_BASE}/servicios-municipales/urbanismo/comunicacion-previa/",
    f"{WP_BASE}/servicios-municipales/urbanismo/actuaciones-exentas/",
    f"{WP_BASE}/servicios-municipales/urbanismo/otros-titulos/",
    f"{WP_BASE}/servicios-municipales/urbanismo/plan-de-movilidad-urbana-sostenible-pmus/",
    f"{SEDE_BASE}/publico/procedimientos",
    f"{SEDE_BASE}/publico/contratacion",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|licencia apertura|segregaci[oó]n|parcelaci[oó]n|vado|"
    r"actuaciones exentas|t[ií]tulos habilitantes)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgo|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|planimetr|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|rectificaci[oó]n|exposici[oó]n p[uú]blica|"
    r"calificaci[oó]n|supletorio|actuaci[oó]n en medio urbano|participaci[oó]n ciudadana|"
    r"pmus|alteraci[oó]n de planeamiento|consulta previa)",
)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://[^"]+|/[^"]+)\.pdf[^"]*)"',
    re.I,
)
RE_WP_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
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
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "nnss" in b or "normas subsidiarias" in b:
        return "NNSS"
    if "ordenanza" in b:
        return "ordenanza"
    if "pmus" in b or "movilidad urbana" in b:
        return "PMUS"
    if "plan parcial" in b:
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "pgo" in b or "pgou" in b or "plan general" in b:
        return "PGOU"
    if "modificaci" in b and "menor" in b:
        return "modificación menor"
    if "modificaci" in b and ("sustancial" in b or "nnss" in b):
        return "modificación sustancial"
    if "alteraci" in b and "planeamiento" in b:
        return "alteración planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "participaci" in b and "ciudadana" in b:
        return "participación ciudadana"
    return "urbanismo"


class LaVictoriaDeAcentejoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (echeide) participación ciudadana + normativa + sede ATM-Maggioli."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.participacion_parent = int(self.config.get("participacion_parent_id", PARTICIPACION_PARENT_ID))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-la-victoria-de-acentejo/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or WP_BASE, href))

    def _collect_wp_rest_pages(self, parent_id: int | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 10:
            params: dict[str, str] = {"per_page": "100", "page": str(page)}
            if parent_id is not None:
                params["parent"] = str(parent_id)
            qs = urllib.parse.urlencode(params)
            try:
                items = self._fetch_json(f"{WP_BASE}/wp-json/wp/v2/pages?{qs}")
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(items, list) or not items:
                break
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = (item.get("title") or {}).get("rendered") or ""
                title = _strip_html(title)
                link = str(item.get("link") or "")
                date = str(item.get("date") or "")[:10] or None
                content = (item.get("content") or {}).get("rendered") or ""
                blob = f"{title} {link} {_strip_html(content)[:500]}"
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": date or _fecha_from_blob(blob),
                        "url": link,
                        "content": content,
                        "blob": blob,
                        "origen": "wordpress_rest",
                    }
                )
            if len(items) < 100:
                break
            page += 1
        return rows

    def _extract_pdfs_from_content(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        content = row.get("content") or ""
        title = row.get("titulo") or ""
        for m in RE_PDF_HREF.finditer(content):
            pdf = self._abs_url(m.group(1))
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            pdf_blob = f"{title} {name} {pdf}"
            out.append(
                {
                    "titulo": f"{title}: {name}"[:500] if title else name[:500],
                    "fecha": _fecha_from_blob(f"{name} {pdf}") or row.get("fecha"),
                    "url": row.get("url"),
                    "pdf_url": pdf,
                    "blob": pdf_blob,
                    "origen": "wordpress_pdf",
                }
            )
        for m in RE_WP_LINK.finditer(content):
            href = m.group(1)
            anchor = _strip_html(m.group(2))
            if not re.search(r"(?i)\.pdf", href):
                continue
            pdf = self._abs_url(href)
            name = anchor if len(anchor) > 5 else unescape(urllib.parse.unquote(Path(pdf).name))
            pdf_blob = f"{title} {name} {pdf}"
            out.append(
                {
                    "titulo": f"{title}: {name}"[:500],
                    "fecha": _fecha_from_blob(f"{name} {pdf}") or row.get("fecha"),
                    "url": row.get("url"),
                    "pdf_url": pdf,
                    "blob": pdf_blob,
                    "origen": "wordpress_pdf",
                }
            )
        return out

    def _collect_seed_html_pages(self) -> list[dict[str, Any]]:
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
            title = _strip_html(re.search(r"<title>([^<]+)", html, re.I).group(1)) if re.search(
                r"<title>([^<]+)", html, re.I
            ) else page_url.rsplit("/", 2)[-2].replace("-", " ")
            title = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", title, flags=re.I).strip()
            blob = f"{title} {page_url}"
            row = {
                "titulo": title[:500],
                "fecha": _fecha_from_blob(f"{title} {page_url} {html[:2000]}"),
                "url": page_url,
                "content": html,
                "blob": blob,
                "origen": "wordpress_page",
            }
            rows.append(row)
            for pdf_row in self._extract_pdfs_from_content(row):
                rows.append(pdf_row)
        return rows

    def _collect_all_sources(self) -> list[dict[str, Any]]:
        raw: list[dict[str, Any]] = []
        for row in self._collect_wp_rest_pages(parent_id=self.participacion_parent):
            raw.append(row)
            raw.extend(self._extract_pdfs_from_content(row))
        for row in self._collect_wp_rest_pages(parent_id=URBANISMO_PAGE_ID):
            raw.append(row)
            raw.extend(self._extract_pdfs_from_content(row))
        raw.extend(self._collect_seed_html_pages())
        return raw

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        info_pages = [
            (f"{WP_BASE}/servicios-municipales/urbanismo/licencias/", "Licencias de obra — urbanismo"),
            (
                f"{WP_BASE}/servicios-municipales/urbanismo/comunicacion-previa/",
                "Comunicación previa — urbanismo",
            ),
            (
                f"{WP_BASE}/servicios-municipales/urbanismo/actuaciones-exentas/",
                "Actuaciones exentas — urbanismo",
            ),
            (f"{WP_BASE}/servicios-municipales/urbanismo/otros-titulos/", "Otros títulos habilitantes"),
            (f"{self.sede_base}/publico/procedimientos", "Catálogo de procedimientos — sede electrónica"),
            (f"{self.sede_base}/", "Sede electrónica municipal"),
        ]
        rows: list[dict[str, Any]] = []
        for url, titulo in info_pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                }
            )
        return rows

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if row.get("origen") == "tramite_informativo":
            return row
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(row.get("titulo", "")):
            return None
        key = row.get("pdf_url") or row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / trámite",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _dedupe(self, rows: list[dict[str, Any]], key: str = "id") -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            rid = row.get(key)
            if not rid or rid in seen:
                continue
            seen.add(rid)
            out.append(row)
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        raw = self._collect_licencia_tramites()
        for row in self._collect_all_sources():
            lic = self._to_licencia(row)
            if lic:
                raw.append(lic)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "wordpress_sede_atm"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        raw: list[dict[str, Any]] = []
        for row in self._collect_all_sources():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "wordpress_rest"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
