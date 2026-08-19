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

WP_BASE = "https://villamanriquedetajo.madrid"
SEDE_BASE = "https://villamanriquedetajo.sedelectronica.es"
MUNICIPIO = "Villamanrique de Tajo"
ID_PREFIX = "villamanrique-de-tajo"

NORMATIVA_URL = f"{WP_BASE}/normativa-municipal/"
TRAMITES_URL = f"{WP_BASE}/tramites-municipales/"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "VILLAMANRIQUE DE TAJO"

DEFAULT_LICENCIA_PDFS: list[dict[str, str]] = [
    {
        "url": f"{WP_BASE}/pdf/solicitud-licencia-obra-mayor-2021.pdf",
        "tipo": "licencia de obra mayor",
        "titulo": "Solicitud de licencia de obra mayor",
    },
    {
        "url": f"{WP_BASE}/pdf/declaracion_responsable-obra.pdf",
        "tipo": "declaración responsable de obra",
        "titulo": "Declaración responsable de obra",
    },
    {
        "url": f"{WP_BASE}/pdf/solicitud-licencia-primera-ocupacion-2021.pdf",
        "tipo": "licencia de primera ocupación",
        "titulo": "Solicitud de licencia de primera ocupación",
    },
    {
        "url": f"{WP_BASE}/pdf/licencia-de-obras.pdf",
        "tipo": "licencia de obras",
        "titulo": "Licencia de obras (modelo)",
    },
    {
        "url": f"{WP_BASE}/pdf/instancia-general-2021.pdf",
        "tipo": "instancia general",
        "titulo": "Instancia general municipal",
    },
    {
        "url": f"{WP_BASE}/pdf/tramites-municipales/impreso-solicitud-ocupacion-via-publica.pdf",
        "tipo": "ocupación vía pública",
        "titulo": "Solicitud de ocupación de vía pública",
    },
]

PGOU_PDF_SEEDS: list[dict[str, str]] = [
    {
        "url": f"{WP_BASE}/pdf/plan-general-urbanistico.pdf",
        "titulo": "Plan General de Ordenación Urbana de Villamanrique de Tajo",
        "fecha": "2016-05-19",
        "tipo": "planeamiento",
    },
    {
        "url": f"{WP_BASE}/pdf/fichas_de_ambitos_villamanrique_de_tajo.pdf",
        "titulo": "Fichas de ámbitos del PGOU",
        "fecha": "2016-05-19",
        "tipo": "documentación PGOU",
    },
    {
        "url": f"{WP_BASE}/pdf/fichas_de_sectores_villamanrique_de_tajo.pdf",
        "titulo": "Fichas de sectores del PGOU",
        "fecha": "2016-05-19",
        "tipo": "documentación PGOU",
    },
    {
        "url": f"{WP_BASE}/pdf/clasificacion_del_suelo.pdf",
        "titulo": "Clasificación del suelo — PGOU",
        "fecha": "2016-05-19",
        "tipo": "ordenación PGOU",
    },
    {
        "url": f"{WP_BASE}/pdf/ordenacion_nucleo_urbano.pdf",
        "titulo": "Ordenación del núcleo urbano — PGOU",
        "fecha": "2016-05-19",
        "tipo": "ordenación PGOU",
    },
]

RE_PREVIEW = re.compile(
    r'href="(https://villamanriquedetajo\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|cedula urban|c[eé]dula urban|ocupaci[oó]n v[ií]a p[uú]blica)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|sector|bando|unidad(?:es)? de ejecuci[oó]n|"
    r"\b(?:AA|SUS|AADA)-[\w\d\s-]+\b|cat[aá]logo|clasificaci[oó]n del suelo|ordenaci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|jurado|selecci[oó]n de personal|"
    r"matrimonio|menores|elecciones|listas electorales|europeas)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:AA|SUS|AADA)-[\w\d\s-]+)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_WP_PDF = re.compile(
    r'href="(https://villamanriquedetajo\.madrid/pdf/[^"]+\.pdf)"',
    re.I,
)


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
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _fecha_from_pdf_url(url: str) -> str | None:
    m = re.search(r"/(\d{4})-(\d{2})/", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(\d{4})", Path(url).stem)
    if m:
        y = int(m.group(1))
        if 1980 <= y <= 2035:
            return f"{y}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\baa-\d+\b", n) or re.search(r"\bsus-\d+\b", n):
        return "plan parcial"
    if re.search(r"\baada-\d+\b", n):
        return "actuación aislada"
    if "plan general" in n or "pgou" in n:
        return "planeamiento"
    if "clasificaci" in n or "ordenaci" in n:
        return "ordenación PGOU"
    if "ficha" in n:
        return "documentación PGOU"
    if "cat[aá]logo" in n or "inventario" in n:
        return "catálogo urbanístico"
    if "cap[ií]tulo" in n or "normas" in n:
        return "normativa PGOU"
    if "informaci" in n:
        return "información pública"
    if "bando" in n:
        return "bando urbanístico"
    return "urbanismo"


def _sector_ilike_parts(text: str) -> list[str]:
    low = text.lower()
    for marker in (" bocm", " aprob", " anuncio", " del pgou", " villamanrique"):
        if marker in low:
            low = low.split(marker, 1)[0]
    parts = [p for p in re.split(r"[\s,;/|()\"«»]+", low) if len(p) >= 2]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        k = p.lower()
        if k not in seen and not re.fullmatch(r"\d{4}", p):
            seen.add(k)
            out.append(p)
    return out[:10]


def _normalize_ambit_code(raw: str) -> str:
    t = re.sub(r"\s+", " ", raw.upper().strip())
    t = re.sub(r"SUS-(\d+)\s*([A-Z]{1,2})", r"SUS-\1 \2", t)
    return t


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
        t = g.get("type")
        coords = g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class VillamanriqueDeTajoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress villamanriquedetajo.madrid + sede espublico eHome + ámbitos SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.normativa_url = str(self.config.get("normativa_url") or NORMATIVA_URL)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
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
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-villamanrique-de-tajo/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

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
            doc = _strip_html(cells[0])
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": _strip_html(cells[1]) if len(cells) > 1 else "",
                    "procedimiento": _strip_html(cells[2]) if len(cells) > 2 else "",
                    "categoria": _strip_html(cells[3]) if len(cells) > 3 else "",
                    "descripcion": _strip_html(cells[4]) if len(cells) > 4 else "",
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])) if len(cells) > 5 else None,
                    "url": link_m.group(1) if link_m else self.board_url,
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board_table(html)

    def _collect_licencia_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in DEFAULT_LICENCIA_PDFS:
            pdf = item["url"]
            rows.append(
                {
                    "id": _stable_id("lic", pdf),
                    "fecha_concesion": _fecha_from_pdf_url(pdf),
                    "tipo": item["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"][:500],
                    "url": self.tramites_url,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "nota": "Modelo descargable; no concesión publicada",
                    "origen": "tramites_wp",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.normativa_url),
                "fecha_concesion": None,
                "tipo": "normativa urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Normativa municipal — PGOU y ordenanzas",
                "url": self.normativa_url,
                "source": "ayuntamiento",
                "nota": "Plan General y documentación urbanística",
                "origen": "wp_normativa",
            },
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "trámites urbanísticos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites municipales — licencias y declaraciones responsables",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Formularios de licencia de obra y primera ocupación",
                "origen": "wp_tramites",
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
                "nota": "Anuncios y edictos publicados en sede",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — presentación de trámites urbanísticos",
                "url": f"{self.sede_base}/info",
                "source": "ayuntamiento",
                "nota": "Presentación telemática de solicitudes",
                "origen": "sede",
            },
        ]

    def _collect_pgou_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_pdf(pdf: str, titulo: str, fecha: str | None, tipo: str, origen: str) -> None:
            if pdf in seen:
                return
            seen.add(pdf)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", pdf),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha or _fecha_from_pdf_url(pdf),
                "tipo": tipo,
                "url": self.normativa_url,
                "pdf_url": pdf,
                "source": "ayuntamiento",
                "origen": origen,
            }
            self._enrich_geometry(rec)
            rows.append(rec)

        for seed in PGOU_PDF_SEEDS:
            add_pdf(seed["url"], seed["titulo"], seed.get("fecha"), seed["tipo"], "pgou_seed")

        try:
            html = self._fetch(self.normativa_url)
        except urllib.error.URLError:
            return rows

        for m in RE_WP_PDF.finditer(html):
            pdf = m.group(1)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            stem = re.sub(r"[-_]+", " ", Path(name).stem).strip()
            if not RE_PROYECTO.search(stem) and "capitulo" not in stem.lower():
                continue
            add_pdf(pdf, stem.title(), "2016-05-19" if "capitulo" in stem.lower() or "pgou" in stem.lower() else None, _proyecto_tipo(stem), "pgou_wp")

        return rows

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
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

    def _load_wfs_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        cache: dict[str, dict[str, Any]] = {}
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            cache.setdefault(name.upper(), f)
            norm = _normalize_ambit_code(name)
            cache.setdefault(norm, f)
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache.setdefault(_normalize_ambit_code(code_m.group(1)), f)
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        if RE_EXCLUDE.search(title):
            return None

        cache = self._load_wfs_ambitos()
        candidates: list[tuple[float, str, dict[str, Any]]] = []

        for m in RE_AMBIT_CODE.finditer(title):
            code = _normalize_ambit_code(m.group(1))
            feat = cache.get(code) or cache.get(code.upper())
            if feat:
                candidates.append((100.0, code, feat))

        parts = _sector_ilike_parts(title)
        muni = self.wfs_municipio.replace("'", "''")
        if parts:
            pattern = "%" + "%".join(p.replace("'", "''") for p in parts[:6]) + "%"
            feats = self._wfs_query(
                f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB ILIKE '{pattern}'",
                count=10,
            )
            title_low = title.lower()
            for f in feats:
                name = str((f.get("properties") or {}).get("DS_NOMB_AMB") or "")
                if not name:
                    continue
                score = sum(5 for p in parts if p.lower() in name.lower())
                if name.lower() in title_low:
                    score += 30
                candidates.append((float(score), name, f))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (-x[0], x[1]))
        best_score, best_name, _ = candidates[0]
        if best_score < 5:
            return None

        same_name = [
            f
            for _, name, f in candidates
            if str((f.get("properties") or {}).get("DS_NOMB_AMB") or "") == best_name
        ]
        if not same_name:
            same_name = [candidates[0][2]]

        merged = _merge_geometries(same_name)
        if not merged:
            return None

        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
            f"AND DS_NOMB_AMB='{best_name.replace(chr(39), chr(39) * 2)}'"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
            ),
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": best_name,
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        rows: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([f])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": "2016-05-19",
                "tipo": _proyecto_tipo(name),
                "url": SITCM_VISOR_URL,
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

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
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
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_EXCLUDE.search(blob):
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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for rec in self._collect_licencia_pdfs():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for rec in self._collect_licencia_pdfs():
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

        for rec in self._collect_sit_ambitos():
            add(rec)
        for rec in self._collect_pgou_pdfs():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        sit_n = sum(1 for r in rows if r.get("origen") == "sit_wfs")
        pgou_n = sum(1 for r in rows if str(r.get("origen", "")).startswith("pgou"))
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_ambitos": sit_n,
            "pgou_docs": pgou_n,
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
