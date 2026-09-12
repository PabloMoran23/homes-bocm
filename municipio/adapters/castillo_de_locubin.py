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

WP_BASE = "https://aytocastillodelocubin.org"
WP_API = f"{WP_BASE}/wp-json/wp/v2"
MUNICIPIO = "Castillo de Locubín"
ID_PREFIX = "castillo-de-locubin"

# Páginas semilla vía WP REST (IDs estables del portal de transparencia)
DEFAULT_PAGE_IDS: list[int] = [
    6032,   # Formularios trámites (licencias)
    8460,   # Anuncios (tablón)
    528,    # Normativa urbanística (PGOU/NN.SS)
    11942,  # Procedimiento exposición pública
]

DEFAULT_SEED_URLS: list[str] = [
    f"{WP_BASE}/formularios/",
    f"{WP_BASE}/portal-de-transparencia/",
]

RE_COLLAPSE_SECTION = re.compile(
    r'<span[^>]*class="collapseomatic[^"]*"[^>]*title="([^"]*)"[^>]*>.*?</span>\s*'
    r'<div[^>]*class="collapseomatic_content[^"]*"[^>]*>(.*?)</div>',
    re.I | re.S,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal)?|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable.*(?:obra|urban|actuaci)|"
    r"certificado urban|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"actuaciones urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nn\.?ss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|exposici[oó]n p[uú]blica|consulta p[uú]blica|"
    r"delimitaci[oó]n|reserva de suelo|inventario de cubiertas|clasificaci[oó]n|"
    r"evaluaci[oó]n ambiental|eae|edar|agrupaci[oó]n de vertidos|calificaci[oó]n ambiental)",
)
RE_NON_URBAN = re.compile(
    r"(?i)(cheque libro|pr[aá]cticas universitarias|premio mar[ií]a moliner|"
    r"barra fiesta|carnaval|colonias felinas|concurso de relatos|escaparates|"
    r"balcones.*navide|yo compro en mi pueblo|casetas feria|bolsa de empleo|"
    r"consejo local de (?:discapacidad|infancia)|plan de juventud|plan local de infancia|"
    r"plan estrat[eé]gico de subvenciones|igualdad|juez de paz|guarder[ií]a|"
    r"selecci[oó]n de personal|empleo|subvenci[oó]n|fiesta|feria|cereza|"
    r"semana santa|emigrante|romer[ií]a|stand|barras|pomp[aá])",
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?aytocastillodelocubin\.org)?/wp-content/uploads/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_WP_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|documents)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

FORMULARIO_TRAMITES: list[tuple[str, str]] = [
    (
        f"{WP_BASE}/wp-content/uploads/2020/10/certificado-urbanistico.pdf",
        "Certificado urbanístico",
    ),
    (
        f"{WP_BASE}/wp-content/uploads/2023/02/Declaracion-responsable-actuaciones-urbanisticas.pdf",
        "Declaración responsable actuaciones urbanísticas",
    ),
    (
        f"{WP_BASE}/wp-content/uploads/2023/05/SOLICITUD-DE-LICENCIA-DE-OBRAS-SUELO-NO-URBANIZABLE.pdf",
        "Solicitud licencia obra menor suelo no urbanizable",
    ),
    (
        f"{WP_BASE}/wp-content/uploads/2023/05/PLANTILLA-LICENCIA-OBRA-MAYOR.pdf",
        "Solicitud licencia obra mayor",
    ),
]


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


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "nn.ss" in b or "normas subsidiarias" in b or "pgou" in b:
        return "PGOU/NN.SS"
    if "delimitaci" in b and "suelo industrial" in b:
        return "delimitación suelo industrial"
    if "inventario de cubiertas" in b:
        return "inventario de cubiertas"
    if "evaluaci" in b and "ambiental" in b:
        return "evaluación ambiental"
    if "edar" in b or "vertidos" in b:
        return "infraestructura EDAR"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "exposici" in b and "p" in b and "blica" in b:
        return "exposición pública"
    if "consulta p" in b and "blica" in b:
        return "consulta pública"
    if "memoria" in b:
        return "memoria planeamiento"
    if "planos" in b or "clasificaci" in b:
        return "cartografía urbanística"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class CastilloDeLocubinAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress BusinessX: formularios + tablón anuncios + transparencia (normativa/exposición pública)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.page_ids = [int(x) for x in (self.config.get("page_ids") or DEFAULT_PAGE_IDS)]
        self.seed_urls = [str(u) for u in (self.config.get("seed_urls") or DEFAULT_SEED_URLS)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-castillo-de-locubin/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{WP_BASE}/", href))

    def _parse_collapse_sections(self, content: str, page_url: str, page_title: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_COLLAPSE_SECTION.finditer(content):
            section_title = _strip_html(unescape(m.group(1)))
            section_html = m.group(2)
            blob = f"{page_title} {section_title}"
            section_row = {
                "titulo": section_title[:500],
                "fecha": _fecha_from_blob(blob),
                "url": page_url,
                "blob": blob,
                "origen": "wordpress_collapse",
            }
            rows.append(section_row)
            for link_m in RE_WP_LINK.finditer(section_html):
                href = link_m.group(1)
                anchor = _strip_html(link_m.group(2))
                if not re.search(r"(?i)\.pdf", href):
                    continue
                pdf = self._abs_url(href)
                name = anchor if len(anchor) > 3 else unescape(urllib.parse.unquote(Path(pdf).name))
                pdf_blob = f"{section_title} {name} {pdf}"
                rows.append(
                    {
                        "titulo": f"{section_title}: {name}"[:500],
                        "fecha": _fecha_from_blob(f"{name} {pdf}") or section_row.get("fecha"),
                        "url": page_url,
                        "pdf_url": pdf,
                        "blob": pdf_blob,
                        "origen": "wordpress_pdf",
                    }
                )
        return rows

    def _extract_pdfs_from_content(
        self, content: str, page_url: str, page_title: str
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PDF_HREF.finditer(content):
            pdf = self._abs_url(m.group(1))
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            pdf_blob = f"{page_title} {name} {pdf}"
            rows.append(
                {
                    "titulo": f"{page_title}: {name}"[:500],
                    "fecha": _fecha_from_blob(f"{name} {pdf}"),
                    "url": page_url,
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
            name = anchor if len(anchor) > 3 else unescape(urllib.parse.unquote(Path(pdf).name))
            pdf_blob = f"{page_title} {name} {pdf}"
            rows.append(
                {
                    "titulo": f"{page_title}: {name}"[:500],
                    "fecha": _fecha_from_blob(f"{name} {pdf}"),
                    "url": page_url,
                    "pdf_url": pdf,
                    "blob": pdf_blob,
                    "origen": "wordpress_pdf",
                }
            )
        return rows

    def _collect_wp_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_id in self.page_ids:
            try:
                item = self._fetch_json(f"{WP_API}/pages/{page_id}")
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(item, dict):
                continue
            title = _strip_html((item.get("title") or {}).get("rendered") or "")
            link = str(item.get("link") or f"{WP_BASE}/?page_id={page_id}")
            date = str(item.get("date") or "")[:10] or None
            content = (item.get("content") or {}).get("rendered") or ""
            blob = f"{title} {link} {_strip_html(content)[:800]}"
            page_row = {
                "titulo": title[:500],
                "fecha": date or _fecha_from_blob(blob),
                "url": link,
                "content": content,
                "blob": blob,
                "origen": "wordpress_rest",
            }
            rows.append(page_row)
            rows.extend(self._parse_collapse_sections(content, link, title))
            rows.extend(self._extract_pdfs_from_content(content, link, title))
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for pdf_url, titulo in FORMULARIO_TRAMITES:
            rows.append(
                {
                    "id": _stable_id("lic", pdf_url),
                    "fecha_concesion": _fecha_from_blob(pdf_url),
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": "formulario_tramite",
                }
            )
        rows.append(
            {
                "id": _stable_id("lic", f"{WP_BASE}/formularios/"),
                "fecha_concesion": None,
                "tipo": "trámite informativo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Formularios trámites urbanismo — ayuntamiento",
                "url": f"{WP_BASE}/formularios/",
                "source": "ayuntamiento",
                "origen": "formulario_tramite",
            }
        )
        return rows

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if row.get("origen") == "formulario_tramite":
            return row
        blob = row.get("blob") or ""
        if RE_NON_URBAN.search(blob):
            return None
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
        if RE_NON_URBAN.search(blob):
            return None
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
            "url": row.get("pdf_url") or row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
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
        for row in self._collect_wp_pages():
            lic = self._to_licencia(row)
            if lic:
                raw.append(lic)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "wordpress_formularios"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        raw: list[dict[str, Any]] = []
        for row in self._collect_wp_pages():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "wordpress_rest"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
