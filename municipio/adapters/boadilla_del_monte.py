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

WP_BASE = "https://www.ayuntamientoboadilladelmonte.org"
SEDE_BASE = "https://carpetaciudadano.aytoboadilla.org/eAdmin"
MUNICIPIO = "Boadilla del Monte"
ID_PREFIX = "boadilla-del-monte"

TABLON_LIST = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/informacion-general-de-urbanismo",
    f"{WP_BASE}/plan-general-de-ordenacion-urbana-2015",
    f"{WP_BASE}/planeamiento-de-desarrollo-del-pgou",
    f"{WP_BASE}/gestion-urbanistica",
    (
        f"{WP_BASE}/informacion-publica-peri-del-suelo-urbano-consolidado-ad-5-"
        "dotacional-monteprincipe"
    ),
    f"{WP_BASE}/convenios-vigentes",
    f"{WP_BASE}/sentencias-sobre-el-nuevo-plan-general-de-ordenacion-urbana",
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{WP_BASE}/licencias-obras",
    f"{WP_BASE}/licencias-urbanisticas-documentacion",
    f"{WP_BASE}/licencias-actividades-e-industria",
]

TABLON_SEARCH_TERMS = (
    "licencia",
    "obra",
    "urbanismo",
    "edicto",
    "plan",
    "convenio",
    "informacion publica",
    "reparcelacion",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|edicto.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|edicto|reparcel|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva|provisional)|peri|"
    r"bocm|memoria|planos|suelo|segregaci|dotacional|monteprincipe)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_BOCM = re.compile(r"bocm[-_]?(\d{4})(\d{2})(\d{2})", re.I)
RE_FECHA_YM = re.compile(r"/(\d{4})[-_](\d{2})/")
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?ayuntamientoboadilladelmonte\.org)?'
    r"/sites/default/files/[^\"]+\.pdf[^\"]*)\"",
    re.I,
)
RE_URBAN_PATH = re.compile(
    r"(?i)(informacion-publica|planeamiento|pgou|urbanismo|convenio|licencia|peri|gestion-urban)",
)
SKIP_PDF = re.compile(r"(?i)(rutas_por_el_monte|favicon)")


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
    name = Path(urllib.parse.unquote(url.split("?")[0])).name
    m = RE_FECHA_BOCM.search(name)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x) for x in re.findall(r"\b(20\d{2})\b", name) if 2010 <= int(x) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r'<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>([^<]+)',
        r"<h1[^>]*>([^<]+)",
        r"<title>([^<]+)",
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3 and "Menú" not in t:
                return t[:500]
    return fallback


class BoadillaDelMonteAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal urbanismo + tablón digital sede (carpetaciudadano)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self.search_terms = list(self.config.get("tablon_search_terms") or TABLON_SEARCH_TERMS)
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 40))

    def _fetch(self, url: str, post: dict[str, str] | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-boadilla/1.0")}
        if post:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            data = urllib.parse.urlencode(post).encode()
            req = urllib.request.Request(url, data=data, headers=headers)
        else:
            req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{WP_BASE}/", href)

    def _extract_pdfs(self, html: str) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_wp(m.group(1))
            if SKIP_PDF.search(u):
                continue
            out.append(u.split("#")[0])
        return list(dict.fromkeys(out))

    def _discover_urban_paths(self, html: str) -> list[str]:
        paths: list[str] = []
        for m in re.finditer(r'href="(/[^"#?]+)"', html):
            p = m.group(1)
            if RE_URBAN_PATH.search(p) and p not in paths:
                paths.append(p)
        return paths

    def _parse_tablon_rows(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in re.findall(r"<tr>\s*<td[^>]*>(.*?)</tr>", html, re.S | re.I):
            if "verAnuncio" not in row:
                continue
            id_m = re.search(r"verAnuncio&id=([A-F0-9]+)", row)
            title_m = re.search(r'width="40%"[^>]*>\s*(.*?)\s*<br>', row, re.S)
            period_m = re.search(
                r"Periodo:</span>\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})",
                row,
            )
            if not id_m or not title_m:
                continue
            ann_id = id_m.group(1)
            if ann_id in seen:
                continue
            seen.add(ann_id)
            title = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", title_m.group(1)))).strip()
            url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rows.append(
                {
                    "id": ann_id,
                    "titulo": title[:500],
                    "url": url,
                    "fecha_inicio": _parse_fecha_dmy(period_m.group(1)) if period_m else None,
                    "fecha_fin": _parse_fecha_dmy(period_m.group(2)) if period_m else None,
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        sources = [None, *[{ "referenciaBusqueda": t} for t in self.search_terms]]
        for post in sources:
            try:
                html = self._fetch(TABLON_LIST, post=post)
            except urllib.error.URLError:
                continue
            for row in self._parse_tablon_rows(html):
                by_id[row["id"]] = row
        return list(by_id.values())

    def _crawl_portal_pages(self) -> list[tuple[str, str, list[str]]]:
        """Returns (page_url, page_title, pdfs)."""
        visited: set[str] = set()
        queue = list(self.seed_pages)
        results: list[tuple[str, str, list[str]]] = []

        while queue and len(visited) < self.max_crawl_pages:
            page_url = queue.pop(0).rstrip("/")
            if page_url in visited:
                continue
            visited.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title = _page_title(html, page_url.rsplit("/", 1)[-1].replace("-", " "))
            pdfs = self._extract_pdfs(html)
            results.append((page_url, title, pdfs))
            if len(visited) < self.max_crawl_pages:
                for path in self._discover_urban_paths(html):
                    link = self._abs_wp(path).rstrip("/")
                    if link not in visited and link not in queue:
                        queue.append(link)
        return results

    def _pdf_to_proyecto(
        self,
        pdf_url: str,
        page_url: str,
        page_title: str,
        default_tipo: str = "documento urbanismo",
    ) -> dict[str, Any] | None:
        name = unescape(urllib.parse.unquote(Path(pdf_url).name))
        blob = f"{name} {page_title} {page_url}"
        if not RE_PROYECTO.search(blob):
            return None
        tipo = default_tipo
        if re.search(r"(?i)convenio", blob):
            tipo = "convenio urbanístico"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|peri", blob):
            tipo = "información pública"
        elif re.search(r"(?i)estudio de detalle", blob):
            tipo = "estudio de detalle"
        elif re.search(r"(?i)pgou|plan general", blob):
            tipo = "PGOU"
        elif re.search(r"(?i)bocm", blob):
            tipo = "publicación BOCM"
        titulo = name[:500] if len(name) > 8 else f"{page_title}: {name}"[:500]
        return {
            "id": _stable_id("proy", pdf_url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": _fecha_from_pdf_url(pdf_url),
            "tipo": tipo,
            "url": page_url,
            "pdf_url": pdf_url,
            "source": "ayuntamiento",
            "origen": page_url,
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title = row["titulo"]
        if not RE_LICENCIA.search(title):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha_inicio"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "url": row["url"],
            "source": "ayuntamiento",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title = row["titulo"]
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        tipo = "urbanismo"
        if re.search(r"(?i)edicto", title):
            tipo = "edicto"
        elif re.search(r"(?i)convenio", title):
            tipo = "convenio"
        elif re.search(r"(?i)plan", title):
            tipo = "planeamiento"
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": row.get("fecha_inicio"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title = _page_title(html, page_url.rsplit("/", 1)[-1].replace("-", " "))
            if not RE_LICENCIA.search(title):
                continue
            pdfs = self._extract_pdfs(html)
            rec: dict[str, Any] = {
                "id": _stable_id("lic", page_url),
                "fecha_concesion": None,
                "tipo": "trámite licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": page_url,
                "source": "ayuntamiento",
                "nota": "Página informativa de trámites; no concesión publicada en tablón",
            }
            if pdfs:
                rec["pdf_url"] = pdfs[0]
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_tablon():
            rec = self._tablon_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_tablon"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencia_tramites():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        for row in self._collect_tablon():
            rec = self._tablon_to_licencia(row)
            if rec and rec["id"] not in existing:
                added += 1
            if rec:
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        portal_pages = self._crawl_portal_pages()
        tablon_items = self._collect_tablon()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for page_url, page_title, pdfs in portal_pages:
            if RE_PROYECTO.search(f"{page_title} {page_url}"):
                add(
                    {
                        "id": _stable_id("proy", page_url),
                        "municipio": MUNICIPIO,
                        "titulo": page_title[:500],
                        "fecha": None,
                        "tipo": "información pública" if "informacion-publica" in page_url else "urbanismo",
                        "url": page_url,
                        "source": "ayuntamiento",
                        "origen": page_url,
                        **({"pdf_url": pdfs[0]} if pdfs else {}),
                    }
                )
            for pdf in pdfs:
                add(self._pdf_to_proyecto(pdf, page_url, page_title))

        for row in tablon_items:
            add(self._tablon_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "portal_pages": len(portal_pages),
            "tablon_items": len(tablon_items),
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
