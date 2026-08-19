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
from municipio.geometry import geometry_centroid, record_geometry
from municipio.gis.sitcm import WFS_BASE, _merge_geometries, resolve_ambito_geometry

WP_BASE = "https://www.aytonavacerrada.org"
SEDE_BASE = "https://aytonavacerrada.sedelectronica.es"
MUNICIPIO = "Navacerrada"
ID_PREFIX = "navacerrada"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "NAVACERRADA"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/urbanismo/",
    f"{WP_BASE}/ordenanzas-urbanisticas-2/",
    f"{WP_BASE}/normativa-urbanistica-2/",
    f"{WP_BASE}/administracion-electronica/",
    *(f"{WP_BASE}/urbanismo/{n}/" for n in range(2, 7)),
]

DEFAULT_LICENCIA_PDFS: list[dict[str, str]] = [
    {
        "url": f"{WP_BASE}/wp-content/uploads/2015/12/NNSS.pdf",
        "titulo": "Normas subsidiarias de planeamiento (NNSS)",
    },
    {
        "url": f"{WP_BASE}/wp-content/uploads/2015/12/1.1.pdf",
        "titulo": "Documentación planeamiento — memoria",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"primera ocupaci[oó]n|instancia general|tasa.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|bando|edicto|desbroce|parcela|suelo|vivienda|licitaci[oó]n.*vivienda|"
    r"obra(?:s)? (?:en |de |calle)|asfalt|movilidad|transporte|ordenanza|"
    r"\b(?:UE|SAU|S)-[\w\d-]+\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(fiestas|cine|empleo|concurso|deporte|ornitol|halloween|navidad|"
    r"caza|vacunaci[oó]n|ludoteca|colegio|escuela|autobus|piscina|"
    r"punto limpio|recogida podas|influencia aviar|tdt 4g|director.*deportes|"
    r"cuenta general|iae|cobranza)",
)
RE_LOC = re.compile(r"<loc>([^<]+)</loc>")
RE_TITLE = re.compile(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>(.*?)</h1>', re.I | re.S)
RE_DATE = re.compile(r'<time[^>]*datetime="([^"]+)"', re.I)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?aytonavacerrada\.org)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_BOARD_PREVIEW = re.compile(
    r'href="(https://aytonavacerrada\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr>\s*(.*?)\s*</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(
    r'data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_AMBIT_CODE = re.compile(r"(?i)\b((?:UE|SAU|S)-[\w\d-]+)\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bsau-\d+\b", n) or re.search(r"\bue-\d", n):
        return "ámbito planeamiento"
    if "plan parcial" in n or "sau-" in n:
        return "plan parcial"
    if "unidad de ejecuci" in n or re.search(r"\bue-\d", n):
        return "unidad de ejecución"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "bando" in n and ("desbroce" in n or "parcela" in n):
        return "bando urbanístico"
    if "vivienda" in n:
        return "vivienda"
    if "licitaci" in n:
        return "licitación obra"
    if "obra" in n or "asfalt" in n:
        return "obra municipal"
    if "plan" in n and "movilidad" in n:
        return "planeamiento movilidad"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    return "urbanismo"


class NavacerradaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress + sede espublico gestiona + SITCM WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency"
        )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_pdfs = list(self.config.get("licencia_pdfs") or DEFAULT_LICENCIA_PDFS)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(
            self.config.get("wfs_municipio") or geom_cfg.get("municipio_filter") or WFS_MUNICIPIO
        )
        self._sitemap_urls: list[str] | None = None
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-navacerrada/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        href = unescape(href).replace("&amp;", "&").strip()
        if href.startswith("//"):
            return "https:" + href
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _sitemap_post_urls(self) -> list[str]:
        if self._sitemap_urls is not None:
            return self._sitemap_urls
        urls: list[str] = []
        for pattern in (
            f"{self.wp_base}/wp-sitemap-posts-post-1.xml",
            f"{self.wp_base}/post-sitemap1.xml",
        ):
            try:
                xml = self._fetch(pattern)
            except urllib.error.URLError:
                continue
            urls.extend(RE_LOC.findall(xml))
        self._sitemap_urls = list(dict.fromkeys(urls))
        return self._sitemap_urls

    def _post_candidate(self, url: str) -> bool:
        slug = url.rstrip("/").split("/")[-1].replace("-", " ")
        keys = (
            "urban", "licenc", "planeam", "obra", "bando", "vivienda",
            "desbroce", "asfalt", "parcela", "suelo", "plan ", "licitacion",
            "ordenanza", "normativa",
        )
        if any(k in slug for k in keys):
            return True
        return bool(RE_PROYECTO.search(slug))

    def _parse_post_page(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None

        title_m = RE_TITLE.search(html)
        title = _strip_html(title_m.group(1)) if title_m else url.rstrip("/").split("/")[-1]
        if RE_EXCLUDE.search(title):
            return None

        blob = f"{title} {html[:12000]}"
        if not RE_PROYECTO.search(blob):
            return None
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(title):
            return None

        date_m = RE_DATE.search(html)
        fecha = date_m.group(1)[:10] if date_m else _fecha_from_blob(url)
        pdfs = list(dict.fromkeys(self._abs_wp(u) for u in RE_PDF_HREF.findall(html)))
        return {
            "titulo": title[:500],
            "fecha": fecha,
            "url": url,
            "pdfs": pdfs,
            "origen": "wp_post",
        }

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for url in self._sitemap_post_urls():
            if not self._post_candidate(url):
                continue
            rec = self._parse_post_page(url)
            if not rec or rec["url"] in seen:
                continue
            seen.add(rec["url"])
            rows.append(rec)
        return rows

    def _parse_seed_pdfs(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(
            r'<a[^>]+href="([^"]+\.pdf[^"]*)"[^>]*>([^<]*)</a>',
            html,
            re.I,
        ):
            pdf_url = self._abs_wp(m.group(1))
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            label = unescape(m.group(2).strip()) or Path(urllib.parse.urlparse(pdf_url).path).name
            rows.append(
                {
                    "titulo": label[:500],
                    "fecha": _fecha_from_url(pdf_url),
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "origen": "wp_sede_pdf",
                }
            )
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            rows.extend(self._parse_seed_pdfs(html, page_url))
        return rows

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I | re.S)
        if tbody_m:
            for row_m in RE_BOARD_ROW.finditer(tbody_m.group(1)):
                row_html = row_m.group(1)
                if "emptyRow" in row_html:
                    continue
                cells: dict[str, str] = {}
                doc_url = self.board_url
                titulo = ""
                for cm in RE_BOARD_CELL.finditer(row_html):
                    label, val = cm.group(1), cm.group(2)
                    link_m = re.search(r'href="([^"]+)"', val, re.I)
                    title_m = re.search(r'title="([^"]*)"', val, re.I)
                    if link_m:
                        doc_url = urllib.parse.urljoin(f"{self.sede_base}/", link_m.group(1))
                    if title_m and title_m.group(1).strip():
                        titulo = unescape(title_m.group(1).strip())
                    cells[label] = _strip_html(val)
                if not titulo:
                    titulo = cells.get("Descripción") or cells.get("Documento") or ""
                if not titulo:
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "expediente": cells.get("Expediente", ""),
                        "procedimiento": cells.get("Procedimiento", ""),
                        "categoria": cells.get("Categoría", ""),
                        "fecha": _parse_fecha_dmy(cells.get("Fecha de Publicación", "")),
                        "url": doc_url,
                        "origen": "sede_board",
                    }
                )
        if not rows:
            for m in RE_BOARD_PREVIEW.finditer(html):
                url = m.group(1)
                local = html[max(0, m.start() - 400) : m.end() + 200]
                title_m = re.search(r'title="([^"]*)"', local, re.I)
                titulo = unescape(title_m.group(1)) if title_m else url
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "expediente": "",
                        "procedimiento": "",
                        "categoria": "",
                        "fecha": None,
                        "url": url,
                        "origen": "sede_board",
                    }
                )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board(html)

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", f"{self.wp_base}/urbanismo/"),
                "fecha_concesion": None,
                "tipo": "urbanismo municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — información y trámites",
                "url": f"{self.wp_base}/urbanismo/",
                "source": "ayuntamiento",
                "origen": "wp_urbanismo",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites urbanísticos",
                "url": self.sede_base,
                "source": "ayuntamiento",
                "origen": "wp_sede",
            },
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.transparency_url),
                "fecha_concesion": None,
                "tipo": "ordenanzas y transparencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Transparencia — urbanismo y medio ambiente",
                "url": self.transparency_url,
                "source": "ayuntamiento",
                "origen": "sede_transparency",
            },
        ]
        for item in self.licencia_pdfs:
            pdf = item["url"]
            titulo = item["titulo"]
            rows.append(
                {
                    "id": _stable_id("lic", pdf),
                    "fecha_concesion": _fecha_from_url(pdf),
                    "tipo": "trámite licencia urbanística",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": pdf,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "nota": "Formulario/información de trámite; sin concesiones publicadas",
                    "origen": "wp_tramite",
                }
            )
        return rows

    def _wfs_query(self, cql: str, *, count: int = 50) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
                "CQL_FILTER": cql,
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(data, dict):
            return []
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _load_sitcm_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        cache: dict[str, dict[str, Any]] = {}
        for feat in self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=50):
            name = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "").strip()
            if name:
                cache[name.upper()] = feat
        self._wfs_cache = cache
        return cache

    def _geometry_from_ambit(self, ambit_name: str) -> dict[str, Any] | None:
        cache = self._load_sitcm_ambitos()
        feat = cache.get(ambit_name.upper())
        if not feat:
            return None
        merged = _merge_geometries([feat])
        if not merged:
            return None
        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
            f"AND DS_NOMB_AMB='{ambit_name.replace(chr(39), chr(39) * 2)}'"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
            ),
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": ambit_name,
        }

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, title)
        if geom:
            return {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": meta.get("ambito_name"),
            }
        for code_m in RE_AMBIT_CODE.finditer(title or ""):
            code = code_m.group(1).upper()
            cache = self._load_sitcm_ambitos()
            for name, feat in cache.items():
                if code in name:
                    hit = self._geometry_from_ambit(str((feat.get("properties") or {}).get("DS_NOMB_AMB") or name))
                    if hit:
                        return hit
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=50)
        rows: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for feat in feats:
            props = feat.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name or name.upper() in seen_names:
                continue
            seen_names.add(name.upper())
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            fecha = str(props.get("FC_BOCM") or props.get("FC_AC") or "")[:10] or None
            merged = _merge_geometries([feat])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(name),
                "url": f"{self.wp_base}/urbanismo/",
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39) * 2)}'"
                )
                rec["geometry_source_url"] = (
                    f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                )
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(merged)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if row.get("origen") not in ("sit_wfs",) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        pdf = row.get("pdf_url") or (row.get("pdfs") or [None])[0]
        key = row.get("expediente") or pdf or row.get("url", "") + "|" + blob
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": blob[:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or self.wp_base,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if pdf:
            rec["pdf_url"] = pdf
        if row.get("expediente"):
            rec["expte"] = row["expediente"]
        self._enrich_geometry(rec)
        return rec

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row.get("expediente") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": blob[:500],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expediente"):
            rec["expte"] = row["expediente"]
        if row.get("pdfs"):
            rec["pdf_url"] = row["pdfs"][0]
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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_board():
            rec = self._row_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") in ("wp_tramite", "wp_sede", "sede_tablon")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for row in self._collect_board():
            rec = self._row_to_licencia(row)
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

        for rec in self._collect_sit_ambitos():
            add(rec)
        for row in self._collect_wp_posts():
            add(self._row_to_proyecto(row))
        for row in self._collect_seed_pages():
            add(self._row_to_proyecto(row))
        for row in self._collect_board():
            add(self._row_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
