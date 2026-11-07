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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry
from municipio.onboarding_snapshot import reviewed_records

WEB_BASE = "https://www.carcaixent.es"
SEDE_BASE = "https://carcaixent.sedelectronica.es"
MUNICIPIO = "Carcaixent"
ID_PREFIX = "carcaixent"
INE_MUN = "46083"
MUNICIPAL_BBOX = "39.0566988,-0.5044569,39.1454756,-0.3340837,urn:ogc:def:crs:EPSG::4326"

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER = "ms:InventarioSuSuz"
VISOR_ICV = "https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/pagina/plano-urbano",
    f"{WEB_BASE}/es/pagina/general/plan-movilidad-urbana-sostenible",
    f"{WEB_BASE}/es/noticia-novetats-pagina/territori",
]

RSS_URL = f"{WEB_BASE}/es/rss.xml"
BOARD_URL = f"{SEDE_BASE}/board"

DEFAULT_CATALOG_TRAMITES: list[tuple[str, str]] = [
    (
        f"{SEDE_BASE}/catalog/t/5d383e20-32a5-4fcf-8725-e51c51e83e6a",
        "Declaració Responsable o Comunicació en Matèria Urbanística",
    ),
    (
        f"{SEDE_BASE}/catalog/t/15fabacb-83b1-47d1-b435-508245672051",
        "Sol·licitud de Llicència o Autorització Urbanística",
    ),
    (
        f"{SEDE_BASE}/catalog/t/f91e4a50-d23d-45c1-a19b-b148da37c59f",
        "Sol·licitud d'Actuació Urbanística",
    ),
    (
        f"{SEDE_BASE}/catalog/t/e8594295-30ea-4a16-8f17-60c061a8a147",
        "Sol·licitud de Recepció d'Obres d'Urbanització",
    ),
    (
        f"{SEDE_BASE}/catalog/t/a3c783fb-bb19-4ea3-b40f-0072d69aebae",
        "Sol·licitud de modificació o renúncia d'una llicència urbanística",
    ),
]

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"obra (?:major|menor)|autoritzaci[oó]|recepci[oó].*obra|actuaci[oó] urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|expedient|modificaci[oó] "
    r"puntual|exposici[oó]|informaci[oó] p[uú]blica|sector|suz|ue[\s\-]|actuaci[oó]|"
    r"reparcel|normes|usos|activitats|planol|plano urbano|mobilitat urban)",
)
RE_NOISE = re.compile(
    r"(?i)(subvenci[oó]|selecci[oó] de personal|convocat[oò]ria.*empleo|ajudes i subvenci|"
    r"cooperaci[oó] internacional|padron|padr[oó])",
)
RE_PDF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
RE_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
RE_NOTICIA_PATH = re.compile(r'href="(/es/noticia[^"]+)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|PRI|PERI|SUZ|SECTOR|UNIDAD DE EJECUCI)[\s\-]?[\w\d]+(?:[\s,\-yY/]+[\w\d]+)*)\b",
)

RE_BOARD_ROW = re.compile(r'<tr[^>]*>\s*<td class="class_name".*?</tr>', re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://carcaixent\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _strip_html(text: str) -> str:
    return _clean(re.sub(r"<[^>]+>", " ", text or ""))


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
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual PGOU"
    if "plan parcial" in n or "sector" in n or re.search(r"\bue[\s\-]", n):
        return "plan parcial / unidad de ejecución"
    if "suz" in n or "suelo urbanizable" in n:
        return "sector SU/SUZ"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "mobilitat" in n or "movilidad" in n:
        return "plan de movilidad urbana"
    if "planol" in n or "plano urbano" in n:
        return "documentación urbanística"
    if "licencia" in n or "llic" in n:
        return "licencia publicada"
    return "planeamiento"


def _sector_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for m in RE_SECTOR_TOKEN.finditer(text or ""):
        tok = _clean(m.group(1))
        if len(tok) >= 3:
            tokens.append(tok)
    return tokens


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    parts = [float(x) for x in poslist.split() if x.strip()]
    if len(parts) < 6:
        return None
    coords: list[list[float]] = []
    for i in range(0, len(parts) - 1, 2):
        lat, lon = parts[i], parts[i + 1]
        coords.append([lon, lat])
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


def _gml_feature_to_geojson(feat: ET.Element) -> dict[str, Any] | None:
    poly = feat.find(".//gml:Polygon", _GML_NS)
    if poly is None:
        return None
    pos = poly.find(".//gml:posList", _GML_NS)
    if pos is None or not (pos.text or "").strip():
        return None
    return _gml_poslist_to_polygon(pos.text.strip())


class CarcaixentAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal carcaixent.es + sede espublico gestiona + ICV InventarioSuSuz WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.ine_mun = str(self.config.get("cod_ine_mun") or INE_MUN)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.wfs_type = str(geom_cfg.get("type_name") or ICV_LAYER)
        self.municipal_bbox = str(geom_cfg.get("bbox") or MUNICIPAL_BBOX)
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.rss_url = str(self.config.get("rss_url") or RSS_URL)
        self.ua = str(self.config.get("user_agent", "poc-bocm-carcaixent/1.0"))
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: int = 90, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept-Language": "es,ca;q=0.9"})
        if sede:
            with self._opener.open(req, timeout=timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
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

    def _wfs_bbox_page_url(self, *, startindex: int = 0, count: int = 200) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": self.wfs_type,
                "count": str(count),
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "bbox": self.municipal_bbox,
                "STARTINDEX": str(startindex),
            }
        )
        return f"{self.wfs_base}?{params}"

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        start = 0
        seen_ids: set[str] = set()
        while start < 2000:
            url = self._wfs_bbox_page_url(startindex=start)
            try:
                raw = self._fetch(url, timeout=180)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", _GML_NS)
            if not members:
                break
            for member in members:
                feat = member.find("ms:InventarioSuSuz", _GML_NS)
                if feat is None:
                    feat = member[0]
                cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
                if cod != self.ine_mun:
                    continue
                fid = feat.findtext("ms:id", default="", namespaces=_GML_NS) or ""
                if fid in seen_ids:
                    continue
                seen_ids.add(fid)
                pp = _clean(feat.findtext("ms:pp", default="", namespaces=_GML_NS) or "")
                ue = _clean(feat.findtext("ms:ue", default="", namespaces=_GML_NS) or "")
                clas = _clean(feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or "")
                f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
                titulo = pp or ue or f"Sector {fid}"
                if ue and ue not in titulo:
                    titulo = f"{pp} ({ue})" if pp else ue
                geom = _gml_feature_to_geojson(feat)
                rec: dict[str, Any] = {
                    "titulo": titulo[:500],
                    "fecha": f_aprob,
                    "url": VISOR_ICV,
                    "tipo": "sector SU/SUZ" if clas else "sector planeamiento",
                    "clasificacion": clas or None,
                    "pp": pp or None,
                    "ue": ue or None,
                    "wfs_id": fid,
                    "origen": "icv_wfs",
                }
                if geom:
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
            if len(members) < 50:
                break
            start += len(members)
        self._wfs_cache = rows
        self._wfs_by_key = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("pp") or "", rec.get("ue") or ""):
                low = str(key).lower().strip()
                if low:
                    self._wfs_by_key[low] = rec
            for tok in _sector_tokens(rec.get("titulo") or ""):
                self._wfs_by_key[tok.lower()] = rec
        return rows

    def _match_wfs(self, text: str) -> dict[str, Any] | None:
        if self._wfs_by_key is None:
            self._collect_icv_wfs()
        low = (text or "").lower()
        best: dict[str, Any] | None = None
        best_len = 0
        for key, rec in (self._wfs_by_key or {}).items():
            if len(key) >= 4 and key in low and len(key) > best_len:
                best = rec
                best_len = len(key)
        if best:
            return best
        for tok in _sector_tokens(text):
            hit = (self._wfs_by_key or {}).get(tok.lower())
            if hit:
                return hit
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "pp", "ue"))
        hit = self._match_wfs(blob)
        if not hit:
            return
        for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if hit.get(key) is not None:
                rec[key] = hit[key]

    def _collect_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(self.rss_url, timeout=60)
            root = ET.fromstring(raw)
        except (urllib.error.URLError, ET.ParseError):
            return []
        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = _clean(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            pub = item.findtext("pubDate") or ""
            fecha = _fecha_from_blob(pub) or _fecha_from_blob(title)
            rows.append({"titulo": title[:500], "url": link, "fecha": fecha, "origen": "web_rss"})
        return rows

    def _collect_web_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        max_articles = int(self.config.get("max_territori_articles", 30))

        def push(row: dict[str, Any]) -> None:
            url = row.get("url") or ""
            if not url or url in seen_urls:
                return
            seen_urls.add(url)
            rows.append(row)

        article_queue: list[str] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url, timeout=90)
            except urllib.error.URLError:
                continue
            title_m = RE_TITLE.search(html)
            page_title = _clean(title_m.group(1)) if title_m else page_url
            push(
                {
                    "titulo": page_title[:500],
                    "url": page_url,
                    "fecha": _fecha_from_blob(page_title),
                    "tipo": _proyecto_tipo(page_title),
                    "origen": "web_seccion",
                }
            )
            for href in RE_NOTICIA_PATH.findall(html):
                if "territori" in href.lower() or "urban" in href.lower():
                    article_queue.append(urljoin(self.web_base + "/", href))
            for m in RE_PDF.finditer(html):
                pdf_url = m.group(1)
                if pdf_url.startswith("/"):
                    pdf_url = urljoin(self.web_base + "/", pdf_url)
                name = urllib.parse.unquote(pdf_url.rsplit("/", 1)[-1]).replace(".pdf", "").replace("%20", " ")
                blob = f"{page_title} {name}"
                if not RE_PROYECTO.search(blob) and "urban" not in pdf_url.lower():
                    continue
                push(
                    {
                        "titulo": f"{page_title} — {name}"[:500],
                        "url": pdf_url,
                        "fecha": _fecha_from_blob(blob),
                        "tipo": _proyecto_tipo(blob),
                        "origen": "web_pdf",
                    }
                )

        for article_url in article_queue[:max_articles]:
            try:
                html = self._fetch(article_url, timeout=90)
            except urllib.error.URLError:
                continue
            h1 = RE_H1.search(html)
            title = _strip_html(h1.group(1)) if h1 else article_url
            push(
                {
                    "titulo": title[:500],
                    "url": article_url,
                    "fecha": _fecha_from_blob(title),
                    "tipo": _proyecto_tipo(title),
                    "origen": "web_noticia",
                }
            )
            for m in RE_PDF.finditer(html):
                pdf_url = m.group(1)
                if pdf_url.startswith("/"):
                    pdf_url = urljoin(self.web_base + "/", pdf_url)
                name = urllib.parse.unquote(pdf_url.rsplit("/", 1)[-1]).replace(".pdf", "")
                blob = f"{title} {name}"
                push(
                    {
                        "titulo": f"{title} — {name}"[:500],
                        "url": pdf_url,
                        "fecha": _fecha_from_blob(blob),
                        "tipo": _proyecto_tipo(blob),
                        "origen": "web_pdf",
                    }
                )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, timeout=90, sede=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))
            documento = cells.get("class_name", "")
            if not documento or documento in ("Documento",):
                continue
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")
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
                    "titulo": titulo[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": f"{documento} {expediente} {procedimiento} {categoria} {descripcion}",
                    "origen": "sede_board",
                }
            )
        return rows

    def _catalog_tramites(self) -> list[dict[str, Any]]:
        catalog = self.config.get("catalog_tramites")
        links: list[tuple[str, str]] = []
        if isinstance(catalog, list):
            for item in catalog:
                if isinstance(item, dict) and item.get("url"):
                    links.append((str(item["url"]), str(item.get("titulo") or item["url"])))
        if not links:
            links = list(DEFAULT_CATALOG_TRAMITES)
        rows: list[dict[str, Any]] = []
        for url, titulo in links:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia urbanística",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página de solicitud en sede espublico gestiona (sin histórico de concesiones)",
                    "origen": "sede_tramite",
                }
            )
        rows.append(
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
                "nota": "Edictos y resoluciones urbanísticas publicados en board",
                "origen": "referencia_portal",
            }
        )
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_NOISE.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("urban", "obra", "licen", "llic", "planeam", "activitat")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("titulo") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("wfs_id") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        for key in (
            "pp",
            "ue",
            "clasificacion",
            "wfs_id",
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
        return rec

    def _portal_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob) and row.get("origen") not in {
            "web_seccion",
            "web_pdf",
            "web_noticia",
            "web_rss",
            "icv_wfs",
        }:
            return None
        return self._to_proyecto(row)

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        if RE_LICENCIA.search(row.get("blob") or "") and not RE_PROYECTO.search(row.get("blob") or ""):
            return None
        if not RE_PROYECTO.search(row.get("blob") or row.get("titulo") or ""):
            return None
        return self._to_proyecto(row)

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        if not RE_LICENCIA.search(row.get("blob") or row.get("titulo") or ""):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia / edicto",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_board",
        }
        self._attach_geometry(rec)
        return rec

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._catalog_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_catalog_board"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_licencias(out_jsonl)
        after = result["rows"]
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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_icv_wfs():
            add(self._to_proyecto(item))
        for item in self._collect_web_seeds():
            add(self._portal_to_proyecto(item))
        for item in self._collect_rss():
            add(self._portal_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web_")),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": after,
                    "added": max(0, after - before),
                    "with_geometry": result.get("with_geometry", 0),
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
