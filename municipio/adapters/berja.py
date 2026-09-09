from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import unicodedata
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

DIPALME_BASE = "https://www.dipalme.org/Servicios/cmsdipro/index.nsf"
PAGE_PARAM = "Berja"
MUNICIPIO = "Berja"
ID_PREFIX = "berja"
COD_INE = "04029"

TABLON_ROL_URL = f"{DIPALME_BASE}/tablon_view_entidad_rol.xsp?p={PAGE_PARAM}"
NOTICIAS_OBRAS_URL = (
    f"{DIPALME_BASE}/noticias_view_entidad_categoria.xsp?p={PAGE_PARAM}&cat=OBRAS+P%C3%9ABLICAS"
)
NORMMAS_URL = f"{DIPALME_BASE}/tablon_view_entidad_categoria1.xsp?p={PAGE_PARAM}&cat=Normas"
INDEX_URL = f"{DIPALME_BASE}/index.xsp?p={PAGE_PARAM}"

_WFS_CQL_INE = urllib.parse.quote(f"cod_ine='{COD_INE}'")
WFS_SECTORS_URL = (
    "https://app.dipalme.org/geoserver/urbanismo/ows?"
    "service=WFS&version=2.0.0&request=GetFeature&"
    "typeName=urbanismo:v_siu_ambitos_o_sectores&"
    f"CQL_FILTER={_WFS_CQL_INE}&"
    "outputFormat=application/json&srsName=EPSG:4326"
)

SEED_TABLON_DOCS: list[str] = [
    "10E2B4207B3C6559C125851A00437BB2",  # NNSS aprobadas definitivamente
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|concesi[oó]n de licencia|otorgamiento de licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|pol[ií]gono|"
    r"cambio de uso|normativa urban|delimitaci[oó]n|reurbaniz|colector|asfalt|obra|"
    r"urbanizaci[oó]n|licencia urban)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|subvenci[oó]n deportiv|fiestas|mercadillo|"
    r"contrataci[oó]n de (?:suministro|servicio)|procedimiento contrato menor|"
    r"acta (?:junta de gobierno|pleno|tribunal)|mesa de contrataci[oó]n)",
)
RE_TABLON_ITEM = re.compile(
    r'<div class="tablon-container">.*?'
    r'<a href="([^"]*tablon\.xsp\?[^"]+)"[^>]*title="([^"]*)"[^>]*>([^<]*)</a>.*?'
    r"<p>([^<]*)</p>.*?<p>([^<]*)</p>",
    re.I | re.S,
)
RE_NOTICIA_ITEM = re.compile(
    r'<span>(\d{1,2}/\d{1,2}/\d{4})</span><span class="titulo">'
    r'<a href="([^"]*noticias\.xsp\?[^"]+)"[^>]*title="([^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", t).strip().upper()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()[:500]


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
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "nnss" in b or "normas subsidiarias" in b:
        return "NNSS / planeamiento"
    if "sector" in b and ("urban" in b or "ue " in b):
        return "sector urbanístico"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "modificaci" in b and "puntual" in b:
        return "modificación puntual"
    if "plan parcial" in b:
        return "plan parcial"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "colector" in b or "saneamiento" in b:
        return "obra infraestructura"
    if "reurbaniz" in b:
        return "reurbanización"
    if "licencia" in b:
        return "licencia urbanística"
    if "obra" in b:
        return "obra municipal"
    return "urbanismo"


class BerjaAyuntamientoAdapter(AyuntamientoAdapter):
    """CMSDIP-PRO Diputación Almería (dipalme.org, p=Berja): tablón + noticias obras + WFS sectores."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or DIPALME_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.max_noticias_pages = int(self.config.get("max_noticias_pages", 5))
        self.fetch_retries = int(self.config.get("fetch_retries", 3))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._sector_cache: list[dict[str, Any]] | None = None
        self._geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str, data: dict[str, str] | None = None) -> str:
        last_err: Exception | None = None
        for attempt in range(self.fetch_retries):
            time.sleep(self.delay_s * (attempt + 1))
            try:
                if data:
                    body = urllib.parse.urlencode(data).encode()
                    req = urllib.request.Request(
                        url,
                        data=body,
                        headers={
                            "User-Agent": self.config.get("user_agent", "poc-bocm-berja/1.0"),
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                    )
                else:
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": self.config.get("user_agent", "poc-bocm-berja/1.0")},
                    )
                with urllib.request.urlopen(req, timeout=90, context=self._ssl_ctx) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return resp.read().decode(charset, errors="replace")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_err = exc
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-berja/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90, context=self._ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_url(self, href: str, page_url: str = DIPALME_BASE) -> str:
        return urljoin(page_url, unescape(href))

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

    def _xsp_viewid(self, html: str) -> str | None:
        m = re.search(r'id="view:_id6__VUID"[^>]*value="([^"]+)"', html)
        return m.group(1) if m else None

    def _xsp_post(self, url: str, html: str, submit_id: str, extra: dict[str, str] | None = None) -> str:
        vuid = self._xsp_viewid(html)
        if not vuid:
            return html
        data: dict[str, str] = {
            "$$viewid": vuid,
            "view:_id6": "view:_id6",
            "$$xspsubmitid": submit_id,
            "$$xspexecid": submit_id,
        }
        if extra:
            data.update(extra)
        try:
            return self._fetch(url, data)
        except urllib.error.URLError:
            return html

    def _parse_tablon_items(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for href, title_attr, title_text, org, categoria in RE_TABLON_ITEM.findall(html):
            titulo = _clean_title(title_attr or title_text)
            url = self._abs_url(href)
            rows.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "fecha": None,
                    "categoria": _clean_title(categoria),
                    "blob": f"{titulo} {categoria} {org}",
                }
            )
        return rows

    def _parse_noticias_items(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for fecha_raw, href, title in RE_NOTICIA_ITEM.findall(html):
            url = self._abs_url(href)
            if url in seen:
                continue
            seen.add(url)
            titulo = _clean_title(title)
            rows.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "categoria": "OBRAS PÚBLICAS",
                    "blob": titulo,
                }
            )
        return rows

    def _collect_tablon_rol(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_ROL_URL)
        except urllib.error.URLError:
            return []
        return self._parse_tablon_items(html)

    def _collect_noticias_obras(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(NOTICIAS_OBRAS_URL)
        except urllib.error.URLError:
            return rows

        def add_items(page_html: str) -> None:
            for item in self._parse_noticias_items(page_html):
                if item["url"] not in seen:
                    seen.add(item["url"])
                    rows.append(item)

        add_items(html)
        pager_links = re.findall(
            r'id="(view:_id6:pager2__Group__lnk__\d+)"', html
        )
        for link_id in pager_links[: self.max_noticias_pages - 1]:
            page_html = self._xsp_post(NOTICIAS_OBRAS_URL, html, link_id)
            if page_html == html:
                continue
            html = page_html
            add_items(html)
        return rows

    def _fetch_tablon_document(self, document_id: str) -> dict[str, Any] | None:
        url = f"{DIPALME_BASE}/tablon.xsp?p={PAGE_PARAM}&documentId={document_id}"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None
        title_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        titulo = _clean_title(title_m.group(1)) if title_m else document_id
        pub = re.search(r"Publicado:\s*(\d{2}/\d{2}/\d{4})", html)
        cat_m = re.search(
            r"<p>([^<]*(?:Urban|Licen|Territor|Planeam|Normas)[^<]*)</p>", html, re.I
        )
        return {
            "titulo": titulo,
            "url": url,
            "fecha": _parse_fecha_dmy(pub.group(1)) if pub else _fecha_from_blob(titulo),
            "categoria": _clean_title(cat_m.group(1)) if cat_m else "Planeamiento Urbanístico",
            "blob": titulo,
        }

    def _collect_seed_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for doc_id in SEED_TABLON_DOCS:
            item = self._fetch_tablon_document(doc_id)
            if item:
                rows.append(item)
        return rows

    def _load_sectors(self) -> list[dict[str, Any]]:
        if self._sector_cache is not None:
            return self._sector_cache
        rows: list[dict[str, Any]] = []
        try:
            data = self._fetch_json(WFS_SECTORS_URL)
            for feat in data.get("features") or []:
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                sector = str(props.get("sector") or "").strip()
                if not sector or not isinstance(geom, dict):
                    continue
                rows.append(
                    {
                        "sector": sector,
                        "sector_norm": _norm_text(sector),
                        "geom": geom,
                        "clase_suelo": props.get("clase_suelo"),
                        "uso_dominante": props.get("uso_dominante"),
                    }
                )
        except (urllib.error.URLError, json.JSONDecodeError, TypeError, ValueError):
            rows = []
        rows.sort(key=lambda r: len(r["sector_norm"]), reverse=True)
        self._sector_cache = rows
        return rows

    def _fetch_geometry_for_title(self, title: str) -> dict[str, Any] | None:
        cache_key = _norm_text(title)
        if cache_key in self._geom_cache:
            return self._geom_cache[cache_key]

        title_norm = _norm_text(title)
        result: dict[str, Any] | None = None
        for row in self._load_sectors():
            sector_norm = row["sector_norm"]
            if len(sector_norm) < 3:
                continue
            if sector_norm in title_norm or re.search(
                rf"\b{re.escape(sector_norm)}\b", title_norm
            ):
                geom = row["geom"]
                sector_escaped = row["sector"].replace("'", "''")
                cql = urllib.parse.quote(
                    f"cod_ine='{COD_INE}' AND sector='{sector_escaped}'"
                )
                query = (
                    "https://app.dipalme.org/geoserver/urbanismo/ows?"
                    "service=WFS&version=2.0.0&request=GetFeature&"
                    "typeName=urbanismo:v_siu_ambitos_o_sectores&"
                    f"CQL_FILTER={cql}&"
                    "count=1&outputFormat=application/json&srsName=EPSG:4326"
                )
                result = {
                    "geom_geojson": geom,
                    "geometry_source": "dipalme_wfs_sector",
                    "geometry_source_url": query,
                    "coord_source": "portal_geometry_centroid",
                    "sector_urbanistico": row["sector"],
                }
                centroid = geometry_centroid(geom)
                if centroid:
                    result["lat"], result["lon"] = centroid
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

    def _sector_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in self._load_sectors():
            sector = row["sector"]
            titulo = f"Sector urbanístico {sector} (Berja)"
            url = "https://app.dipalme.org/visor-gis/"
            geom = row["geom"]
            sector_escaped = sector.replace("'", "''")
            cql = urllib.parse.quote(f"cod_ine='{COD_INE}' AND sector='{sector_escaped}'")
            query = (
                "https://app.dipalme.org/geoserver/urbanismo/ows?"
                "service=WFS&version=2.0.0&request=GetFeature&"
                "typeName=urbanismo:v_siu_ambitos_o_sectores&"
                f"CQL_FILTER={cql}&count=1&outputFormat=application/json&srsName=EPSG:4326"
            )
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"wfs-sector-{sector}"),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": None,
                "tipo": "sector urbanístico",
                "url": url,
                "source": "ayuntamiento",
                "geom_geojson": geom,
                "geometry_source": "dipalme_wfs_sector",
                "geometry_source_url": query,
                "coord_source": "portal_geometry_centroid",
                "sector_urbanistico": sector,
                "clase_suelo": row.get("clase_suelo"),
                "uso_dominante": row.get("uso_dominante"),
            }
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            rows.append(rec)
        return rows

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item.get("titulo") or ""
        if RE_TABLON_SKIP.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        url = item["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"][:500],
            "fecha": item.get("fecha") or _fecha_from_blob(blob),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
        }
        if item.get("categoria"):
            rec["categoria_tablon"] = item["categoria"]
        return self._enrich_geometry(rec)

    def _item_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        url = item["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": item.get("fecha") or _fecha_from_blob(blob),
            "tipo": "licencia urbanística",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["titulo"][:500],
            "url": url,
            "source": "ayuntamiento",
        }
        geom_fields = self._fetch_geometry_for_title(item.get("titulo") or "")
        if geom_fields:
            rec.update(geom_fields)
        return rec

    def _collect_licencias_info(self) -> list[dict[str, Any]]:
        seeds = [
            INDEX_URL,
            f"{DIPALME_BASE}/informacion.xsp?p={PAGE_PARAM}&documentId=912A3EBCB6B926CAC125854B0023CC38",
            NORMMAS_URL,
        ]
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in seeds:
            if seed in seen:
                continue
            seen.add(seed)
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            title_m = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
            title = _clean_title(title_m.group(1)) if title_m else "Trámites sede electrónica"
            rows.append(
                {
                    "id": _stable_id("lic", seed),
                    "fecha_concesion": None,
                    "tipo": "trámite urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": seed,
                    "source": "ayuntamiento",
                    "nota": "Página informativa; licencias se publican en tablón (Autorizaciones y Licencias)",
                }
            )
            for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{8,200})</a>', html, re.I):
                href, link_title = m.group(1), _clean_title(m.group(2))
                if not RE_LICENCIA.search(link_title):
                    continue
                url = self._abs_url(href, seed)
                if url in seen or not url.startswith("http"):
                    continue
                seen.add(url)
                rows.append(
                    {
                        "id": _stable_id("lic", url),
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": link_title[:500],
                        "url": url,
                        "source": "ayuntamiento",
                        "nota": "Trámite informativo en sede Diputación",
                    }
                )
        return rows

    def _collect_raw_items(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        items: list[dict[str, Any]] = []

        def add_many(rows: list[dict[str, Any]]) -> None:
            for row in rows:
                url = row.get("url") or ""
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    items.append(row)

        add_many(self._collect_tablon_rol())
        add_many(self._collect_noticias_obras())
        add_many(self._collect_seed_documents())
        return items

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_raw_items():
            add(self._item_to_proyecto(item))
        for rec in self._sector_proyectos():
            add(rec)
        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_raw_items():
            add(self._item_to_licencia(item))
        for rec in self._collect_licencias_info():
            add(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}
