from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

PROD_BASE = "https://coslada.es"
MIRROR_BASE = "https://cosladapre.toools.es"
POLITICA_PATH = "/politica-territorial"
MUNICIPIO = "Coslada"
ID_PREFIX = "coslada"

DEFAULT_PROYECTO_PAGES: list[str] = [
    f"{PROD_BASE}{POLITICA_PATH}/urbanismo/planes-y-proyectos/planes-planeamiento/",
    f"{PROD_BASE}{POLITICA_PATH}/urbanismo/planes-y-proyectos/planes-pgou/",
    f"{PROD_BASE}{POLITICA_PATH}/urbanismo/convenios-urbanisticos/",
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{PROD_BASE}{POLITICA_PATH}/urbanismo/impresos-administrativos/tramites-obra/",
    f"{PROD_BASE}{POLITICA_PATH}/urbanismo/impresos-administrativos/tramites-actividad/",
    f"{PROD_BASE}{POLITICA_PATH}/urbanismo/impresos-administrativos/informacion-urbanistica/",
    f"{PROD_BASE}{POLITICA_PATH}/urbanismo/impresos-administrativos/ocupacion-via-publica/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|tr[aá]mite.*obra|tr[aá]mite.*actividad)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|peri|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|urbanizaci[oó]n|"
    r"memoria|planos|ficha|certificado)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DOC_ROW = re.compile(r"<div class='document-icon-row'>(.*?)</div>\s*</div>", re.S | re.I)
RE_DOC_TITLE = re.compile(r'class="title">([^<]+)', re.I)
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


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


def _fecha_from_url(url: str) -> str | None:
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


def _clean_project_name(title: str) -> str:
    t = unescape(title or "").strip()
    t = re.sub(r"^\d{1,2}[-_]", "", t)
    t = re.sub(r"\.pdf$", "", t, flags=re.I)
    t = re.sub(r"[-_]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if t and not t[0].isupper():
        t = t[:1].upper() + t[1:]
    return t[:500] if t else title[:500]


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r"<title>([^<]+)",
        r'<h2[^>]*class="[^"]*subheader-maintitle[^"]*"[^>]*>([^<]+)',
        r"<h1[^>]*>([^<]+)",
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-–|].*(?:Política territorial|Ayuntamiento).*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _proyecto_tipo(blob: str, page_hint: str = "") -> str:
    text = f"{blob} {page_hint}".lower()
    if "convenio" in text:
        return "convenio urbanístico"
    if "pgou" in text or "plan general" in text:
        return "PGOU"
    if "peri" in text or "plan parcial" in text:
        return "plan parcial"
    if "estudio de detalle" in text or "estudio detalle" in text:
        return "estudio de detalle"
    if "reparcel" in text:
        return "reparcelación"
    if "urbaniz" in text:
        return "proyecto de urbanización"
    if "informacion publica" in text or "información pública" in text:
        return "información pública"
    if "modificacion" in text or "modificación" in text:
        return "modificación PGOU"
    return "planeamiento"


class CosladaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (política territorial): rejillas PDF + trámites informativos."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or PROD_BASE)
        self.prod_base = self.base_url.rstrip("/")
        self.fetch_base = str(self.config.get("fetch_base") or MIRROR_BASE).rstrip("/")
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.proyecto_pages = [str(u) for u in (self.config.get("proyecto_pages") or DEFAULT_PROYECTO_PAGES)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]

    def _to_fetch_url(self, url: str) -> str:
        return url.replace(self.prod_base, self.fetch_base)

    def _canonical_url(self, url: str) -> str:
        return url.replace(self.fetch_base, self.prod_base)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        fetch_url = self._to_fetch_url(url)
        req = urllib.request.Request(
            fetch_url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-coslada/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, page_url: str) -> str:
        resolved = urllib.parse.urljoin(page_url, unescape(href))
        return self._canonical_url(resolved)

    def _parse_document_rows(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for block in RE_DOC_ROW.findall(html):
            titles = [unescape(t.strip()) for t in RE_DOC_TITLE.findall(block)]
            pdfs = [self._abs_url(h, page_url) for h in RE_PDF_HREF.findall(block)]
            if not titles and not pdfs:
                continue
            rows.append({"titles": titles, "pdfs": pdfs})
        return rows

    def _pick_project_title(self, titles: list[str], page_url: str) -> str:
        for t in titles:
            tl = t.lower()
            if any(k in tl for k in ("ficha", "resumen-ambito", "resumen ambito")):
                return _clean_project_name(t)
        for t in titles:
            if re.search(r"(?i)estudio de detalle|estudio detalle|peri |reparcel|urbaniz|convenio|modificaci[oó]n|pgou", t):
                return _clean_project_name(t)
        for t in titles:
            if re.search(r"(?i)certificado.*(?:inicial|definitiva)", t):
                return _clean_project_name(t)
        if titles:
            return _clean_project_name(titles[0])
        return _page_title("", Path(page_url).parent.name.replace("-", " "))

    def _row_to_proyecto(self, row: dict[str, Any], page_url: str) -> dict[str, Any] | None:
        titles = row.get("titles") or []
        pdfs = row.get("pdfs") or []
        if not pdfs and not titles:
            return None
        titulo = self._pick_project_title(titles, page_url)
        blob = f"{titulo} {' '.join(titles)} {' '.join(pdfs)}"
        if not RE_PROYECTO.search(blob):
            return None
        pdf_url = pdfs[0] if pdfs else page_url
        fecha = None
        for candidate in [titulo, *titles, *pdfs]:
            fecha = _parse_fecha_dmy(candidate) or _fecha_from_url(candidate)
            if fecha:
                break
        return {
            "id": _stable_id("proy", pdf_url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": fecha,
            "tipo": _proyecto_tipo(blob, page_url),
            "url": page_url,
            "pdf_url": pdf_url if pdf_url.endswith(".pdf") else None,
            "source": "ayuntamiento",
            "origen": page_url,
            "documentos": len(pdfs),
        }

    def _pdf_to_proyecto(self, pdf_url: str, page_url: str, page_title: str) -> dict[str, Any] | None:
        name = unescape(urllib.parse.unquote(Path(pdf_url).name))
        titulo = _clean_project_name(name)
        if len(titulo) < 8:
            titulo = f"{page_title}: {titulo}"[:500]
        blob = f"{titulo} {name} {page_url}"
        if not RE_PROYECTO.search(blob):
            return None
        if re.search(r"(?i)thumb|favicon|alegacion|informe sectorial|estudio ambiental|estudio acust|estudio de suelos", name):
            return None
        fecha = _parse_fecha_dmy(name) or _fecha_from_url(pdf_url)
        return {
            "id": _stable_id("proy", pdf_url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(blob, page_url),
            "url": page_url,
            "pdf_url": pdf_url,
            "source": "ayuntamiento",
            "origen": page_url,
        }

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for page_url in self.proyecto_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            canonical_page = self._canonical_url(page_url)
            page_title = _page_title(html, canonical_page.rstrip("/").rsplit("/", 1)[-1])

            for row in self._parse_document_rows(html, canonical_page):
                add(self._row_to_proyecto(row, canonical_page))

            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1), canonical_page)
                if any(pdf in (r.get("pdf_url") or "") for r in rows):
                    continue
                add(self._pdf_to_proyecto(pdf, canonical_page, page_title))

        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            canonical_page = self._canonical_url(page_url)
            title = _page_title(html, canonical_page.rstrip("/").rsplit("/", 1)[-1].replace("-", " "))
            if not RE_LICENCIA.search(f"{title} {canonical_page}"):
                continue
            pdfs = [self._abs_url(h, canonical_page) for h in RE_PDF_HREF.findall(html)]
            rec: dict[str, Any] = {
                "id": _stable_id("lic", canonical_page),
                "fecha_concesion": None,
                "tipo": "trámite licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": canonical_page,
                "source": "ayuntamiento",
                "nota": "Página informativa de trámites; sede sin listado público de concesiones",
            }
            if pdfs:
                rec["pdf_url"] = pdfs[0]
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
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
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_informativos"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
            else:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "politica_territorial_pdfs"}

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
