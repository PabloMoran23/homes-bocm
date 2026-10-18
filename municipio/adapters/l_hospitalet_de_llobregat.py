from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from pyproj import Transformer

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

_TRANSFORMER_25831_TO_4326 = Transformer.from_crs("EPSG:25831", "EPSG:4326", always_xy=True)

WEB_BASE = "https://www.l-h.cat"
SEDE_BASE = "https://seuelectronica.l-h.cat"
GEOPORTAL_BASE = "https://geoportal.l-h.cat"
CARTO_API = f"{GEOPORTAL_BASE}/CartoAPI.ashx"
MUNICIPIO = "L'Hospitalet de Llobregat"
ID_PREFIX = "l-hospitalet-de-llobregat"

URBANISME_WEB = f"{WEB_BASE}/urbanismehabitatge/264048_1.aspx?id=1"
CONSULTA_PUBLICA = f"{SEDE_BASE}/2317545_2.aspx"
GEOVISOR = f"{GEOPORTAL_BASE}/urbanisme/"
TAULER_URL = "https://tauler.seu.cat/inici.do?idens=810170005"

URBANISME_TRAMITS_ROOT = (
    f"{SEDE_BASE}/tramits/r/navegacioTramits.aspx?"
    "q1y0frqazAsAuOvY7DvCFGzkW3zDc5cKaw5F7QBzmb3mecnhcVIjBaDZZaPfjUbcqazCCIGsGfRuv9o5EqazB"
)

TRAMIT_FOLDERS: tuple[str, ...] = (
    "https://seuelectronica.l-h.cat/tramits/r/navegacioTramits.aspx?"
    "f0lzKqGNqazAMh2SUNVqazCCaPxH5kHoDtuwNMQxFFd3TX02GpLttfsFBDHv2Ga2Ew2pgj7oJvc89wqTJomrOwDksTqazCUNYq9sCLsl0A3x4qazC2H1GX1O7CDIn5MjroBscNqazC8lqcaNmGqEDMTkqsqazB",
    "https://seuelectronica.l-h.cat/tramits/r/navegacioTramits.aspx?"
    "f0lzKqGNqazAMhzwLa8jb5UPXpafjxh5qazAbeB1iiQe4Gd9rjMn4qazCWIMTYF3HLEc55gHJV38k9tXOxjtBCqazC1q7biEmQMdqpX5NHq1DSz9jmq76bP0qazCXqazC9vlkg8yL9wHMhLhgPDWDXXZMLqazAzcqazB",
    "https://seuelectronica.l-h.cat/tramits/r/navegacioTramits.aspx?"
    "UQIQ8MHjqZKl6YifXc6QzkR0RhsAaLYCXYbNYFDZvbhotAqazAenarrV6zaqazCCXWTZkU5DHnupEyy8tRCmbrJsg4ZP3daMJJlljFdKjmwpdHIgYYre6bAHqMBzsAul9qazAWajqazC",
    "https://seuelectronica.l-h.cat/tramits/r/navegacioTramits.aspx?"
    "UQIQ8MHjqZLJkmcMgy3GC57lwUvvxD3qazAsbhFSgns83YCjN2d3Qbk52d9H99Tt85mb6EN94PqazA54AFVpfO5RJVJqU526O3QTelvYxFR6cjnGvQHs14tvvO598IcgSigi33",
)

RE_DETALL_TRAMIT = re.compile(
    r'href="(https://seuelectronica\.l-h\.cat/tramits/r/detallTramit\.aspx\?[^"]+)"[^>]*>\s*([^<]+)',
    re.I,
)
RE_CONSULTA_LINK = re.compile(
    r'href="(/utils/obreFitxer\.ashx\?[^"]+)"[^>]*>\s*([^<]{20,})',
    re.I,
)
RE_DOC_LINK = re.compile(
    r'href="(https://www\.l-h\.cat/utils/obreFitxer[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n pr[eè]via|declaraci[oó]n responsable|"
    r"obra (?:major|menor)|primera utilitzaci[oó]|ocupaci[oó]n.*obra)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

TIPUS_LABELS = {
    "P": "planeamiento",
    "C": "convenio",
    "G": "gestión",
    "N": "normativa",
    "U": "urbanización",
    "S": "suspensión",
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _parse_yyyymmdd(value: str | None) -> str | None:
    if not value or len(str(value)) != 8:
        return None
    try:
        s = str(value)
        return datetime(int(s[:4]), int(s[4:6]), int(s[6:8])).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_text(text: str) -> str | None:
    return _parse_fecha_dmy(text) or (
        f"{max(int(y.group(1)) for y in RE_YEAR.finditer(text))}-01-01"
        if RE_YEAR.search(text or "")
        else None
    )


def _proyecto_tipo(props: dict[str, Any]) -> str:
    inst = str(props.get("instrument") or "").strip()
    tipus = str(props.get("tipus") or "").strip()
    if inst:
        return inst
    return TIPUS_LABELS.get(tipus, "planeamiento")


def _first_doc_url(html_desc: str) -> str | None:
    m = RE_DOC_LINK.search(html_desc or "")
    return m.group(1) if m else None


def _transform_coord_pair(pair: list[float] | tuple[float, float]) -> list[float]:
    lon, lat = _TRANSFORMER_25831_TO_4326.transform(float(pair[0]), float(pair[1]))
    return [lon, lat]


def _transform_coords(node: Any) -> Any:
    if isinstance(node, list):
        if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
            if len(node) == 2 or (len(node) > 2 and not isinstance(node[2], (list, tuple))):
                return _transform_coord_pair(node)
        return [_transform_coords(item) for item in node]
    return node


def _wgs84_geometry(geom: dict[str, Any]) -> dict[str, Any]:
    return {"type": geom.get("type"), "coordinates": _transform_coords(geom.get("coordinates"))}


class LHospitaletDeLlobregatAyuntamientoAdapter(AyuntamientoAdapter):
    """CartoAPI PLA_AMBITS (geoportal) + sede consultas públicas + trámites licencia."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.carto_api = str(self.config.get("carto_api") or CARTO_API)
        self.ua = str(self.config.get("user_agent", "poc-bocm-l-hospitalet-de-llobregat/1.0"))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
        return raw.decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def _geometry_url(self, layer_id: str) -> str:
        q = urllib.parse.urlencode(
            {
                "request": "GetLayer",
                "layer": "PLA_AMBITS",
                "language": "ca",
                "srid": "EPSG:4326",
                "filter": f"id:'{layer_id}'",
            }
        )
        return f"{self.carto_api}?{q}"

    def _collect_pla_ambits(self) -> list[dict[str, Any]]:
        q = urllib.parse.urlencode(
            {
                "request": "GetLayer",
                "layer": "PLA_AMBITS",
                "language": "ca",
                "srid": "EPSG:4326",
                "filter": "",
            }
        )
        url = f"{self.carto_api}?{q}"
        data = self._fetch_json(url)
        features = data.get("features") if isinstance(data, dict) else []
        rows: list[dict[str, Any]] = []
        for feat in features or []:
            if not isinstance(feat, dict):
                continue
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            layer_id = str(props.get("id") or "")
            expedient = _clean(str(props.get("expedientG") or ""))
            title = _clean(str(props.get("name") or expedient or f"Ámbito {layer_id}"))
            fecha = (
                _parse_yyyymmdd(props.get("dataAprovacio"))
                or _parse_yyyymmdd(props.get("dataPublicacio"))
                or (str(props.get("anyAprovacio")) + "-01-01" if props.get("anyAprovacio") else None)
            )
            desc_html = str(props.get("description") or "")
            doc_url = _first_doc_url(desc_html)
            key = expedient or layer_id or title
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": title[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(props),
                "url": doc_url or GEOVISOR,
                "source": "ayuntamiento",
                "origen": "geoportal_pla_ambits",
                "expediente": expedient or None,
                "instrument": props.get("instrument"),
                "tipus_expedient": props.get("tipus"),
                "organismo": props.get("organisme"),
            }
            if isinstance(geom, dict) and geom.get("type"):
                geom_wgs = _wgs84_geometry(geom)
                rec["geom_geojson"] = geom_wgs
                rec["geometry_source"] = "portal_cartoapi"
                rec["geometry_source_url"] = self._geometry_url(layer_id) if layer_id else url
                rec["geometry_crs"] = "EPSG:4326"
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(geom_wgs)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_consulta_publica(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(CONSULTA_PUBLICA)
        except urllib.error.URLError:
            return rows
        seen: set[str] = set()
        for m in RE_CONSULTA_LINK.finditer(html):
            href, title = m.group(1), _clean(m.group(2))
            if not re.search(r"(?i)consulta|memoria|planeam", title):
                continue
            url = urllib.parse.urljoin(f"{SEDE_BASE}/", href)
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": _fecha_from_text(title),
                    "tipo": "consulta pública previa",
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sede_consulta_publica",
                }
            )
        return rows

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        pages = [URBANISME_TRAMITS_ROOT, *TRAMIT_FOLDERS]
        for page_url in pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_DETALL_TRAMIT.finditer(html):
                url, title = m.group(1), _clean(m.group(2))
                if url in seen:
                    continue
                if not RE_LICENCIA.search(title):
                    continue
                seen.add(url)
                rows.append(
                    {
                        "id": _stable_id("lic", url),
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title[:500],
                        "url": url,
                        "source": "ayuntamiento",
                        "nota": "Trámite sede electrónica; no concesión publicada en listado masivo",
                    }
                )
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_tramites()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_tramites():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_pla_ambits():
            add(rec)
        for rec in self._collect_consulta_publica():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "pla_ambits": sum(1 for r in rows if r.get("origen") == "geoportal_pla_ambits"),
            "consulta_publica": sum(1 for r in rows if r.get("origen") == "sede_consulta_publica"),
            "with_geometry": with_geom,
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
