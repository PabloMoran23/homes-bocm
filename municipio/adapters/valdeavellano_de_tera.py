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

DRUPAL_BASE = "https://www.valdeavellanodetera.es"
SEDE_BASE = "https://valdeavellanodetera.sedelectronica.es"
PLAI_BASE = "https://servicios.jcyl.es/PlanPublica"
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/ows"
MUNICIPIO = "Valdeavellano de Tera"
ID_PREFIX = "valdeavellano-de-tera"
PLAI_MUNICIPIO = 206
PLAI_PROVINCIA = 42

WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{DRUPAL_BASE}/modificacion-no-12-de-las-normas-urbanisticas-municipales",
    f"{DRUPAL_BASE}/informacion-municipal",
    f"{DRUPAL_BASE}/ayuntamiento",
]

RE_PREVIEW = re.compile(
    r'href="(https://valdeavellanodetera\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://valdeavellanodetera\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_DRUPAL_PDF = re.compile(
    r'href="((?:https://www\.valdeavellanodetera\.es)?/sites/valdeavellanodetera\.es/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|ocupaci[oó]n (?:de |en )?v[ií]a|segregaci[oó]n|parcelaci[oó]n|"
    r"recepci[oó]n de obras|certificado urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|bocyl|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|"
    r"edicto|bando.*parcel|actuaci[oó]n urban|normas urban|num\b|instrumento|"
    r"concentraci[oó]n parcelaria|regad[ií]o|nss|nut\b|solar|molinillo|"
    r"42191ua|surd\.so)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|nombramiento|empleo p[uú]blico|subvenci[oó]n|"
    r"licitaci[oó]n|contrataci[oó]n patrimonial|pleno ordinario|junta de gobierno|"
    r"electores|cobranza|iae|fiestas|vendimia|cine|senderismo)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_SECTOR = re.compile(
    r"(?i)\b(?:sector|sect\.?)\s*([\"«]?\s*[0-9]+[A-Z0-9\"»\s-]*|[A-ZÁÉÍÓÚÑ][\w\s\"»-]{2,40})",
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
    years = [int(y.group(1)) for y in re.finditer(r"\b((?:19|20)\d{2})\b", text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str, instrumento: str = "") -> str:
    blob = f"{title} {instrumento}".lower()
    if "concentraci" in blob and "parcel" in blob:
        return "concentración parcelaria"
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "plan parcial" in blob:
        return "plan parcial"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "normas urban" in blob or blob.strip() == "num":
        return "normas urbanísticas"
    if "informaci" in blob:
        return "información pública"
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "sector" in blob or "gatopardo" in blob or "vega de alcozar" in blob:
        return "sector urbanístico"
    return "planeamiento"


def _sector_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    low = (text or "").lower()
    for pat in (
        r"42191ua(?:\.\d+)?",
        r"42191surd\.so(?:\.\d+)?",
        r"molinillo",
        r"estudio de detalle",
    ):
        m = re.search(pat, low, re.I)
        if m:
            tok = re.sub(r"\s+", " ", m.group(0)).strip()
            if tok not in seen:
                seen.add(tok)
                tokens.append(tok)
    for m in RE_SECTOR.finditer(text or ""):
        tok = re.sub(r"\s+", " ", m.group(1)).strip(" \"«»")
        if len(tok) >= 2 and tok.lower() not in seen:
            seen.add(tok.lower())
            tokens.append(tok)
    return tokens


class ValdeavellanoDeTeraAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 7 valdeavellanodetera.es + sede espublico + PLAI JCYL + IDECyL WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or DRUPAL_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.drupal_base = str(self.config.get("drupal_base") or DRUPAL_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.info_url = str(self.config.get("info_url") or f"{self.sede_base}/info")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.plai_municipio = int(self.config.get("plai_municipio") or PLAI_MUNICIPIO)
        self.plai_provincia = int(self.config.get("plai_provincia") or PLAI_PROVINCIA)
        self.plai_max_pages = int(self.config.get("plai_max_pages", 8))
        self.plai_page_size = int(self.config.get("plai_page_size", 15))
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_title: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-valdeavellano-de-tera/1.0")},
        )
        opener = self._opener if sede or self.config.get("insecure_ssl", True) else urllib.request.build_opener()
        with opener.open(req, timeout=90 if sede else 60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-valdeavellano-de-tera/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_drupal(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.drupal_base}/", href)

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r'<tbody[^>]*id="[^"]*">(.*?)</tbody>', html, re.S | re.I)
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
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url, origen in ((self.board_url, "tablon"), (self.info_url, "info_tablon")):
            try:
                html = self._fetch(url, sede=True)
            except urllib.error.URLError:
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url, sede=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if not url.startswith("http"):
                url = f"{self.sede_base}{url}"
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        return rows

    def _collect_drupal_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = ""
            m = re.search(r"<title>([^<]+)", html, re.I)
            if m:
                page_title = _strip_html(m.group(1))
            for m in RE_DRUPAL_PDF.finditer(html):
                pdf = self._abs_drupal(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("-", " ").replace("_", " ")
                link_text = ""
                ctx = html[max(0, m.start() - 200) : m.end() + 50]
                text_m = re.search(r">([^<]{3,120})</a>", ctx)
                if text_m:
                    link_text = _strip_html(text_m.group(1))
                titulo = link_text or name or page_title
                blob = f"{page_title} {titulo} {pdf}"
                if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    if "urban" not in page_url.lower() and "norma" not in page_url.lower():
                        continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": page_url,
                        "pdf_url": pdf,
                        "fecha": _fecha_from_blob(pdf + " " + titulo + " " + page_title),
                        "origen": "drupal_pdf",
                        "page_title": page_title,
                    }
                )
            if RE_PROYECTO.search(page_title) or RE_PROYECTO.search(_strip_html(html[:4000])):
                key = page_url
                if key not in seen:
                    seen.add(key)
                    rows.append(
                        {
                            "titulo": page_title[:500] or page_url,
                            "url": page_url,
                            "fecha": _fecha_from_blob(page_title + html[:2000]),
                            "origen": "drupal_page",
                        }
                    )
        return rows

    def _plai_page_url(self, offset: int) -> str:
        params = {
            "pager.size": str(self.plai_page_size),
            "pager.reload": "no",
            "municipio": f"{self.plai_municipio:03d}",
            "provincia": str(self.plai_provincia),
            "urlResults": "searchVPubDocMuniPlai.do",
            "pager.offset": str(offset),
        }
        return f"{PLAI_BASE}/searchVPubDocMuniPlai.do?{urllib.parse.urlencode(params)}"

    @staticmethod
    def _parse_plai_rows(html: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            cells = [
                _strip_html(c)
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            ]
            cells = [c for c in cells if c]
            if len(cells) < 5 or cells[0] in {"Libro", "Tipo"}:
                continue
            titulo = cells[4] if len(cells) > 4 else cells[-1]
            if not titulo or re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", titulo):
                continue
            fecha_pub = cells[2]
            doc_m = re.search(r"doOpen\('(\d+)'", tr) or re.search(r"doOpenDocumento\((\d+)\)", tr)
            boletin_m = re.search(r"doGoBoletin\('(\d+)'", tr)
            doc_id = doc_m.group(1) if doc_m else (boletin_m.group(1) if boletin_m else None)
            if doc_id and doc_m:
                url = f"{PLAI_BASE}/openDocumento.do?cDocId={doc_id}"
            elif boletin_m:
                url = f"{PLAI_BASE}/openBoletin.do?cDocId={boletin_m.group(1)}"
            else:
                url = (
                    f"{PLAI_BASE}/searchVPubDocMuniPlai.do?"
                    f"provincia={PLAI_PROVINCIA}&municipio={PLAI_MUNICIPIO:03d}"
                )
            rows.append(
                {
                    "title": titulo,
                    "url": url,
                    "fecha": fecha_pub,
                    "instrumento": cells[1] if len(cells) > 1 else "",
                    "origen": "plai_jcyl",
                    "doc_id": doc_id or "",
                }
            )
        return rows

    def _collect_plai(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(self.plai_max_pages):
            offset = page * self.plai_page_size
            try:
                html = self._fetch(self._plai_page_url(offset))
            except urllib.error.URLError:
                break
            parsed = self._parse_plai_rows(html)
            if not parsed:
                break
            for item in parsed:
                key = item["url"] + item["title"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": item["title"][:500],
                        "fecha": _parse_fecha_dmy(item.get("fecha") or ""),
                        "url": item["url"],
                        "instrumento": item.get("instrumento") or "",
                        "origen": "plai_jcyl",
                    }
                )
            if len(parsed) < self.plai_page_size:
                break
        return rows

    def _wfs_query_url(self, layer: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "200",
                "CQL_FILTER": f"n_mun = '{self.wfs_municipio}'",
            }
        )
        return f"{self.wfs_base}?{params}"

    def _collect_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        for layer, default_tipo in WFS_LAYERS:
            url = self._wfs_query_url(layer)
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            for feat in data.get("features") or []:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                sector = str(props.get("n_sector") or "").strip()
                num = str(props.get("n_num_sect") or "").strip()
                titulo = sector
                if num and num not in titulo:
                    titulo = f"{sector} ({num})" if sector else num
                if not titulo:
                    titulo = str(props.get("c_id_sect") or props.get("c_plan") or layer)
                instrum = str(props.get("c_instrum") or props.get("n_instrum") or "")
                key = str(props.get("c_id_sect") or props.get("c_plan") or props.get("fid") or titulo)
                rec: dict[str, Any] = {
                    "titulo": titulo[:500],
                    "fecha": None,
                    "url": str(props.get("url_doc_info") or "").strip() or url,
                    "instrumento": instrum,
                    "origen": "idecyl_wfs",
                    "wfs_layer": layer,
                    "wfs_key": key,
                    "sector_name": sector or None,
                    "sector_num": num or None,
                    "tipo": default_tipo,
                }
                if isinstance(geom, dict) and geom.get("type"):
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
        self._wfs_cache = rows
        self._wfs_by_title = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("sector_name") or "", rec.get("sector_num") or ""):
                low = str(key).lower().strip()
                if low:
                    self._wfs_by_title[low] = rec
        return rows

    def _match_wfs(self, text: str) -> dict[str, Any] | None:
        if self._wfs_by_title is None:
            self._collect_wfs()
        low = (text or "").lower()
        best: dict[str, Any] | None = None
        best_len = 0
        for key, rec in (self._wfs_by_title or {}).items():
            if len(key) >= 4 and key in low and len(key) > best_len:
                best = rec
                best_len = len(key)
        for tok in _sector_tokens(text):
            tok_low = tok.lower()
            for key, rec in (self._wfs_by_title or {}).items():
                if tok_low in key or key in tok_low:
                    return rec
        return best

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "instrumento"))
        hit = self._match_wfs(blob)
        if not hit:
            return
        for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if hit.get(key) is not None:
                rec[key] = hit[key]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_NOISE.search(blob):
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
        self._attach_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_NOISE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
            "tipo": _proyecto_tipo(row["titulo"], row.get("categoria", "")),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _drupal_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('page_title', '')} {row.get('pdf_url', '')}"
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or row.get("pdf_url") or self.drupal_base,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
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
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        if RE_LICENCIA.search(row["titulo"]) and not re.search(
            r"(?i)planeam|actuaci[oó]n urban|modificaci[oó]n del planeamiento|consulta de proyectos",
            row["titulo"],
        ):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _plai_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row.get("instrumento", "")),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "instrumento": row.get("instrumento") or None,
        }
        self._attach_geometry(rec)
        return rec

    def _wfs_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = f"wfs:{row.get('wfs_layer')}:{row.get('wfs_key')}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or "planeamiento",
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "wfs_layer": row.get("wfs_layer"),
        }
        for key_name in (
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if row.get(key_name) is not None:
                rec[key_name] = row[key_name]
        return rec

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        pages = [
            (f"{self.sede_base}/catalog/t/urbanismo", "trámite urbanismo — sede"),
            (f"{self.sede_base}/catalog/t/licencias", "trámite licencias — sede"),
            (self.board_url, "tablón de anuncios — licencias y urbanismo"),
        ]
        rows: list[dict[str, Any]] = []
        for url, tipo in pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": tipo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámite o publicación",
                    "origen": "sede_tramite",
                }
            )
        return rows

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

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for item in self._collect_plai():
            rec = self._plai_to_proyecto(item)
            by_id[rec["id"]] = rec
        for item in self._collect_wfs():
            rec = self._wfs_to_proyecto(item)
            by_id[rec["id"]] = rec
        for item in self._collect_drupal_seeds():
            rec = self._drupal_to_proyecto(item)
            if rec:
                by_id[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_proyecto(item)
            if rec:
                by_id[rec["id"]] = rec
        for item in self._collect_tramites():
            rec = self._tramite_to_proyecto(item)
            if rec:
                by_id[rec["id"]] = rec
        return list(by_id.values())

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") in ("catalogo_tramites", "sede_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencias():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, len(rows) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if r.get("geom_geojson"))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "plai": sum(1 for r in rows if r.get("origen") == "plai_jcyl"),
            "wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "drupal": sum(1 for r in rows if str(r.get("origen", "")).startswith("drupal")),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
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
