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
from municipio.geometry import geometry_centroid, record_geometry
from municipio.gis.sitcm import _merge_geometries, resolve_ambito_geometry

WEB_BASE = "https://www.ayuntamientocorpa.es"
SEDE_BASE = "https://corpa.sedelectronica.es"
SEDECORPA_BASE = "https://sedecorpa.eadministracion.es"
MUNICIPIO = "Corpa"
ID_PREFIX = "corpa"

URBANISMO_URL = f"{WEB_BASE}/urbanismo"
NORMATIVA_URL = f"{WEB_BASE}/normativa"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "CORPA"

DEFAULT_LICENCIA_DOCS: list[dict[str, str]] = [
    {
        "path": "/Ficheros/Documentos/INSTANCIA-GENERAL.doc",
        "tipo": "instancia general",
        "titulo": "Instancia general (solicitudes)",
    },
    {
        "path": "/Ficheros/Documentos/ORDENANZA-REGULADORA-DE-LA-TASA-POR-LICENCIAS-Y-OTRAS-ACTUACIONES-URBANISTICAS.pdf",
        "tipo": "ordenanza licencias urbanísticas",
        "titulo": "Ordenanza reguladora tasa licencias y actuaciones urbanísticas",
    },
    {
        "path": "/Ficheros/Documentos/ORDENANZA-LICENCIA-PRIMERA-OCUPACION.pdf",
        "tipo": "ordenanza primera ocupación",
        "titulo": "Ordenanza licencia de primera ocupación",
    },
]

RE_PREVIEW = re.compile(
    r'href="(https://corpa\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|vallado|limpieza de solares)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"estudio de detalle|modificaci[oó]n puntual|sector|sus[\s-]?r|aa[\s-]?\d|apd[\s-]?i|"
    r"catalogo|ordenaci[oó]n|calificaci[oó]n|plano|memoria|bienes protegidos|"
    r"\b(?:ue|sau)-[a-z0-9]+\b|unidad de ejecuci[oó]n)",
)
RE_SKIP = re.compile(
    r"(?i)(presupuesto|modificaci[oó]n (?:de )?cr[eé]dito|calendario fiscal|"
    r"ordenanza (?:de )?(?:tasa|fiscal|basura|cementerio|ivtm|iae)|"
    r"nombramiento|candidatura|empleo p[uú]blico|educador|oferta de empleo|"
    r"veh[ií]culo|ivtm|padron|padr[oó]n|subvenci[oó]n|dedicaci[oó]n parcial)",
)
RE_PDF_LINK = re.compile(
    r'<a\s+href="([^"]+\.(?:pdf|PDF)(?:[^"]*)?)"[^>]*?(?:tittle|title)="([^"]*)"[^>]*>([^<]*)</a>'
    r'|<a\s+href="([^"]+\.(?:pdf|PDF)(?:[^"]*)?)"[^>]*>([^<]*)</a>',
    re.I,
)
RE_BOLD_SECTION = re.compile(
    r'<(?:span|strong|b)[^>]*style="[^"]*font-weight:\s*(?:bold|700)[^"]*"[^>]*>([^<]+)</(?:span|strong|b)>'
    r'|<(?:span|strong|b)[^>]*>([^<]{8,120})</(?:span|strong|b)>'
    r'|<h[1-6][^>]*>([^<]+)</h[1-6]>',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_BOCM_DATE = re.compile(r"BOCM[-_]?(\d{4})(\d{2})(\d{2})", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_BOCM_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _abs_url(href: str, base: str = WEB_BASE) -> str:
    href = unescape(href).replace("&amp;", "&").strip()
    # strip broken query fragments from Neosoft CMS
    href = href.split("&quot;", 1)[0]
    return urllib.parse.urljoin(f"{base}/", href)


def _pgou_tipo(name: str) -> str:
    n = name.lower()
    if "normas" in n and "urban" in n:
        return "normas urbanísticas"
    if "nnss" in n or "subsidiarias" in n:
        return "normas subsidiarias"
    if "catalogo" in n or "bienes protegidos" in n:
        return "catálogo de bienes protegidos"
    if "indice" in n:
        return "índice PGOU"
    if "modificacion" in n or "modificación" in n:
        return "modificación puntual"
    if "plano" in n or "ordenacion" in n:
        return "planos de ordenación"
    return "documento PGOU"


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bue-[a-z0-9]+\b", n):
        return "unidad de ejecución"
    if re.search(r"\bsau-\d", n):
        return "sector de actuación urbanística"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "plan parcial" in n or "pgou" in n:
        return "planeamiento"
    if "informaci" in n:
        return "información pública"
    if "aprobaci" in n:
        return "aprobación"
    if "catalogo" in n or "bienes protegidos" in n:
        return "catálogo PGOU"
    if "plano" in n:
        return "planos PGOU"
    return "urbanismo"


class CorpaAyuntamientoAdapter(AyuntamientoAdapter):
    """Neosoft web + sede espublico eHome + ámbitos SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.normativa_url = str(self.config.get("normativa_url") or NORMATIVA_URL)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._sitcm_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-corpa/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _section_at(self, html: str, pos: int) -> str:
        chunk = html[max(0, pos - 4000) : pos]
        sections = [_clean_title(m.group(1) or m.group(2) or m.group(3) or "") for m in RE_BOLD_SECTION.finditer(chunk)]
        sections = [s for s in sections if s and len(s) >= 5]
        return sections[-1] if sections else ""

    def _parse_pdf_links(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_LINK.finditer(html):
            href = m.group(1) or m.group(4) or ""
            tittle = _clean_title(m.group(2) or "")
            anchor = _clean_title(m.group(3) or m.group(5) or "")
            pdf_url = _abs_url(href)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            section = self._section_at(html, m.start())
            title = section or tittle or anchor or Path(pdf_url).stem
            if section and anchor and anchor.lower() not in section.lower():
                if len(anchor) > 4 and not anchor.lower().startswith("anuncio"):
                    title = f"{section}: {anchor}"
            elif tittle and len(tittle) > 4:
                title = tittle
            rows.append(
                {
                    "titulo": title[:500],
                    "pdf_url": pdf_url,
                    "url": page_url,
                    "fecha": _parse_fecha_dmy(f"{title} {pdf_url}"),
                    "blob": f"{title} {pdf_url}",
                }
            )
        return rows

    def _load_sitcm_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._sitcm_cache is not None:
            return self._sitcm_cache
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "50",
                "CQL_FILTER": f"DS_MUNICIPIO='{self.wfs_municipio}'",
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._sitcm_cache = {}
            return self._sitcm_cache
        cache: dict[str, dict[str, Any]] = {}
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                continue
            name = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "").strip()
            if name:
                cache[name.upper()] = feat
        self._sitcm_cache = cache
        return cache

    def _geometry_from_ambit(self, ambit_name: str) -> dict[str, Any] | None:
        feat = self._load_sitcm_ambitos().get(ambit_name.upper())
        if not feat:
            return None
        merged = _merge_geometries([feat])
        if not merged:
            return None
        esc = ambit_name.replace("'", "''")
        cql = f"DS_MUNICIPIO='{self.wfs_municipio}' AND DS_NOMB_AMB='{esc}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "5",
                "CQL_FILTER": cql,
            }
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": f"{self.wfs_url}?{params}",
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
        title_up = title.upper()
        for ambit_name in self._load_sitcm_ambitos():
            if ambit_name in title_up.replace(" ", "") or ambit_name.replace("-", "") in title_up.replace(" ", ""):
                return self._geometry_from_ambit(ambit_name)
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_urbanismo_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for rec in self._parse_pdf_links(html, self.urbanismo_url):
            name = Path(rec["pdf_url"]).name
            if RE_SKIP.search(name) and not RE_PROYECTO.search(name):
                continue
            row = {
                "id": _stable_id("proy", rec["pdf_url"]),
                "municipio": MUNICIPIO,
                "titulo": f"PGOU Corpa: {rec['titulo']}"[:500],
                "fecha": rec.get("fecha"),
                "tipo": _pgou_tipo(name),
                "url": self.urbanismo_url,
                "pdf_url": rec["pdf_url"],
                "source": "ayuntamiento",
                "origen": "urbanismo_pgou",
            }
            self._attach_geometry(row)
            rows.append(row)
        return rows

    def _collect_sitcm_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for ambit_name, feat in self._load_sitcm_ambitos().items():
            merged = _merge_geometries([feat])
            if not merged:
                continue
            titulo = f"Ámbito planeamiento SITCM — {ambit_name}"
            row: dict[str, Any] = {
                "id": _stable_id("proy", f"sitcm-{ambit_name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": None,
                "tipo": _proyecto_tipo(ambit_name),
                "url": SITCM_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sitcm_ambito",
            }
            geom = self._geometry_from_ambit(ambit_name)
            if geom:
                row.update(geom)
                centroid = geometry_centroid(geom["geom_geojson"])
                if centroid:
                    row["lat"], row["lon"] = centroid
            rows.append(row)
        return rows

    def _parse_board_table(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 4:
                continue
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            titulo = (title_m.group(1).strip() if title_m else "") or _strip_html(cells[0])
            expediente = _strip_html(cells[1]) if len(cells) > 1 else ""
            procedimiento = _strip_html(cells[2]) if len(cells) > 2 else ""
            categoria = _strip_html(cells[3]) if len(cells) > 3 else ""
            descripcion = _strip_html(cells[4]) if len(cells) > 4 else titulo
            fecha_cell = _strip_html(cells[5]) if len(cells) > 5 else ""
            url = link_m.group(1) if link_m else self.board_url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente,
                    "procedimiento": procedimiento,
                    "categoria": categoria,
                    "descripcion": descripcion,
                    "fecha": _parse_fecha_dmy(fecha_cell) or _parse_fecha_dmy(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        items = self._parse_board_table(html)
        if not items:
            for m in RE_PREVIEW.finditer(html):
                url = m.group(1)
                local = html[max(0, m.start() - 300) : m.end() + 100]
                title_m = re.search(r'title="([^"]*)"', local, re.I)
                titulo = unescape(title_m.group(1).strip()) if title_m else url
                items.append(
                    {
                        "titulo": titulo[:500],
                        "expediente": "",
                        "procedimiento": "",
                        "categoria": "",
                        "descripcion": titulo,
                        "fecha": _parse_fecha_dmy(titulo),
                        "url": url,
                        "pdf_url": url,
                        "origen": "tablon",
                    }
                )
        return items

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.config.get("licencia_docs") or DEFAULT_LICENCIA_DOCS:
            doc_url = _abs_url(str(item["path"]))
            rows.append(
                {
                    "id": _stable_id("lic", doc_url),
                    "fecha_concesion": None,
                    "tipo": item["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": doc_url,
                    "source": "ayuntamiento",
                    "nota": "Formulario u ordenanza; no concesión publicada",
                    "origen": "web_normativa",
                }
            )
        rows.extend(
            [
                {
                    "id": _stable_id("lic", self.board_url),
                    "fecha_concesion": None,
                    "tipo": "tablón licencias urbanísticas",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Tablón de anuncios — sede electrónica",
                    "url": self.board_url,
                    "source": "ayuntamiento",
                    "nota": "Anuncios vigentes en espublico gestiona",
                    "origen": "sede_tablon",
                },
                {
                    "id": _stable_id("lic", SEDECORPA_BASE),
                    "fecha_concesion": None,
                    "tipo": "sede electrónica urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Sede electrónica — trámites urbanísticos",
                    "url": f"{SEDECORPA_BASE}/PortalCiudadano/Menus/wfrBienvenida.aspx",
                    "source": "ayuntamiento",
                    "nota": "Presentación telemática vía Maggioli eAdmin",
                    "origen": "sede_eadmin",
                },
            ]
        )
        return rows

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_SKIP.search(blob) and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia / autorización (anuncio)",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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
        rows = self._collect_licencia_info()
        seen: set[str] = {r["id"] for r in rows}
        for item in self._collect_board():
            lic = self._board_to_licencia(item)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "source": "ayuntamiento", "at": datetime.now(timezone.utc).isoformat()}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in self._collect_urbanismo_pdfs() + self._collect_sitcm_proyectos():
            if row["id"] not in seen:
                seen.add(row["id"])
                rows.append(row)
        for item in self._collect_board():
            proy = self._board_to_proyecto(item)
            if proy and proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "source": "ayuntamiento",
            "at": datetime.now(timezone.utc).isoformat(),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
