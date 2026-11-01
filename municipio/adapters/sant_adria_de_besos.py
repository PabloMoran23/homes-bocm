from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.sant-adria.cat"
SEDE_BASE = "https://seu.sant-adria.net"
SEU_E_URBANISME = (
    "https://seu-e.cat/ca/web/santadriadebesos/tramits-i-gestions/"
    "-/tramits/classificacio/urbanisme"
)
MUNICIPIO = "Sant Adrià de Besòs"
ID_PREFIX = "santadria"
INE_MUN = "08169"

AMB_EXP_LAYER = (
    "https://geoportal.amb.cat/geoserveisapp/rest/services/"
    "Planejament/Expedients/MapServer/3"
)
AMB_SECTORS_LAYER = (
    "https://geoportal.amb.cat/geoserveisapp/rest/services/"
    "Planejament/Sectors/MapServer/0"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/sant-adria-per-temes/territori/urbanisme",
    f"{WEB_BASE}/sant-adria-per-temes/territori/urbanisme/urbanisme",
    f"{WEB_BASE}/sant-adria-per-temes/territori/urbanisme/publicitat-del-planejament-urbanistic",
    (
        f"{WEB_BASE}/sant-adria-per-temes/territori/urbanisme/"
        "tramit-dinformacio-publica-planejament-urbanistic"
    ),
    f"{WEB_BASE}/sant-adria-per-temes/territori/urbanisme/publicitat-dels-convenis-urbanistics",
    (
        f"{WEB_BASE}/sant-adria-per-temes/territori/urbanisme/"
        "planejament-urbanistic-inclou-limitacions-implantacio-noves-activitats"
    ),
    f"{WEB_BASE}/sant-adria-per-temes/territori/convenis",
    f"{WEB_BASE}/sant-adria-per-temes/territori/normativa-municipal",
    SEU_E_URBANISME,
]

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "licència d'obres",
    "licencia de obras",
    "llicència d'obres",
    "comunicació previa",
    "comunicacion previa",
    "declaració responsable",
    "obra menor",
    "obres majors",
    "enderroc",
    "licència urbanística",
    "licencia urbanística",
    "divisió o segregació",
    "urbanisme: informes",
    "urbanisme: certificats",
    "informe urbanístic",
    "certificat urbanístic",
)

RE_LICENCIA = re.compile(
    r"(?i)(licen[cs]i[ao]|llicen[cs]i[ao]|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:major|menor)|enderroc|segregaci)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgm|mpgm|conveni|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n|expedient|reparcel|modificaci[oó]n|"
    r"delimitaci|gesti[oó] urban|sector|àmbit|ambit|verificaci)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|empleo p[uú]blico|subvenci[oó]n|"
    r"terrassa|ocupaci[oó]n del espacio p[uú]blico)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_EXPTE = re.compile(
    r"(?i)(?:exp(?:te)?\.?|expedient|n[uú]mero d.?expedient)\s*[:\.]?\s*"
    r"(\d{1,4}/[A-Z0-9-]+(?:\s+\d{4}/\d+[A-Z]?)?|\d{4}/\d+[A-Z]?)",
)
RE_CARD = re.compile(
    r'card-title[^>]*>\s*<a href="([^"]+)"[^>]*>([^<]+)</a>.*?card-text[^>]*>(.*?)</p>',
    re.I | re.S,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PLONE_LINK = re.compile(
    r'href="((?:https://www\.sant-adria\.cat)?/(?:sant-adria-per-temes/territori|fitxers)/[^"#?]+)"',
    re.I,
)
RE_CONTENT_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "mpgm" in n or "pgm" in n or "pla general metropolit" in n:
        return "modificación PGM"
    if "plan parcial" in n or re.search(r"\bpp\b", n):
        return "plan parcial"
    if "plan especial" in n:
        return "plan especial"
    if "reparcel" in n:
        return "reparcelación"
    if "conveni" in n:
        return "convenio urbanístico"
    if "verificaci" in n:
        return "verificación planeamiento"
    if "delimitaci" in n:
        return "delimitación"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    return "planeamiento"


class SantAdriaDeBesosAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone (urbanisme) + sede STA (catálogo) + seu-e + AMB ArcGIS (geometría expedientes)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.catalogo_url = str(
            self.config.get("catalogo_url")
            or f"{self.sede_base}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_CATSERV&lang=ES"
        )
        geom_cfg = self.config.get("geometry") or {}
        self.amb_exp_layer = str(geom_cfg.get("arcgis_expedients_layer") or AMB_EXP_LAYER)
        self.amb_sectors_layer = str(geom_cfg.get("arcgis_sectors_layer") or AMB_SECTORS_LAYER)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        self._amb_cache: list[dict[str, Any]] | None = None
        self._amb_by_norm_name: dict[str, dict[str, Any]] | None = None

    def _ua(self) -> str:
        return str(self.config.get("user_agent") or "poc-bocm-sant-adria-de-besos/1.0")

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        url = self._quote_url(url)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua()})
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _quote_url(self, url: str) -> str:
        parts = urllib.parse.urlsplit(url)
        path = urllib.parse.quote(parts.path, safe="/%:@+&=")
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

    @staticmethod
    def _is_html_page_url(url: str) -> bool:
        low = url.lower()
        if "/@@download/" in low or low.endswith(".pdf"):
            return False
        return True

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS_CATSERV&lang=ES"
        )

    def _catalog_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            dboid = str(item.get("dboid") or "")
            name = _clean_title(str(item.get("name") or ""))
            if not name or not dboid:
                continue
            rows.append(
                {
                    "titulo": name,
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _parse_cards(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_CARD.finditer(html):
            link = self._abs_web(m.group(1))
            title = _clean_title(m.group(2))
            body = unescape(re.sub(r"<[^>]+>", " ", m.group(3)))
            body = re.sub(r"\s+", " ", body).strip()
            blob = f"{title} {body}"
            pdfs = [self._quote_url(self._abs_web(u)) for u in RE_PDF.findall(body)]
            rows.append(
                {
                    "titulo": title,
                    "fecha": _parse_fecha_dmy(blob),
                    "url": link,
                    "pdf_url": pdfs[0] if pdfs else None,
                    "nota": body[:400],
                    "origen": "plone_card",
                    "page_url": page_url,
                }
            )
        return rows

    def _parse_content_links(self, html: str, page_url: str) -> list[dict[str, Any]]:
        m = re.search(r'id="content-core"[^>]*>(.*)', html, re.I | re.S)
        chunk = m.group(1) if m else html
        rows: list[dict[str, Any]] = []
        for href, raw in RE_CONTENT_LINK.findall(chunk):
            link = self._abs_web(href)
            if "sant-adria.cat" not in link and not link.startswith("/"):
                continue
            title = _clean_title(raw)
            if len(title) < 10:
                continue
            low = title.lower()
            if not RE_PROYECTO.search(title) and not RE_LICENCIA.search(title):
                if "/fitxers/" not in link and "informacio-publica" not in link:
                    continue
            pdf_url = link if ".pdf" in link.lower() or "/fitxers/" in link.lower() else None
            rows.append(
                {
                    "titulo": title,
                    "fecha": _parse_fecha_dmy(title) or _parse_fecha_dmy(link),
                    "url": link,
                    "pdf_url": pdf_url,
                    "origen": "plone_content_link",
                    "page_url": page_url,
                }
            )
        return rows

    def _parse_page_pdfs(self, html: str, page_url: str) -> list[dict[str, Any]]:
        h1 = re.search(r'<h1[^>]*>([^<]+)', html)
        page_title = _clean_title(h1.group(1)) if h1 else page_url
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pdf in RE_PDF.findall(html):
            pdf_url = self._quote_url(self._abs_web(pdf))
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            name = Path(urllib.parse.urlparse(pdf_url).path).name
            rows.append(
                {
                    "titulo": f"{page_title} — {name}"[:500],
                    "fecha": _parse_fecha_dmy(pdf_url) or _parse_fecha_dmy(html[:5000]),
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "origen": "plone_pdf",
                }
            )
        return rows

    def _collect_web_docs(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        queue: list[str] = list(self.seed_pages)
        rows: list[dict[str, Any]] = []
        max_pages = int(self.config.get("max_crawl_pages", 35))

        while queue and len(seen_urls) < max_pages:
            page_url = queue.pop(0)
            if page_url in seen_urls:
                continue
            seen_urls.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            rows.extend(self._parse_cards(html, page_url))
            rows.extend(self._parse_content_links(html, page_url))
            rows.extend(self._parse_page_pdfs(html, page_url))
            for link in RE_PLONE_LINK.findall(html):
                abs_link = self._abs_web(link)
                if not self._is_html_page_url(abs_link):
                    continue
                if abs_link not in seen_urls and abs_link not in queue:
                    queue.append(abs_link)
        return rows

    def _load_amb_expedients(self) -> list[dict[str, Any]]:
        if self._amb_cache is not None:
            return self._amb_cache
        features: list[dict[str, Any]] = []
        offset = 0
        page_size = 100
        base_query = (
            f"{self.amb_exp_layer}/query?"
            f"where=CODI_INE%3D%27{self.ine_mun}%27"
            "&outFields=NOMEXP%2CDGU%2CCMB%2CURL%2CDAPRDEF%2CVIGENT"
            "&returnGeometry=true&outSR=4326&f=geojson"
        )
        while True:
            url = f"{base_query}&resultOffset={offset}&resultRecordCount={page_size}"
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            batch = data.get("features") or []
            if not batch:
                break
            features.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        self._amb_cache = features
        by_name: dict[str, dict[str, Any]] = {}
        for feat in features:
            props = feat.get("properties") or {}
            nom = str(props.get("NOMEXP") or "").strip()
            if not nom:
                continue
            by_name[_norm_text(nom)] = feat
        self._amb_by_norm_name = by_name
        return features

    def _amb_hit_for_blob(self, blob: str) -> dict[str, Any] | None:
        self._load_amb_expedients()
        by_name = self._amb_by_norm_name or {}
        norm_blob = _norm_text(blob)
        for nom_norm, feat in by_name.items():
            if len(nom_norm) >= 8 and nom_norm in norm_blob:
                return feat
        tokens = [t for t in re.split(r"[\s,;/|()]+", norm_blob) if len(t) >= 5]
        best: dict[str, Any] | None = None
        best_score = 0
        for nom_norm, feat in by_name.items():
            nom_tokens = [t for t in re.split(r"[\s,;/|()]+", nom_norm) if len(t) >= 4]
            score = sum(1 for t in nom_tokens if t in norm_blob)
            if score > best_score and score >= 2:
                best_score = score
                best = feat
        return best

    def _apply_amb_geometry(self, rec: dict[str, Any], feat: dict[str, Any], query_url: str) -> None:
        geom = feat.get("geometry")
        if not isinstance(geom, dict) or geom.get("type") not in {"Polygon", "MultiPolygon"}:
            return
        props = feat.get("properties") or {}
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_axis_order"] = "xy"
        rec["geometry_source"] = "portal_visor_arcgis"
        rec["geometry_source_url"] = query_url
        rec["coord_source"] = "portal_geometry_centroid"
        cent = geometry_centroid(geom)
        if cent:
            rec["lat"], rec["lon"] = cent

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = f"{rec.get('titulo', '')} {rec.get('nota', '')} {rec.get('expte', '')}"
        feat = self._amb_hit_for_blob(blob)
        if feat:
            self._apply_amb_geometry(rec, feat, f"{self.amb_exp_layer}/query")

    def _amb_to_proyecto(self, feat: dict[str, Any]) -> dict[str, Any]:
        props = feat.get("properties") or {}
        nom = _clean_title(str(props.get("NOMEXP") or "Expediente urbanístico"))
        dgu = str(props.get("DGU") or "").strip()
        url = str(props.get("URL") or "").strip() or self.web_base
        key = dgu or nom
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"amb:{key}"),
            "municipio": MUNICIPIO,
            "titulo": nom,
            "fecha": _parse_fecha_dmy(str(props.get("DAPRDEF") or "")),
            "tipo": _proyecto_tipo(nom),
            "url": url,
            "source": "ayuntamiento",
            "origen": "amb_expedients_gis",
        }
        if dgu:
            rec["expte"] = dgu
        self._apply_amb_geometry(rec, feat, f"{self.amb_exp_layer}/query")
        return rec

    def _collect_amb_proyectos(self) -> list[dict[str, Any]]:
        return [self._amb_to_proyecto(f) for f in self._load_amb_expedients()]

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        lower = titulo.lower()
        if not any(p in lower for p in LICENCIA_TRAMITE_PATTERNS) and not RE_LICENCIA.search(titulo):
            return None
        if RE_NOISE.search(titulo) and "licen" not in lower and "llicen" not in lower:
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Trámite catálogo sede STA; tablón PTS2_TABLON sin filas publicadas",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('nota', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("nota"):
            rec["nota"] = row["nota"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        m = RE_EXPTE.search(blob)
        if m:
            rec["expte"] = m.group(1).strip()
        self._enrich_geometry(rec)
        return rec

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

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for row in self._catalog_rows():
            rec = self._tramite_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._collect_web_docs():
            add(self._row_to_proyecto(row))
        for rec in self._collect_amb_proyectos():
            add(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_catalogo"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "plone_seue_amb_gis"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}
