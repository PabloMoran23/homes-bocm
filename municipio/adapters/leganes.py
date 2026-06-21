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
from municipio.geometry import geometry_centroid

WP_BASE = "https://www.leganes.org"
SEDE_BASE = "https://sede.leganes.org"
MUNICIPIO = "Leganés"
ID_PREFIX = "leganes"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"
TRAMITES_SEDE_URL = f"{SEDE_BASE}/sta/CarpetaPublic/Public?APP_CODE=STA&PAGE_CODE=PTS2_HOME"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/urbanismo-e-industria",
    f"{WP_BASE}/planes-parciales-urbanismo",
    f"{WP_BASE}/planes-especiales",
    f"{WP_BASE}/planeamiento-en-tramitacion",
    f"{WP_BASE}/acuerdo-de-aprobacion-plan-general",
    f"{WP_BASE}/memoria-del-plan-general",
    f"{WP_BASE}/normas-del-plan-general",
    f"{WP_BASE}/planos-del-plan-general",
    f"{WP_BASE}/modificaciones-puntuales-del-pgou",
    f"{WP_BASE}/correccion-de-errores-del-pgou",
    f"{WP_BASE}/plan-de-sectorizacion-autovia-de-toledo-norte",
    f"{WP_BASE}/texto-del-plan-peri-casco-antiguo",
    f"{WP_BASE}/planos-del-plan-peri-casco-antiguo",
    f"{WP_BASE}/plano-del-catalogo-de-edificios-protegidos",
    f"{WP_BASE}/normativa-especifica-planes-parciales-antiguos",
    f"{WP_BASE}/obras-e-infraestructuras",
    f"{WP_BASE}/normativa-obras",
]

RE_DOC_PDF = re.compile(
    r'href="(/documents/\d+/\d+/([^"/?]+\.pdf)/[^"]*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|solicitud de licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan(?:o|es)?\b|pgou|convenio|informaci[oó]n p[uú]blica|"
    r"expediente|edicto|anuncio|bocm|memoria|texto|aprobaci[oó]n|modificaci[oó]n|"
    r"reparcel|estudio|peri\b|pp-|pp_\d|plnesp|saneamiento|cat[aá]logo|notificaci|"
    r"sectorizaci|revisi[oó]n|correcci[oó]n)",
)
RE_PLANO_TECNICO = re.compile(
    r"(?i)^plano\s+\d",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_AMBITO_CODE = re.compile(
    r"(?i)\b(UE-\d+|PP-\d+(?:\s+[A-Z]+)?|PLNESP|PERI|PGOU|PP[_\s-]?\d+)\b",
)

WFS_DEFAULT = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE_DEFAULT = "sitcm:VPLA_V_AMBITO"
WFS_FILTER_DEFAULT = "DS_MUNICIPIO ILIKE '%LEGAN%'"


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
    years = [int(m.group(1)) for m in RE_YEAR.finditer(text or "") if 1980 <= int(m.group(1)) <= 2030]
    if not years:
        return None
    return f"{max(years)}-01-01"


def _fecha_from_pdf_url(url: str) -> str | None:
    m = re.search(r"[?&]t=(\d{13})", url)
    if m:
        try:
            ts = int(m.group(1)) / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass
    return _parse_fecha_dmy(url) or _iso_from_year(url)


def _title_from_pdf_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    parts = [p for p in path.split("/") if p and not re.fullmatch(r"[0-9a-f-]{36}", p, re.I)]
    name = parts[-1] if parts else Path(path).name
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    return name.replace("+", " ").strip()[:500]


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
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _proyecto_tipo(title: str) -> str:
    t = title.lower()
    if "plan parcial" in t or re.search(r"\bpp-\d", t):
        return "plan parcial"
    if "plan especial" in t or "plnesp" in t:
        return "plan especial"
    if "informaci" in t and "p" in t and "blica" in t:
        return "información pública"
    if "anuncio" in t or "edicto" in t or "notificaci" in t:
        return "anuncio"
    if "pgou" in t or "plan general" in t:
        return "planeamiento"
    if "peri" in t:
        return "PERI"
    if "memoria" in t:
        return "memoria"
    if "bocm" in t:
        return "publicación BOCM"
    return "urbanismo"


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        y, mo, d = int(obj["year"]), int(obj["month"]), int(obj["day"])
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


class LeganesAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay urbanismo (documentos PDF) + intento sede STA tablón + WFS IDEM geometría."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_DEFAULT)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE_DEFAULT)
        self.wfs_filter = str(geom_cfg.get("municipio_filter") or WFS_FILTER_DEFAULT)
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-leganes/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or self.sede_base in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{WP_BASE}/", href))

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = ["
        start = html.find(needle)
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _tablon_row_to_record(self, row: dict[str, Any]) -> tuple[str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        fecha = _xml_date(row.get("pubDateIni")) or ""
        dboid = str(row.get("dboid") or title)
        url = f"{TABLON_URL}#dboid={dboid}"
        return title, fecha, url

    def _extract_page_pdfs(self, html: str, page_url: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, _fname in RE_DOC_PDF.findall(html):
            pdf_url = self._abs_url(href)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            titulo = _title_from_pdf_url(pdf_url)
            fecha = _fecha_from_pdf_url(pdf_url) or _iso_from_year(titulo)
            records.append(
                {
                    "titulo": titulo,
                    "fecha": fecha,
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "page_url": page_url,
                }
            )
        return records

    def _is_relevant_proyecto_pdf(self, titulo: str) -> bool:
        if RE_PLANO_TECNICO.match(titulo.strip()):
            return False
        return bool(RE_PROYECTO.search(titulo))

    def _collect_seed_documents(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_name = _page_title(html, page_url.rsplit("/", 1)[-1])
            pdfs = self._extract_page_pdfs(html, page_url)
            relevant = [p for p in pdfs if self._is_relevant_proyecto_pdf(p["titulo"])]
            if relevant:
                items.extend(relevant)
            elif pdfs and RE_PROYECTO.search(page_name):
                items.append(
                    {
                        "titulo": page_name,
                        "fecha": _iso_from_year(page_name),
                        "url": page_url,
                        "pdf_url": pdfs[0]["pdf_url"],
                        "page_url": page_url,
                    }
                )
        return items

    def _fetch_wfs_ambitos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": self.wfs_type,
            "outputFormat": "application/json",
            "count": "500",
            "CQL_FILTER": self.wfs_filter,
        }
        url = self.wfs_url + "?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-leganes/1.0")},
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read())
            self._wfs_cache = data.get("features") or []
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            self._wfs_cache = []
        return self._wfs_cache

    def _match_wfs_geometry(self, title: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        features = self._fetch_wfs_ambitos()
        if not features:
            return None, None
        title_up = title.upper()
        codes = [m.group(1).upper().replace(" ", "-") for m in RE_AMBITO_CODE.finditer(title)]
        best: dict[str, Any] | None = None
        best_score = 0
        for feat in features:
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            if not isinstance(geom, dict):
                continue
            amb = str(props.get("DS_NOMB_AMB") or "").upper()
            fig = str(props.get("DS_FIG_DES") or "").upper()
            score = 0
            for code in codes:
                if code in title_up and (code in amb or code.replace("-", "") in amb.replace("-", "")):
                    score += 3
            if amb and amb in title_up:
                score += 2
            for token in re.split(r"[\s,;/|]+", title_up):
                if len(token) >= 4 and token in amb:
                    score += 1
            if "PLAN PARCIAL" in title_up and "PLAN PARCIAL" in fig:
                score += 1
            if score > best_score:
                best_score = score
                best = feat
        if best_score < 2 or not best:
            return None, None
        return best.get("geometry"), best.get("properties") or {}

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        geom, props = self._match_wfs_geometry(rec.get("titulo") or "")
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = (
            f"{self.wfs_url}?service=WFS&typeNames={self.wfs_type}&CQL_FILTER={urllib.parse.quote(self.wfs_filter)}"
        )
        rec["coord_source"] = "portal_geometry_centroid"
        if props.get("DS_NOMB_AMB"):
            rec["ambito_sit"] = props["DS_NOMB_AMB"]
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _title_to_licencia(self, title: str, url: str, fecha: str | None, pdf_url: str | None = None) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", pdf_url or url),
            "fecha_concesion": fecha,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
        return rec

    def _title_to_proyecto(
        self,
        title: str,
        url: str,
        fecha: str | None,
        pdf_url: str | None = None,
        origen: str | None = None,
    ) -> dict[str, Any] | None:
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", pdf_url or url + title),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(title),
            "url": url,
            "source": "ayuntamiento",
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
        if origen:
            rec["origen"] = origen
        self._enrich_geometry(rec)
        return rec

    def _collect_tramites_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.append(
            {
                "id": _stable_id("lic", TRAMITES_SEDE_URL),
                "fecha_concesion": None,
                "tipo": "trámite licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites y gestiones de urbanismo (Sede Electrónica Leganés)",
                "url": TRAMITES_SEDE_URL,
                "source": "ayuntamiento",
                "nota": "Catálogo sede STA; concesiones no publicadas en web accesible",
            }
        )
        try:
            html = self._fetch(f"{WP_BASE}/urbanismo-e-industria")
        except urllib.error.URLError:
            return rows
        for m in re.finditer(r'href="([^"]+)"[^>]*>([^<]{5,120})</a>', html, re.I):
            href = unescape(m.group(1).replace("&amp;", "&"))
            text = unescape(m.group(2).strip())
            if not RE_LICENCIA.search(text) and "tramit" not in text.lower():
                continue
            url = href if href.startswith("http") else self._abs_url(href)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": text[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Enlace informativo portal municipal",
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            title, fecha, url = self._tablon_row_to_record(item)
            add(self._title_to_licencia(title, url, fecha or None))

        for doc in self._collect_seed_documents():
            add(
                self._title_to_licencia(
                    doc["titulo"],
                    doc["url"],
                    doc.get("fecha"),
                    doc.get("pdf_url"),
                )
            )

        for rec in self._collect_tramites_licencias():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "liferay_y_tramites"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
        after_rows = self._load_jsonl(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(after_rows),
                    "added": max(0, len(after_rows) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(after_rows), "added": max(0, len(after_rows) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            title, fecha, url = self._tablon_row_to_record(item)
            add(self._title_to_proyecto(title, url, fecha or None, origen="sede_tablon"))

        for doc in self._collect_seed_documents():
            add(
                self._title_to_proyecto(
                    doc["titulo"],
                    doc["url"],
                    doc.get("fecha"),
                    doc.get("pdf_url"),
                    origen=doc.get("page_url"),
                )
            )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "seed_pages": len(self.seed_pages),
            "tablon_rows": len(self._collect_tablon()),
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
