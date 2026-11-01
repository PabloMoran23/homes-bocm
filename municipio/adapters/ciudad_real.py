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

BASE = "https://www.ciudadreal.es"
MUNICIPIO = "Ciudad Real"
ID_PREFIX = "ciudad-real"

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/servicios-municipales/urbanismo/planificacion-y-operaciones-estrategicas/documentacion-en-tramite.html",
    f"{BASE}/servicios-municipales/urbanismo/planificacion-y-operaciones-estrategicas/modificaciones.html",
    (
        f"{BASE}/servicios-municipales/urbanismo/planificacion-y-operaciones-estrategicas/"
        "instrumentos-de-desarrollo-y-complementarios/estudios-de-detalle.html"
    ),
    (
        f"{BASE}/servicios-municipales/urbanismo/planificacion-y-operaciones-estrategicas/"
        "instrumentos-de-desarrollo-y-complementarios/sectores.html"
    ),
    (
        f"{BASE}/servicios-municipales/urbanismo/planificacion-y-operaciones-estrategicas/"
        "instrumentos-de-desarrollo-y-complementarios/unidades-de-ejecucion.html"
    ),
    f"{BASE}/servicios-municipales/urbanismo/planificacion-y-operaciones-estrategicas/pgou-ciudad-real.html",
    f"{BASE}/ayuntamiento/convenios/convenios-urbanisticos-2.html",
]

LICENCIA_PAGES: list[str] = [
    f"{BASE}/servicios-municipales/urbanismo/servicio-de-licencias.html",
    f"{BASE}/servicios-municipales/urbanismo/formularios-y-solicitudes.html",
    f"{BASE}/servicios-municipales/urbanismo/planificacion-y-operaciones-estrategicas/tramites.html",
]

RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?ciudadreal\.es)?'
    r"/documentos/(?:urbanismo|conveniosurbanismo|Tramites/urbanismo)[^\"]+\.(?:pdf|PDF|zip))\"",
    re.I,
)
RE_URBAN_LINK = re.compile(
    r'href="((?:https?://(?:www\.)?ciudadreal\.es)?/servicios-municipales/urbanismo[^\"#?]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|primera ocupaci[oó]n|solicitud.*obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial)|pgou|convenio|informaci[oó]n p[uú]blica|"
    r"modificaci[oó]n|estudio de detalle|pau |sector |unidad de ejecuci|reparcel|expropi)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_PREFIX = re.compile(r"(?:^|/)(\d{8})[_\-.]")
RE_HEADING = re.compile(
    r"<(?:h[1-3]|strong|b)[^>]*>\s*([^<]{25,500}?)\s*</(?:h[1-3]|strong|b)>",
    re.I | re.S,
)
RE_LASTMOD = re.compile(
    r"Última actualización:\s*(\d{1,2})\s+(\w+)\s+(\d{4})",
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


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_path(path: str) -> str | None:
    m = RE_FECHA_PREFIX.search(path or "")
    if not m:
        return None
    s = m.group(1)
    try:
        return datetime(int(s[:4]), int(s[4:6]), int(s[6:8])).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_lastmod(html: str) -> str | None:
    m = RE_LASTMOD.search(html or "")
    if not m:
        return None
    mo = MESES.get(m.group(2).lower())
    if not mo:
        return None
    try:
        return datetime(int(m.group(3)), mo, int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _proyecto_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "estudio de detalle" in n or "estudio detalle" in n:
        return "estudio de detalle"
    if "pau" in n or "programa de actuaci" in n:
        return "PAU"
    if "convenio" in n:
        return "convenio urbanístico"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "sector" in n:
        return "sector"
    if "unidad de ejecuci" in n or "ue-" in n:
        return "unidad de ejecución"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "pgou" in n:
        return "PGOU"
    return "planeamiento"


def _normalize_title(text: str) -> str:
    t = unescape(re.sub(r"\s+", " ", (text or "").strip()))
    return t[:500]


def _project_key_from_pdf(pdf_url: str) -> str:
    name = Path(urllib.parse.urlparse(pdf_url).path).stem
    name = re.sub(r"^\d{8}[_\-.]?", "", name, flags=re.I)
    for token in (
        "DOCM",
        "BOP",
        "ANUNCIO",
        "MEMORIA",
        "PLANOS",
        "EVALUACION",
        "EAE",
        "ACTA",
        "DILIGENCIA",
        "APROB",
        "PUBLICACION",
        "INFORME",
        "DICTAMEN",
    ):
        name = re.sub(rf"(?i)[_\s-]*{token}.*$", "", name)
    name = re.sub(r"[_\s-]+", "_", name).strip("_")
    return name[:120] or pdf_url


class CiudadRealAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla www.ciudadreal.es: planeamiento en páginas HTML + PDFs en /documentos/urbanismo/."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 12))

    @staticmethod
    def _encode_url(url: str) -> str:
        parts = urllib.parse.urlsplit(url)
        path = urllib.parse.quote(parts.path, safe="/%")
        query = urllib.parse.quote(parts.query, safe="=&%") if parts.query else parts.query
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))

    def _fetch(self, url: str) -> str:
        url = self._encode_url(url)
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ciudad-real/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return self._encode_url(urllib.parse.urljoin(BASE, href))

    def _item_page_html(self, html: str) -> str:
        m = re.search(r'class="[^"]*item-page[^"]*"', html, re.I)
        if not m:
            return html
        start = m.start()
        end = html.find('<div class="moduletable', start)
        if end < 0:
            end = start + 120_000
        return html[start:end]

    def _page_title(self, html: str, fallback: str = "") -> str:
        chunk = self._item_page_html(html)
        for pat in (
            r"<h1[^>]*>([^<]+)",
            r'class="[^"]*page-header[^"]*"[^>]*>\s*<h1[^>]*>([^<]+)',
            r"<title>([^<]+)",
        ):
            m = re.search(pat, chunk, re.I)
            if m:
                t = _normalize_title(m.group(1))
                t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
                if len(t) > 3:
                    return t
        return fallback

    def _extract_pdfs(self, html: str) -> list[str]:
        chunk = self._item_page_html(html)
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(chunk):
            u = self._abs_url(m.group(1))
            if u not in out:
                out.append(u)
        return out

    def _collect_tramite_sections(self, html: str, page_url: str) -> list[dict[str, Any]]:
        chunk = self._item_page_html(html)
        rows: list[dict[str, Any]] = []
        headings: list[tuple[int, str]] = []
        for m in RE_HEADING.finditer(chunk):
            title = _normalize_title(m.group(1))
            if len(title) < 25:
                continue
            upper_ratio = sum(1 for c in title if c.isupper()) / max(len(title), 1)
            if upper_ratio < 0.45 and not RE_PROYECTO.search(title):
                continue
            headings.append((m.start(), title))

        pdf_positions = [(m.start(), self._abs_url(m.group(1))) for m in RE_PDF_HREF.finditer(chunk)]
        page_fecha = _fecha_from_lastmod(chunk)

        for i, (pos, title) in enumerate(headings):
            end = headings[i + 1][0] if i + 1 < len(headings) else len(chunk)
            pdfs = [u for p, u in pdf_positions if pos <= p < end]
            if not RE_PROYECTO.search(title) and not pdfs:
                continue
            fechas = [_fecha_from_path(u) for u in pdfs]
            fechas = [f for f in fechas if f]
            fecha = max(fechas) if fechas else page_fecha
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"section:{page_url}:{title}"),
                "municipio": MUNICIPIO,
                "titulo": title,
                "fecha": fecha,
                "tipo": _proyecto_tipo(title),
                "url": page_url,
                "source": "ayuntamiento",
                "origen": "seccion_tramite",
            }
            if pdfs:
                rec["pdf_url"] = pdfs[0]
                if len(pdfs) > 1:
                    rec["pdf_urls"] = pdfs[:40]
            rows.append(rec)
        return rows

    def _collect_pdf_projects(self, html: str, page_url: str) -> list[dict[str, Any]]:
        title = self._page_title(html, page_url.rsplit("/", 1)[-1])
        page_fecha = _fecha_from_lastmod(html)
        by_key: dict[str, dict[str, Any]] = {}
        for pdf in self._extract_pdfs(html):
            key = _project_key_from_pdf(pdf)
            bucket = by_key.setdefault(
                key,
                {"pdfs": [], "titulos": [], "page": page_url, "page_title": title},
            )
            if pdf not in bucket["pdfs"]:
                bucket["pdfs"].append(pdf)

        rows: list[dict[str, Any]] = []
        for key, data in by_key.items():
            titulo = key.replace("_", " ")
            if data["page_title"] and data["page_title"] not in titulo:
                titulo = f"{data['page_title']}: {titulo}"
            fechas = [_fecha_from_path(u) for u in data["pdfs"]]
            fechas = [f for f in fechas if f]
            fecha = max(fechas) if fechas else page_fecha
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"pdf:{page_url}:{key}"),
                "municipio": MUNICIPIO,
                "titulo": _normalize_title(titulo),
                "fecha": fecha,
                "tipo": _proyecto_tipo(titulo),
                "url": data["page"],
                "source": "ayuntamiento",
                "origen": page_url,
            }
            if data["pdfs"]:
                rec["pdf_url"] = data["pdfs"][0]
                if len(data["pdfs"]) > 1:
                    rec["pdf_urls"] = data["pdfs"][:40]
            rows.append(rec)
        return rows

    def _crawl_seeds(self) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue = list(self.seed_pages)
        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen_ids:
                seen_ids.add(rec["id"])
                rows.append(rec)

        while queue and len(visited) < self.max_crawl_pages:
            url = queue.pop(0).rstrip("/")
            if url in visited:
                continue
            visited.add(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue

            if "documentacion-en-tramite" in url:
                for rec in self._collect_tramite_sections(html, url):
                    add(rec)

            for rec in self._collect_pdf_projects(html, url):
                add(rec)

            if len(visited) < self.max_crawl_pages:
                chunk = self._item_page_html(html)
                for m in RE_URBAN_LINK.finditer(chunk):
                    link = self._abs_url(m.group(1)).rstrip("/")
                    if link in visited or link in queue:
                        continue
                    if any(
                        skip in link
                        for skip in (
                            "servicio-de-licencias",
                            "servicio-de-regimen",
                            "servicio-de-control",
                            "normativa-urbanismo",
                            "accesibilidad",
                            "contacto.html",
                            "directorio.html",
                            "memoria-del-servicio",
                        )
                    ):
                        continue
                    if not link.startswith(BASE):
                        continue
                    if "/planificacion-y-operaciones-estrategicas/" in link or "/convenios/" in link:
                        if all(ord(c) < 128 for c in link):
                            queue.append(link)

        return rows

    def _collect_licencias_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for url in LICENCIA_PAGES:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = self._page_title(html, url.rsplit("/", 1)[-1])
            pdfs = [
                p
                for p in self._extract_pdfs(html)
                if "licenc" in p.lower() or "/Tramites/urbanismo/" in p
            ]
            if RE_LICENCIA.search(title) or pdfs or "licenc" in url.lower():
                rec_id = _stable_id("lic", url)
                if rec_id in seen:
                    continue
                seen.add(rec_id)
                rec: dict[str, Any] = {
                    "id": rec_id,
                    "fecha_concesion": _fecha_from_lastmod(html),
                    "tipo": "trámite / información licencias",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Sin tablón público de concesiones; memoria y formularios del servicio",
                }
                if pdfs:
                    rec["pdf_url"] = pdfs[0]
                    if len(pdfs) > 1:
                        rec["pdf_urls"] = pdfs[:20]
                rows.append(rec)

        try:
            lic_html = self._fetch(LICENCIA_PAGES[0])
        except urllib.error.URLError:
            lic_html = ""
        for pdf in self._extract_pdfs(lic_html):
            if "licenc" not in pdf.lower():
                continue
            rec_id = _stable_id("lic", pdf)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": _fecha_from_path(pdf),
                    "tipo": "memoria servicio licencias",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": Path(urllib.parse.urlparse(pdf).path).name,
                    "url": pdf,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
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
        rows = self._collect_licencias_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "licencias_info"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_pages():
            if rec["id"] not in existing:
                added += 1
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
        rows = self._crawl_seeds()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "joomla_planeamiento"}

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
