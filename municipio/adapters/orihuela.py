from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, quote

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.orihuela.es"
SEDE_BASE = "https://orihuela.sedeelectronica.es"
DOSSIER_URL = "http://orihuela.sedeelectronica.es/dossier"
PLAN_URL = "https://plangeneral.orihuela.es/pg90.html"
TRANSPARENCIA_URL = "https://transparencia.orihuela.es/urbanismo-obras-y-medio-ambiente/"
FORMULARIOS_URL = f"{WEB_BASE}/formularios/"
MUNICIPIO = "Orihuela"
ID_PREFIX = "orihuela"
INE_MUN = "03099"

WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
WFS_TYPE = "InventarioSuSuz"

WP_SEARCH_TERMS = (
    "exposición pública",
    "urbanismo",
    "planeamiento",
    "zona de bajas emisiones",
    "licencia de obra",
)

RE_PREVIEW = re.compile(
    r'href="(https://orihuela\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="(https://orihuela\.sedelectronica\.es/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|andamio|apertura de establecimiento)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|proyecto|"
    r"modificaci[oó]n|reparcel|estudio de detalle|sector|edicto|zona de bajas emisiones|"
    r"ordenanza|compatibilidad urban|peopcho|pau-|hypp|delimitaci[oó]n)",
)
RE_FORM_LIC = re.compile(
    r"(?i)(lic|obra|apertura|curban|andam|vado|mesas|act_la|act_vp|dec_resp|inocua|ambient)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(proceso selectivo|convocatoria.*empleo|veh[ií]culo depositado|"
    r"subvenci[oó]n diputaci[oó]n|nombramiento|bolsa de)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_WP_ENTRY = re.compile(
    r'class="blog-post_title"[^>]*>\s*<a href="([^"]+)"[^>]*>([^<]+)</a>',
    re.I | re.S,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_PLAN_MOD = re.compile(
    r'href="(pg90/modificaciones/[^"]+\.pdf)"[^>]*>([^<]*)</a>|'
    r'href="(pg90/modificaciones/[^"]+\.pdf)"',
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
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "zona de bajas emisiones" in n or "zbe" in n:
        return "zona de bajas emisiones"
    if "modificaci" in n:
        return "modificación PGOU"
    if "plan especial" in n or "peopcho" in n:
        return "plan especial"
    if "plan parcial" in n or "pau-" in n:
        return "plan parcial"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "pgou" in n or "pgmou" in n:
        return "PGOU"
    if "licencia" in n:
        return "licencia publicada"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.strip().split()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lon = nums[i], nums[i + 1]
        ring.append([lon, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


class OrihuelaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress orihuela.es + sede espublico (tablón/catálogo) + ICV InventarioSuSuz WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.info_url = str(self.config.get("info_url") or f"{self.sede_base}/info.1")
        self.dossier_url = str(self.config.get("dossier_url") or DOSSIER_URL)
        self.plan_url = str(self.config.get("plan_url") or PLAN_URL)
        self.formularios_url = str(self.config.get("formularios_url") or FORMULARIOS_URL)
        self.wp_search_terms = tuple(self.config.get("wp_search_terms") or WP_SEARCH_TERMS)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or WFS_BASE).rstrip("/")
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._dossier_html: str | None = None

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-orihuela/1.0")},
        )
        opener = urllib.request.build_opener(
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        with opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_with_cookies(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-orihuela/1.0")},
        )
        with opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-orihuela/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
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
                    "origen": origen,
                }
            )
        return rows

    def _parse_board_links(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            local = html[max(0, m.start() - 500) : m.end() + 300]
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
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        sources = (
            (self.board_url, "tablon", self._fetch),
            (self.info_url, "info_tablon", self._fetch_with_cookies),
        )
        for url, origen, fetcher in sources:
            try:
                html = fetcher(url)
            except (urllib.error.URLError, urllib.error.HTTPError):
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _load_dossier_html(self) -> str:
        if self._dossier_html is not None:
            return self._dossier_html
        try:
            self._dossier_html = self._fetch_with_cookies(self.dossier_url)
        except (urllib.error.URLError, urllib.error.HTTPError):
            self._dossier_html = ""
        return self._dossier_html

    def _collect_tramites(self) -> list[dict[str, Any]]:
        html = self._load_dossier_html()
        if not html:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        return rows

    def _collect_formularios(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.formularios_url, timeout=60)
        except urllib.error.URLError:
            return []
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for href in RE_PDF.findall(html):
            pdf = urljoin(self.formularios_url, href)
            if pdf in seen:
                continue
            name = unquote(Path(pdf).name).replace("-", " ")
            blob = f"{name} {pdf}"
            if not (
                RE_LICENCIA.search(blob)
                or RE_FORM_LIC.search(blob)
                or (RE_PROYECTO.search(blob) and "plan_agenda" not in blob.lower())
            ):
                continue
            seen.add(pdf)
            rows.append(
                {
                    "titulo": name[:500],
                    "url": self.formularios_url,
                    "pdf_url": pdf,
                    "origen": "formularios_web",
                }
            )
        return rows

    def _collect_plan_modificaciones(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.plan_url, timeout=60)
        except urllib.error.URLError:
            return []
        base = "https://plangeneral.orihuela.es/"
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PLAN_MOD.finditer(html):
            rel = m.group(1) or m.group(3)
            if not rel or rel in seen:
                continue
            seen.add(rel)
            label = (m.group(2) or "").strip() if m.lastindex and m.lastindex >= 2 else ""
            titulo = label or unquote(Path(rel).stem).replace("_", " ")
            if not titulo.lower().startswith("mod"):
                titulo = f"Modificación PGOU — {titulo}"
            pdf = urljoin(base, rel)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": self.plan_url,
                    "pdf_url": pdf,
                    "origen": "plangeneral_pg90",
                }
            )
        rows.append(
            {
                "titulo": "Plan General de Ordenación Urbana de Orihuela (PGOU vigente)",
                "fecha": None,
                "url": self.plan_url,
                "origen": "plangeneral_pg90",
            }
        )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for term in self.wp_search_terms:
            q = quote(term)
            url = f"{self.web_base}/?s={q}"
            try:
                html = self._fetch(url, timeout=60)
            except urllib.error.URLError:
                continue
            for m in RE_WP_ENTRY.finditer(html):
                link, title = m.group(1), unescape(m.group(2).strip())
                if link in seen:
                    continue
                blob = f"{title} {term}"
                if not RE_PROYECTO.search(blob):
                    continue
                seen.add(link)
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _fecha_from_blob(title),
                        "url": link,
                        "origen": "web_noticias",
                    }
                )
        return rows

    def _wfs_matches_municipio(self, props: dict[str, Any]) -> bool:
        return props.get("cod_ine_mun") == self.ine_mun

    def _parse_wfs_feature(self, feat_el: ET.Element) -> dict[str, Any] | None:
        props: dict[str, Any] = {}
        geom: dict[str, Any] | None = None
        for child in feat_el:
            tag = child.tag.split("}", 1)[-1]
            if tag == "msGeometry":
                for gchild in child.iter():
                    gtag = gchild.tag.split("}", 1)[-1]
                    if gtag == "posList" and gchild.text:
                        geom = _gml_poslist_to_polygon(gchild.text)
            elif child.text and tag not in {"boundedBy", "msGeometry"}:
                props[tag] = child.text.strip()
        if not self._wfs_matches_municipio(props):
            return None
        titulo = _strip_html(str(props.get("pp") or props.get("ue") or props.get("clasificacion") or ""))
        if not titulo:
            return None
        fecha = _fecha_from_blob(str(props.get("f_aprob") or props.get("f_public") or ""))
        key = str(props.get("id") or titulo)
        wfs_url = (
            f"{self.wfs_base}?service=WFS&version=2.0.0&request=GetFeature"
            f"&typename={self.wfs_type}&outputFormat=GML3&srsName=EPSG:4326"
            f"&count=1&STARTINDEX=0"
        )
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"wfs:{key}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": fecha,
            "tipo": _proyecto_tipo(f"{titulo} {props.get('clasificacion', '')}"),
            "url": self.plan_url,
            "source": "ayuntamiento",
            "origen": "icv_wfs",
        }
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_crs"] = "EPSG:4326"
            rec["geometry_axis_order"] = "xy"
            rec["geometry_source"] = "portal_wfs_icv"
            rec["geometry_source_url"] = wfs_url
            rec["coord_source"] = "portal_geometry_centroid"
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
        return rec

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        start = 0
        step = 200
        while True:
            url = (
                f"{self.wfs_base}?service=WFS&version=2.0.0&request=GetFeature"
                f"&typename={self.wfs_type}&outputFormat=GML3&srsName=EPSG:4326"
                f"&count={step}&STARTINDEX={start}"
            )
            try:
                raw = self._fetch_bytes(url)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = [el for el in root if el.tag.endswith("member")]
            if not members:
                break
            for member in members:
                rec = self._parse_wfs_feature(member[0])
                if rec:
                    rows.append(rec)
            start += step
            if len(members) < step:
                break
        self._wfs_cache = rows
        return rows

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        titulo = str(rec.get("titulo") or "").lower()
        for wfs_rec in self._collect_wfs_proyectos():
            wfs_title = str(wfs_rec.get("titulo") or "").lower()
            if titulo and (titulo in wfs_title or wfs_title in titulo):
                for key in (
                    "geom_geojson",
                    "geometry_crs",
                    "geometry_axis_order",
                    "geometry_source",
                    "geometry_source_url",
                    "coord_source",
                    "lat",
                    "lon",
                ):
                    if wfs_rec.get(key) is not None:
                        rec[key] = wfs_rec[key]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "categoria", "descripcion"))
        if RE_TABLON_SKIP.search(blob):
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

    def _generic_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('origen', '')}"
        if row.get("origen") == "formularios_web":
            if not RE_FORM_LIC.search(blob) and not RE_LICENCIA.search(blob):
                return None
        elif not RE_LICENCIA.search(blob):
            return None
        if row.get("origen") == "catalogo_tramites":
            return {
                "id": _stable_id("lic", row["url"]),
                "fecha_concesion": None,
                "tipo": "trámite licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": row["titulo"],
                "url": row["url"],
                "source": "ayuntamiento",
                "nota": "Trámite catálogo sede; no concesión publicada en tablón",
                "origen": row.get("origen"),
            }
        key = row.get("pdf_url") or row.get("url") or row["titulo"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "formulario licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "categoria", "descripcion"))
        if RE_TABLON_SKIP.search(blob):
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
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
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

    def _generic_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('origen', '')}"
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and row.get("origen") == "catalogo_tramites":
            if not re.search(r"(?i)planeam|compatibilidad|urban", blob):
                return None
        key = row.get("pdf_url") or row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or self.web_base,
            "source": "ayuntamiento",
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_board():
            add(self._board_to_licencia(item))
        for item in self._collect_tramites():
            add(self._generic_to_licencia(item))
        for item in self._collect_formularios():
            add(self._generic_to_licencia(item))

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

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
                rows.append(rec)

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_tramites():
            add(self._generic_to_proyecto(item))
        for item in self._collect_plan_modificaciones():
            add(self._generic_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._generic_to_proyecto(item))
        for item in self._collect_wfs_proyectos():
            add(item)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if r.get("geom_geojson"))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
