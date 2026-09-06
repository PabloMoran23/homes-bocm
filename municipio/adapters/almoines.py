from __future__ import annotations

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

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

BASE = "https://www.almoines.es"
API_BASE = "https://api.digitalvalue.es/almoines/collections"
SEDE = "https://almoines.sedelectronica.es"
BOARD_URL = f"{SEDE}/board"
MUNICIPIO = "Almoines"
ID_PREFIX = "almoines"
INE_MUN = "46012"

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER_SU = "ms:InventarioSuSuz"
ICV_LAYER_ZON = "Planeamiento.Zonificacion"

HUB_SLUGS = {
    "normes-urbanistiques",
    "informacio-urbanistica",
    "text-consolidat-del-planejament-urbanistic-vigent",
    "descarrega-documents",
    "convenis-urbanistics",
    "modificacions-aprovades-al-pgou",
    "acces-a-la-informacio-publica-de-l-ajuntament",
    "dret-d-acces-a-la-informacio",
    "derecho-de-acceso-a-la-informacion",
    "punt-d-informacio-cadastral",
    "servici-d-informacio-de-whatsapp",
}

LICENCIA_INFO_SEEDS = [
    {
        "titulo": "Normes urbanístiques i tràmits (sede electrònica)",
        "url": f"{BASE}/pagina/normes-urbanistiques",
    },
    {
        "titulo": "Tauler d'anuncis — llicències i edictes urbanístics",
        "url": BOARD_URL,
    },
    {
        "titulo": "Tràmits en línia (sede electrònica Almoines)",
        "url": f"{SEDE}/dossier",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n.*obra|primera ocupaci[oó]n|obra[s]? (?:major|menor)|edificaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pge|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de )?detalle|sector|ue-|unidad de ejecuci|avaluaci[oó]n ambiental|"
    r"plantejament|homologaci[oó]n|mobilitat urbana|agenda urbana|conviure|pmus)",
)
RE_NOISE = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvenci[oó]n.*beca|plens municipals|horari|iae|cobranza|festes|"
    r"torneig|setmana esportiva|jurado|rept\b)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://almoines\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|SECTOR|FUENTE)[\s\-]?(?:[\dA-ZÁÉÍÓÚ'._\-]+(?:[\s,\-yY/]+[\dA-ZÁÉÍÓÚ'._\-]+)*))\b",
)

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


def _gml_find(feat: ET.Element, tag: str) -> ET.Element | None:
    el = feat.find(f"gml:{tag}", _GML_NS)
    if el is not None:
        return el
    return feat.find(f".//{{{_GML_NS['gml']}}}{tag}")


def _gml_findtext(feat: ET.Element, tag: str, default: str = "") -> str:
    el = _gml_find(feat, tag)
    return (el.text or default).strip() if el is not None else default


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _strip_html(text: str) -> str:
    return _clean(re.sub(r"<[^>]+>", " ", text or ""))


def _localized(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("es", "und", "va", "ca"):
            if value.get(key):
                return str(value[key])
        for v in value.values():
            if v:
                return str(v)
        return ""
    return str(value or "")


def _slug_value(item: dict[str, Any]) -> str:
    data = item.get("data") or {}
    slug = data.get("slug")
    if isinstance(slug, dict):
        return _localized(slug).strip("/")
    return str(slug or "").strip("/")


def _title(item: dict[str, Any]) -> str:
    return _strip_html(_localized(item.get("title")))


def _article_url(item: dict[str, Any]) -> str:
    rel = item.get("rel")
    if rel:
        return f"{BASE}/node/{rel}"
    slug = _slug_value(item)
    node_types = item.get("nodeTypes") or []
    if "pagina" in node_types and slug:
        return f"{BASE}/pagina/{slug}"
    if slug:
        return f"{BASE}/noticia-pagina/{slug}"
    return f"{BASE}/node/{item.get('_id', '')}"


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


def _article_fecha(item: dict[str, Any]) -> str | None:
    for key in ("date", "modified", "updated", "created"):
        raw = item.get(key)
        if not raw:
            continue
        text = str(raw)
        if "T" in text:
            return text.split("T", 1)[0]
        parsed = _parse_fecha_dmy(text)
        if parsed:
            return parsed
    return _parse_fecha_dmy(_title(item))


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "avaluaci" in n and "ambiental" in n:
        return "evaluación ambiental territorial"
    if "plan general" in n or "pgou" in n or "pge" in n:
        return "PGOU/PGE"
    if "plan parcial" in n or "sector" in n or "unidad de ejecuci" in n:
        return "plan parcial"
    if "mobilitat urbana" in n or "pmus" in n:
        return "plan movilidad urbana"
    if "agenda urbana" in n:
        return "agenda urbana"
    if "conviure" in n:
        return "plan Conviure"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "conveni" in n:
        return "convenio urbanístico"
    if "modificaci" in n:
        return "modificación planeamiento"
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
    poly = _gml_find(feat, "Polygon")
    if poly is None:
        return None
    pos = poly.find(f".//{{{_GML_NS['gml']}}}posList")
    if pos is None or not (pos.text or "").strip():
        return None
    return _gml_poslist_to_polygon(pos.text.strip())


class AlmoinesAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal DigitalValue (almoines.es) + sede espublico gestiona + ICV WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.api_base = str(self.config.get("api_base") or API_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_layer_su = str(geom_cfg.get("type_name_su") or ICV_LAYER_SU)
        self.icv_layer_zon = str(geom_cfg.get("type_name_zon") or ICV_LAYER_ZON)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or INE_MUN)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60, retries: int = 3) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-almoines/1.0")},
            )
            ctx = self._ssl_ctx if url.startswith("https://") else None
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, ConnectionResetError, TimeoutError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                clean = {k: v for k, v in row.items() if v is not None}
                f.write(json.dumps(clean, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def _fetch_all_articulos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        limit = 200
        while True:
            url = f"{self.api_base}/articulos?limit={limit}&offset={offset}"
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            batch = data.get("items", []) if isinstance(data, dict) else data
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return rows

    def _is_proyecto_article(self, item: dict[str, Any]) -> bool:
        slug = _slug_value(item).lower()
        if slug in HUB_SLUGS:
            return False
        title = _title(item)
        blob = f"{title} {slug}"
        if RE_NOISE.search(blob):
            return False
        if RE_PROYECTO.search(blob):
            return True
        if item.get("filesGroup") and (
            "informacio-publica" in slug
            or "informaci-publica" in slug
            or "expedient" in slug
            or "pgou" in slug
            or "planejament" in slug
        ):
            return True
        return False

    def _is_licencia_article(self, item: dict[str, Any]) -> bool:
        slug = _slug_value(item).lower()
        title = _title(item)
        blob = f"{title} {slug}"
        return bool(RE_LICENCIA.search(blob))

    def _article_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        title = _title(item)
        url = _article_url(item)
        blob = title
        files: list[str] = []
        for group in item.get("filesGroup") or []:
            if not isinstance(group, dict):
                continue
            for f in group.get("files") or []:
                if isinstance(f, dict):
                    ft = _localized(f.get("title"))
                    if ft:
                        files.append(ft)
                        blob = f"{blob} {ft}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": _article_fecha(item),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "slug": _slug_value(item),
            "origen": "digitalvalue_api",
        }
        if files:
            rec["documentos"] = files[:20]
        self._attach_geometry(rec)
        return rec

    def _article_to_licencia(self, item: dict[str, Any]) -> dict[str, Any]:
        title = _title(item)
        url = _article_url(item)
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": _article_fecha(item),
            "tipo": "información pública licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "url": url,
            "source": "ayuntamiento",
            "nota": "Publicación informativa; sin registro de concesiones",
            "origen": "digitalvalue_api",
        }

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
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento or documento in ("Documento",):
                continue

            blob = f"{documento} {expediente} {procedimiento} {categoria} {descripcion}"
            if self._board_non_urban(blob):
                continue
            if not (RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob)):
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
                    "blob": blob,
                    "origen": "sede_tablon",
                }
            )
        return rows

    def _board_non_urban(self, blob: str) -> bool:
        return bool(RE_NOISE.search(blob))

    def _wfs_page_url(self, type_name: str, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": type_name,
                "count": "200",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{self.icv_wfs_url}?{params}"

    def _parse_wfs_member(self, member: ET.Element, *, layer: str) -> dict[str, Any] | None:
        feat = None
        for tag in (f"{{{_GML_NS['ms']}}}{layer}", f"{{{_GML_NS['ms']}}}InventarioSuSuz"):
            feat = member.find(tag)
            if feat is not None:
                break
        if feat is None:
            for child in member:
                if child.tag.endswith("InventarioSuSuz") or child.tag.endswith("Zonificacion"):
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
        denom = _clean(
            feat.findtext("ms:denominaci", default="", namespaces=_GML_NS)
            or feat.findtext("ms:denominaci_val", default="", namespaces=_GML_NS)
            or ""
        )
        clas = _clean(feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or "")
        f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
        titulo = pp or denom or ue
        if ue and ue not in titulo:
            titulo = f"{titulo} ({ue})" if titulo else ue
        if not titulo:
            titulo = f"Sector {fid}"
        geom = _gml_feature_to_geojson(feat)
        rec: dict[str, Any] = {
            "titulo": titulo[:500],
            "fecha": f_aprob,
            "url": self._wfs_page_url(self.icv_layer_su, 0),
            "tipo": "sector SU/SUZ" if clas else "zonificación",
            "clasificacion": clas or None,
            "pp": pp or None,
            "ue": ue or None,
            "wfs_id": f"{layer}:{fid}",
            "origen": "icv_wfs",
        }
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = rec["url"]
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
        for type_name, layer in ((self.icv_layer_su, "InventarioSuSuz"),):
            start = 0
            while start < 15000:
                url = self._wfs_page_url(type_name, start)
                try:
                    raw = self._fetch(url, timeout=90)
                    root = ET.fromstring(raw)
                except (urllib.error.URLError, ET.ParseError):
                    break
                members = root.findall(".//wfs:member", _GML_NS)
                if not members:
                    break
                for member in members:
                    rec = self._parse_wfs_member(member, layer=layer.split(".")[-1])
                    if rec and rec["wfs_id"] not in seen:
                        seen.add(rec["wfs_id"])
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
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "pp", "ue", "slug"))
        hit = self._match_wfs(blob)
        if not hit:
            return
        for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if hit.get(key) is not None:
                rec[key] = hit[key]

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
            "documentos",
            "slug",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
        return rec

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for seed in LICENCIA_INFO_SEEDS:
            rec = {
                "id": _stable_id("lic", seed["url"]),
                "fecha_concesion": None,
                "tipo": "trámite informativo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": seed["titulo"],
                "url": seed["url"],
                "source": "ayuntamiento",
                "nota": "Página informativa; sin registro público de concesiones",
                "origen": "portal_seed",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._fetch_all_articulos():
            if not self._is_licencia_article(item):
                continue
            rec = self._article_to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_board():
            blob = item.get("blob") or item["titulo"]
            if not RE_LICENCIA.search(blob):
                continue
            rec = {
                "id": _stable_id("lic", item["url"]),
                "fecha_concesion": item.get("fecha"),
                "tipo": "edicto tablón",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": item["titulo"],
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "api_seeds_sede_tablon"}

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

        for item in self._fetch_all_articulos():
            if self._is_proyecto_article(item):
                add(self._article_to_proyecto(item))

        for wfs_row in self._collect_icv_wfs():
            add(self._to_proyecto(wfs_row))

        for item in self._collect_board():
            blob = item.get("blob") or item["titulo"]
            if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
                continue
            if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                continue
            if not RE_PROYECTO.search(blob):
                continue
            add(self._to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "digitalvalue_api_icv_wfs_sede"}

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
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
