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

SEDE_BASE = "https://ayamonte.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
WEB_BASE = "https://ayamonte.es"
PGOM_BASE = "https://ayamontepgom.es"
URBANISMO_URL = f"{WEB_BASE}/ayuntamiento-por-areas/urbanismo-y-medioambiente/"
VISOR_URL = f"{PGOM_BASE}/visor/index14.html"
VISOR_JS_BASE = f"{PGOM_BASE}/visor/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Ayamonte"
ID_PREFIX = "ayamonte"

DEFAULT_PGOM_SEEDS: list[str] = [
    PGOM_BASE + "/",
    f"{PGOM_BASE}/noticias/",
    f"{PGOM_BASE}/rt-portfolios/plan-especial-del-casco-historico/",
    f"{PGOM_BASE}/rt-portfolios/plan-especial-del-barrio-la-villa/",
    f"{PGOM_BASE}/rt-portfolios/carta-arqueologica-de-ayamonte/",
    f"{PGOM_BASE}/rt-portfolios/otros-instrumentos/",
]

VISOR_LAYERS: list[tuple[str, str]] = [
    ("Terminomunicipal.js", "termino"),
    ("Limiteurbano.js", "clasificacion_suelo"),
    ("ATU.js", "atu"),
    ("Zonassr.js", "zonas_sr"),
    ("CATEGORIASSUELORUSTICO.js", "categorias_sr"),
    ("AGRUPACION_IRREGU.js", "agrupacion_irregular"),
    ("elemento_estructurantes.js", "elementos_estructurantes"),
    ("Movilidad.js", "movilidad"),
    ("EQ_LOCAL.js", "equipamientos"),
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia apertura)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|pou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|consulta p[uú]blica|avance|participaci[oó]n|"
    r"agenda urbana|edusi|pmus|atu|clasificaci[oó]n|visor|instrumento|"
    r"carta arqueol[oó]gica|casco hist[oó]rico|la villa)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|modificaci[oó]n de rpt|planificaci[oó]n y ordenaci[oó]n de personal|"
    r"presupuesto|junta de gobierno|actividades o cursos)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://ayamonte\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', re.I)
RE_ATU_CODE = re.compile(r"(?i)\b(ATU-[A-Z]{2,3}-[A-Z0-9]+)\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DATE_IN_PDF = re.compile(r"(20\d{6})")


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_DATE_IN_PDF.search(text or "")
    if m:
        raw = m.group(1)
        try:
            return datetime(int(raw[:4]), int(raw[4:6]), int(raw[6:8])).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _pdf_title(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).stem.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", name).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgom" in b:
        return "PGOM"
    if "pou" in b and "pgom" not in b:
        return "POU"
    if "plan especial" in b or "pe " in b:
        return "plan especial"
    if "plan parcial" in b:
        return "plan parcial"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "pmus" in b:
        return "PMUS"
    if "consulta" in b and "p" in b and "blica" in b:
        return "consulta pública"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "avance" in b:
        return "avance planeamiento"
    if "atu" in b:
        return "ámbito territorial urbanizable"
    if "clasificaci" in b and "suelo" in b:
        return "clasificación del suelo"
    if "carta arqueol" in b:
        return "carta arqueológica"
    if "agenda urbana" in b or "edusi" in b:
        return "agenda urbana"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class AyamonteAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress ayamonte.es + portal PGOM/POU + visor Leaflet + sede espublico."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or PGOM_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.pgom_base = str(self.config.get("pgom_base") or PGOM_BASE).rstrip("/")
        self.visor_url = str(self.config.get("visor_url") or VISOR_URL)
        self.pgom_seeds = [str(u) for u in (self.config.get("pgom_seeds") or DEFAULT_PGOM_SEEDS)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._geom_cache: dict[str, dict[str, Any]] | None = None
        self._termino_geom: dict[str, Any] | None = None

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ayamonte/1.0")},
        )
        if use_sede_ssl or "sedelectronica.es" in url:
            with self._opener.open(req, timeout=90) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        href = unescape(href).replace("&amp;", "&").strip()
        if href.startswith("//"):
            return "https:" + href
        return urllib.parse.urljoin(f"{(base or self.pgom_base)}/", href)

    def _parse_visor_js(self, filename: str) -> dict[str, Any] | None:
        url = f"{VISOR_JS_BASE}{filename}"
        try:
            text = self._fetch(url)
        except urllib.error.URLError:
            return None
        m = re.search(r"=\s*(\{.*\})\s*;?\s*$", text, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None

    def _feature_label(self, props: dict[str, Any]) -> str:
        for key in (
            "NOM_PD_ATU",
            "COD_PD_ATU",
            "Nombre",
            "NAMEUNIT",
            "nombre",
            "name",
            "DESCRIPCION",
        ):
            val = str(props.get(key) or "").strip()
            if val:
                return val
        return ""

    def _load_geometry_index(self) -> dict[str, dict[str, Any]]:
        if self._geom_cache is not None:
            return self._geom_cache

        cache: dict[str, dict[str, Any]] = {}
        for filename, layer_kind in VISOR_LAYERS:
            data = self._parse_visor_js(filename)
            if not data:
                continue
            for feat in data.get("features") or []:
                if not isinstance(feat, dict):
                    continue
                geom = feat.get("geometry")
                if not isinstance(geom, dict) or not geom.get("type"):
                    continue
                props = feat.get("properties") or {}
                label = self._feature_label(props)
                if not label:
                    continue
                entry = {
                    "geom_geojson": geom,
                    "geometry_source_url": f"{VISOR_JS_BASE}{filename}",
                    "layer_kind": layer_kind,
                    "label": label,
                    "props": props,
                }
                cache[label.upper()] = entry
                for key in ("COD_PD_ATU", "NOM_PD_ATU", "Nombre", "NAMEUNIT"):
                    val = str(props.get(key) or "").strip()
                    if val:
                        cache[val.upper()] = entry
                if layer_kind == "termino" and self._termino_geom is None:
                    self._termino_geom = geom

        self._geom_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str, *, fallback_termino: bool = True) -> dict[str, Any] | None:
        cache = self._load_geometry_index()
        title_up = (titulo or "").upper()

        for m in RE_ATU_CODE.finditer(titulo or ""):
            entry = cache.get(m.group(1).upper())
            if entry:
                return {
                    "geom_geojson": entry["geom_geojson"],
                    "geometry_source": "portal_geojson",
                    "geometry_source_url": entry["geometry_source_url"],
                    "coord_source": "portal_geometry_centroid",
                    "visor_layer": entry["layer_kind"],
                    "visor_label": entry["label"],
                }

        best: tuple[int, dict[str, Any]] | None = None
        for key, entry in cache.items():
            if len(key) < 4 or key in {"AYAMONTE"}:
                continue
            if key in title_up:
                score = len(key)
                if best is None or score > best[0]:
                    best = (score, entry)
        if best:
            entry = best[1]
            return {
                "geom_geojson": entry["geom_geojson"],
                "geometry_source": "portal_geojson",
                "geometry_source_url": entry["geometry_source_url"],
                "coord_source": "portal_geometry_centroid",
                "visor_layer": entry["layer_kind"],
                "visor_label": entry["label"],
            }

        if fallback_termino and self._termino_geom and re.search(
            r"(?i)pgom|pou|planeamiento|visor|avance|participaci[oó]n", titulo or ""
        ):
            return {
                "geom_geojson": self._termino_geom,
                "geometry_source": "portal_geojson",
                "geometry_source_url": f"{VISOR_JS_BASE}Terminomunicipal.js",
                "coord_source": "portal_geometry_centroid",
                "visor_layer": "termino",
                "visor_label": "Ayamonte",
            }
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if not geom:
            return
        rec.update(geom)
        cen = geometry_centroid(geom["geom_geojson"])
        if cen:
            rec.setdefault("lat", cen[0])
            rec.setdefault("lon", cen[1])

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, use_sede_ssl=True)
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

    def _collect_pgom_pdfs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.pgom_seeds:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf_url = self._abs_url(m.group(1), self.pgom_base)
                if pdf_url in seen:
                    continue
                title = _pdf_title(pdf_url)
                blob = f"{title} {pdf_url}"
                if not RE_PROYECTO.search(blob):
                    continue
                seen.add(pdf_url)
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": pdf_url,
                        "fecha": _fecha_from_blob(blob),
                        "blob": blob,
                        "page_url": page_url,
                    }
                )
        return rows

    def _collect_pgom_portfolios(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.pgom_seeds:
            if "/rt-portfolios/" not in page_url:
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
            title = _strip_html(title_m.group(1) if title_m else page_url.rstrip("/").split("/")[-1])
            title = re.sub(r"\s*-\s*PGOM.*$", "", title).strip()
            if not title or not RE_PROYECTO.search(title):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "url": page_url,
                    "fecha": None,
                    "blob": title,
                }
            )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for base, tag in ((self.pgom_base, "pgom"), (self.web_base, "web")):
            for search in ("pgom", "planeamiento", "urban", "edusi", "consulta publica"):
                api = f"{base}/wp-json/wp/v2/posts?search={urllib.parse.quote(search)}&per_page=30"
                try:
                    raw = self._fetch(api)
                    items = json.loads(raw)
                except (urllib.error.URLError, json.JSONDecodeError):
                    continue
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    title = _strip_html(str((item.get("title") or {}).get("rendered") or ""))
                    link = str(item.get("link") or "")
                    if not title or not link:
                        continue
                    blob = title
                    if not RE_PROYECTO.search(blob):
                        continue
                    rows.append(
                        {
                            "titulo": title[:500],
                            "url": link,
                            "fecha": str(item.get("date") or "")[:10] or None,
                            "blob": blob,
                            "origen": f"wp_{tag}",
                        }
                    )
        return rows

    def _collect_visor_zones(self) -> list[dict[str, Any]]:
        self._load_geometry_index()
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for filename, layer_kind in VISOR_LAYERS:
            if layer_kind == "termino":
                continue
            data = self._parse_visor_js(filename)
            if not data:
                continue
            for feat in data.get("features") or []:
                props = feat.get("properties") or {}
                label = self._feature_label(props)
                geom = feat.get("geometry")
                if not label or label.upper() in seen or not isinstance(geom, dict):
                    continue
                seen.add(label.upper())
                titulo = f"{label} — visor PGOM ({layer_kind.replace('_', ' ')})"
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", f"visor:{layer_kind}:{label}"),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": None,
                    "tipo": _proyecto_tipo(titulo),
                    "url": self.visor_url,
                    "source": "ayuntamiento",
                    "origen": "visor_capa",
                    "visor_layer": layer_kind,
                    "visor_label": label,
                    "geom_geojson": geom,
                    "geometry_source": "portal_geojson",
                    "geometry_source_url": f"{VISOR_JS_BASE}{filename}",
                    "coord_source": "portal_geometry_centroid",
                }
                cen = geometry_centroid(geom)
                if cen:
                    rec["lat"], rec["lon"] = cen
                rows.append(rec)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias de obra y actividad",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y edictos publicados en sede electrónica espublico",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier.2"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier.2",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", URBANISMO_URL),
                "fecha_concesion": None,
                "tipo": "área urbanismo y medio ambiente",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Área de Urbanismo y Medio Ambiente — web municipal",
                "url": URBANISMO_URL,
                "source": "ayuntamiento",
                "nota": "Información de trámites y enlaces a portal PGOM/POU",
                "origen": "web_urbanismo",
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
                "nota": "Requiere identificación; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "participaci")):
            return True
        if "urbanismo" in cat:
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

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "participaci" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        rec = {
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
        self._enrich_geometry(rec)
        return rec

    def _generic_to_proyecto(self, row: dict[str, Any], origen: str) -> dict[str, Any]:
        blob = row.get("blob") or row.get("titulo") or ""
        rec = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": origen,
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
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_urbanismo")),
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_pgom_pdfs():
            add(self._generic_to_proyecto(item, "pgom_pdf"))
        for item in self._collect_pgom_portfolios():
            add(self._generic_to_proyecto(item, "pgom_portfolio"))
        for item in self._collect_wp_posts():
            add(self._generic_to_proyecto(item, item.get("origen") or "wp_post"))
        for rec in self._collect_visor_zones():
            add(rec)

        visor_rec = {
            "id": _stable_id("proy", self.visor_url),
            "municipio": MUNICIPIO,
            "titulo": "Visor urbanístico PGOM/POU de Ayamonte",
            "fecha": None,
            "tipo": "visor urbanístico",
            "url": self.visor_url,
            "source": "ayuntamiento",
            "origen": "visor",
        }
        self._enrich_geometry(visor_rec)
        add(visor_rec)

        situa_rec = {
            "id": _stable_id("proy", SITUA_SEARCH),
            "municipio": MUNICIPIO,
            "titulo": "PGOM Ayamonte — consulta SITUA (Junta de Andalucía)",
            "fecha": None,
            "tipo": "planeamiento",
            "url": SITUA_SEARCH,
            "source": "ayuntamiento",
            "origen": "situa",
        }
        self._enrich_geometry(situa_rec)
        add(situa_rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "pgom_pdf": sum(1 for r in rows if r.get("origen") == "pgom_pdf"),
            "visor_capa": sum(1 for r in rows if r.get("origen") == "visor_capa"),
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
