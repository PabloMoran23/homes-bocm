from __future__ import annotations

import hashlib
import http.cookiejar
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
from municipio.gis.sitcm import resolve_ambito_geometry, resolve_municipio_wfs

WP_BASE = "https://patones.net/site/ayto"
WP_API = f"{WP_BASE}/wp-json/wp/v2"
SEDE_BASE = "https://patones.sedelectronica.es"
MUNICIPIO = "Patones"
ID_PREFIX = "patones"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/arquitecto-municipal/",
    f"{WP_BASE}/normas-subsidiarias/",
    (
        f"{WP_BASE}/plan-especial-de-aparcamientos-y-mejora-de-accesos-para-el-fomento-de-la-"
        "sostenibilidad-turistica-en-patones/"
    ),
    (
        f"{WP_BASE}/plan-especial-de-aparcamientos-y-mejora-de-accesos-en-patones-subsanado-de-"
        "acuerdo-con-iae-e-informes-sectoriales/"
    ),
    f"{WP_BASE}/bandos/",
    f"{WP_BASE}/boletin-municipal/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|"
    r"punto de recarga)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|normas subsidiarias|nnss|memoria|"
    r"modificaci[oó]n|estudio (?:ac[uú]stico|ambiental|de detalle)|pamif|paminun|"
    r"citeco|aparcamiento|bando.*desbroce|ordenanza|bocm|edicto|plano|"
    r"aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|ue[\.\-\s]*\d+)",
)
RE_BOARD_SKIP = re.compile(
    r"(?i)(calendario fiscal|tributari|revisi[oó]n en v[ií]a administrativa|"
    r"liquidaci[oó]n.*basura|subvenci[oó]n|empleo|personal|fiestas)",
)
RE_SKIP_PDF = re.compile(
    r"(?i)(indice_|catalogo_\d{3}|nurbanisticas_\d{3}|formulario|instrucciones|"
    r"consideraciones|cuenta_para)",
)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?patones\.net)?/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_PREVIEW = re.compile(
    r'href="(https://patones\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"


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


def _fecha_from_url(url: str, title: str = "") -> str | None:
    blob = f"{url} {title}"
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"Boletin[_\s]*(\d+)[_\s]*([A-Za-z]+)[_\s]*(\d{4})", blob, re.I)
    if m:
        meses = {
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
            "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
            "jun": 6, "oct": 10, "dic": 12, "abr": 4, "ago": 8,
        }
        mes = meses.get(m.group(2).lower()[:3], meses.get(m.group(2).lower()))
        if mes:
            return f"{m.group(3)}-{mes:02d}-01"
    years = [int(y.group(1)) for y in RE_YEAR.finditer(blob) if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(title: str, url: str = "") -> str:
    blob = f"{title} {url}".lower()
    if "normas subsidiarias" in blob or "nnss" in blob:
        return "normas subsidiarias"
    if "plan especial" in blob or "aparcamiento" in blob or "up2403" in blob:
        return "plan especial"
    if "pamif" in blob or "paminun" in blob or "citeco" in blob:
        return "plan especial"
    if "memoria" in blob:
        return "memoria"
    if "plano" in blob:
        return "planos"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "bando" in blob and "desbroce" in blob:
        return "bando urbanístico"
    if "informaci" in blob:
        return "información pública"
    if "bocm" in blob or "boletin" in blob:
        return "boletín municipal"
    if re.search(r"ue[\.\-\s]*\d+", blob):
        return "unidad de ejecución"
    return "urbanismo"


class PatonesAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (planeamiento PDF) + tablón sede espublico + geometría SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.municipio_wfs = str(
            geom_cfg.get("municipio_wfs")
            or resolve_municipio_wfs(MUNICIPIO)
            or "PATONES"
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-patones/1.0")},
        )
        use_sede = sede or "sedelectronica.es" in url
        if use_sede:
            with self._opener.open(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", unescape(href))

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

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        title = str(rec.get("titulo") or "")
        if not title or not self.municipio_wfs:
            return
        geom, meta = resolve_ambito_geometry(self.municipio_wfs, title)
        if not geom:
            return
        ambit = meta.get("ambito_name") or ""
        cql = f"DS_MUNICIPIO='{self.municipio_wfs}'"
        if ambit:
            cql += f" AND DS_NOMB_AMB='{str(ambit).replace(chr(39), chr(39)*2)}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "5",
                "CQL_FILTER": cql,
            }
        )
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "cm_sit_wfs"
        rec["geometry_source_url"] = f"{WFS_BASE}?{params}"
        rec["coord_source"] = "portal_geometry_centroid"
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
                "CQL_FILTER": cql,
            }
        )
        url = f"{WFS_BASE}?{params}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-patones/1.0")},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(data, dict):
            return []
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        muni = self.municipio_wfs.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        rows: list[dict[str, Any]] = []
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            geom = f.get("geometry")
            if not isinstance(geom, dict):
                continue
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            cql = f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB='{name.replace(chr(39), chr(39)*2)}'"
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeName": WFS_TYPE,
                    "outputFormat": "application/json",
                    "srsName": "EPSG:4326",
                    "count": "5",
                    "CQL_FILTER": cql,
                }
            )
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": f"{self.sede_base}/transparency/",
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
                "geom_geojson": geom,
                "geometry_source": "cm_sit_wfs",
                "geometry_source_url": f"{WFS_BASE}?{params}",
                "coord_source": "portal_geometry_centroid",
            }
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            rows.append(rec)
        return rows

    def _extract_pdfs(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf_url = self._abs_url(m.group(1).split("#")[0])
            if pdf_url in seen or RE_SKIP_PDF.search(pdf_url):
                continue
            seen.add(pdf_url)
            name = unescape(urllib.parse.unquote(Path(pdf_url).name))
            name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("%20", " ").replace("_", " ")
            titulo = name[:500] if len(name) > 4 else page_url
            blob = f"{titulo} {pdf_url}"
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                if "boletin" not in page_url.lower():
                    continue
            rec: dict[str, Any] = {
                "id": _stable_id("proy", pdf_url),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": _fecha_from_url(pdf_url, titulo),
                "tipo": _proyecto_tipo(titulo, pdf_url),
                "url": page_url,
                "pdf_url": pdf_url,
                "source": "ayuntamiento",
                "origen": "wp_pdf",
            }
            self._attach_geometry(rec)
            rows.append(rec)
        return rows

    def _collect_wp_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = ""
            tm = re.search(r"<title>([^<|]+)", html, re.I)
            if tm:
                page_title = _strip_html(tm.group(1).replace("&#8211;", "-"))[:200]
            if page_title and RE_PROYECTO.search(page_title):
                rec_id = _stable_id("proy", page_url)
                if rec_id not in seen:
                    seen.add(rec_id)
                    rec = {
                        "id": rec_id,
                        "municipio": MUNICIPIO,
                        "titulo": page_title,
                        "fecha": None,
                        "tipo": _proyecto_tipo(page_title, page_url),
                        "url": page_url,
                        "source": "ayuntamiento",
                        "origen": "wp_page",
                    }
                    self._attach_geometry(rec)
                    rows.append(rec)
            for rec in self._extract_pdfs(html, page_url):
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        return rows

    def _parse_board_table(self, html: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 6:
                continue
            link_m = re.search(
                r'href="(https://patones\.sedelectronica\.es/preview-document/[^"]+)"',
                tr,
                re.I,
            )
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0])
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": _strip_html(cells[1]),
                    "procedimiento": _strip_html(cells[2]),
                    "categoria": _strip_html(cells[3]),
                    "descripcion": _strip_html(cells[4]),
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])),
                    "url": link_m.group(1) if link_m else self.board_url,
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": "tablon",
                }
            )
        return rows

    def _parse_board_links(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            local = html[max(0, m.start() - 400) : m.end() + 200]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": titulo[:500],
                    "expediente": "",
                    "procedimiento": "",
                    "categoria": "",
                    "descripcion": titulo,
                    "fecha": _fecha_from_url(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, sede=True)
        except urllib.error.URLError:
            return []
        items = self._parse_board_table(html)
        if not items:
            items = self._parse_board_links(html)
        return items

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y exposiciones públicas en sede electrónica",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación Cl@ve; no hay listado público",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.wp_base}/arquitecto-municipal/"),
                "fecha_concesion": None,
                "tipo": "información urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Arquitecto municipal — trámites urbanísticos",
                "url": f"{self.wp_base}/arquitecto-municipal/",
                "source": "ayuntamiento",
                "nota": "Contacto arquitecto municipal; cita previa",
                "origen": "wp_tramite",
            },
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_BOARD_SKIP.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_BOARD_SKIP.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            if "bando" not in blob.lower() and "ordenanza" not in blob.lower():
                return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_url(row["titulo"]),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "wp_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
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

        for rec in self._collect_wp_pages():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
