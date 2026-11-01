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

WEB_BASE = "https://www.alcantarilla.es"
SEDE_BASE = "https://alcantarilla.sedipualba.es"
MUNICIPIO = "Alcantarilla"
ID_PREFIX = "alcantarilla"

PGOU_URL = f"{WEB_BASE}/areas/desarrollo-urbano/plan-de-ordenacion-urbana-de-alcantarilla/"
URBANISMO_AREA_URL = f"{SEDE_BASE}/catalogoservicios.aspx?area=1197&ambito=1"
TABLON_HOME = f"{SEDE_BASE}/"
TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
SITMURCIA_VISOR = "https://sitmurcia.carm.es/planeamiento-urbanistico"

WFS_URL = (
    "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo"
    "&CQL_FILTER=Municipio%3D%27Alcantarilla%27"
    "&count=1000&outputFormat=application/json&srsName=EPSG:4326"
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de parcelaci[oó]n)?|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n (?:previa|de ocupaci[oó]n)|"
    r"certificado urban|obra (?:mayor|menor)|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmo|modificaci[oó]n|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|reparcel|sector|suelo|"
    r"unidad(?:es)? de actuaci[oó]n|\bua-\d+\b|\buz[reae]-\d+|zonificaci[oó]n|"
    r"ordenanza|normas urban|pol[ií]gono (?:industrial|de (?:actuaci[oó]n|ejecuci[oó]n))|"
    r"dominio|cabezo verde|el soto|coroneja|borm\b|plano gu)",
)
RE_SKIP = re.compile(
    r"(?i)(oferta de empleo|empleo p[uú]blico|jurado|subvenci[oó]n|iae\b|ibi\b|"
    r"basura|tasa de recogida|polic[ií]a local|datos personales|tribunal|"
    r"antifraude|memoria.?rsc|c[oó]digo conducta)",
)
RE_TRAMITE = re.compile(
    r'href="(https://alcantarilla\.sedipualba\.es/carpetaciudadana/tramite\.aspx\?idtramite=\d+)"'
    r"[^>]*title='[^']*URBANISMO\.?\s*([^']+)'",
    re.I,
)
DEFAULT_LICENCIA_TRAMITES: list[dict[str, str]] = [
    {
        "url": f"{SEDE_BASE}/carpetaciudadana/tramite.aspx?idtramite=11664",
        "tipo": "Solicitud de licencia urbanística",
        "titulo": "URBANISMO. Solicitud de licencia urbanística",
    },
    {
        "url": f"{SEDE_BASE}/carpetaciudadana/tramite.aspx?idtramite=11666",
        "tipo": "Declaración responsable — ejecución de obras",
        "titulo": "URBANISMO. Declaración responsable en Materia Urbanística. Ejecución de obras",
    },
    {
        "url": f"{SEDE_BASE}/carpetaciudadana/tramite.aspx?idtramite=11665",
        "tipo": "Comunicación previa en materia urbanística",
        "titulo": "URBANISMO. Comunicación Previa en Materia Urbanística",
    },
]
RE_TABLON_ROW = re.compile(
    r'data-clickable-url="([^"]+)".*?anuncio-ts">([^<]+)</div>\s*<div class="anuncio-titulo">([^<]+)',
    re.S | re.I,
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{3,400})</a>', re.I)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b(UA-\d{1,3}|UZ[REAET]{1,2}-\d{1,3}|PE-\d+|PP-\d+|C\d+|CV\s*\d+)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_AD_DATE = re.compile(r"\bAD\s+(\d{1,2})/(\d{1,2})/(\d{4})\b", re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_AD_DATE, RE_FECHA_DMY):
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


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return None


def _normalize_ambit(raw: str) -> str:
    return re.sub(r"\s+", " ", unescape(raw or "").strip())


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "modificaci" in b and "pgou" in b:
        return "modificación PGOU"
    if "plan general" in b or "pgmo" in b:
        return "PGMO"
    if "pgou" in b:
        return "PGOU"
    if "plan parcial" in b:
        return "plan parcial"
    if re.search(r"\bua-\d+", b):
        return "unidad de actuación"
    if "polígono" in b or "poligono" in b:
        return "polígono urbanístico"
    if "dominio" in b:
        return "dominio público"
    if "informaci" in b:
        return "información pública"
    return "planeamiento"


class AlcantarillaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress alcantarilla.es + sede sedipualba + WFS planeamiento SITMURCIA (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.wfs_url = str(self.config.get("wfs_url") or WFS_URL)
        self._wfs_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, encoding: str = "utf-8", timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alcantarilla/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if encoding == "latin-1":
                return raw.decode("latin-1", errors="replace")
            return raw.decode(encoding, errors="replace")

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

    def _build_wfs_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_index is not None:
            return self._wfs_index
        index: dict[str, dict[str, Any]] = {}
        try:
            data = json.loads(self._fetch(self.wfs_url))
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_index = index
            return index
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                continue
            props = feat.get("properties") or {}
            ambito = _normalize_ambit(str(props.get("Ambito") or ""))
            geom = feat.get("geometry")
            if not ambito or not isinstance(geom, dict):
                continue
            key = ambito.upper()
            rec = {
                "geom_geojson": geom,
                "geometry_crs": "EPSG:4326",
                "geometry_axis_order": "xy",
                "geometry_source": "portal_wfs",
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito": ambito,
                "clasificacion": props.get("Clasificacion"),
            }
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            index[key] = rec
        self._wfs_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "blob"))
        index = self._build_wfs_index()
        blob_up = blob.upper()
        for code in RE_AMBIT_CODE.findall(blob):
            for key, hit in index.items():
                if code.replace(" ", "").upper() in key.replace(" ", "").replace(".", ""):
                    rec.update({k: v for k, v in hit.items() if v is not None})
                    return
        for key, hit in index.items():
            compact_key = re.sub(r"[\s.\-]", "", key)
            compact_blob = re.sub(r"[\s.\-]", "", blob_up)
            if len(compact_key) >= 8 and compact_key in compact_blob:
                rec.update({k: v for k, v in hit.items() if v is not None})
                return

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key in sorted(self._build_wfs_index()):
            hit = self._build_wfs_index()[key]
            ambito = str(hit.get("ambito") or key)
            titulo = f"Ámbito planeamiento SITMURCIA — {ambito}"
            row: dict[str, Any] = {
                "id": _stable_id("proy", f"wfs-{ambito}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(ambito),
                "url": SITMURCIA_VISOR,
                "source": "ayuntamiento",
                "origen": "sitmurcia_wfs",
            }
            row.update({k: v for k, v in hit.items() if v is not None})
            rows.append(row)
        return rows

    def _collect_pgou_docs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.pgou_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title in RE_LINK.findall(html):
            titulo = _strip_html(title)
            if len(titulo) < 4:
                continue
            url = urllib.parse.urljoin(f"{self.web_base}/", unescape(href))
            if url in seen:
                continue
            blob = f"{titulo} {url}"
            if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
                continue
            if not RE_PROYECTO.search(blob):
                continue
            if not any(x in url.lower() for x in ("sharepoint", "borm.es", "wp-content", self.web_base)):
                continue
            seen.add(url)
            row: dict[str, Any] = {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_blob(blob),
                "tipo": _proyecto_tipo(blob),
                "url": self.pgou_url,
                "documento_url": url,
                "source": "ayuntamiento",
                "origen": "pgou_wp",
            }
            rows.append(row)
        return rows

    def _collect_tablon_home(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.sede_base + "/")
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            url, fecha_raw, titulo = m.group(1), m.group(2), _strip_html(m.group(3))
            blob = f"{titulo} {fecha_raw}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": blob,
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            xml_text = self._fetch(TABLON_RSS, encoding="latin-1")
            root = ET.fromstring(xml_text)
        except (urllib.error.URLError, ET.ParseError):
            return []
        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = _strip_html(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            pub = _parse_rss_date(item.findtext("pubDate") or "")
            if not title:
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": pub,
                    "url": link or TABLON_HOME,
                    "blob": title,
                    "origen": "tablon_rss",
                }
            )
        return rows

    def _collect_tramites_urbanismo(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(URBANISMO_AREA_URL)
        except urllib.error.URLError:
            html = ""
        for href, title in RE_TRAMITE.findall(html):
            titulo = _strip_html(unescape(f"URBANISMO. {title}"))
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": unescape(href),
                    "fecha": None,
                    "blob": titulo,
                    "origen": "sede_tramite",
                    "es_tramite": True,
                }
            )
        if not rows:
            for item in DEFAULT_LICENCIA_TRAMITES:
                rows.append(
                    {
                        "titulo": item["titulo"],
                        "url": item["url"],
                        "fecha": None,
                        "blob": item["titulo"],
                        "origen": "sede_tramite",
                        "es_tramite": True,
                    }
                )
        return rows

    def _to_proyecto(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        url = str(raw.get("url") or self.pgou_url)
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": str(raw.get("titulo") or "")[:500],
            "fecha": raw.get("fecha") or _fecha_from_blob(blob),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _to_licencia(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if raw.get("es_tramite"):
            if not RE_LICENCIA.search(blob):
                return None
        elif not RE_LICENCIA.search(blob):
            return None
        if RE_SKIP.search(blob):
            return None
        url = str(raw.get("url") or URBANISMO_AREA_URL)
        titulo = str(raw.get("titulo") or "")[:500]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": raw.get("fecha") or _fecha_from_blob(blob) or "1970-01-01",
            "tipo": titulo[:200],
            "distrito": MUNICIPIO,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
            "url": url,
            "nota": "Página informativa sedipualba; sin registro público de concesiones",
        }
        self._attach_geometry(rec)
        centroid = self.config.get("centroid") or [37.9692, -1.2171]
        if rec.get("lat") is None or rec.get("lon") is None:
            rec["lat"], rec["lon"] = float(centroid[0]), float(centroid[1])
            rec["coord_source"] = "municipio_centroid"
        rec["coordinates_crs"] = "EPSG:4326"
        return rec

    def _collect_proyecto_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        sources = (
            self._collect_wfs_proyectos()
            + self._collect_pgou_docs()
            + self._collect_tablon_home()
            + self._collect_tablon_rss()
        )
        for raw in sources:
            if raw.get("id"):
                rec = raw
            else:
                rec = self._to_proyecto(raw)
            if not rec or rec["id"] in seen:
                continue
            seen.add(rec["id"])
            rows.append(rec)
        return rows

    def _collect_licencia_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for raw in self._collect_tramites_urbanismo() + self._collect_tablon_home() + self._collect_tablon_rss():
            rec = self._to_licencia(raw)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_rows()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": stats["rows"],
                    "added": max(0, stats["rows"] - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {**stats, "added": max(0, stats["rows"] - before)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyecto_rows()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs": sum(1 for r in rows if r.get("origen") == "sitmurcia_wfs"),
            "pgou": sum(1 for r in rows if r.get("origen") == "pgou_wp"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": stats["rows"],
                    "added": max(0, stats["rows"] - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {**stats, "added": max(0, stats["rows"] - before)}
