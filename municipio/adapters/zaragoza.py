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

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid

BASE = "https://www.zaragoza.es"
WFS_BASE = "https://idezar-sig.zaragoza.es/servicios/geoserver/urbanismo/wfs"
MUNICIPIO = "Zaragoza"
ID_PREFIX = "zaragoza"

IP_URL = f"{BASE}/sede/portal/urbanismo/planeamiento/informacion-publica"
TRAMITES_URL = f"{BASE}/sede/portal/urbanismo/tramites"
TABLON_URL = f"{BASE}/sede/servicio/tablon-edicto/"

WFS_INSTRUMENTOS = "urbanismo:PLA_1_Instrumentos_ambito"
WFS_AMBITOS_LAYERS = (
    "urbanismo:PLA_1_Ambitos_desarrollo",
    "urbanismo:PLA_1_Ambitos_recogido",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|vallas y andamios)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial)|pgou|pgouz|modificaci[oó]n|"
    r"informaci[oó]n p[uú]blica|expediente|instrumento|convenio|reparcel|"
    r"aprobaci[oó]n|gerencia urban)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")
RE_IP_PDF = re.compile(
    r'href="((?:https://www\.zaragoza\.es)?/contenidos/urbanismo/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_TRAMITE_ID = re.compile(r"/sede/servicio/tramite/(\d+)")
RE_TABLON_ID = re.compile(r"tablon-edicto/(\d+)")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str | None) -> str | None:
    if not text:
        return None
    m = RE_FECHA_DMY.search(text.strip())
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000 if y < 50 else 1900
    try:
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_iso_date(text: str | None) -> str | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _tipo_instrumento(props: dict[str, Any]) -> str:
    blob = " ".join(
        str(props.get(k) or "")
        for k in (
            "nombre_instrumento",
            "tipo_instrumento",
            "tipo_base",
            "identificacion_instrumento",
        )
    ).lower()
    if "modificaci" in blob or props.get("tipo_instrumento", "").upper().startswith("M"):
        return "modificación planeamiento"
    if "plan parcial" in blob or props.get("tipo_base") == "PP":
        return "plan parcial"
    if "plan especial" in blob or props.get("tipo_base") == "PE":
        return "plan especial"
    if "pgou" in blob:
        return "PGOU"
    return props.get("nombre_instrumento") or "instrumento urbanístico"


class ZaragozaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede Zaragoza (IP + tablón JSON) + IDEZar GeoServer WFS (instrumentos y ámbitos)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.max_tablon_pages = int(self.config.get("max_tablon_pages", 8))
        self.max_tablon_json_fetch = int(self.config.get("max_tablon_json_fetch", 120))
        self._ambito_geom: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-zaragoza/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs(self, href: str) -> str:
        return urllib.parse.urljoin(BASE, href)

    def _wfs_features(self, type_name: str, max_features: int = 5000) -> list[dict[str, Any]]:
        qs = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "1.0.0",
                "request": "GetFeature",
                "typeName": type_name,
                "outputFormat": "application/json",
                "maxFeatures": str(max_features),
                "srsName": "EPSG:4326",
            }
        )
        url = f"{self.wfs_base}?{qs}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        feats = data.get("features") if isinstance(data, dict) else None
        return feats if isinstance(feats, list) else []

    def _load_ambito_geometry(self) -> dict[str, dict[str, Any]]:
        if self._ambito_geom is not None:
            return self._ambito_geom
        index: dict[str, dict[str, Any]] = {}
        for layer in WFS_AMBITOS_LAYERS:
            for feat in self._wfs_features(layer):
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                code = str(props.get("codigo_ambito") or "").strip()
                geom = feat.get("geometry")
                if code and isinstance(geom, dict) and geom.get("type"):
                    qs = urllib.parse.urlencode(
                        {
                            "service": "WFS",
                            "version": "1.0.0",
                            "request": "GetFeature",
                            "typeName": layer,
                            "outputFormat": "application/json",
                            "CQL_FILTER": f"codigo_ambito='{code.replace(chr(39), chr(39)*2)}'",
                            "maxFeatures": "1",
                            "srsName": "EPSG:4326",
                        }
                    )
                    index[code] = {
                        "geom_geojson": geom,
                        "geometry_source_url": f"{self.wfs_base}?{qs}",
                    }
        self._ambito_geom = index
        return index

    def _attach_geometry(self, rec: dict[str, Any], codigo_ambito: str | None) -> None:
        if not codigo_ambito:
            return
        hit = self._load_ambito_geometry().get(codigo_ambito)
        if not hit:
            return
        geom = hit["geom_geojson"]
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = hit["geometry_source_url"]
        rec["coord_source"] = "portal_geometry_centroid"
        rec["codigo_ambito"] = codigo_ambito
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _instrumentos_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for feat in self._wfs_features(WFS_INSTRUMENTOS):
            if not isinstance(feat, dict):
                continue
            props = feat.get("properties") or {}
            if not isinstance(props, dict):
                continue
            expediente = str(props.get("expediente") or "").strip()
            codigo = str(props.get("codigo_ambito") or "").strip()
            titulo_parts = [
                props.get("nombre_instrumento"),
                codigo,
                props.get("identificacion_instrumento"),
            ]
            titulo = " — ".join(str(p).strip() for p in titulo_parts if p and str(p).strip())
            if not titulo:
                titulo = expediente or codigo or "Instrumento urbanístico"
            fecha = (
                _parse_fecha_dmy(props.get("apr_definitiva"))
                or _parse_fecha_dmy(props.get("fecha_publicacion"))
                or _parse_fecha_dmy(props.get("apr_definitiva_urb"))
            )
            url = (
                props.get("enlace_acuerdo")
                or props.get("enlace_planos")
                or props.get("enlace_normas")
                or f"{BASE}/sede/portal/urbanismo/visores/cartografia-planeamiento"
            )
            if url and not str(url).startswith("http"):
                url = self._abs(str(url))
            key = expediente or f"{codigo}:{props.get('id')}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": _tipo_instrumento(props),
                "url": url,
                "source": "ayuntamiento",
                "origen": "idezar_wfs_instrumentos",
            }
            if expediente:
                rec["expte"] = expediente
            if props.get("area"):
                rec["distrito"] = f"Área {props.get('area')}"
            self._attach_geometry(rec, codigo)
            rows.append(rec)
        return rows

    def _informacion_publica_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(IP_URL)
        except urllib.error.URLError:
            return rows
        seen: set[str] = set()
        for m in RE_IP_PDF.finditer(html):
            href = unescape(m.group(1))
            url = self._abs(href)
            if url in seen:
                continue
            seen.add(url)
            name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
            name = re.sub(r"[_\-]+", " ", name)
            name = re.sub(r"\.pdf.*$", "", name, flags=re.I).strip()
            fecha = None
            fm = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", url)
            if fm:
                fecha = f"{fm.group(1)}-{fm.group(2)}-{fm.group(3)}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": (name or "Documento información pública")[:500],
                "fecha": fecha,
                "tipo": "información pública",
                "url": url,
                "source": "ayuntamiento",
                "origen": "informacion_publica_portal",
            }
            rows.append(rec)
        return rows

    def _tablon_gerencia_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        ids: list[str] = []
        for page in range(self.max_tablon_pages):
            start = page * 50
            url = f"{TABLON_URL}?start={start}" if start else TABLON_URL
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            page_ids = RE_TABLON_ID.findall(html)
            if not page_ids:
                break
            ids.extend(page_ids)
        seen_ids: set[str] = set()
        for eid in ids:
            if eid in seen_ids:
                continue
            seen_ids.add(eid)
            if len(seen_ids) > self.max_tablon_json_fetch:
                break
            json_url = f"{TABLON_URL}{eid}.json"
            try:
                item = self._fetch_json(json_url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(item, dict):
                continue
            tipo = (item.get("tipo") or {}).get("title") or ""
            title = str(item.get("title") or "")
            desc = str(item.get("description") or "")
            blob = f"{tipo} {title} {desc}"
            if "gerencia" not in blob.lower() or "urbanismo" not in blob.lower():
                continue
            if not RE_PROYECTO.search(blob):
                continue
            doc = item.get("document") or f"{TABLON_URL}{eid}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"tablon:{eid}"),
                "municipio": MUNICIPIO,
                "titulo": title[:500],
                "fecha": _parse_iso_date(item.get("publicationDate")),
                "tipo": "extracto gerencia urbanismo",
                "url": str(doc),
                "source": "ayuntamiento",
                "origen": "tablon_edicto",
            }
            rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for rec in (
            self._instrumentos_proyectos()
            + self._informacion_publica_pdfs()
            + self._tablon_gerencia_proyectos()
        ):
            by_id[rec["id"]] = rec
        return list(by_id.values())

    def _tramite_ids(self) -> list[str]:
        try:
            html = self._fetch(TRAMITES_URL)
        except urllib.error.URLError:
            return []
        return sorted(set(RE_TRAMITE_ID.findall(html)), key=int)

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tid in self._tramite_ids():
            url = f"{BASE}/sede/servicio/tramite/{tid}"
            json_url = f"{url}.json"
            try:
                item = self._fetch_json(json_url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title or not RE_LICENCIA.search(title):
                continue
            fecha = _parse_iso_date(item.get("lastUpdated"))
            rec: dict[str, Any] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": fecha,
                "tipo": "trámite licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": url,
                "source": "ayuntamiento",
                "nota": "Trámite sede electrónica; no registro público de concesiones",
            }
            rows.append(rec)
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
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            rows.append(obj)
                    except json.JSONDecodeError:
                        continue
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if r.get("geom_geojson"))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "source": "idezar_wfs+ip+tablon",
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_tramites()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_urbanismo"}

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
