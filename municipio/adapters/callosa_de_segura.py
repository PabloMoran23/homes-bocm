from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.callosadesegura.es"
SEDE_BASE = "https://callosadesegura.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board//"
PGOU_URL = f"{WEB_BASE}/el-ayuntamiento/concejalias/obras-y-servicios/plan-general-ordenacion-urbana/"
MUNICIPIO = "Callosa de Segura"
ID_PREFIX = "callosa-de-segura"
INE_COD_MUN = "03009"

GVA_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
GVA_WFS_TYPE = "Planeamiento.Zonificacion"
GVA_WFS_OFFSETS = [0, 2000, 4000, 6000, 8000, 10500, 13500]

DEFAULT_WP_SEEDS: tuple[str, ...] = (
    "/el-ayuntamiento/concejalias/obras-y-servicios/plan-general-ordenacion-urbana/",
    "/el-ayuntamiento/concejalias/urbanismo-y-accesibilidad-urbana/",
    "/el-ayuntamiento/agenda-urbana/",
    "/el-ayuntamiento/concejalias/obras-y-servicios/retirada-del-estudio-de-integracion-paisajistica/",
    "/obras-e-infraestructuras/",
)

DEFAULT_ETRAMITES: tuple[str, ...] = (
    "/el-ayuntamiento/e-tramites-ayuntamiento/declaracion-responsable-para-la-ejecucion-de-obras-menores/",
    "/el-ayuntamiento/e-tramites-ayuntamiento/declaracion-responsable-de-primera-ocupacion-de-viviendas-de-nueva-planta-en-suelo-urbano/",
    "/el-ayuntamiento/e-tramites-ayuntamiento/declaracion-responsable-de-segunda-ocupacion-de-viviendas-locales-en-suelo-urbano/",
    "/el-ayuntamiento/e-tramites-ayuntamiento/solicitud-de-certificado-de-compatibilidad-urbanistica/",
    "/el-ayuntamiento/e-tramites-ayuntamiento/solicitud-de-informacion-urbanistica/",
    "/el-ayuntamiento/e-tramites-ayuntamiento/solicitud-de-licencia-ambiental-ley-6-2014/",
    "/el-ayuntamiento/e-tramites-ayuntamiento/solicitud-de-licencia-de-parcelacion-segregacion-y-division-de-terrenos-o-declaracion-de-innecesariedad/",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|parcelaci[oó]n|segregaci[oó]n|certificado.*urban|"
    r"licencia de actividad|hosteler)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|integraci[oó]n)|memoria|planos|edicto|"
    r"aprobaci[oó]n|expropiaci[oó]n|parcela|suelo|sector|ordenanza|huerto solar|"
    r"agenda urbana|homologaci[oó]n)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvencion|padrones|bop\b|boe\b|dogv\b|pleno|jgl|empleo|bolsa de trabajo|"
    r"comisi[oó]n especial de cuentas|ley del tribunal del jurado)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://callosadesegura\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.I)
RE_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_WP_LINK = re.compile(
    r'href="((?:https://www\.callosadesegura\.es)?/[^"#?]+)"',
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
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and ("pgou" in n or "plan general" in n):
        return "modificación PGOU"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "expropiaci" in n:
        return "expropiación"
    if "licencia" in n and "ambiental" in n:
        return "licencia ambiental"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "edicto" in n:
        return "edicto"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "estudio" in n and "integraci" in n:
        return "estudio integración paisajística"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.split() if x.strip()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lng = nums[i], nums[i + 1]
        ring.append([lng, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _merge_geometries(geoms: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for g in geoms:
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


def _pdf_title(url: str) -> str:
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    name = name.replace("-", " ").replace("_", " ")
    return name[:200] or "documento PGOU"


class CallosaDeSeguraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress callosadesegura.es + sede espublico gestiona + ICV GVA WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.wp_seeds = tuple(self.config.get("wp_seeds") or DEFAULT_WP_SEEDS)
        self.etramites = tuple(self.config.get("etramites") or DEFAULT_ETRAMITES)
        geom_cfg = self.config.get("geometry") or {}
        self.gva_wfs = str(geom_cfg.get("wfs_url") or GVA_WFS)
        self.gva_type = str(geom_cfg.get("type_name") or GVA_WFS_TYPE)
        self.gva_offsets = list(geom_cfg.get("offsets") or GVA_WFS_OFFSETS)
        self.ine_cod_mun = str(geom_cfg.get("ine_cod_mun") or INE_COD_MUN)
        self._gva_cache: list[dict[str, Any]] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-callosa-de-segura/1.0")},
        )
        ctx = self._ssl_ctx if url.startswith("https://") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-callosa-de-segura/1.0")},
        )
        ctx = self._ssl_ctx if url.startswith("https://") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read()

    def _abs_web(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.web_base}/", href))

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento or documento in ("Documento",):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _parse_wp_page(self, path: str) -> dict[str, Any] | None:
        url = self._abs_web(path)
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None

        h1 = RE_H1.search(html)
        title_m = RE_TITLE.search(html)
        titulo = _strip_html(h1.group(1) if h1 else (title_m.group(1) if title_m else path))
        titulo = re.sub(r"\s*\|.*Callosa.*$", "", titulo, flags=re.I).strip()
        if not titulo:
            return None

        pdf_urls = sorted({self._abs_web(m.group(1)) for m in RE_PDF.finditer(html)})
        child_links: list[str] = []
        for m in RE_WP_LINK.finditer(html):
            href = self._abs_web(m.group(1))
            if href.startswith(self.web_base) and any(
                k in href.lower()
                for k in ("urban", "planeam", "pgou", "licenc", "obra", "agenda-urbana", "impresos/pgou")
            ):
                child_links.append(href)

        return {
            "titulo": titulo[:500],
            "fecha": _fecha_from_blob(html[:12000]),
            "url": url,
            "pdf_urls": pdf_urls,
            "child_links": child_links[:40],
            "blob": f"{titulo} {path} {' '.join(pdf_urls)}",
            "origen": "wordpress",
            "path": path,
        }

    def _collect_wp_pages(self) -> list[dict[str, Any]]:
        seen_paths: set[str] = set()
        rows: list[dict[str, Any]] = []
        for path in (*self.wp_seeds, *self.etramites):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            item = self._parse_wp_page(path)
            if item:
                rows.append(item)
        return rows

    def _collect_pgou_proyectos(self) -> list[dict[str, Any]]:
        item = self._parse_wp_page(
            "/el-ayuntamiento/concejalias/obras-y-servicios/plan-general-ordenacion-urbana/"
        )
        if not item:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        main = {
            "id": _stable_id("proy", self.pgou_url),
            "municipio": MUNICIPIO,
            "titulo": "Plan General de Ordenación Urbana — Callosa de Segura",
            "fecha": item.get("fecha"),
            "tipo": "PGOU",
            "url": self.pgou_url,
            "source": "ayuntamiento",
            "origen": "wordpress_pgou",
        }
        rows.append(main)
        seen.add(main["id"])

        for pdf in item.get("pdf_urls") or []:
            rec = {
                "id": _stable_id("proy", pdf),
                "municipio": MUNICIPIO,
                "titulo": f"PGOU — {_pdf_title(pdf)}",
                "fecha": _fecha_from_blob(pdf),
                "tipo": "PGOU documentación",
                "url": pdf,
                "source": "ayuntamiento",
                "origen": "wordpress_pgou_pdf",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_gva_features(self) -> list[dict[str, Any]]:
        if self._gva_cache is not None:
            return self._gva_cache

        feats: list[dict[str, Any]] = []
        seen: set[str] = set()
        ns = {"wfs": "http://www.opengis.net/wfs/2.0", "gml": "http://www.opengis.net/gml"}

        for start in self.gva_offsets:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "request": "GetFeature",
                    "version": "2.0.0",
                    "typeName": self.gva_type,
                    "outputFormat": "GML3",
                    "srsName": "EPSG:4326",
                    "count": "500",
                    "startIndex": str(start),
                }
            )
            url = f"{self.gva_wfs}?{params}"
            try:
                raw = self._fetch_bytes(url, timeout=120)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                continue

            for member in root.findall(".//wfs:member", ns):
                feat_el = member[0]
                props: dict[str, str] = {}
                geom = None
                for child in feat_el:
                    tag = child.tag.split("}")[-1]
                    if tag == "msGeometry":
                        pos = child.find(".//gml:posList", ns)
                        if pos is not None and pos.text:
                            geom = _gml_poslist_to_polygon(pos.text)
                    else:
                        props[tag] = (child.text or "").strip()

                if props.get("cod_ine_mun") != self.ine_cod_mun:
                    continue
                if not geom:
                    continue

                label = props.get("denominaci") or props.get("expediente") or ""
                key = f"{props.get('expediente')}:{label}"
                if key in seen:
                    continue
                seen.add(key)
                feats.append(
                    {
                        "label": label,
                        "expediente": props.get("expediente") or "",
                        "geom": geom,
                        "source_url": (
                            f"{self.gva_wfs}?service=WFS&request=GetFeature&"
                            f"startIndex={start}&count=500"
                        ),
                    }
                )

        self._gva_cache = feats
        return feats

    def _match_gva_keywords(self, title: str) -> list[str]:
        low = (title or "").lower()
        keys: list[str] = []
        for token in (
            "plan general",
            "pgou",
            "clerigo",
            "clérigo",
            "castellar",
            "solana",
            "sargento",
            "plan parcial",
            "sector",
            "industrial",
            "modificaci",
        ):
            if token in low:
                keys.append(token)
        return keys

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        keys = self._match_gva_keywords(title)
        if not keys and "pgou" not in title.lower() and "plan general" not in title.lower():
            return None

        feats = self._collect_gva_features()
        if not feats:
            return None

        title_low = title.lower()
        candidates: list[tuple[float, dict[str, Any], str]] = []
        for feat in feats:
            label = (feat.get("label") or "").lower()
            score = 0.0
            for k in keys:
                if k in label or k in title_low:
                    score += 1.0
            if "plan general" in title_low and "plan general" in label:
                score += 2.0
            if score <= 0 and ("pgou" in title_low or "plan general" in title_low):
                if "plan general" in label or feat.get("expediente") == "00000000":
                    score = 0.5
            if score <= 0:
                continue
            candidates.append((score, feat, feat.get("source_url") or self.gva_wfs))

        if not candidates:
            return None

        candidates.sort(key=lambda x: -x[0])
        best_score, best_feat, source_url = candidates[0]
        matched = [f["geom"] for f in feats if f.get("geom")]
        if "plan general" in title_low or "pgou" in title_low:
            pg_geoms = [
                f["geom"]
                for f in feats
                if "plan general" in (f.get("label") or "").lower()
                or f.get("expediente") == "00000000"
            ]
            if pg_geoms:
                matched = pg_geoms
        geom = _merge_geometries(matched) or best_feat.get("geom")
        if not geom:
            return None

        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": source_url,
            "coord_source": "portal_geometry_centroid",
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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
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
                "nota": "Edictos publicados en callosadesegura.sedelectronica.es",
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
                "nota": "Requiere identificación; sin listado público de concesiones",
                "origen": "sede_tramite",
            },
        ]
        for path in self.etramites:
            url = self._abs_web(path)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia/urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")[:200],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Ficha e-trámite WordPress; sin registro público de concesiones",
                    "origen": "wordpress_tramite",
                }
            )
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "expropiaci")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "expropiaci" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _wp_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or ""
        if item.get("path", "").endswith("/plan-general-ordenacion-urbana/"):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                clean = {k: v for k, v in row.items() if v is not None}
                f.write(json.dumps(clean, ensure_ascii=False) + "\n")

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
            "tramites": sum(1 for r in rows if r.get("origen") == "wordpress_tramite"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                self._enrich_geometry(rec)
                rows.append(rec)

        for rec in self._collect_pgou_proyectos():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_wp_pages():
            add(self._wp_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pgou": sum(1 for r in rows if str(r.get("origen", "")).startswith("wordpress_pgou")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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
