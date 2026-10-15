from __future__ import annotations

import hashlib
import http.cookiejar
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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.roquetasdemar.es"
SEDE_BASE = "https://sede.aytoroquetas.org"
SITUA_URL = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=04079"
GEOPORTAL_URL = "https://app.dipalme.org/visor-gis/"
MUNICIPIO = "Roquetas de Mar"
ID_PREFIX = "roquetas-de-mar"
COD_INE = "04079"

_WFS_CQL_INE = urllib.parse.quote(f"cod_ine='{COD_INE}'")
WFS_SECTORS_URL = (
    "https://app.dipalme.org/geoserver/urbanismo/ows?"
    "service=WFS&version=2.0.0&request=GetFeature&"
    "typeName=urbanismo:v_siu_ambitos_o_sectores&"
    f"CQL_FILTER={_WFS_CQL_INE}&"
    "outputFormat=application/json&srsName=EPSG:4326"
)

DEFAULT_TABLON_SUBSECTIONS = ("TAB2", "TAB3", "TAB4")

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/tu-ayuntamiento/areas-municipales/urbanismo-y-patrimonio",
    f"{WEB_BASE}/tu-ayuntamiento/areas-municipales/urbanismo-y-patrimonio/ordenacion-urbanistica",
    f"{WEB_BASE}/tu-ayuntamiento/areas-municipales/urbanismo-y-patrimonio/ordenacion-urbanistica/pgou-2009",
]

RE_PDF_URBAN_NAME = re.compile(
    r"(?i)(pgou|pgom|pou|planeam|urban|innov|sector|pop[\-_]|ue[\-_]|boja|bop|"
    r"edict|estudio|memoria|normas|ordenanza|instrumento|ficha[\-_]|ce[\-_]0|situa)",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|fresado|asfaltad|pintura asfalt|corte de calle|"
    r"ampliaci[oó]n red|renovaci[oó]n de abastecimiento|acometidas domiciliarias)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|pou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|innovaci[oó]n|avance|consulta p[uú]blica|calificaci[oó]n|"
    r"ordenanza|instrumento|nnss|normas subsidiarias)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(selecci[oó]n de personal|oferta de empleo|oposici[oó]n|jornada laboral|"
    r"inmatriculaci[oó]n|estatutos|bienes y derechos|residuos|igualdad|"
    r"censo electoral|jurado|competencias propias|pol[ií]tica de seguridad|"
    r"suspensi[oó]n temporal del uso de las instalaciones|plan de prevenci[oó]n de residuos)",
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.roquetasdemar\.es)?/sites/default/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b(?:sector\s*)?(\d{1,3})\b|"
    r"\b(ue[\-\s]?\d+[a-z]?)\b|"
    r"\b(pop[\-\s]?\d+[\-\s_]?\d*)\b|"
    r"\b(s[\-\s]?\d+[a-z]?)\b|"
    r"\b(ficha[\-\s]?(?:ue|s)[\-\s]?\d+)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YM.search(url or text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "innovaci" in n and "pgou" in n:
        return "innovación PGOU"
    if "pgom" in n or "pou" in n:
        return "planeamiento"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "edicto" in n:
        return "edicto"
    if "estudio" in n:
        return "estudio urbanístico"
    return "urbanismo"


class RoquetasDeMarAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 11 (PGOU PDFs) + sede Insuit tablón JSON + WFS DipAlmería sectores."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_opc_id = str(self.config.get("tablon_opc_id") or "268")
        self.tablon_subsections = tuple(
            self.config.get("tablon_subsections") or DEFAULT_TABLON_SUBSECTIONS
        )
        self.seed_pages = list(self.config.get("seed_pages") or DEFAULT_SEED_PAGES)
        self.situa_url = str(self.config.get("situa_url") or SITUA_URL)
        self.geoportal_url = str(self.config.get("geoportal_url") or GEOPORTAL_URL)
        self.cod_ine = str(self.config.get("cod_ine") or COD_INE)
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
        self._sector_cache: list[dict[str, Any]] | None = None
        self._geom_cache: dict[str, dict[str, Any] | None] = {}
        self._tablon_warmed = False

    def _fetch(
        self,
        url: str,
        *,
        data: bytes | None = None,
        charset: str = "utf-8",
    ) -> str:
        time.sleep(self.delay_s)
        headers = {
            "User-Agent": self.config.get("user_agent", "poc-bocm-roquetas-de-mar/1.0"),
        }
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=60) as resp:
            raw = resp.read()
            enc = resp.headers.get_content_charset() or charset
            return raw.decode(enc, errors="replace")

    def _fetch_json(self, url: str, *, data: bytes | None = None) -> Any:
        text = self._fetch(url, data=data, charset="utf-8")
        return json.loads(text)

    def _abs_web(self, href: str, page: str | None = None) -> str:
        return urljoin(page or self.web_base + "/", unescape(href).replace("&amp;", "&"))

    def _abs_sede(self, href: str) -> str:
        return urljoin(f"{self.sede_base}/", unescape(href).replace("&amp;", "&"))

    def _warm_tablon_session(self) -> None:
        if self._tablon_warmed:
            return
        self._fetch(
            f"{self.sede_base}/portal/noEstatica.do?"
            f"opc_id={self.tablon_opc_id}&ent_id=1&idioma=1",
            charset="iso-8859-1",
        )
        self._tablon_warmed = True

    def _tablon_post(self, subseccion: str) -> dict[str, Any]:
        self._warm_tablon_session()
        url = f"{self.sede_base}/sede/tablonElectronico.do"
        payload = urllib.parse.urlencode(
            {
                "opcion": "consultar",
                "opc_id": self.tablon_opc_id,
                "ent_id": "1",
                "subseccion": subseccion,
            }
        ).encode()
        data = self._fetch_json(url, data=payload)
        return data if isinstance(data, dict) else {}

    def _doc_url(self, doc: dict[str, Any], sub: str) -> str:
        raw = doc.get("docUrl") or ""
        if raw:
            return self._abs_sede(raw)
        code = doc.get("docCve") or ""
        if code:
            return (
                f"{self.sede_base}/portal/verificarDocumentos.do?"
                f"ent_id=1&opcion=verificar&codigo={urllib.parse.quote(str(code))}"
                f"&subseccion={sub}&idioma=1"
            )
        return (
            f"{self.sede_base}/portal/noEstatica.do?"
            f"opc_id={self.tablon_opc_id}&ent_id=1&idioma=1"
        )

    def _collect_tablon(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        subsections = list(self.tablon_subsections)
        try:
            root = self._tablon_post("TABLONVIRTUAL")
            for s in root.get("listaSubsecciones") or []:
                code = str(s.get("cod") or "")
                if code and code not in subsections and code != "TAB1":
                    subsections.append(code)
        except urllib.error.URLError:
            pass

        for sub in subsections:
            if sub == "TAB1":
                continue
            try:
                data = self._tablon_post(sub)
            except urllib.error.URLError:
                continue
            for doc in data.get("listaDocumentos") or []:
                name = _clean_title(str(doc.get("docNom") or ""))
                if not name:
                    continue
                key = f"doc:{doc.get('docId') or doc.get('docCve') or name}"
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": name,
                        "fecha": _parse_fecha_dmy(str(doc.get("docFpu") or name)),
                        "url": self._doc_url(doc, sub),
                        "subseccion": sub,
                        "origen": "tablon",
                        "doc_cve": doc.get("docCve"),
                    }
                )
            for exp in data.get("listaExpedientes") or []:
                name = _clean_title(str(exp.get("nombre") or ""))
                if not name:
                    continue
                code = f"{exp.get('anno')}/{exp.get('codigo')}"
                key = f"exp:{exp.get('idExp') or code}"
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": name,
                        "fecha": _parse_fecha_dmy(
                            str(exp.get("fechaPublicacion") or exp.get("fechaCreacion") or "")
                        ),
                        "url": (
                            f"{self.sede_base}/portal/noEstatica.do?"
                            f"opc_id={self.tablon_opc_id}&ent_id=1&idioma=1"
                        ),
                        "subseccion": sub,
                        "origen": "tablon_expediente",
                        "expte": code,
                    }
                )
        return rows

    def _collect_drupal_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for href in RE_PDF_HREF.findall(html):
                pdf_url = self._abs_web(href, page_url)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                name = urllib.parse.unquote(Path(pdf_url).name)
                if not RE_PDF_URBAN_NAME.search(name):
                    continue
                titulo = f"Documento urbanismo — {name.rsplit('.', 1)[0]}"
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(name, pdf_url),
                        "url": pdf_url,
                        "origen": "drupal_pdf",
                    }
                )
        return rows

    def _collect_metadata_seeds(self) -> list[dict[str, Any]]:
        ordenacion = (
            f"{self.web_base}/tu-ayuntamiento/areas-municipales/"
            "urbanismo-y-patrimonio/ordenacion-urbanistica"
        )
        tablon_page = (
            f"{self.sede_base}/portal/noEstatica.do?"
            f"opc_id={self.tablon_opc_id}&ent_id=1&idioma=1"
        )
        return [
            {
                "titulo": "Ordenación urbanística — PGOU e innovación de planeamiento (web municipal)",
                "fecha": None,
                "url": ordenacion,
                "origen": "web_urbanismo",
            },
            {
                "titulo": "PGOU Roquetas de Mar — consulta SITUA (Junta de Andalucía, INE 04079)",
                "fecha": None,
                "url": self.situa_url,
                "origen": "situa",
            },
            {
                "titulo": "Visor GIS urbanismo — Diputación de Almería",
                "fecha": None,
                "url": self.geoportal_url,
                "origen": "geoportal",
            },
            {
                "titulo": "Tablón virtual — edictos y bandos (sede electrónica)",
                "fecha": None,
                "url": tablon_page,
                "origen": "tablon_portal",
            },
        ]

    def _load_sectors(self) -> list[dict[str, Any]]:
        if self._sector_cache is not None:
            return self._sector_cache
        rows: list[dict[str, Any]] = []
        wfs_url = str(self.config.get("wfs_sectors_url") or WFS_SECTORS_URL)
        try:
            data = self._fetch_json(wfs_url)
            for feat in data.get("features") or []:
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                sector = str(props.get("sector") or "").strip()
                if not sector or not isinstance(geom, dict):
                    continue
                rows.append(
                    {
                        "sector": sector,
                        "sector_norm": re.sub(r"\s+", " ", sector.upper()),
                        "geom": geom,
                    }
                )
        except (urllib.error.URLError, json.JSONDecodeError, TypeError, ValueError):
            rows = []
        rows.sort(key=lambda r: len(r["sector_norm"]), reverse=True)
        self._sector_cache = rows
        return rows

    def _sector_tokens_from_title(self, title: str) -> list[str]:
        tokens: list[str] = []
        for m in RE_SECTOR_CODE.finditer(title or ""):
            for g in m.groups():
                if g:
                    tokens.append(g.upper().replace("_", " ").replace("-", " "))
        return tokens

    def _fetch_geometry_for_title(self, title: str) -> dict[str, Any] | None:
        cache_key = title or ""
        if cache_key in self._geom_cache:
            return self._geom_cache[cache_key]

        title_up = re.sub(r"\s+", " ", (title or "").upper())
        title_compact = title_up.replace(" ", "")
        result: dict[str, Any] | None = None

        for row in self._load_sectors():
            sector_norm = row["sector_norm"]
            compact = sector_norm.replace(" ", "")
            if (
                len(sector_norm) >= 4
                and (sector_norm in title_up or compact in title_compact)
            ):
                geom = row["geom"]
                sector_escaped = row["sector"].replace("'", "''")
                cql = urllib.parse.quote(
                    f"cod_ine='{self.cod_ine}' AND sector='{sector_escaped}'"
                )
                query = (
                    "https://app.dipalme.org/geoserver/urbanismo/ows?"
                    "service=WFS&version=2.0.0&request=GetFeature&"
                    "typeName=urbanismo:v_siu_ambitos_o_sectores&"
                    f"CQL_FILTER={cql}&count=1&"
                    "outputFormat=application/json&srsName=EPSG:4326"
                )
                result = {
                    "geom_geojson": geom,
                    "geometry_crs": "EPSG:4326",
                    "geometry_source": "dipalme_wfs_sector",
                    "geometry_source_url": query,
                    "coord_source": "portal_geometry_centroid",
                    "sector_urbanistico": row["sector"],
                }
                cen = geometry_centroid(geom)
                if cen:
                    result["lat"], result["lon"] = cen
                break

        if result is None:
            for tok in self._sector_tokens_from_title(title):
                tok_norm = re.sub(r"\s+", " ", tok.upper())
                for row in self._load_sectors():
                    if tok_norm in row["sector_norm"] or tok_norm.replace(" ", "") in row[
                        "sector_norm"
                    ].replace(" ", ""):
                        geom = row["geom"]
                        result = {
                            "geom_geojson": geom,
                            "geometry_crs": "EPSG:4326",
                            "geometry_source": "dipalme_wfs_sector",
                            "geometry_source_url": WFS_SECTORS_URL,
                            "coord_source": "portal_geometry_centroid",
                            "sector_urbanistico": row["sector"],
                        }
                        cen = geometry_centroid(geom)
                        if cen:
                            result["lat"], result["lon"] = cen
                        break
                if result:
                    break

        self._geom_cache[cache_key] = result
        return result

    def _enrich_geometry(self, rec: dict[str, Any]) -> dict[str, Any]:
        if record_geometry(rec):
            return rec
        geom_fields = self._fetch_geometry_for_title(rec.get("titulo") or "")
        if geom_fields:
            rec.update(geom_fields)
        return rec

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        sub = str(row.get("subseccion") or "")
        if sub == "TAB3":
            if not RE_PROYECTO.search(blob):
                return None
        elif sub == "TAB4":
            if not RE_PROYECTO.search(blob):
                return None
        elif not RE_PROYECTO.search(blob):
            return None
        key = row.get("doc_cve") or row.get("expte") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", str(key)),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "subseccion": sub,
        }
        return self._enrich_geometry(rec)

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("titulo") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        return self._enrich_geometry(rec)

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("doc_cve") or row.get("expte") or row["url"]
        tipo = "bando obra pública" if str(row.get("subseccion")) == "TAB3" else "edicto"
        return {
            "id": _stable_id("lic", str(key)),
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

    def _licencia_info_pages(self) -> list[dict[str, Any]]:
        catalog = f"{self.sede_base}/sede/catalogoTramites.do?ent_id=1&idioma=1"
        return [
            {
                "id": _stable_id("lic", catalog),
                "fecha_concesion": None,
                "tipo": "catálogo trámites sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica Roquetas de Mar",
                "url": catalog,
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede; sin listado de concesiones",
                "origen": "catalogo_tramites",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/portal/noEstatica.do?opc_id={self.tablon_opc_id}"),
                "fecha_concesion": None,
                "tipo": "tablón virtual",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón virtual — edictos y bandos de obras",
                "url": (
                    f"{self.sede_base}/portal/noEstatica.do?"
                    f"opc_id={self.tablon_opc_id}&ent_id=1&idioma=1"
                ),
                "source": "ayuntamiento",
                "origen": "tablon_portal",
            },
        ]

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

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_metadata_seeds():
            add(self._doc_to_proyecto(item))
        for item in self._collect_drupal_pdfs():
            add(self._doc_to_proyecto(item))
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
            "info": sum(1 for r in rows if r.get("origen") in ("catalogo_tramites", "tablon_portal")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows)},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": len(rows) - before, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
            "drupal_pdf": sum(1 for r in rows if r.get("origen") == "drupal_pdf"),
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_proyectos():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "rows": len(rows),
                    "with_geometry": sum(1 for r in rows if record_geometry(r)),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "rows": len(rows),
            "added": len(rows) - before,
            "status": "ok",
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
        }
