from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records

import hashlib
import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid
from municipio.http import PortalReadError, read_response

WEB_BASE = "https://www.ceuta.es/ceuta"
SEDE_BASE = "https://sede.ceuta.es"
MUNICIPIO = "Ceuta"
ID_PREFIX = "ceuta"
PGOU_TOMO3_URL = f"{WEB_BASE}/la-institucion/normativa/152-paginas/paginas/pgou/paginas/4863-tomo-3-2023"
SIU_SECTORES = "https://mapas.fomento.gob.es/arcgis/rest/services/SIU/%C3%81mbitos_o_Sectores/MapServer/0/query"
SIU_PREFIX = "GIS_SIU.SIU.SECTORES_WM."
PORTAL_FAILURES = (urllib.error.URLError, TimeoutError, PortalReadError)

TRAMITE_URL = (
    f"{SEDE_BASE}/controlador/controlador?cmd=tramite&modulo=tramites&tramite={{code}}"
)

DEFAULT_PGOU_PAGES: list[str] = [
    f"{WEB_BASE}/trpgouce",
    f"{WEB_BASE}/por-servicios/sede-electronica/152-paginas/paginas/pgou/paginas",
    PGOU_TOMO3_URL,
]

BOCCE_MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")

DEFAULT_TRAMITES: list[tuple[str, str]] = [
    ("OMAY", "licencia"),
    ("LOM", "licencia"),
    ("SLDPO", "licencia"),
    ("SPE", "proyecto"),
    ("SAMCI", "proyecto"),
    ("SADCD", "proyecto"),
    ("SGBB", "proyecto"),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|primera ocupaci[oó]n|"
    r"c[eé]dula urban|demolici[oó]n|segregaci[oó]n|parcelaci[oó]n|calificaci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio|memoria|planos?|aprobaci[oó]n|revisi[oó]n|bocce|instrumento|"
    r"ordenaci[oó]n|suelo|ruina|sector|normas urban|ape_|apr_|pepch_|sup_|"
    r"cambio de uso|complejo inmobiliario|descalificaci)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(proceso selectivo|empleo p[uú]blico|punto limpio|ordenanza fiscal|"
    r"padrones?|impuesto sobre|subvenci[oó]n deportiv|becas?|oposici[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_JDOWNLOAD = re.compile(
    r'href=["\']([^"\']*component/jdownloads/(?:finish|summary|download|viewfile)/[^"\']+)["\']',
    re.I,
)
RE_LINK_TEXT = re.compile(
    r'href=["\']([^"\']+)["\'][^>]*>([^<]{3,200})</a>',
    re.I,
)
RE_H1 = re.compile(r"<h1[^>]*>\s*([^<]+)", re.I)
RE_PAGE_TITLE = re.compile(r"<title>\s*([^<|]+)", re.I)
RE_INSTRUMENT_CODE = re.compile(
    r"\b((?:APE|APR|PEPCH|SUP)_[0-9]{2}_[0-9]{2,3})\b",
    re.I,
)
RE_BOCCE_ITEM = re.compile(
    r"(?m)^[ \t]*(?:(?:ORDINARIO|E?EXTRAORDINARIO)[ \t]+)?(\d+)\s*\.\s*[-\u00ad\u2010-\u2014][ \t]*"
)
RE_BOCCE_PAGE = re.compile(r"\bP[áa]g\.?\s*\d+", re.I)
RE_BOCCE_CATEGORY = re.compile(r'href=["\']([^"\']*/viewcategory/\d+-([a-z0-9]+)(?:\?[^"\']*)?)["\']', re.I)
RE_BOCCE_PLANNING = re.compile(
    r"(?i)planeamiento|plan (?:parcial|especial|general)|PGOU|urban[ií]stic|"
    r"reparcel|ordenaci[oó]n urbana|suelo (?:urbano|urbanizable)|estudio de detalle|"
    r"proyecto de (?:urbanizaci[oó]n|edificaci[oó]n)"
)
RE_BOCCE_FILE = re.compile(
    r'href=["\']([^"\']*component/jdownloads/finish/[^"\']*bocce[^"\']*)["\']',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", t).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                continue
    return None


def _fecha_from_text(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return None  # No observed full date; preserve unknown precision.
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if re.search(r"\bape_", b):
        return "área planeamiento específico"
    if re.search(r"\bapr_", b):
        return "área planeamiento remitido"
    if re.search(r"\bpepch_", b):
        return "plan especial protección conjunto histórico"
    if re.search(r"\bsup_", b):
        return "suelo urbanizable programado"
    if "plan especial" in b:
        return "plan especial"
    if "plan parcial" in b:
        return "plan parcial"
    if "bocce" in b or "decreto" in b and "urban" in b:
        return "disposición urbanística"
    if "cambio de uso" in b:
        return "cambio de uso"
    if "complejo inmobiliario" in b:
        return "complejo inmobiliario"
    return "urbanismo"


class CeutaAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal ceuta.es (Joomla/jDownloads) + sede controlador + BOCCE."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.pgou_pages = [str(u) for u in (self.config.get("pgou_pages") or DEFAULT_PGOU_PAGES)]
        self.bocce_categories = [str(u) for u in self.config.get("bocce_categories", [])]
        raw_tram = self.config.get("tramites") or DEFAULT_TRAMITES
        self.tramites: list[tuple[str, str]] = [
            (str(a), str(b)) for a, b in raw_tram
        ]
        self.bocce_max_issues = int(self.config.get("bocce_max_issues", 6))
        self._cache_dir: Path | None = None
        cache = self.config.get("http_cache_dir")
        if cache:
            self._cache_dir = Path(str(cache))

    def _cache_path(self, url: str) -> Path | None:
        if not self._cache_dir:
            return None
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        return self._cache_dir / f"{key}.html"

    def _fetch(self, url: str, timeout: int = 22) -> str:
        cached = self._cache_path(url)
        if cached and cached.is_file():
            return cached.read_text(encoding="utf-8", errors="replace")

        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ceuta/1.0")},
        )
        raw, _ = read_response(req, timeout=timeout, attempts=2)

        for enc in ("utf-8", "latin-1", "iso-8859-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
        if cached:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(text, encoding="utf-8")
        return text

    def _recent_bocce_categories(self) -> list[str]:
        archive = f"{self.web_base}/bocce"
        years = {slug: self._abs_url(href, archive) for href, slug in RE_BOCCE_CATEGORY.findall(self._fetch(archive))}
        now = datetime.now(timezone.utc)
        dates = [now, now.replace(day=1) - timedelta(days=1)]
        months = {}
        categories = []
        for date in dates:
            if date.year not in months:
                year_url = years.get(str(date.year))
                if not year_url:
                    continue
                months[date.year] = {slug: self._abs_url(href, year_url)
                                     for href, slug in RE_BOCCE_CATEGORY.findall(self._fetch(year_url))}
            month = months[date.year].get(BOCCE_MONTHS[date.month - 1])
            if month:
                categories.append(month)
        if not categories:
            raise RuntimeError(f"BOCCE: no recent month categories found at {archive}")
        return categories

    def _bocce_summary(self, url: str) -> str:
        req = urllib.request.Request(
            url, headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ceuta/1.0")},
        )
        raw, _ = read_response(req, timeout=22, attempts=2)
        if raw.startswith(b"%PDF-"):
            return subprocess.run(
                ["pdftotext", "-layout", "-f", "1", "-l", "4", "-", "-"],
                input=raw, capture_output=True, check=True, timeout=25,
            ).stdout.decode("utf-8")
        html = raw.decode("utf-8", errors="replace")
        text = re.sub(r"</(?:p|li|div|tr)>|<br\s*/?>", "\n", html, flags=re.I)
        return unescape(re.sub(r"<[^>]+>", "", text))

    def _abs_url(self, href: str, page_url: str) -> str:
        return unescape(urllib.parse.urljoin(page_url, href))

    def _tramite_url(self, code: str) -> str:
        return TRAMITE_URL.format(code=code)

    def _page_heading(self, html: str, fallback: str) -> str:
        for pat in (RE_H1, RE_PAGE_TITLE):
            m = pat.search(html)
            if m:
                t = _clean_title(m.group(1))
                t = re.sub(r"^Ciudad Autónoma de Ceuta\s*-?\s*", "", t, flags=re.I).strip()
                t = re.sub(r"^Sede Electrónica.*Trámites\s*", "", t, flags=re.I).strip()
                if t and t.lower() not in {"trámites", "documentos"}:
                    return t[:200]
        return fallback

    def _collect_pgou_documents(self, unavailable: list[dict[str, str]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(title: str, url: str, pdf_url: str | None, fecha: str | None) -> None:
            key = pdf_url or url + title
            if key in seen:
                return
            seen.add(key)
            items.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": url,
                    "pdf_url": pdf_url,
                    "origen": "pgou_jdownloads",
                }
            )

        for page_url in self.pgou_pages:
            try:
                html = self._fetch(page_url, timeout=12)
            except PORTAL_FAILURES as exc:
                unavailable.append({"source": "pgou", "url": page_url, "error": str(exc)})
                continue
            page_title = self._page_heading(html, "PGOU Ceuta")
            fecha_page = _fecha_from_text(html) or None
            for href in RE_JDOWNLOAD.findall(html):
                pdf_url = self._abs_url(href, page_url)
                title = unescape(Path(urllib.parse.urlparse(pdf_url).path).name.replace("-", " "))
                for link_href, link_text in RE_LINK_TEXT.findall(html):
                    if href in link_href or urllib.parse.unquote(href) in link_href:
                        title = _clean_title(link_text) or title
                        break
                if not title or len(title) < 3:
                    title = page_title
                add(title, page_url, pdf_url, _fecha_from_text(title) or fecha_page)

            for code in RE_INSTRUMENT_CODE.findall(html):
                add(
                    f"PGOU 2023 — instrumento {code.upper()}",
                    page_url,
                    None,
                    fecha_page,
                )

            if RE_PROYECTO.search(page_title) and "pgou" in page_title.lower():
                add(
                    "Revisión y Adaptación PGOU Ceuta 2023 (página oficial)",
                    page_url,
                    None,
                    None,
                )

        return items

    def _collect_siu_sectors(self) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode({
            "where": f"{SIU_PREFIX}ProvINE='51001' AND {SIU_PREFIX}FechaBaja='99999999'",
            "f": "geojson", "outFields": "*", "returnGeometry": "true", "outSR": 4326,
            "resultRecordCount": 100,
        })
        url = f"{SIU_SECTORES}?{params}"
        data = json.loads(self._fetch(url, timeout=15))
        features = data.get("features")
        if data.get("type") != "FeatureCollection" or not isinstance(features, list) or not 0 < len(features) < 100:
            raise ValueError("SIU returned no usable complete Ceuta sector collection")
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for feature in features:
            props, geom = feature["properties"], feature["geometry"]
            code = str(props.get(f"{SIU_PREFIX}IdSector") or "").removeprefix("51001")
            if (props.get(f"{SIU_PREFIX}ProvINE") != "51001" or code in seen
                    or not RE_INSTRUMENT_CODE.fullmatch(code)):
                raise ValueError(f"Unexpected Ceuta sector identity from SIU: {code}")
            if not isinstance(geom, dict) or geom.get("type") not in {"Polygon", "MultiPolygon"}:
                raise ValueError(f"Missing SIU sector polygon for Ceuta {code}")
            seen.add(code)
            # Tomo 3 keys are also used by the municipal scraper for these planning codes.
            title = f"PGOU 2023 — instrumento {code}"
            row = self._to_proyecto(title, PGOU_TOMO3_URL, None, origen="siu_sectores")
            row.update({
                "geom_geojson": geom, "geometry_crs": "EPSG:4326", "geometry_source": "portal_wfs",
                "geometry_source_url": url, "coord_source": "portal_geometry_centroid",
            })
            center = geometry_centroid(geom)
            if center:
                row["lat"], row["lon"] = center
            rows.append(row)
        return rows

    def _collect_bocce(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        issue_urls: list[str] = []
        seen_issues: set[str] = set()

        for cat_url in self.bocce_categories or self._recent_bocce_categories():
            for href in RE_BOCCE_FILE.findall(self._fetch(cat_url)):
                full = self._abs_url(href, cat_url)
                key = urllib.parse.urlsplit(full).path
                if key not in seen_issues:
                    seen_issues.add(key)
                    issue_urls.append(full)

        issue_urls.sort(key=lambda url: _fecha_from_text(url) or "", reverse=True)
        if not issue_urls:
            raise RuntimeError("BOCCE: no issues found in recent categories")
        for issue_url in issue_urls[: self.bocce_max_issues]:
            plain = self._bocce_summary(issue_url)
            fecha = _fecha_from_text(issue_url) or _fecha_from_text(plain)
            starts = list(RE_BOCCE_ITEM.finditer(plain))
            seen_articles = set()
            for index, match in enumerate(starts):
                num = match.group(1)
                stop = starts[index + 1].start() if index + 1 < len(starts) else len(plain)
                body = plain[match.end():stop].split("\f", 1)[0]
                page = RE_BOCCE_PAGE.search(body)
                if not page or num in seen_articles:
                    continue
                seen_articles.add(num)
                blob = f"{num}.- {_clean_title(body[:page.start()])}"
                if RE_EXCLUDE.search(blob):
                    continue
                if not RE_BOCCE_PLANNING.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                items.append(
                    {
                        "titulo": blob[:500],
                        "fecha": fecha,
                        "url": issue_url,
                        "pdf_url": issue_url,
                        "origen": "bocce",
                    }
                )
        return items

    def _available_bocce(self, unavailable: list[dict[str, str]]) -> list[dict[str, Any]]:
        try:
            return self._collect_bocce()
        except PORTAL_FAILURES as exc:
            unavailable.append({"source": "bocce", "url": f"{self.web_base}/bocce", "error": str(exc)})
            return []

    def _collect_tramites(self, unavailable: list[dict[str, str]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for code, kind_hint in self.tramites:
            url = self._tramite_url(code)
            try:
                html = self._fetch(url, timeout=12)
            except urllib.error.URLError:
                continue
            except (TimeoutError, PortalReadError) as exc:
                unavailable.append({"source": "sede_tramites", "url": url, "error": str(exc)})
                break
            title = self._page_heading(html, code)
            rows.append(
                {
                    "titulo": title,
                    "url": url,
                    "code": code,
                    "kind_hint": kind_hint,
                    "origen": "sede_tramite",
                }
            )
        return rows

    @staticmethod
    def _coverage(unavailable: list[dict[str, str]]) -> dict[str, Any]:
        if not unavailable:
            return {"status": "ok"}
        sources = dict.fromkeys(item["source"] for item in unavailable)
        return {
            "status": "partial", "reason": f"ceuta_sources_unavailable: {', '.join(sources)}",
            "unavailable_sources": unavailable,
        }

    def _to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("titulo") or ""
        if item.get("kind_hint") != "licencia" and not RE_LICENCIA.search(blob):
            return None
        if RE_EXCLUDE.search(blob):
            return None
        return {
            "id": _stable_id("lic", item["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": blob[:500],
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _to_proyecto(
        self,
        title: str,
        url: str,
        fecha: str | None,
        pdf_url: str | None = None,
        origen: str | None = None,
    ) -> dict[str, Any] | None:
        blob = title or ""
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", (pdf_url or url) + title),
            "municipio": MUNICIPIO,
            "titulo": blob[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
        if origen:
            rec["origen"] = origen
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
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

    def _collect_licencias(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        unavailable: list[dict[str, str]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tramites(unavailable):
            if item.get("kind_hint") == "licencia":
                add(self._to_licencia(item))
        for item in self._available_bocce(unavailable):
            blob = item["titulo"]
            if RE_LICENCIA.search(blob):
                add(
                    {
                        "id": _stable_id("lic", item["url"] + blob[:80]),
                        "fecha_concesion": None,
                        "fecha_publicacion": item.get("fecha"),
                        "tipo": "licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": blob[:500],
                        "url": item["url"],
                        "source": "ayuntamiento",
                        "origen": "bocce",
                    }
                )

        return rows, self._coverage(unavailable)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows, coverage = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            **coverage,
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
            "bocce": sum(1 for r in rows if r.get("origen") == "bocce"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows, coverage = self._collect_licencias()
        return self._update_rows(out_jsonl, state_path, rows, coverage)

    def _collect_proyectos(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        unavailable: list[dict[str, str]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for doc in self._collect_pgou_documents(unavailable):
            add(
                self._to_proyecto(
                    doc["titulo"],
                    doc["url"],
                    doc.get("fecha"),
                    pdf_url=doc.get("pdf_url"),
                    origen=doc.get("origen"),
                )
            )

        for item in self._available_bocce(unavailable):
            add(
                self._to_proyecto(
                    item["titulo"],
                    item["url"],
                    item.get("fecha"),
                    pdf_url=item.get("pdf_url"),
                    origen=item.get("origen"),
                )
            )

        if unavailable and not rows:
            for row in self._collect_siu_sectors():
                add(row)

        for item in self._collect_tramites(unavailable):
            if item.get("kind_hint") == "proyecto":
                add(
                    self._to_proyecto(
                        item["titulo"],
                        item["url"],
                        None,
                        origen=item.get("origen"),
                    )
                )

        return rows, self._coverage(unavailable)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows, coverage = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            **coverage,
            "pgou": sum(1 for r in rows if r.get("origen") == "pgou_jdownloads"),
            "bocce": sum(1 for r in rows if r.get("origen") == "bocce"),
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows, coverage = self._collect_proyectos()
        return self._update_rows(out_jsonl, state_path, rows, coverage)

    def _update_rows(
        self, out_jsonl: Path, state_path: Path, rows: list[dict[str, Any]], coverage: dict[str, Any],
    ) -> dict[str, Any]:
        existing = self._load_jsonl(out_jsonl)
        if coverage["status"] == "partial":
            by_id = {row["id"]: row for row in existing}
            for row in rows:
                previous = by_id.setdefault(row["id"], {})
                previous.update({key: value for key, value in row.items() if value is not None})
            rows = list(by_id.values())
        self._write_jsonl(out_jsonl, rows)
        result = {"rows": len(rows), "added": max(0, len(rows) - len(existing)), **coverage}
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    **result,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return result
