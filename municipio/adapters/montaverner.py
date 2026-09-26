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
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.montaverner.es"
SEDE_BASE = "https://montaverner.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
ORDENANCES_URL = f"{WEB_BASE}/pagina/ordenances-municipals"
TRAMITS_URL = f"{WEB_BASE}/pagina/tramits"
MUNICIPIO = "Montaverner"
ID_PREFIX = "montaverner"
INE_COD_MUN = "46167"

GVA_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
GVA_WFS_TYPE = "Planeamiento.Zonificacion"
GVA_WFS_OFFSETS = [0, 4000, 8000, 10000, 12000]

DEFAULT_AVISO_SEEDS: tuple[str, ...] = ()

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| ambiental)?|"
    r"llic[eè]ncia|notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|venta productos)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pla especial|pla urba|convenio|"
    r"informaci[oó]n p[uú]blica|consulta (?:p[uú]blica|pr[eè]via)|expediente|proyecto|modificaci[oó]n|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|cat[aà]leg|protecci[oó]|minimitzaci[oó]|impacte territorial|"
    r"rectificaci[oó]n descriptiva|pl[aà]nol|ordenan[cç]a|construcci[oó]n|pol[ií]gon|industrial|"
    r"normes subsidi[aà]ries|zonificaci[oó])",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|nomenament|convocatoria.*empleo|"
    r"cobranza iae|padrones|padr[oó] fiscal|convenis|festiu local|processos selectius|"
    r"auxiliar administrativo|concurs disfresses|bar[oò]metre)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://montaverner\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.I)
RE_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
RE_AVISO_LINK = re.compile(
    r'href="(/(?:va|es)?/?(?:pagina-aviso|noticia-aviso)/[^"#?]+)"',
    re.I,
)
RE_DATETIME = re.compile(r'datetime="((?:19|20)\d{2}-\d{2}-\d{2})"', re.I)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_text(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _parse_fecha_iso(text)


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "pla especial" in n or "plan especial" in n:
        return "plan especial"
    if "pla urba" in n or "plan urba" in n:
        return "plan urbanístico de actuación"
    if "consulta" in n and ("pública" in n or "prèvia" in n or "previa" in n):
        return "consulta pública"
    if "catàleg" in n or "catálogo" in n:
        return "catálogo patrimonial"
    if "plànol" in n or "planol" in n:
        return "plano urbanístico"
    if "licencia ambiental" in n or "llicència ambiental" in n:
        return "licencia ambiental"
    if "pgou" in n or "planeam" in n:
        return "planeamiento"
    if "ordenan" in n:
        return "ordenanza urbanística"
    if "construcc" in n or "obra" in n:
        return "ordenanza obras"
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


class MontavernerAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 10 Portales + sede espublico gestiona + ICV GVA WFS (zonificación parcial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.ordenances_url = str(self.config.get("ordenances_url") or ORDENANCES_URL)
        self.tramits_url = str(self.config.get("tramits_url") or TRAMITS_URL)
        self.aviso_seeds = tuple(self.config.get("aviso_seeds") or DEFAULT_AVISO_SEEDS)
        geom_cfg = self.config.get("geometry") or {}
        self.gva_wfs = str(geom_cfg.get("wfs_url") or GVA_WFS)
        self.gva_type = str(geom_cfg.get("type_name") or GVA_WFS_TYPE)
        self.gva_offsets = list(geom_cfg.get("offsets") or GVA_WFS_OFFSETS)
        self._gva_cache: list[dict[str, Any]] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, retries: int = 3, timeout: int = 45) -> str:
        ua = self.config.get("user_agent", "poc-bocm-montaverner/1.0")
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": ua,
                    "Accept-Language": "ca,es;q=0.9",
                },
            )
            try:
                with self._opener.open(req, timeout=timeout) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return resp.read().decode(charset, errors="replace")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_err = exc
                if attempt + 1 < retries:
                    time.sleep(1.5 * (attempt + 1))
        raise last_err or urllib.error.URLError("fetch failed")

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
                cls = cm.group(1)
                cells[cls] = _strip_html(cm.group(2))

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

    def _discover_aviso_paths(self) -> list[str]:
        paths: set[str] = set()
        for raw in self.aviso_seeds:
            if "aviso" in raw:
                paths.add(raw)
        for seed in (self.ordenances_url, self.tramits_url):
            try:
                html = self._fetch(seed, retries=2)
            except urllib.error.URLError:
                continue
            for m in RE_AVISO_LINK.finditer(html):
                paths.add(m.group(1))
        return sorted(paths)

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-montaverner/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read()

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

            members = root.findall(".//wfs:member", ns)
            if not members:
                break

            for member in members:
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

                if props.get("cod_ine_mun") != INE_COD_MUN:
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
            "normes subsidi",
            "industrial",
            "polígon",
            "poligon",
            "modificaci",
            "ordenanza",
            "ordenança",
            "construcc",
            "zonific",
        ):
            if token in low:
                keys.append(token)
        return keys

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        keys = self._match_gva_keywords(title)
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
            if "normes subsidi" in title_low and "normes subsidi" in label:
                score += 2.0
            if score <= 0:
                continue
            candidates.append((score, feat, feat.get("source_url") or self.gva_wfs))

        if not candidates:
            return None

        candidates.sort(key=lambda x: -x[0])
        _, best_feat, source_url = candidates[0]
        geom = best_feat.get("geom")
        if "plan general" in title_low or "pgou" in title_low:
            matched = [
                f["geom"]
                for f in feats
                if "plan general" in (f.get("label") or "").lower()
                or "normes subsidi" in (f.get("label") or "").lower()
            ]
            geom = _merge_geometries(matched) or geom
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

    def _collect_ordenances(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.ordenances_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
            href, text = m.group(1), _strip_html(m.group(2))
            if not text or len(text) < 4:
                continue
            blob = f"{text} {href}"
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            if RE_BOARD_NON_URBAN.search(blob):
                continue
            if re.search(r"(?i)igualtat|igualdad|violencia de g[eè]nero", blob):
                continue
            url = self._abs_web(href)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            titulo = text if text.upper() != "ORDENANÇA/ORDENANZA" else _strip_html(
                unescape(href.split("/")[-1].replace("%20", " "))
            )[:200]
            if titulo.upper() == "ORDENANÇA/ORDENANZA":
                titulo = f"Ordenanza municipal — {href.split('/')[-1][:80]}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_text(blob),
                    "url": url,
                    "blob": blob,
                    "origen": "ordenances",
                }
            )
        return rows

    def _collect_tramits_info(self) -> list[dict[str, Any]]:
        static = [
            ("Obra Major", "licencia de obra mayor"),
            ("Obra Menor", "licencia de obra menor"),
            ("Informe Urbanistic", "informe urbanístico"),
            ("Declaració Ambiental", "declaración ambiental"),
        ]
        rows: list[dict[str, Any]] = []
        for label, tipo in static:
            rows.append(
                {
                    "id": _stable_id("lic", f"tramit:{label}"),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": f"Tràmit: {label}",
                    "url": self.tramits_url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo publicado en la web municipal (sin histórico de concesiones)",
                    "origen": "web_tramite",
                }
            )
        return rows

    def _collect_planeamiento_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        feats = self._collect_gva_features()
        labels: set[str] = set()
        for feat in feats:
            label = (feat.get("label") or "").strip()
            if not label or label in labels:
                continue
            labels.add(label)
            exp = feat.get("expediente") or ""
            titulo = f"{label} (exp. {exp})" if exp else label
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"gva:{exp}:{label}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(label),
                "url": feat.get("source_url") or self.gva_wfs,
                "source": "ayuntamiento",
                "origen": "gva_wfs",
                "expte": exp or None,
                "geom_geojson": feat["geom"],
                "geometry_source": "portal_wfs",
                "geometry_source_url": feat.get("source_url") or self.gva_wfs,
                "coord_source": "portal_geometry_centroid",
            }
            cen = geometry_centroid(feat["geom"])
            if cen:
                rec["lat"], rec["lon"] = cen[0], cen[1]
            rows.append(rec)
        return rows

    def _ordenance_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "ordenances",
        }
        self._enrich_geometry(rec)
        return rec

    def _parse_aviso_page(self, path: str) -> dict[str, Any] | None:
        url = self._abs_web(path)
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None

        h1 = RE_H1.search(html)
        title_m = RE_TITLE.search(html)
        titulo = _clean_title(h1.group(1) if h1 else (title_m.group(1) if title_m else path))
        titulo = re.sub(r"\s*\|.*Ajuntament.*$", "", titulo, flags=re.I).strip()
        if not titulo or "no trobada" in titulo.lower() or "not found" in titulo.lower():
            return None

        fecha = None
        dt_m = RE_DATETIME.search(html)
        if dt_m:
            fecha = dt_m.group(1)
        if not fecha:
            fecha = _fecha_from_text(html[:8000])

        pdf_urls = [self._abs_web(m.group(1)) for m in RE_PDF.finditer(html)]
        blob = f"{titulo} {path} {' '.join(pdf_urls)}"

        return {
            "titulo": titulo,
            "fecha": fecha,
            "url": url,
            "pdf_urls": pdf_urls,
            "blob": blob,
            "origen": "drupal_aviso",
            "path": path,
        }

    def _collect_drupal_avisos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in self._discover_aviso_paths():
            if path in seen:
                continue
            seen.add(path)
            item = self._parse_aviso_page(path)
            if item:
                rows.append(item)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tauler d'anuncis — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos y anuncios publicados en espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias de obra y comunicaciones previas vía sede (sin histórico público)",
                "origen": "sede_tramite",
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
                "nota": "Requiere identificación Cl@ve; sin listado público",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.tramits_url),
                "fecha_concesion": None,
                "tipo": "trámites obra y urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tràmits municipals — obra i urbanisme",
                "url": self.tramits_url,
                "source": "ayuntamiento",
                "nota": "Obra major/menor, informe urbanístic y declaración ambiental",
                "origen": "web_tramite",
            },
        ]
        pages.extend(self._collect_tramits_info())
        return pages

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "llicència")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _aviso_is_licencia(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob)) and not (
            RE_PROYECTO.search(blob) and "ambiental" not in blob.lower()
        )

    def _aviso_is_proyecto(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        if RE_PROYECTO.search(blob):
            return True
        if RE_LICENCIA.search(blob) and "ambiental" in blob.lower():
            return True
        return False

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
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _aviso_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._aviso_is_licencia(row):
            return None
        blob = row.get("blob") or ""
        tipo = "licencia ambiental" if "ambiental" in blob.lower() else "licencia"
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc:
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
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _aviso_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._aviso_is_proyecto(row):
            return None
        blob = row.get("blob") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_drupal_avisos():
            rec = self._aviso_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "drupal": sum(1 for r in rows if r.get("origen") == "drupal_aviso"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite")),
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
        for item in self._collect_drupal_avisos():
            rec = self._aviso_to_licencia(item)
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

        for item in self._collect_board():
            rec = self._board_to_proyecto(item)
            if rec:
                self._enrich_geometry(rec)
            add(rec)
        for item in self._collect_drupal_avisos():
            add(self._aviso_to_proyecto(item))
        for item in self._collect_ordenances():
            add(self._ordenance_to_proyecto(item))
        for seed in self._collect_planeamiento_seeds():
            add(seed)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "drupal": sum(1 for r in rows if r.get("origen") == "drupal_aviso"),
            "ordenances": sum(1 for r in rows if r.get("origen") == "ordenances"),
            "gva_wfs": sum(1 for r in rows if r.get("origen") == "gva_wfs"),
            "with_geometry": with_geom,
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
