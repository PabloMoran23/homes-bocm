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

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

BASE = "https://www.ondara.org"
SEDE_BASE = "https://ondara.sedelectronica.es"
MUNICIPIO = "Ondara"
ID_PREFIX = "ondara"
INE_COD_MUN = "03093"

TRANSPARENCY_URBANISMO = (
    f"{SEDE_BASE}/transparency/52540845-cbee-4e1c-9a3a-7c66289baf5e/"
)
URBANISMO_URL = f"{BASE}/serveis-municipals/urbanisme-2/"

GVA_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
GVA_WFS_TYPE = "ms:Planeamiento.Zonificacion"

WP_PDF_SEEDS: list[dict[str, str]] = [
    {
        "url": f"{BASE}/wp-content/uploads/2025/09/PLANOL-ONDARA.pdf",
        "titulo": "Plànol d'Ondara",
        "tipo": "documentación urbanística",
        "fecha": "2025-09-01",
    },
    {
        "url": f"{BASE}/wp-content/uploads/2025/03/PLA-SOSTENIBILITAT-TURISTICA-ONDARA-24-29.pdf",
        "titulo": "Pla de Sostenibilitat Turística Ondara 2024-2029",
        "tipo": "plan turístico-urbanístico",
        "fecha": "2025-03-01",
    },
]

ICV_ZONES: list[dict[str, str]] = [
    {
        "expediente": "19920509",
        "denominaci": "Revisión normas subsidiarias",
        "tipo": "normas subsidiarias",
    },
    {
        "expediente": "20060095",
        "denominaci": 'HOMOLOGACIÓN Y PP. DE MEJORA SECTOR "SALINETAS"',
        "tipo": "plan parcial",
    },
    {
        "expediente": "20020808",
        "denominaci": "P.P. REFUNDIDO DEL SECTOR SAU/I 2 DE LAS NN.SS",
        "tipo": "plan parcial",
    },
    {
        "expediente": "19920509",
        "denominaci": "REVISIÓN NNSS, SAU / E",
        "tipo": "normas subsidiarias",
    },
    {
        "expediente": "19920509",
        "denominaci": "REVISIÓN NNSS, SAU / D",
        "tipo": "normas subsidiarias",
    },
    {
        "expediente": "20060096",
        "denominaci": "P.P. DEL SECTOR 'LA SERRETA'",
        "tipo": "plan parcial",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:major|menor|nova|nova)|"
    r"primera ocupaci[oó]n|inicio de obra|cartell acreditatiu|legalitat urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|urbanisme|planeam|plan (?:parcial|especial|general)|pgou|pge|"
    r"informaci[oó]n p[uú]blica|expedient|projecte|proyecto|modificaci[oó]n|reparcel|"
    r"aprobaci[oó]n|edicto|dogv|bopa|sector|suelo|nnss|normes subsidi|salinet|serreta|"
    r"sostenibilitat tur|planol|homologaci[oó]n|sau\b)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocat[oò]ria.*empleo|"
    r"subvenci[oó]n|padron|padr[oó]|junta de govern|ple municipal|contractaci|"
    r"ocupaci[oó] p[uú]blica|bases t[eè]cnic|conserge|video c[aà]meres)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://ondara\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_TRANSPARENCY_ROW = re.compile(r"<tr[^>]*>.*?</tr>", re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _fecha_from_expediente(expediente: str) -> str | None:
    digits = re.sub(r"\D", "", expediente or "")
    if len(digits) >= 8:
        try:
            y, mo, d = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
            if 1980 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(expediente or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").upper().replace("Ó", "O").replace("É", "E").replace("Í", "I"))


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "plan parcial" in n or "sector" in n or "salinet" in n or "serreta" in n:
        return "plan parcial"
    if "normas subsidi" in n or "nnss" in n:
        return "normas subsidiarias"
    if "homologaci" in n:
        return "homologación planeamiento"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n or "bopa" in n or "dogv" in n:
        return "información pública"
    if "sostenibilitat" in n or "tur" in n:
        return "plan turístico"
    if "planol" in n or "plànol" in n:
        return "documentación urbanística"
    if "licencia" in n or "llic" in n:
        return "licencia publicada"
    return "planeamiento"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.split() if x.strip()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lng = nums[i], nums[i + 1]
        ring.append([lng, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _merge_geometries(geoms: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for g in geoms:
        t = g.get("type")
        coords = g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class OndaraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress ondara.org + sede espublico gestiona + ICV GVA WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.transparency_url = str(
            self.config.get("transparency_urbanismo_url") or TRANSPARENCY_URBANISMO
        )
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._gva_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ondara/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

    def _collect_transparency(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TRANSPARENCY_ROW.finditer(html):
            row_html = m.group(0)
            if "preview-document" not in row_html:
                continue
            preview_m = RE_PREVIEW_LINK.search(row_html)
            if not preview_m:
                continue
            url = self._abs_sede(preview_m.group(1))
            if url in seen:
                continue
            seen.add(url)
            titulo = _strip_html(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            if title_m and len(title_m.group(1).strip()) > 10:
                titulo = title_m.group(1).strip()
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(titulo),
                    "url": url,
                    "origen": "sede_transparencia",
                    "blob": titulo,
                }
            )
        return rows

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
            url = self._abs_sede(url)
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
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _collect_wp_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in WP_PDF_SEEDS:
            rows.append(
                {
                    "titulo": seed["titulo"],
                    "fecha": seed.get("fecha"),
                    "url": seed["url"],
                    "tipo": seed.get("tipo") or "planeamiento",
                    "origen": "web_pdf",
                    "blob": seed["titulo"],
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tauler d'anuncis — licencias y edictos urbanísticos",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y edictos publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias, DR y comunicaciones previas vía sede (sin histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "información trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanisme — normativa y trámites",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Página municipal con normativa urbanística y enlaces a sede",
                "origen": "web_urbanismo",
            },
        ]

    def _load_gva_features(self) -> list[dict[str, Any]]:
        if self._gva_cache is not None:
            return self._gva_cache
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": GVA_WFS_TYPE,
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "count": "8000",
            }
        )
        url = f"{GVA_WFS}?{params}"
        feats: list[dict[str, Any]] = []
        try:
            raw = self._fetch(url, timeout=180)
            root = ET.fromstring(raw)
        except (urllib.error.URLError, ET.ParseError):
            self._gva_cache = feats
            return feats
        ns = {
            "wfs": "http://www.opengis.net/wfs/2.0",
            "gml": "http://www.opengis.net/gml",
        }
        for member in root.findall(".//{http://www.opengis.net/wfs/2.0}member"):
            feat_el = member[0]
            props: dict[str, str] = {}
            geom = None
            for child in feat_el:
                tag = child.tag.split("}")[-1]
                if tag == "msGeometry":
                    pos = child.find(".//{http://www.opengis.net/gml}posList", ns)
                    if pos is not None and pos.text:
                        geom = _gml_poslist_to_polygon(pos.text)
                else:
                    props[tag] = (child.text or "").strip()
            if props.get("cod_ine_mun") != INE_COD_MUN:
                continue
            if not geom:
                continue
            label = props.get("denominaci") or props.get("expediente") or ""
            feats.append(
                {
                    "label": label,
                    "zon_suelo": props.get("zon_suelo") or "",
                    "descripcio": props.get("descripcio") or "",
                    "info_adici": props.get("info_adici") or "",
                    "expediente": props.get("expediente") or "",
                    "geom": geom,
                    "source_url": (
                        f"{GVA_WFS}?service=WFS&request=GetFeature&"
                        f"typeName={GVA_WFS_TYPE}&count=8000"
                    ),
                }
            )
        self._gva_cache = feats
        return feats

    def _match_icv_zone(self, titulo: str) -> dict[str, str] | None:
        norm = _normalize_title(titulo)
        best: tuple[float, dict[str, str]] | None = None
        for zone in ICV_ZONES:
            den = _normalize_title(zone["denominaci"])
            score = 0.0
            if den and den in norm:
                score = 100.0
            else:
                tokens = [t for t in re.split(r"[^A-Z0-9]+", den) if len(t) >= 5]
                hits = sum(1 for t in tokens if t in norm)
                score = hits * 12.0
            for token in ("SALINET", "SERRETA", "NNSS", "SAU"):
                if token in norm and token in den:
                    score += 20.0
            if score > 0 and (best is None or score > best[0]):
                best = (score, zone)
        if best and best[0] >= 24:
            return best[1]
        return None

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        zone = self._match_icv_zone(titulo)
        if zone:
            exp = zone.get("expediente", "")
            den = _normalize_title(zone.get("denominaci", ""))
            candidates: list[tuple[float, dict[str, Any], str]] = []
            for item in self._load_gva_features():
                label = _normalize_title(item["label"])
                score = 0.0
                if den and den == label:
                    score = 100.0
                elif den and den in label:
                    score = 80.0
                elif exp and exp == item.get("expediente"):
                    score = 60.0
                if score >= 60:
                    candidates.append((score, item["geom"], item["source_url"]))
            if candidates:
                candidates.sort(key=lambda x: -x[0])
                merged = _merge_geometries([g for _, g, _ in candidates[:3]])
                if merged:
                    return {
                        "geom_geojson": merged,
                        "geometry_source": "portal_wfs",
                        "geometry_source_url": candidates[0][2],
                        "coord_source": "portal_geometry_centroid",
                    }

        title_low = (titulo or "").lower()
        keys: list[str] = []
        for token in (
            "salinet",
            "serreta",
            "nnss",
            "normas subsidi",
            "plan parcial",
            "plan general",
            "homologaci",
            "sau",
        ):
            if token in title_low:
                keys.append(token)
        candidates = []
        for item in self._load_gva_features():
            blob = " ".join(
                [
                    item["label"].lower(),
                    item.get("descripcio", "").lower(),
                    item.get("info_adici", "").lower(),
                    item.get("zon_suelo", "").lower(),
                ]
            )
            score = sum(20 for k in keys if k in blob or k in title_low)
            if score >= 20:
                candidates.append((score, item["geom"], item["source_url"]))
        if not candidates:
            return None
        candidates.sort(key=lambda x: -x[0])
        merged = _merge_geometries([g for _, g, _ in candidates[:3]])
        if not merged:
            return None
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": candidates[0][2],
            "coord_source": "portal_geometry_centroid",
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_icv_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        visor_url = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"
        seen: set[str] = set()
        for zone in ICV_ZONES:
            key = f"{zone['expediente']}:{zone['denominaci']}"
            if key in seen:
                continue
            seen.add(key)
            titulo = zone["denominaci"]
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv:{key}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_expediente(zone.get("expediente", "")),
                "tipo": zone.get("tipo") or "planeamiento",
                "url": visor_url,
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "expte": zone.get("expediente"),
            }
            self._enrich_geometry(rec)
            rows.append(rec)
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "llic", "urban", "actividad", "legalidad")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _transparency_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row.get("blob") or row.get("titulo") or ""):
            return None
        key = row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_transparencia",
        }
        self._enrich_geometry(rec)
        return rec

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web_pdf",
        }
        self._enrich_geometry(rec)
        return rec

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif "legalidad" in proc:
            tipo = "protección legalidad urbanística"
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
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
            "origen": "sede_board",
        }
        self._enrich_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "sede_board",
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
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_board"),
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

        for rec in self._collect_icv_proyectos():
            add(rec)
        for item in self._collect_wp_pdfs():
            add(self._wp_to_proyecto(item))
        for item in self._collect_transparency():
            add(self._transparency_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "web_pdf": sum(1 for r in rows if r.get("origen") == "web_pdf"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "sede_transparencia"),
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_board"),
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
