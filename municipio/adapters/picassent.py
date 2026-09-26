from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

BASE = "https://www.picassent.es"
SEDE = "https://picassent.sedipualba.es"
GOVERNALIA_PLANEAMIENTO = (
    "https://picassent.governalia.es/es/transparencia/planes-urbanisticos-y-estudios-de-impacto-ambiental/"
)
GVA_PG_INDEX = (
    "https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/"
    "4%20VALENCIA/46194%20PICASSENT/1%20P.%20GENERAL/"
)
MUNICIPIO = "Picassent"
ID_PREFIX = "picassent"
INE_MUN = "46194"

TABLON_RSS = f"{SEDE}/tablondeanuncios/tablon_rss.aspx"
CATALOGO_TRAMITES = f"{SEDE}/catalogoservicios.aspx?ambito=1&area=1635"

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/es/seccion/urbanisme",
    GOVERNALIA_PLANEAMIENTO,
    GVA_PG_INDEX,
]

RE_TRAMITE = re.compile(
    r'href="(https://picassent\.sedipualba\.es/carpetaciudadana/tramite\.aspx\?idtramite=\d+)"[^>]*>'
    r"\s*URB[^<]*-\s*([^<]+)",
    re.I,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf)"', re.I)
RE_H2 = re.compile(r'<h2[^>]*class="wp-block-heading"[^>]*>([^<]+)</h2>', re.I)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"primera ocupaci[oó]n|obra[s]? (?:major|menor)|autoritzaci[oó]|\blam\b|exp \d+/\d+)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pri|peri|"
    r"informaci[oó]n p[uú]blica|expedient|expropi|projecte|modificaci[oó]n|"
    r"estudi(?:s)? (?:de )?detall|reparcel|conveni|sector|ue-|sd-|suz|fotovolt|"
    r"participaci[oó]|reforma interior|urbanitz|parcel)",
)
RE_NOISE = re.compile(
    r"(?i)(subvenci[oó]n|igualtat|cultural|festiu|ve[iï]nal|musical|empadron|"
    r"compte general|matr[ií]cula iae|borsa de treball|cessi[oó] d.us|personal|"
    r"policia local|psic[oó]logo|padr[oó]n tasa|residuos s[oó]lidos)",
)
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|PRI|PERI|PE|PAI|RES|SUZ[R]?)[\s\-]?(?:IND\s*)?[\dA-Z]+(?:[\s,\-yY/]+[\dA-Z]+)*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_GVA_FOLDER = re.compile(r'href="([^"]+)"[^>]*>([^<]+)</a>', re.I)

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER = "ms:InventarioSuSuz"

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "fotovolt" in n:
        return "instalación fotovoltaica"
    if "expropi" in n:
        return "expropiación"
    if "plan especial" in n or "peri" in n or "pri" in n or "reforma interior" in n:
        return "plan especial reforma interior"
    if "plan parcial" in n or re.search(r"\bpp[\s-]", n):
        return "plan parcial"
    if "estudi" in n and "detall" in n:
        return "estudio de detalle"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "pgou" in n or "plan general" in n:
        return "plan general"
    if re.search(r"\b(sd|ue|sector|suz)", n):
        return "sector planeamiento"
    if "informaci" in n:
        return "información pública"
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


class PicassentAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal picassent.es + sede sedipualba + governalia transparencia + ICV WFS InventarioSuSuz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60, retries: int = 3, encoding: str = "utf-8") -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-picassent/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read()
                    if encoding == "latin-1":
                        return raw.decode("latin-1", errors="replace")
                    return raw.decode(encoding, errors="replace")
            except (urllib.error.URLError, ConnectionResetError, TimeoutError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

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

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_TRAMITES)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for href, title in RE_TRAMITE.findall(html):
            rows.append(
                {
                    "titulo": _clean(f"URB - {title}"),
                    "url": href,
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(TABLON_RSS, encoding="latin-1")
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        for item in root.findall(".//item"):
            title = _clean(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            fecha = _parse_rss_date(item.findtext("pubDate") or "")
            if not title or not link:
                continue
            rows.append({"titulo": title, "url": link, "fecha": fecha, "origen": "tablon_rss"})
        return rows

    def _collect_governalia_planeamiento(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(GOVERNALIA_PLANEAMIENTO)
        except urllib.error.URLError:
            return rows

        sections = RE_H2.findall(html)
        current_section = "Planeamiento"
        parts = re.split(r'(<h2[^>]*class="wp-block-heading"[^>]*>[^<]+</h2>)', html, flags=re.I)
        for part in parts:
            h2 = RE_H2.search(part)
            if h2:
                current_section = _clean(h2.group(1))
                rows.append(
                    {
                        "titulo": current_section,
                        "url": GOVERNALIA_PLANEAMIENTO,
                        "fecha": _parse_fecha_dmy(current_section),
                        "tipo": _proyecto_tipo(current_section),
                        "origen": "governalia_seccion",
                    }
                )
                continue
            for href in RE_PDF.findall(part):
                pdf_url = href if href.startswith("http") else urllib.parse.urljoin(GOVERNALIA_PLANEAMIENTO, href)
                name = urllib.parse.unquote(pdf_url.rsplit("/", 1)[-1]).replace(".pdf", "").replace("-", " ")
                titulo = f"{current_section} — {name}"[:500]
                rows.append(
                    {
                        "titulo": titulo,
                        "url": pdf_url,
                        "fecha": _parse_fecha_dmy(titulo) or _parse_fecha_dmy(current_section),
                        "tipo": _proyecto_tipo(f"{current_section} {name}"),
                        "origen": "governalia_pdf",
                    }
                )
        return rows

    def _collect_gva_index(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(GVA_PG_INDEX)
        except urllib.error.URLError:
            return rows
        for href, label in RE_GVA_FOLDER.findall(html):
            if href.startswith("?"):
                continue
            url = urllib.parse.urljoin(GVA_PG_INDEX, href)
            titulo = _clean(label)
            if not titulo or titulo in {".", "..", "Parent Directory"}:
                continue
            rows.append(
                {
                    "titulo": f"GVA — {titulo}"[:500],
                    "url": url,
                    "fecha": _parse_fecha_dmy(titulo),
                    "tipo": _proyecto_tipo(titulo),
                    "origen": "gva_registro",
                }
            )
        return rows

    def _wfs_page_url(self, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": ICV_LAYER,
                "count": "200",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{ICV_WFS}?{params}"

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        start = 0
        while start < 8000:
            url = self._wfs_page_url(start)
            try:
                raw = self._fetch(url, timeout=90)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", _GML_NS)
            if not members:
                break
            for member in members:
                feat = member.find("ms:InventarioSuSuz", _GML_NS)
                if feat is None:
                    continue
                cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
                if cod != INE_MUN:
                    continue
                fid = feat.findtext("ms:id", default="", namespaces=_GML_NS) or ""
                pp = _clean(feat.findtext("ms:pp", default="", namespaces=_GML_NS) or "")
                ue = _clean(feat.findtext("ms:ue", default="", namespaces=_GML_NS) or "")
                clas = _clean(feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or "")
                f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
                titulo = pp
                if ue and ue not in titulo:
                    titulo = f"{pp} ({ue})" if pp else ue
                if not titulo:
                    titulo = f"Sector {fid}"
                geom = _gml_feature_to_geojson(feat)
                rec: dict[str, Any] = {
                    "titulo": titulo[:500],
                    "fecha": f_aprob,
                    "url": url,
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
            start += 200
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
            "nota": "Página informativa sedipualba; sin registro público de concesiones",
            "origen": row.get("origen"),
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "edicto tablón",
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
        blob = row["titulo"]
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob) and row.get("origen") not in {
            "governalia_seccion",
            "governalia_pdf",
            "gva_registro",
            "icv_wfs",
        }:
            return None
        return self._to_proyecto(row)

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return self._to_proyecto(row)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon_rss():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites_tablon"}

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
        for item in self._collect_governalia_planeamiento():
            add(self._portal_to_proyecto(item))
        for item in self._collect_gva_index():
            add(self._portal_to_proyecto(item))
        for item in self._collect_tablon_rss():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "governalia": sum(1 for r in rows if str(r.get("origen", "")).startswith("governalia")),
            "gva": sum(1 for r in rows if r.get("origen") == "gva_registro"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_rss"),
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
