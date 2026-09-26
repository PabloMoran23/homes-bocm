from __future__ import annotations

import base64
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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.elda.es"
SEDE_BASE = "https://eamic.elda.es:20443"
MUNICIPIO = "Elda"
ID_PREFIX = "elda"
INE_MUN = "03066"

URBANISMO_HUB = f"{WEB_BASE}/urbanismo-y-actividades/"
ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER = "InventarioSuSuz"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_HUB,
    f"{WEB_BASE}/urbanismo-y-actividades/documentos-intervencion-ambiental-en-tramitacion/",
    f"{WEB_BASE}/urbanismo-y-actividades/instalaciones-fotovoltaicas/",
    f"{WEB_BASE}/urbanismo-y-actividades/informacion-sobre-cuartelillos-2025/",
]

TRANSPARENCIA_ROOT = 1401
TRANSPARENCIA_MAX_EPIGRAFES = 60

LICENCIA_TRAMITE_URLS: list[tuple[str, str]] = [
    (
        "Solicitud de licencia de obra / actividad (sede EAMIC)",
        f"{SEDE_BASE}/web/inicioWebc.do?opcion=noreg&entidad=03066",
    ),
    (
        "Catálogo de trámites y servicios (ventanilla virtual)",
        f"{SEDE_BASE}/cargaMenuWeb.do?entidad=03066&idioma=1",
    ),
]

RE_ENTRY_TITLE = re.compile(
    r'class="entry-title[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)',
    re.I | re.S,
)
RE_PUBLISHED = re.compile(
    r'class="published"[^>]*>([^<]+)|<time[^>]*datetime="([^"]+)"',
    re.I,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licències|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|licencias de actividad|intervenci[oó]n ambiental)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pge|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de )?detalle|sector|unidad(?:es)? de actuaci[oó]n|ue-|"
    r"pemu|fotovolt|plano|ordenanza|normas urban|homologaci[oó]n|"
    r"participaci[oó]n p[uú]blica|pol[ií]gono|finca lacy|torreta)",
)
RE_NOISE = re.compile(
    r"(?i)(fiestas|moros y cristianos|cuartelillo|empleo p[uú]blico|"
    r"formaci[oó]n cultura y ocio|juventud|comercio|subvenci[oó]n deportiv|"
    r"huertos urbanos|selecci[oó]n de personal)",
)
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|PRI|PEMU|SECTOR|UA|UNIDAD)[\s\-]?(?:IND\s*)?[\dA-ZÁÉÍÓÚ'._\-]+(?:[\s,\-yY/]+[\dA-ZÁÉÍÓÚ'._\-]+)*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_TXT = re.compile(
    r"(?i)\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b",
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    t = unescape(re.sub(r"\s+", " ", text or "")).strip()
    if "Ã" in t or "Â" in t:
        try:
            t = t.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return t


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_DMY_TXT.search(text or "")
    if m:
        y = int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return datetime(y, int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_published(text: str) -> str | None:
    if not text:
        return None
    text = text.strip()
    for fmt in ("%b %d, %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:20], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return _parse_fecha_dmy(text)


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "plan especial" in n or "pemu" in n or "pri " in n:
        return "plan especial"
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual"
    if "unidad" in n and "actuaci" in n:
        return "unidad de actuación"
    if "informaci" in n and "p" in n:
        return "información pública"
    if "fotovolt" in n or "renovable" in n:
        return "instalación fotovoltaica"
    if "intervenci" in n and "ambiental" in n:
        return "intervención ambiental"
    if "plano" in n or "ordenanza" in n:
        return "documentación urbanística"
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
    for tag in ("posList",):
        for pos in feat.iter():
            if pos.tag.endswith(tag) and (pos.text or "").strip():
                geom = _gml_poslist_to_polygon(pos.text.strip())
                if geom:
                    return geom
    return None


def _epigrafe_url(epi: int) -> str:
    key = base64.b64encode(f"Ayuntamiento de Elda@@@{epi}".encode()).decode().rstrip("=")
    return f"{SEDE_BASE}/web/transparencia/{key}/03066"


class EldaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (elda.es) + sede EAMIC transparencia + ICV WFS InventarioSuSuz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_wp_pages = int(self.config.get("max_wp_pages", 8))
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_layer = str(geom_cfg.get("type_name") or ICV_LAYER)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or INE_MUN)
        self.insecure_ssl = bool(self.config.get("insecure_ssl", True))
        self._ssl_ctx = ssl.create_default_context()
        if self.insecure_ssl:
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-elda/1.0")},
        )
        ctx = self._ssl_ctx if url.startswith("https://eamic.") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            if encoding:
                return raw.decode(encoding, errors="replace")
            charset = resp.headers.get_content_charset() or "utf-8"
            try:
                return raw.decode(charset, errors="replace")
            except LookupError:
                return raw.decode("utf-8", errors="replace")

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

    def _collect_wp_articles(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(1, self.max_wp_pages + 1):
            url = (
                f"{self.web_base}/urbanismo-y-actividades/page/{page}/?et_blog"
                if page > 1
                else f"{self.web_base}/urbanismo-y-actividades/"
            )
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            hits = 0
            for href, title in RE_ENTRY_TITLE.findall(html):
                link = href.strip()
                if link in seen:
                    continue
                seen.add(link)
                titulo = _clean(title)
                if not titulo:
                    continue
                fecha = None
                block_start = html.find(link)
                if block_start >= 0:
                    block = html[max(0, block_start - 400) : block_start + 1200]
                    pub = RE_PUBLISHED.search(block)
                    if pub:
                        fecha = _parse_published(pub.group(1) or pub.group(2))
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": fecha,
                        "url": link,
                        "origen": "wp_urbanismo",
                    }
                )
                hits += 1
            if hits == 0:
                break
        return rows

    def _collect_wp_hub_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            if page_url.rstrip("/") == URBANISMO_HUB.rstrip("/"):
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for pdf_href in RE_PDF.findall(html):
                pdf = urljoin(page_url, pdf_href)
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = _clean(Path(urllib.parse.unquote(pdf)).name)
                rows.append(
                    {
                        "titulo": name or Path(page_url).name,
                        "fecha": _parse_fecha_dmy(name),
                        "url": page_url,
                        "pdf_url": pdf,
                        "origen": "wp_hub_pdf",
                    }
                )
        return rows

    def _parse_transparencia_epigrafe(self, epi: int) -> tuple[str, list[int], list[dict[str, Any]]]:
        try:
            html = self._fetch(_epigrafe_url(epi), encoding="iso-8859-15")
        except urllib.error.URLError:
            return "", [], []
        children = [int(m.group(1)) for m in re.finditer(r"pulsaEpigrafe\((\d+)\)", html)]
        docs: list[dict[str, Any]] = []
        header = ""
        hm = re.search(r'\$\("#textoCabecera"\)\.html\("([^"]+)"\)', html)
        if hm:
            header = _clean(hm.group(1))
        for m in re.finditer(r'tbody"\)\.append\("((?:[^"\\]|\\.)*)"\)', html):
            chunk = m.group(1).encode("utf-8").decode("unicode_escape")
            dm = re.search(r"verDoc\((\d+)\)'[^>]*>(?:<[^>]+>)*\s*([^<]+)", chunk)
            if not dm:
                continue
            titulo = _clean(dm.group(2))
            docs.append(
                {
                    "id_doc": dm.group(1),
                    "titulo": titulo,
                    "fecha": _parse_fecha_dmy(titulo),
                    "url": _epigrafe_url(epi),
                    "section": header,
                    "origen": "eamic_transparencia",
                }
            )
        return header, children, docs

    def _collect_transparencia_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_epi: set[int] = set()
        queue = [TRANSPARENCIA_ROOT]
        while queue and len(seen_epi) < TRANSPARENCIA_MAX_EPIGRAFES:
            epi = queue.pop(0)
            if epi in seen_epi:
                continue
            seen_epi.add(epi)
            _header, children, docs = self._parse_transparencia_epigrafe(epi)
            rows.extend(docs)
            for child in children:
                if child not in seen_epi:
                    queue.append(child)
        return rows

    def _wfs_page_url(self, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": f"ms:{self.icv_layer}",
                "count": "200",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{self.icv_wfs_url}?{params}"

    def _parse_wfs_member(self, member: ET.Element) -> dict[str, Any] | None:
        feat = None
        for child in member:
            if child.tag.endswith("InventarioSuSuz"):
                feat = child
                break
        if feat is None:
            return None
        cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
        if cod != self.cod_ine_mun:
            return None
        fid = feat.findtext("ms:id", default="", namespaces=_GML_NS) or ""
        pp = _clean(feat.findtext("ms:pp", default="", namespaces=_GML_NS) or "")
        ue = _clean(feat.findtext("ms:ue", default="", namespaces=_GML_NS) or "")
        clas = _clean(feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or "")
        f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
        titulo = pp or ue or f"Unidad {fid}"
        if ue and ue not in titulo:
            titulo = f"{titulo} ({ue})"
        geom = _gml_feature_to_geojson(feat)
        url = self._wfs_page_url(0)
        rec: dict[str, Any] = {
            "titulo": titulo[:500],
            "fecha": f_aprob,
            "url": url,
            "tipo": "sector SU/SUZ" if clas else "zonificación",
            "clasificacion": clas or None,
            "pp": pp or None,
            "ue": ue or None,
            "wfs_id": f"InventarioSuSuz:{fid}",
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
        return rec

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        start = 0
        while start < 10000:
            url = self._wfs_page_url(start)
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": self.config.get("user_agent", "poc-bocm-elda/1.0")},
                )
                raw = urllib.request.urlopen(req, timeout=90).read()
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", _GML_NS)
            if not members:
                break
            page_hits = 0
            for member in members:
                rec = self._parse_wfs_member(member)
                if rec and rec["wfs_id"] not in seen:
                    seen.add(rec["wfs_id"])
                    rows.append(rec)
                    page_hits += 1
            if page_hits == 0 and start > 3000:
                break
            start += 200
            time.sleep(self.delay_s)
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
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "section", "pp", "ue"))
        hit = self._match_wfs(blob)
        if not hit:
            return
        for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if hit.get(key) is not None:
                rec[key] = hit[key]

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
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
        self._attach_geometry(rec)
        return rec

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        section = row.get("section") or ""
        titulo = row["titulo"]
        if section and section.lower() not in titulo.lower():
            titulo = f"{section}: {titulo}"
        blob = titulo
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"doc:{row.get('id_doc') or row['url']}:{titulo}"),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "section": section or None,
            "id_doc": row.get("id_doc"),
        }
        self._attach_geometry(rec)
        return rec

    def _wfs_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("wfs_id") or row["titulo"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row["titulo"]),
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
        return rec

    def _wp_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        if RE_NOISE.search(row["titulo"]) and not RE_LICENCIA.search(row["titulo"]):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "noticia licencias",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _tramite_informativo(self, titulo: str, url: str) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": None,
            "tipo": "trámite informativo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": url,
            "source": "ayuntamiento",
            "nota": "Página informativa sede EAMIC; sin registro público de concesiones",
            "origen": "sede_tramite",
        }

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for titulo, url in LICENCIA_TRAMITE_URLS:
            rec = self._tramite_informativo(titulo, url)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_wp_articles():
            rec = self._wp_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites_wp"}

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
            add(self._wfs_to_proyecto(item))
        for item in self._collect_transparencia_docs():
            add(self._doc_to_proyecto(item))
        for item in self._collect_wp_hub_pdfs():
            add(self._doc_to_proyecto(item))
        for item in self._collect_wp_articles():
            add(self._wp_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "eamic_transparencia"),
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **result}
