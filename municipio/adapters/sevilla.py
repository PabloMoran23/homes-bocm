from __future__ import annotations

import hashlib
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

WEB_BASE = "https://www.urbanismosevilla.org"
EXTRANET_BASE = "https://extranet.urbanismosevilla.org"
MUNICIPIO = "Sevilla"
ID_PREFIX = "sevilla"

NN_DD_INDEX = (
    f"{WEB_BASE}/areas/planeamiento-desarrollo-urbanistico/"
    "planeamiento-en-tramite-segun-nn-dd-de-la-documentacion-electronica-de-los-"
    "instrumentos-de-ordenacion-urbanistica-de-andalucia/"
)
NN_DD_PREFIX = NN_DD_INDEX.rstrip("/")

CALLEJERO_SEARCH = "https://map4.urbanismosevilla.org/GIS_GIE/GIE_EXP/TR_Callejero_ORA_json.ashx"
CDAU_PORTALES = (
    "https://map5.urbanismosevilla.org/sci/rest/services/Callejero/Callejero_CDAU/MapServer/1"
)
CDAU_REFERER = "https://map4.urbanismosevilla.org/GIS_GIE/CAU/callejero/Embedded.aspx"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/planeamiento/planeamiento-en-tramite-nn-dd-junta-de-andalucia",
    NN_DD_INDEX,
    f"{WEB_BASE}/areas/planeamiento-desarrollo-urbanistico/planeamiento-en-tramite",
    f"{WEB_BASE}/areas/planeamiento-desarrollo-urbanistico/planeamiento-en-desarrollo-1",
    f"{WEB_BASE}/areas/planeamiento-desarrollo-urbanistico/seccion-de-convenios-urbanisticos",
    f"{WEB_BASE}/planeamiento/plan-general-vigente",
    f"{WEB_BASE}/geo-informacion/portal-de-datosabiertos",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|inspecci[oó]n t[eé]cnica|ite\b|velador|calicata|vado)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|loua|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|"
    r"boja|edicto|aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|"
    r"sector|nnss|sunp|supi|peri|urbaniz|delimitaci[oó]n|actuaci[oó]n|nn\.dd)",
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_STREET_NUM = re.compile(
    r"(?i)(?:calle|avda\.?|avenida|av\.?|plaza|paseo|camino|glorieta)\s+"
    r"(?:de\s+|del\s+|la\s+)?([^,.\n]+?)(?:\s+n[oº°\.]?\s*(\d+))?",
)
RE_KNOWN_STREET = re.compile(
    r"(?i)\b(luis montoto|kansas city|genaro parlade|molini|su eminencia)\b[^0-9]*(\d+)?",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


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
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _slug_to_title(slug: str) -> str:
    t = slug.replace("-", " ").strip()
    return t[:1].upper() + t[1:] if t else slug


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if re.search(r"(?i)\be[\.\s-]?d[\.\s-]?\b", b) or "estudio de detalle" in b:
        return "estudio de detalle"
    if re.search(r"(?i)\be[\.\s-]?o[\.\s-]?\b", b) or "estudio de ordenaci" in b:
        return "estudio de ordenación"
    if "plan parcial" in b or " pp " in b or "dbp" in b:
        return "plan parcial"
    if "plan especial" in b or "sunp" in b:
        return "plan especial"
    if "modificaci" in b and "puntual" in b:
        return "modificación puntual PGOU"
    if "convenio" in b:
        return "convenio urbanístico"
    if "urbaniz" in b:
        return "proyecto de urbanización"
    if "nnss" in b or "nn.dd" in b:
        return "instrumento en trámite"
    if "pgou" in b or "loua" in b or "plan general" in b:
        return "PGOU"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    return "urbanismo"


class SevillaAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone urbanismosevilla.org (NN.DD planeamiento) + oficina virtual extranet + CDUS callejero."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.nn_dd_index = str(self.config.get("nn_dd_index") or NN_DD_INDEX)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, referer: str | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {
            "User-Agent": self.config.get("user_agent", "Mozilla/5.0 poc-bocm-sevilla/1.0"),
        }
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=90, context=self._ssl_ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str, *, referer: str | None = None) -> Any:
        raw = self._fetch(url, referer=referer or CDAU_REFERER)
        return json.loads(raw)

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or f"{WEB_BASE}/", unescape(href))

    def _collect_nn_dd_urls(self) -> list[str]:
        try:
            html = self._fetch(self.nn_dd_index)
        except urllib.error.URLError:
            html = ""
        urls: set[str] = set()
        prefix = self.nn_dd_index.rstrip("/")
        for page in [self.nn_dd_index, f"{WEB_BASE}/planeamiento/planeamiento-en-tramite-nn-dd-junta-de-andalucia"]:
            if page != self.nn_dd_index:
                try:
                    html = self._fetch(page)
                except urllib.error.URLError:
                    continue
            for m in re.finditer(
                r'href="(https://www\.urbanismosevilla\.org/areas/planeamiento-desarrollo-urbanistico/'
                r'planeamiento-en-tramite-segun-nn-dd[^"]+)"',
                html,
            ):
                u = m.group(1).split("?")[0].rstrip("/")
                if u == prefix or "sendto_form" in u:
                    continue
                urls.add(u)
        return sorted(urls)

    def _parse_project_page(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None
        slug = url.rstrip("/").split("/")[-1]
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        titulo = _strip_html(h1.group(1)) if h1 else _slug_to_title(slug)
        if not titulo or titulo.lower().startswith("planeamiento en trámite"):
            titulo = _slug_to_title(slug)
        fecha = _fecha_from_blob(html, url)
        pdfs = [
            self._abs_url(h)
            for h in re.findall(r'href="([^"]+\.pdf[^"]*)"', html, re.I)
        ]
        doc_url = pdfs[0] if pdfs else url
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(titulo),
            "url": doc_url,
            "source": "ayuntamiento",
            "origen": "nn_dd",
            "portal_url": url,
        }

    def _collect_seed_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_LINK.finditer(html):
                href = m.group(1)
                anchor = _strip_html(m.group(2))
                if href.startswith("#") or "javascript:" in href.lower():
                    continue
                if not self._is_doc_href(href) and not RE_PROYECTO.search(anchor):
                    continue
                url = self._abs_url(href)
                if url in seen:
                    continue
                seen.add(url)
                titulo = anchor or url.split("/")[-1]
                if len(titulo) < 8:
                    continue
                if not RE_PROYECTO.search(f"{titulo} {url}"):
                    continue
                rows.append(
                    {
                        "id": _stable_id("proy", url),
                        "municipio": MUNICIPIO,
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(titulo, url),
                        "tipo": _proyecto_tipo(titulo),
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "seed",
                    }
                )
        return rows

    @staticmethod
    def _is_doc_href(href: str) -> bool:
        h = href.lower()
        return bool(
            re.search(r"(?i)\.(pdf|zip)(?:\?|$)", h)
            or "preview-document" in h
            or "folder_files_summary_view" in h
            or "opendata.arcgis.com" in h
        )

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages: list[tuple[str, str, str]] = [
            (
                "Consulta de expedientes — Oficina Virtual",
                f"{WEB_BASE}/oficina-virtual/consulta-de-expedientes",
                "consulta expedientes",
            ),
            (
                "Obra Menor (DR sin Técnico Modelo 2)",
                f"{EXTRANET_BASE}/Extranet/DefaultNuevo2.aspx?p=OBRA_MENOR",
                "declaración responsable obra menor",
            ),
            (
                "Declaración Responsable con Técnico (Modelo 5)",
                f"{EXTRANET_BASE}/Extranet/DefaultNuevo2.aspx?p=DR_TECNICO",
                "declaración responsable obra con técnico",
            ),
            (
                "Inspección Técnica de Edificios (ITE)",
                f"{WEB_BASE}/oficina-virtual/inspeccion-tecnica-de-edificios",
                "inspección técnica edificación",
            ),
            (
                "Licencias — trámites y servicios",
                f"{WEB_BASE}/tramites-y-servicios/licencias",
                "licencia urbanística",
            ),
            (
                "Formularios y solicitudes urbanismo",
                f"{WEB_BASE}/tramites-y-servicios/formularios-y-solicitudes",
                "solicitud licencia",
            ),
            (
                "Listado de aprobaciones — Gerencia Urbanismo",
                f"{EXTRANET_BASE}/Extranet/ListadoAprobaciones.aspx",
                "listado aprobaciones planeamiento",
            ),
            (
                "Portal datos abiertos ide.SEVILLA",
                "https://cda-idesevilla.opendata.arcgis.com/",
                "datos abiertos urbanismo",
            ),
        ]
        rows: list[dict[str, Any]] = []
        for titulo, url, tipo in pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "web_tramite",
                }
            )
        return rows

    def _extract_address(self, text: str) -> tuple[str | None, str | None]:
        blob = unescape(text or "")
        m = RE_KNOWN_STREET.search(blob)
        if m:
            street = m.group(1).strip()
            num = m.group(2)
            return street, num
        m = RE_STREET_NUM.search(blob)
        if m:
            return m.group(1).strip(), m.group(2)
        if "luis montoto" in blob.lower():
            nm = re.search(r"luis montoto\D*(\d+)", blob, re.I)
            return "luis montoto", nm.group(1) if nm else None
        if "kansas city" in blob.lower():
            nm = re.search(r"kansas city\D*(\d+)", blob, re.I)
            return "kansas city", nm.group(1) if nm else None
        if "genaro parlade" in blob.lower():
            nm = re.search(r"genaro parlade\D*(\d+)", blob, re.I)
            return "genaro parlade", nm.group(1) if nm else None
        if "molini" in blob.lower():
            nm = re.search(r"molini\D*(\d+)", blob, re.I)
            return "molini", nm.group(1) if nm else None
        return None, None

    def _search_id_vial(self, street: str) -> int | None:
        params = {
            "sEcho": "1",
            "iColumns": "3",
            "sColumns": ",,",
            "iDisplayStart": "0",
            "iDisplayLength": "5",
            "sSearch": street,
            "bRegex": "false",
            "iSortingCols": "0",
        }
        url = CALLEJERO_SEARCH + "?" + urllib.parse.urlencode(params)
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError, ValueError):
            return None
        rows = data.get("aaData") or []
        if not rows:
            return None
        return int(rows[0][0])

    def _query_cdau_portal(
        self,
        id_vial: int,
        *,
        num: str | None = None,
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        where = f"id_vial={id_vial}"
        if num and num.isdigit():
            where += f" AND (NUM_POR_DE={num} OR NUM_POR_HA={num})"
        qurl = CDAU_PORTALES + "/query?" + urllib.parse.urlencode(
            {
                "where": where,
                "returnGeometry": "true",
                "outSR": "4326",
                "outFields": "NOM_VIA,NUM_POR_DE,REFCATPARC,ETIQUETA",
                "f": "geojson",
            }
        )
        try:
            data = self._fetch_json(qurl)
        except (urllib.error.URLError, json.JSONDecodeError, ValueError):
            return []
        feats = list(data.get("features") or [])
        return feats[:limit]

    def _fetch_portal_geometry(self, id_vial: int, num: str | None) -> dict[str, Any] | None:
        feats = self._query_cdau_portal(id_vial, num=num, limit=1)
        if not feats and num:
            feats = self._query_cdau_portal(id_vial, limit=1)
        if not feats:
            return None
        geom = feats[0].get("geometry")
        if not geom or not geom.get("type"):
            return None
        where = f"id_vial={id_vial}"
        if num and num.isdigit():
            where += f" AND (NUM_POR_DE={num} OR NUM_POR_HA={num})"
        qurl = CDAU_PORTALES + "/query?" + urllib.parse.urlencode(
            {
                "where": where,
                "returnGeometry": "true",
                "outSR": "4326",
                "outFields": "NOM_VIA,NUM_POR_DE,REFCATPARC",
                "f": "geojson",
            }
        )
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_cdau_portal",
            "geometry_source_url": qurl,
            "coord_source": "portal_geometry_centroid",
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        street, num = self._extract_address(
            f"{rec.get('titulo', '')} {rec.get('portal_url', '')} {rec.get('url', '')}"
        )
        if not street:
            return
        id_vial = self._search_id_vial(street)
        if not id_vial:
            return
        geom_pack = self._fetch_portal_geometry(id_vial, num)
        if not geom_pack:
            return
        rec.update(geom_pack)
        centroid = geometry_centroid(geom_pack["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

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
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

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

        for url in self._collect_nn_dd_urls():
            add(self._parse_project_page(url))
        for rec in self._collect_seed_docs():
            add(rec)

        add(
            {
                "id": _stable_id("proy", f"{WEB_BASE}/geo-informacion/informacion-urbanistica"),
                "municipio": MUNICIPIO,
                "titulo": "Información urbanística — visor ide.SEVILLA (geoSEVILLA)",
                "fecha": None,
                "tipo": "visor urbanístico",
                "url": f"{WEB_BASE}/geo-informacion/informacion-urbanistica",
                "source": "ayuntamiento",
                "origen": "visor",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "nn_dd": sum(1 for r in rows if r.get("origen") == "nn_dd"),
            "seed": sum(1 for r in rows if r.get("origen") == "seed"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
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
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            "with_geometry": result.get("with_geometry", 0),
        }
