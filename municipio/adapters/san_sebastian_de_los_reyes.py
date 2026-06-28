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
from urllib.parse import unquote, urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import record_geometry

BASE = "https://www.ssreyes.org"
SEDE_BASE = "https://sede.ssreyes.es"
MUNICIPIO = "San Sebastián de los Reyes"
ID_PREFIX = "san-sebastian-de-los-reyes"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/plan-general-de-ordenaci%C3%B3n-urbana-p.g.o.u.-",
    f"{BASE}/planos",
    f"{BASE}/desarrollos-urban%C3%ADsticos-mediante-plan-parcial",
    f"{BASE}/plan-especial-de-la-marina",
    f"{BASE}/plan-especial-de-reforma-interior-p.e.r.i.-",
    f"{BASE}/planes-especiales",
    f"{BASE}/desarrollo-urbano",
    f"{BASE}/urbanismo-obras-e-infraestructuras",
    f"{BASE}/sistema-de-informaci%C3%B3n-territorial-de-urbanismo",
    (
        f"{BASE}/tr%C3%A1mites1/-/asset_publisher/ag3ZJ41Ir8vd/content/id/2613627"
    ),
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    (
        f"{BASE}/tr%C3%A1mites1/-/asset_publisher/ag3ZJ41Ir8vd/content/id/2613627"
    ),
    f"{SEDE_BASE}/tr%C3%A1mites",
]

GEOM_HINTS: list[tuple[str, str]] = [
    ("tempranales", "Tempranales"),
    ("fresno-norte", "Fresno"),
    ("fresno norte", "Fresno"),
    ("pilar-de-abajo", "Pilar"),
    ("pilar de abajo", "Pilar"),
    ("puente-cultural", "Puente"),
    ("puente cultural", "Puente"),
    ("cerro del baile", "Cerro"),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|autoliquidaci[oó]n.*urban|"
    r"\blota\b|licencia urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|peri|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|aprobaci[oó]n|"
    r"desarrollo|tempranales|fresno|marina|cementerio|ordenaci[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DOC_LINK = re.compile(r'href="(/documents/[^"]+)"', re.I)
RE_URBAN_LINK = re.compile(
    r'href="(https://www\.ssreyes\.org/(?:plan|desarrollo|urban|temprana|fresno|pilar|puente|peri|marina|cerro|pgou|planeam)[^"#?]*)"',
    re.I,
)
RE_PAGE_TITLE = re.compile(
    r"<h2[^>]*>\s*([^<]+?)\s*</h2>|<title>([^<]+)",
    re.I,
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


def _iso_from_year(text: str) -> str | None:
    years = [
        int(m.group(1))
        for m in RE_YEAR.finditer(text or "")
        if 1980 <= int(m.group(1)) <= 2030
    ]
    if not years:
        return None
    return f"{max(years)}-01-01"


def _fecha_from_url(url: str) -> str | None:
    m = re.search(r"[?&]t=(\d{13})", url)
    if m:
        try:
            ts = int(m.group(1)) / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass
    return _iso_from_year(unquote(Path(url).name))


def _title_from_pdf_url(url: str) -> str:
    path = unquote(url.split("?")[0])
    parts = [p for p in path.split("/") if p and not re.fullmatch(r"[0-9a-f-]{36}", p, re.I)]
    for part in reversed(parts):
        if part.lower().endswith(".pdf"):
            name = re.sub(r"\.pdf$", "", part, flags=re.I)
            name = re.sub(r"^\d+\.\s*", "", name)
            if len(name) > 4 and not re.fullmatch(r"[0-9a-f-]{36}", name, re.I):
                return name.replace("+", " ").strip()[:500]
    name = Path(path).name
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    return name.replace("+", " ").strip()[:500]


def _page_title(html: str, fallback: str = "") -> str:
    for m in RE_PAGE_TITLE.finditer(html):
        t = unescape((m.group(1) or m.group(2) or "").strip())
        t = re.sub(r"\s*[-|].*ssreyes.*$", "", t, flags=re.I).strip()
        if t and len(t) > 3 and "verificando" not in t.lower():
            return t[:500]
    return fallback


def _tipo_proyecto(title: str, page_url: str = "") -> str:
    blob = f"{title} {page_url}".lower()
    if "estudio" in blob and "detalle" in blob:
        return "estudio de detalle"
    if "plan parcial" in blob or "tempranales" in blob or "fresno" in blob:
        return "plan parcial"
    if "plan especial" in blob or "peri" in blob or "marina" in blob:
        return "plan especial"
    if "pgou" in blob or "ordenaci" in blob:
        return "PGOU"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "convenio" in blob:
        return "convenio"
    return "documento urbanismo"


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for feat in features:
        geom = feat.get("geometry")
        if not isinstance(geom, dict):
            continue
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif gtype == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class SanSebastianDeLosReyesAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay ssreyes.org: planeamiento PDFs + trámites licencia; geometría WFS CM SIT."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.browser_cookie = str(self.config.get("browser_cookie", "browser_verified=1"))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 35))
        self._geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get(
                    "user_agent", "poc-bocm-san-sebastian-de-los-reyes/1.0"
                ),
                "Cookie": self.browser_cookie,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-ES,es;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, page: str = BASE) -> str:
        return urljoin(page, href)

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

    def _discover_urban_links(self, html: str) -> list[str]:
        links: list[str] = []
        for href in RE_URBAN_LINK.finditer(html):
            url = href.group(1).rstrip("/")
            if url not in links and "ssreyes.org" in url:
                links.append(url)
        return links

    def _extract_page_docs(self, html: str, page_url: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        seen: set[str] = set()
        for m in RE_DOC_LINK.finditer(html):
            href = m.group(1)
            link = self._abs_url(href, page_url)
            key = link.split("?")[0]
            if key in seen:
                continue
            seen.add(key)
            idx = m.start()
            ctx = unescape(re.sub(r"<[^>]+>", " ", html[max(0, idx - 500) : idx + 120]))
            ctx = re.sub(r"\s+", " ", ctx).strip()
            title = _title_from_pdf_url(link)
            link_m = re.search(
                r"((?:Plan|Aprobaci[oó]n|Memoria|Normativa|Documento)[^.]{8,180})",
                ctx,
                re.I,
            )
            if link_m:
                title = link_m.group(1).strip()[:500]
            elif len(ctx) > 20:
                tail = ctx[-120:].strip()
                if len(tail) > 8 and not tail.lower().startswith("href"):
                    title = tail[:500]
            out.append((title, link))
        return out

    def _wfs_query(self, name_hint: str, max_features: int = 25) -> dict[str, Any] | None:
        if name_hint in self._geom_cache:
            cached = self._geom_cache[name_hint]
            return cached.copy() if cached else None
        esc = name_hint.replace("'", "''")
        cql = f"DS_MUNICIPIO ILIKE '%San Sebasti%' AND DS_NOMB_AMB ILIKE '%{esc}%'"
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": WFS_TYPE,
            "outputFormat": "application/json",
            "count": str(max_features),
            "CQL_FILTER": cql,
        }
        url = f"{WFS_BASE}?{urllib.parse.urlencode(params)}"
        try:
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.config.get(
                        "user_agent", "poc-bocm-san-sebastian-de-los-reyes/1.0"
                    )
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            self._geom_cache[name_hint] = None
            return None
        geom = _merge_geometries(data.get("features") or [])
        if not geom:
            self._geom_cache[name_hint] = None
            return None
        result = {
            "geom_geojson": geom,
            "geometry_source": "cm_sit_wfs",
            "geometry_source_url": url,
            "coord_source": "portal_geometry_centroid",
        }
        self._geom_cache[name_hint] = result
        return result.copy()

    def _fetch_geometry(self, title: str, page_url: str) -> dict[str, Any]:
        blob = f"{title} {page_url}".lower()
        for needle, wfs_hint in GEOM_HINTS:
            if needle in blob:
                geom = self._wfs_query(wfs_hint)
                if geom:
                    return geom
        return {}

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        extra = self._fetch_geometry(
            str(rec.get("titulo") or ""),
            str(rec.get("url") or rec.get("origen") or ""),
        )
        rec.update(extra)

    def _crawl_planeamiento(self) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue = list(self.seed_pages)
        rows: list[dict[str, Any]] = []
        seen_docs: set[str] = set()
        seen_pages: set[str] = set()

        while queue and len(visited) < self.max_crawl_pages:
            page_url = queue.pop(0).rstrip("/")
            if page_url in visited:
                continue
            visited.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            page_title = _page_title(html, "")
            if page_title and RE_PROYECTO.search(page_title) and page_url not in seen_pages:
                seen_pages.add(page_url)
                rec = {
                    "id": _stable_id("proy", page_url),
                    "municipio": MUNICIPIO,
                    "titulo": page_title,
                    "fecha": _iso_from_year(page_title),
                    "tipo": _tipo_proyecto(page_title, page_url),
                    "url": page_url,
                    "source": "ayuntamiento",
                    "origen": page_url,
                }
                self._attach_geometry(rec)
                rows.append(rec)

            for title, link in self._extract_page_docs(html, page_url):
                key = link.split("?")[0]
                if key in seen_docs:
                    continue
                seen_docs.add(key)
                blob = f"{title} {link} {page_title}"
                if not RE_PROYECTO.search(blob):
                    continue
                rec = {
                    "id": _stable_id("proy", link),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": _parse_fecha_dmy(title) or _fecha_from_url(link) or _iso_from_year(title),
                    "tipo": _tipo_proyecto(title, page_url),
                    "url": page_url,
                    "pdf_url": link,
                    "source": "ayuntamiento",
                    "origen": page_url,
                }
                self._attach_geometry(rec)
                rows.append(rec)

            for link in self._discover_urban_links(html):
                if link.rstrip("/") not in visited and link not in queue:
                    queue.append(link)

        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            page_title = _page_title(html, "")
            if page_title and RE_LICENCIA.search(page_title):
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
                            "nota": "Página informativa de trámites urbanísticos",
                        }
                    )

            for title, link in self._extract_page_docs(html, page_url):
                link_decoded = unquote(link)
                blob = f"{title} {link} {link_decoded}"
                if not RE_LICENCIA.search(blob):
                    continue
                key = link.split("?")[0]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "id": _stable_id("lic", link),
                        "fecha_concesion": _fecha_from_url(link),
                        "tipo": "formulario licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": (title if len(title) > 8 else _title_from_pdf_url(link))[:500],
                        "url": page_url,
                        "pdf_url": link,
                        "source": "ayuntamiento",
                        "nota": "Impreso de trámite; no concesión publicada en tablón",
                    }
                )
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_impresos"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
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
        rows = self._crawl_planeamiento()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "source": "planeamiento_pages",
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
