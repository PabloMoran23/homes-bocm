from __future__ import annotations

import hashlib
import http.cookiejar
import json
import math
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
from municipio.geometry import geometry_centroid

SEDE_BASE = "https://adeje.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
MUNICIPIO = "Adeje"
ID_PREFIX = "adeje"
SITCAN_PACKAGE = "planeamiento-urbanistico-de-adeje"
GEOBDP_MUNICIPIO = "https://geobdp.grafcan.es/core/municipios/38001/"
NORMATIVA_URL = (
    f"{SEDE_BASE}/citizen-service/481ea75d-2411-4f93-8dc9-19f0deae5af9"
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|licencia apertura|segregaci[oó]n|parcelaci[oó]n|vado)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgo|pgou|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto de urbaniz|modificaci[oó]n|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|planimetr|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|rectificaci[oó]n|exposici[oó]n p[uú]blica|"
    r"calificaci[oó]n|supletorio|actuaci[oó]n en medio urbano|revisi[oó]n parcial|"
    r"texto refundido|suspensi[oó]n de determinaciones|programa de actuaci|"
    r"evaluaci[oó]n ambiental|consulta p[uú]blica)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"decreto alc|decreto cde|decreto gho|decreto ppt|junta de gobierno|pleno|"
    r"comisi[oó]n informativa|herederos|sustituci[oó]n del alcalde|notoriedad)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://adeje\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DOT = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_GEOBDP_DOC = re.compile(
    r'href="/core/documentos/(\d+)\.html">([^<]+)',
    re.I,
)
RE_ZOOM_EXTENT = re.compile(
    r"App\.Map\.zoomToExtent\((\{.*?\})\);",
    re.S,
)
RE_GEOBDP_URL = re.compile(r"geobdp\.grafcan\.es/core/documentos/(\d+)")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_title(text: str) -> str:
    t = unescape(text or "").lower()
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DOT):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "plan parcial" in b or " pp " in b:
        return "plan parcial"
    if "plan especial" in b or "reforma interior" in b:
        return "plan especial"
    if "pgo" in b or "pgou" in b or "plan general" in b:
        return "PGOU"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "modificaci" in b and ("menor" in b or "puntual" in b):
        return "modificación puntual"
    if "revisi" in b and "parcial" in b:
        return "revisión parcial"
    if "reparcel" in b:
        return "reparcelación"
    if "programa de actuaci" in b:
        return "programa actuación"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "evaluaci" in b and "ambiental" in b:
        return "evaluación ambiental"
    if "consulta p" in b and "blica" in b:
        return "consulta pública"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


def _is_valid_canarias(lng: float, lat: float) -> bool:
    return 27.0 <= lat <= 30.0 and -19.0 <= lng <= -12.0


def _utm28n_to_wgs84(easting: float, northing: float) -> tuple[float, float] | None:
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e = math.sqrt(2 * f - f * f)
    e2 = e * e / (1 - e * e)
    zone = 28
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)

    x = easting - 500000.0
    y = northing
    m = y / k0
    mu = m / (a * (1 - e**2 / 4 - 3 * e**4 / 64 - 5 * e**6 / 256))

    e1 = (1 - math.sqrt(1 - e**2)) / (1 + math.sqrt(1 - e**2))
    phi1 = mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
    phi1 += (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
    phi1 += (151 * e1**3 / 96) * math.sin(6 * mu)

    n1 = a / math.sqrt(1 - e**2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = e2 * math.cos(phi1) ** 2
    r1 = a * (1 - e**2) / (1 - e**2 * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * k0)

    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e2) * d**4 / 24
    )
    lon = lon0 + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e2 + 24 * t1**2) * d**5 / 120
    ) / math.cos(phi1)

    lng_deg = math.degrees(lon)
    lat_deg = math.degrees(lat)
    if not _is_valid_canarias(lng_deg, lat_deg):
        return None
    return lng_deg, lat_deg


def _reproject_coords(node: Any) -> Any:
    if isinstance(node, (list, tuple)):
        if (
            len(node) >= 2
            and isinstance(node[0], (int, float))
            and isinstance(node[1], (int, float))
            and not isinstance(node[0], bool)
        ):
            out = _utm28n_to_wgs84(float(node[0]), float(node[1]))
            if out:
                return [out[0], out[1]]
            return [float(node[0]), float(node[1])]
        return [_reproject_coords(x) for x in node]
    return node


def _first_coord_pair(node: Any) -> tuple[float, float] | None:
    if isinstance(node, (list, tuple)):
        if (
            len(node) >= 2
            and isinstance(node[0], (int, float))
            and isinstance(node[1], (int, float))
            and not isinstance(node[0], bool)
        ):
            return float(node[0]), float(node[1])
        for item in node:
            pair = _first_coord_pair(item)
            if pair:
                return pair
    return None


def _reproject_geometry(geom: dict[str, Any]) -> dict[str, Any] | None:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not gtype or coords is None:
        return None
    out = {"type": gtype, "coordinates": _reproject_coords(coords)}
    pair = _first_coord_pair(out["coordinates"])
    if not pair or not _is_valid_canarias(pair[0], pair[1]):
        return None
    return out


class AdejeAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona (tablón) + SITCAN CKAN + GEOBDP Grafcan (Canarias)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.sitcan_package = str(self.config.get("sitcan_package") or SITCAN_PACKAGE)
        self.geobdp_municipio = str(self.config.get("geobdp_municipio") or GEOBDP_MUNICIPIO)
        self._geobdp_doc_index: dict[str, str] | None = None
        self._geometry_cache: dict[str, dict[str, Any] | None] = {}
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-adeje/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_sede(self, href: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        if href.startswith("http"):
            return href
        return urllib.parse.urljoin(f"{self.sede_base}/", href.lstrip("/"))

    def _load_geobdp_index(self) -> dict[str, str]:
        if self._geobdp_doc_index is not None:
            return self._geobdp_doc_index
        index: dict[str, str] = {}
        try:
            html = self._fetch(self.geobdp_municipio)
        except urllib.error.URLError:
            self._geobdp_doc_index = index
            return index
        for m in RE_GEOBDP_DOC.finditer(html):
            doc_id, title = m.group(1), _strip_html(m.group(2))
            index[_norm_title(title)] = doc_id
            short = _norm_title(re.sub(r"\(.*\)$", "", title))
            if short:
                index.setdefault(short, doc_id)
        self._geobdp_doc_index = index
        return index

    def _match_geobdp_doc(self, title: str, urls: list[str]) -> str | None:
        for url in urls:
            m = RE_GEOBDP_URL.search(url or "")
            if m:
                return m.group(1)
        norm = _norm_title(title)
        idx = self._load_geobdp_index()
        if norm in idx:
            return idx[norm]
        for key, doc_id in idx.items():
            if len(key) > 20 and (key in norm or norm in key):
                return doc_id
        return None

    def _fetch_geobdp_geometry(self, doc_id: str) -> dict[str, Any] | None:
        if doc_id in self._geometry_cache:
            return self._geometry_cache[doc_id]
        url = f"https://geobdp.grafcan.es/core/documentos/{doc_id}.html"
        geom_out: dict[str, Any] | None = None
        try:
            html = self._fetch(url)
            m = RE_ZOOM_EXTENT.search(html)
            if m:
                fc = json.loads(m.group(1))
                features = fc.get("features") or []
                if features:
                    raw_geom = features[0].get("geometry")
                    if isinstance(raw_geom, dict):
                        geom_out = _reproject_geometry(raw_geom)
        except (urllib.error.URLError, json.JSONDecodeError, ValueError):
            geom_out = None
        self._geometry_cache[doc_id] = geom_out
        return geom_out

    def _attach_geometry(self, rec: dict[str, Any], title: str, urls: list[str]) -> None:
        doc_id = self._match_geobdp_doc(title, urls)
        if not doc_id:
            return
        geom = self._fetch_geobdp_geometry(doc_id)
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_geobdp_grafcan"
        rec["geometry_source_url"] = f"https://geobdp.grafcan.es/core/documentos/{doc_id}.html"
        rec["coord_source"] = "portal_geometry_centroid"
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_sitcan(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        api = (
            "https://opendata.sitcan.es/api/3/action/package_show"
            f"?id={urllib.parse.quote(self.sitcan_package)}"
        )
        try:
            payload = self._fetch_json(api)
        except (urllib.error.URLError, json.JSONDecodeError):
            return rows
        resources = (payload.get("result") or {}).get("resources") or []
        seen: set[str] = set()
        grouped: dict[str, dict[str, Any]] = {}
        for res in resources:
            name = (res.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            url = (res.get("url") or "").strip()
            grouped[name] = {
                "titulo": name[:500],
                "fecha": _fecha_from_blob(name),
                "url": url or f"https://opendata.sitcan.es/dataset/{self.sitcan_package}",
                "blob": name,
                "origen": "sitcan_ckan",
                "urls": [url] if url else [],
            }
        for res in resources:
            name = (res.get("name") or "").strip()
            if name not in grouped:
                continue
            url = (res.get("url") or "").strip()
            if url and url not in grouped[name]["urls"]:
                grouped[name]["urls"].append(url)
            if url and "geobdp" in url:
                grouped[name]["url"] = url
        return list(grouped.values())

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

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            url = self._abs_sede(url)

            titulo = cells.get("class_description") or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()

            expediente = cells.get("class_folderCode", "")
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": cells.get("class_folderName", "")[:200],
                    "categoria": cells.get("class_boardCategory", "")[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(cells.get("class_dateFrom", "")),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {cells.get('class_folderName', '')} "
                        f"{cells.get('class_boardCategory', '')} "
                        f"{cells.get('class_description', '')} "
                        f"{title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if cat == "urbanismo" or any(k in proc for k in ("planeamiento", "licencia", "urban", "obra")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        tramites = [
            ("tablon_sede", "Tablón de anuncios — licencias y urbanismo", self.board_url, "tablón"),
            ("sede_dossier", "Catálogo de trámites — sede electrónica", f"{self.sede_base}/dossier", "trámites"),
            ("normativa", "Normativa urbanística", NORMATIVA_URL, "normativa urbanística"),
            ("sede_info", "Información pública — sede electrónica", f"{self.sede_base}/info", "información pública"),
        ]
        rows: list[dict[str, Any]] = []
        for key, titulo, url, tipo in tramites:
            rows.append(
                {
                    "id": _stable_id("lic", key),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_info",
                }
            )
        return rows

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        return {
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
            "origen": "tablon",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "urban" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }
        return rec

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        urls = row.get("urls") or [row.get("url", "")]
        self._attach_geometry(rec, row["titulo"], [u for u in urls if u])
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _dedupe(self, rows: list[dict[str, Any]], key: str = "id") -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            rid = row.get(key)
            if not rid or rid in seen:
                continue
            seen.add(rid)
            out.append(row)
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        raw = self._collect_licencia_info_pages()
        for item in self._collect_board():
            lic = self._board_to_licencia(item)
            if lic:
                raw.append(lic)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") == "tramite_info"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        stats = self.backfill_licencias(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": stats["rows"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return stats

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        raw: list[dict[str, Any]] = []
        for row in self._collect_sitcan():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        for item in self._collect_board():
            proy = self._board_to_proyecto(item)
            if proy:
                raw.append(proy)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sitcan": sum(1 for r in rows if r.get("origen") == "sitcan_ckan"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        stats = self.backfill_proyectos(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": stats["rows"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return stats
