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
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

BASE = "https://www.onda.es"
SEDE_BASE = "https://seu.onda.es"
MUNICIPIO = "Onda"
ID_PREFIX = "onda"
INE_COD_MUN = "12084"

URBANISMO_URL = f"{BASE}/ond/web_php/index.php?contenido=subapartados_woden&id_boto=158"
SAT_URL = f"{BASE}/ond/web_php/index.php?contenido=subapartados_woden&id_boto=167"

DIPCAS_API = (
    "https://dipcas.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
    "planeamiento-urbanistico/records"
)
ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_WFS_TYPE = "InventarioSuSuz"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"demolici[oó]n|gr[uú]a|edificaci[oó]n|segregaci[oó]n|informaci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|modificaci[oó]n|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|reparcel|expropiaci[oó]n|"
    r"aprobaci[oó]n|unidad(?:es)? de ejecuci[oó]n|\bue[\s-]|sector|sur[\s-]|"
    r"normativa urban|zonas de ordenaci|estudio estrat|die|plenario|suspensi[oó]n|"
    r"sonella|rehabilitaci[oó]n|plan local|incendios forestales|normas urban)",
)
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploaded|AreasMunicipales)/(?:[^/]+/)*(\d{4})[./_-]?(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR = re.compile(r"(?i)\b(SUR[\s-]?\d+|UE[\s-]?\d+|sector[\s-]?\d+)")

GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(url) if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "plan parcial" in n or re.search(r"sur[\s-]?\d+", n):
        return "plan parcial"
    if "plan especial" in n:
        return "plan especial"
    if "pgou" in n or "plan general" in n or "normativa urban" in n:
        return "PGOU"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "expropiaci" in n:
        return "expropiación"
    if "estudio estrat" in n or "die" in n:
        return "estudio estratégico"
    if "unidad de ejecuci" in n or re.search(r"\bue[\s-]", n):
        return "unidad de ejecución"
    if "sector" in n or re.search(r"sur[\s-]", n):
        return "sector urbanizable"
    if "acuerdo plenario" in n or "suspensi" in n:
        return "acuerdo plenario"
    if "informaci" in n:
        return "información pública"
    return "urbanismo"


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


class OndaAyuntamientoAdapter(AyuntamientoAdapter):
    """CMS Woden onda.es + SAT trámites + ICV WFS InventarioSuSuz + DipCAS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.sat_url = str(self.config.get("sat_url") or SAT_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.dipcas_api = str(geom_cfg.get("dipcas_api") or DIPCAS_API)
        self.icv_wfs = str(geom_cfg.get("icv_wfs") or ICV_WFS).rstrip("/")
        self.icv_type = str(geom_cfg.get("icv_type") or ICV_WFS_TYPE)
        self.ine_cod_mun = str(geom_cfg.get("cod_ine_mun") or INE_COD_MUN)
        self._dipcas_cache: list[dict[str, Any]] | None = None
        self._icv_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-onda/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-onda/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _abs_url(self, href: str, base: str = BASE) -> str:
        return unescape(urllib.parse.urljoin(base, href))

    def _extract_pdfs(self, html: str, base: str = BASE) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_url(m.group(1), base)
            if "favicon" in u.lower():
                continue
            out.append(u)
        return list(dict.fromkeys(out))

    def _collect_urbanismo_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return rows
        for pdf in self._extract_pdfs(html, self.urbanismo_url):
            if pdf in seen:
                continue
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            blob = f"{name} {pdf}"
            if not RE_PROYECTO.search(blob):
                continue
            seen.add(pdf)
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_url(pdf),
                    "url": pdf,
                    "pdf_url": pdf,
                    "origen": "urbanismo_pdf",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            {
                "titulo": "Sede electrónica — trámites urbanismo (OpenSEA)",
                "url": self.sede_base,
                "tipo": "sede electrónica",
                "origen": "sede_info",
            },
            {
                "titulo": "SAT — formularios licencias de obra y edificación",
                "url": self.sat_url,
                "tipo": "catálogo trámites SAT",
                "origen": "sat_tramites",
            },
        ]
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.sat_url)
        except urllib.error.URLError:
            html = ""
        for pdf in self._extract_pdfs(html, self.sat_url):
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            if not RE_LICENCIA.search(name):
                continue
            rows.append(
                {
                    "id": _stable_id("lic", pdf),
                    "fecha_concesion": None,
                    "tipo": "formulario trámite",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": name[:500],
                    "url": pdf,
                    "source": "ayuntamiento",
                    "nota": "Instancia SAT; no es concesión publicada",
                    "origen": "sat_formulario",
                }
            )
        for page in pages:
            rows.append(
                {
                    "id": _stable_id("lic", page["url"]),
                    "fecha_concesion": None,
                    "tipo": page["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": page["titulo"],
                    "url": page["url"],
                    "source": "ayuntamiento",
                    "nota": "Sin histórico público de licencias concedidas",
                    "origen": page["origen"],
                }
            )
        return rows

    def _load_dipcas_geometries(self) -> list[dict[str, Any]]:
        if self._dipcas_cache is not None:
            return self._dipcas_cache
        url = (
            f"{self.dipcas_api}?where=cod_mun%3D%27{self.ine_cod_mun}%27"
            "&limit=500&select=denominacion,tipo_suelo,tipo_urba,geo_shape"
        )
        cache: list[dict[str, Any]] = []
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._dipcas_cache = cache
            return cache
        for rec in data.get("results") or []:
            shape = rec.get("geo_shape") or {}
            geom = shape.get("geometry") if isinstance(shape, dict) else None
            if not isinstance(geom, dict):
                continue
            label = str(rec.get("denominacion") or rec.get("tipo_suelo") or "").strip()
            cache.append(
                {
                    "label": label,
                    "tipo_suelo": str(rec.get("tipo_suelo") or ""),
                    "geom": geom,
                    "source_url": url,
                }
            )
        self._dipcas_cache = cache
        return cache

    def _load_icv_suz(self) -> list[dict[str, Any]]:
        if self._icv_cache is not None:
            return self._icv_cache
        feats: list[dict[str, Any]] = []
        start = 0
        while start < 10_000:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeNames": self.icv_type,
                    "outputFormat": "GML3",
                    "srsName": "EPSG:4326",
                    "count": "500",
                    "STARTINDEX": str(start),
                }
            )
            url = f"{self.icv_wfs}?{params}"
            try:
                raw = self._fetch_bytes(url, timeout=120)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", GML_NS)
            if not members:
                break
            for member in members:
                feat_el = member[0]
                props: dict[str, str] = {}
                geom = None
                for child in feat_el:
                    tag = child.tag.split("}")[-1]
                    if tag == "msGeometry":
                        pos = child.find(".//gml:posList", GML_NS)
                        if pos is not None and pos.text:
                            geom = _gml_poslist_to_polygon(pos.text)
                    elif tag != "boundedBy":
                        props[tag] = (child.text or "").strip()
                if props.get("cod_ine_mun") != self.ine_cod_mun:
                    continue
                if not geom:
                    continue
                pp = props.get("pp") or ""
                ue = props.get("ue") or props.get("ue_val") or ""
                clas = props.get("clasificacion") or ""
                label = " ".join(x for x in (pp, ue, clas) if x).strip() or f"SUZ {props.get('id', '')}"
                feats.append(
                    {
                        "label": label,
                        "pp": pp,
                        "ue": ue,
                        "clasificacion": clas,
                        "uso": props.get("uso") or "",
                        "geom": geom,
                        "feature_id": props.get("id") or "",
                        "source_url": (
                            f"{self.icv_wfs}?service=WFS&request=GetFeature&"
                            f"typeNames={self.icv_type}&featureId={props.get('id', '')}"
                        ),
                    }
                )
            start += len(members)
            if len(members) < 500:
                break
        self._icv_cache = feats
        return feats

    def _match_keywords(self, title: str) -> list[str]:
        low = title.lower()
        keys: list[str] = []
        for m in RE_SECTOR.finditer(title):
            keys.append(re.sub(r"\s+", " ", m.group(0).lower()).strip())
        for token in (
            "sur-11",
            "sur 11",
            "sur-10",
            "sonella",
            "modificacion puntual",
            "modificación puntual",
            "plan general",
            "normas urban",
            "expropiacion",
            "expropiación",
            "die",
            "estudio estrat",
            "rehabilitacion",
            "rehabilitación",
        ):
            if token in low:
                keys.append(token)
        return keys

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        keys = self._match_keywords(title)
        title_low = title.lower()
        candidates: list[tuple[float, dict[str, Any], str]] = []

        for item in self._load_icv_suz():
            label = item["label"].lower()
            score = 0.0
            for k in keys:
                kn = k.replace("-", " ").replace("  ", " ")
                ln = label.replace("-", " ")
                if k in label or kn in ln or k in title_low:
                    score += 25
            if "sur 11" in title_low and "sur 11" in label:
                score += 40
            if "sur-11" in title_low and "sur 11" in label:
                score += 40
            if score >= 20:
                candidates.append((score, item["geom"], item["source_url"]))

        for item in self._load_dipcas_geometries():
            label = item["label"].lower()
            score = 0.0
            for k in keys:
                if k in label or k in title_low:
                    score += 15
            if "plan general" in title_low and "plan general" in label:
                score += 20
            if score >= 15:
                candidates.append((score, item["geom"], item["source_url"]))

        if not candidates:
            return None
        candidates.sort(key=lambda x: -x[0])
        _, geom, source_url = candidates[0]
        merged = _merge_geometries([geom])
        if not merged:
            return None
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": source_url,
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

    def _icv_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        titulo = f"{item['label']} — {MUNICIPIO}"
        key = f"icv:{item.get('feature_id') or item['label']}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": None,
            "tipo": _proyecto_tipo(item["label"]),
            "url": item["source_url"],
            "source": "ayuntamiento",
            "origen": "icv_wfs",
            "geom_geojson": item["geom"],
            "geometry_source": "portal_wfs",
            "geometry_source_url": item["source_url"],
            "coord_source": "portal_geometry_centroid",
        }
        cen = geometry_centroid(item["geom"])
        if cen:
            rec["lat"], rec["lon"] = cen
        return rec

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("pdf_url") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
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
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "formularios": sum(1 for r in rows if r.get("origen") == "sat_formulario"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_info", "sat_tramites")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._load_icv_suz():
            add(self._icv_to_proyecto(item))
        for item in self._collect_urbanismo_pdfs():
            add(self._pdf_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "urbanismo_pdf": sum(1 for r in rows if r.get("origen") == "urbanismo_pdf"),
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
