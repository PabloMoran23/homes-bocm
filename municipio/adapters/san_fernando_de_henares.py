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

BASE = "https://www.ayto-sanfernando.com"

DEFAULT_TABLON_PAGES = [
    f"{BASE}/tablon-anuncios-ayuntamiento/",
    f"{BASE}/tablon-anuncios-otras-administraciones/",
]
DEFAULT_PLANEAMIENTO_PAGES = [
    f"{BASE}/planificacion-de-la-ciudad-y-desarrollo-sostenible/",
    f"{BASE}/plan-general/",
]
DEFAULT_LICENCIA_PAGES = [
    f"{BASE}/licencias-urbanismo/",
    f"{BASE}/licencia-urbanistica/",
    f"{BASE}/declaracion-responsable-urbanistica/",
    f"{BASE}/certificacion-urbanistica/",
    f"{BASE}/cambio-de-uso-de-inmuebles/",
]

RE_TABLON_ITEM = re.compile(
    r'<li>(\d{1,2}/\d{1,2}/\d{4})\s*[–\-&#8211;]\s*'
    r'<a href="([^"]+)"[^>]*>([^<]+)</a></li>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|certificaci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|modificaci[oó]n|"
    r"aprobaci[oó]n (?:inicial|definitiva)|edicto|estudio (?:ac[uú]stico|ambiental)|"
    r"orden de ejecuci|segregaci|mejora de la ordenaci)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/wp-content/uploads/(\d{4})/(\d{2})/")
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.ayto-sanfernando\.com)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"sanfernando-{prefix}-{h}"


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
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>([^<]+)',
        r"<h1[^>]*>([^<]+)",
        r"<title>([^<]+)",
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _pgou_tipo(name: str) -> str:
    n = name.lower()
    if "informacion" in n or "info" in n:
        return "información pública"
    if "convenio" in n:
        return "convenio urbanístico"
    if "plan parcial" in n or "modificacion" in n or "modificación" in n:
        return "planeamiento"
    if "plan especial" in n or "pe-" in n:
        return "plan especial"
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "estudio" in n or "ambiental" in n:
        return "estudio ambiental"
    return "documento urbanismo"


class SanFernandoDeHenaresAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi: tablón HTML + PDFs planeamiento + trámites informativos."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.tablon_pages = [str(u) for u in (self.config.get("tablon_pages") or DEFAULT_TABLON_PAGES)]
        self.planeamiento_pages = [
            str(u) for u in (self.config.get("planeamiento_pages") or DEFAULT_PLANEAMIENTO_PAGES)
        ]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-sanfernando/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60, context=self._ssl_ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(BASE, href)

    def _collect_tablon(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.tablon_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_TABLON_ITEM.finditer(html):
                fecha_raw = m.group(1)
                pdf_url = self._abs_url(m.group(2))
                titulo = unescape(m.group(3).strip())
                key = pdf_url
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _parse_fecha_dmy(fecha_raw),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "origen": page_url,
                    }
                )
        return rows

    def _collect_planeamiento_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.planeamiento_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = _page_title(html, page_url.rsplit("/", 2)[-2].replace("-", " "))
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                titulo = name[:500]
                ctx_start = max(0, m.start() - 800)
                ctx = unescape(re.sub(r"<[^>]+>", " ", html[ctx_start : m.start() + 200]))
                link_m = re.search(
                    r"((?:Plan|Aprobaci[oó]n|Modificaci[oó]n|Convenio|Expediente)[^.]{10,200})",
                    ctx,
                    re.I,
                )
                if link_m:
                    titulo = link_m.group(1).strip()[:500]
                elif page_title:
                    titulo = f"{page_title}: {name}"[:500]
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_pdf_url(pdf),
                        "url": page_url,
                        "pdf_url": pdf,
                        "tipo": _pgou_tipo(titulo + " " + name),
                        "origen": page_url,
                    }
                )
        return rows

    def _collect_licencia_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self.licencia_pages:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = _page_title(html, url.rsplit("/", 2)[-2].replace("-", " "))
            if not RE_LICENCIA.search(title) and "urbanismo" not in url and "urban" not in url:
                continue
            pdfs = [self._abs_url(m.group(1)) for m in RE_PDF_HREF.finditer(html)]
            rec: dict[str, Any] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": "trámite licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": url,
                "source": "ayuntamiento",
                "nota": "Página informativa de trámite; no concesión publicada en tablón",
            }
            if pdfs:
                rec["pdf_url"] = pdfs[0]
            rows.append(rec)
        return rows

    def _tablon_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item["titulo"]
        if not RE_LICENCIA.search(titulo):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", item["pdf_url"]),
            "fecha_concesion": item.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": item.get("url", ""),
            "source": "ayuntamiento",
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        return rec

    def _tablon_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item["titulo"]
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        if not RE_PROYECTO.search(titulo):
            return None
        tipo = "urbanismo"
        if re.search(r"(?i)plan parcial|modificaci[oó]n", titulo):
            tipo = "planeamiento"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica", titulo):
            tipo = "información pública"
        elif re.search(r"(?i)convenio", titulo):
            tipo = "convenio"
        elif re.search(r"(?i)acuerdo|pleno", titulo):
            tipo = "acuerdo plenario"
        return {
            "id": _stable_id("proy", item["pdf_url"]),
            "municipio": "San Fernando de Henares",
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": tipo,
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "pdf_url": item.get("pdf_url"),
            "origen": item.get("origen"),
        }

    def _planeamiento_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        pdf = item.get("pdf_url") or item["url"]
        return {
            "id": _stable_id("proy", pdf),
            "municipio": "San Fernando de Henares",
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": item.get("tipo", "documento urbanismo"),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "pdf_url": item.get("pdf_url"),
            "origen": item.get("origen"),
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
        for rec in self._collect_licencia_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tramite_pages": len(self.licencia_pages)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_pages():
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

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_planeamiento_pdfs():
            add(self._planeamiento_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_pages": len(self.tablon_pages),
            "planeamiento_pages": len(self.planeamiento_pages),
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
