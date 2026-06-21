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

WP_BASE = "https://web.trescantos.es"
SEDE_BASE = "https://sede.trescantos.es"
MUNICIPIO = "Tres Cantos"
ID_PREFIX = "tres-cantos"

TABLON_DEFAULT = f"{SEDE_BASE}/eAdmin/Tablon.do?action=verAnuncios&tipoTablon=1"
LICENCIAS_TRAMITE = f"{WP_BASE}/tramite/licencias-urbanisticas/"

DEFAULT_PUBLICACION_PAGES: list[str] = [
    f"{WP_BASE}/publicacion/plan-genera-ordenacion-urbana/",
    f"{WP_BASE}/publicacion/planes-parciales/",
    f"{WP_BASE}/publicacion/planes-especiales/",
    f"{WP_BASE}/publicacion/proyectos-de-urbanizacion/",
    f"{WP_BASE}/publicacion/estudios-de-detalle/",
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    LICENCIAS_TRAMITE,
    f"{WP_BASE}/tramite/acceso-a-la-informacion-publica-archivos-y-registros-de-urbanismo/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|edicto.*licencia|"
    r"notificaci[oó]n.*licencia|disciplina urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva)|orden de ejecuci|segregaci|parcela|"
    r"urbanizaci[oó]n|exp\.\s*\d)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[./_-](\d{2})[./_-]")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="((?:https?://[^"]+|/[^"]+)\.pdf[^"]*)"', re.I)
RE_TABLON_LINK = re.compile(
    r'href="([^"]*Tablon\.do\?[^"]*action=verAnuncio[^"]*id=([A-F0-9]+)[^"]*)"',
    re.I,
)
RE_TABLON_DESC = re.compile(
    r"(?i)Descripci[oó]n\s*</[^>]+>\s*</[^>]+>\s*<[^>]+>\s*([^<]+)",
)
RE_TABLON_FECHA = re.compile(
    r"(?i)Fecha inicio publicaci[oó]n\s*</[^>]+>\s*</[^>]+>\s*<[^>]+>\s*"
    r"(\d{1,2}/\d{1,2}/\d{4})",
)
RE_EXP = re.compile(r"(?i)(?:EXP\.?|Expediente)\s*[:.]?\s*([A-Z0-9./-]+)")


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{prefix}-{h}"


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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(Path(url).name) if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r"<title>([^<]+)",
        r'<h1[^>]*class="[^"]*elementor-heading-title[^"]*"[^>]*>([^<]+)',
        r"<h1[^>]*>([^<]+)",
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3 and "buscado" not in t.lower():
                return t[:500]
    return fallback


def _pdf_tipo(name: str, section: str = "") -> str:
    blob = f"{name} {section}".lower()
    if "estudio" in blob and "detalle" in blob:
        return "estudio de detalle"
    if "plan parcial" in blob or re.search(r"\d{2}pd\d{4}", blob):
        return "plan parcial"
    if "plan especial" in blob or re.search(r"\d{2}pe\d{4}", blob):
        return "plan especial"
    if "pgou" in blob or "ordenacion" in blob or "ordenación" in blob:
        return "PGOU"
    if "urbaniz" in blob:
        return "proyecto urbanización"
    if "convenio" in blob:
        return "convenio"
    if "informacion" in blob or "información" in blob:
        return "información pública"
    return "documento urbanismo"


class TresCantosAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress publicaciones urbanismo + tablón sede eAdmin + trámites licencia."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_DEFAULT)
        self.publicacion_pages = [str(u) for u in (self.config.get("publicacion_pages") or DEFAULT_PUBLICACION_PAGES)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-tres-cantos/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.trescantos.es" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str = WP_BASE) -> str:
        return urllib.parse.urljoin(base, unescape(href))

    def _abs_sede(self, href: str) -> str:
        return self._abs_url(href, f"{self.sede_base}/")

    def _extract_pdfs_with_context(self, html: str, page_url: str) -> list[dict[str, Any]]:
        """PDFs con sección h3/h4 más cercana para título enriquecido."""
        page_title = _page_title(html, page_url.rstrip("/").rsplit("/", 1)[-1].replace("-", " "))
        sections: list[tuple[int, str]] = []
        for m in re.finditer(r"<h[34][^>]*>([^<]+)", html, re.I):
            sections.append((m.start(), unescape(m.group(1).strip())[:200]))

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf = self._abs_url(m.group(1))
            if "manual_ivc" in pdf.lower() or "favicon" in pdf.lower():
                continue
            if "/contenido/urbanismo/" not in pdf.lower() and "/fondo-documental/" not in pdf.lower():
                if not RE_PROYECTO.search(pdf):
                    continue
            pos = m.start()
            section = page_title
            for start, title in sections:
                if start < pos:
                    section = title
                else:
                    break
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            rec_id = _stable_id("proy", pdf)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            titulo = f"{section}: {name}" if section and section.lower() not in name.lower() else name
            rows.append(
                {
                    "id": rec_id,
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_pdf_url(pdf),
                    "tipo": _pdf_tipo(name, section),
                    "url": page_url,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "origen": "publicacion",
                    "expte": (RE_EXP.search(section) or RE_EXP.search(name) or RE_EXP.search(titulo)),
                }
            )
        for row in rows:
            ex = row.pop("expte", None)
            if ex:
                row["expte"] = ex.group(1).strip()
        return rows

    def _collect_publicacion_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.publicacion_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for rec in self._extract_pdfs_with_context(html, page_url):
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        return rows

    def _parse_tablon_list(self, html: str) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        seen: set[str] = set()
        for m in RE_TABLON_LINK.finditer(html):
            href, ann_id = m.group(1), m.group(2)
            if ann_id in seen:
                continue
            seen.add(ann_id)
            items.append({"id": ann_id, "url": self._abs_sede(href)})
        if items:
            return items
        for m in re.finditer(
            r"verAnuncio[^\"']*id=([A-F0-9]+)",
            html,
            re.I,
        ):
            ann_id = m.group(1)
            if ann_id in seen:
                continue
            seen.add(ann_id)
            items.append(
                {
                    "id": ann_id,
                    "url": f"{self.sede_base}/eAdmin/Tablon.do?action=verAnuncio&id={ann_id}",
                }
            )
        return items

    def _fetch_tablon_detail(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url, use_sede_ssl=True)
        except urllib.error.URLError:
            return None
        title_m = re.search(r"<h2[^>]*>([^<]+)", html, re.I)
        title = unescape(title_m.group(1).strip()) if title_m else ""
        if not title:
            desc_m = RE_TABLON_DESC.search(html)
            title = unescape(desc_m.group(1).strip()) if desc_m else ""
        fecha_m = RE_TABLON_FECHA.search(html)
        fecha = _parse_fecha_dmy(fecha_m.group(1)) if fecha_m else None
        pdfs = [self._abs_sede(x) for x in re.findall(r'href="([^"]+\.pdf[^"]*)"', html, re.I)]
        return {
            "titulo": title[:500],
            "fecha": fecha,
            "url": url,
            "pdf_url": pdfs[0] if pdfs else None,
            "pdf_urls": pdfs[:20],
        }

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        items = self._parse_tablon_list(html)
        rows: list[dict[str, Any]] = []
        for item in items:
            detail = self._fetch_tablon_detail(item["url"])
            if detail and detail.get("titulo"):
                detail["ann_id"] = item["id"]
                rows.append(detail)
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title = str(row.get("titulo") or "")
        if not RE_LICENCIA.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row.get("ann_id") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
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
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("ann_id") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": row.get("fecha"),
            "tipo": "urbanismo",
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
            page_title = _page_title(html, "Licencias urbanísticas")
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
                        "nota": "Página informativa; tramitación vía sede electrónica",
                    }
                )
            for m in re.finditer(r"<h4[^>]*>([^<]*[Ll]icencia[^<]{0,200})</h4>", html, re.I):
                title = unescape(re.sub(r"\s+", " ", m.group(1)).strip())
                rid = _stable_id("lic", title)
                if rid in seen:
                    continue
                seen.add(rid)
                rows.append(
                    {
                        "id": rid,
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title[:500],
                        "url": page_url,
                        "source": "ayuntamiento",
                        "origen": "tramite_info",
                    }
                )
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                if "fondo-documental" not in pdf.lower() and "l_lu" not in pdf.lower():
                    continue
                rid = _stable_id("lic", pdf)
                if rid in seen:
                    continue
                seen.add(rid)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                rows.append(
                    {
                        "id": rid,
                        "fecha_concesion": _fecha_from_pdf_url(pdf),
                        "tipo": "documentación licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": name[:500],
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": "tramite_doc",
                    }
                )
        return rows

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
            "tramites": sum(1 for r in rows if r.get("origen", "").startswith("tramite")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencias_tramites():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
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

        for rec in self._collect_publicacion_proyectos():
            add(rec)
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "publicacion": sum(1 for r in rows if r.get("origen") == "publicacion"),
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
