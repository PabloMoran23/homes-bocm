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
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.alboraya.es"
SITAE_BASE = "https://alborayasitae.sede.gva.es/sitae"
SEDE_BASE = "https://alboraya.sede-virtual.es"
GOVERNALIA_BASE = "https://alboraya.governalia.es"
MUNICIPIO = "Alboraya"
ID_PREFIX = "alboraya"
COD_INE_MUN = "46013"

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE_NAME = "Planeamiento.Zonificacion"
ICV_OFFSETS = list(range(109_500, 118_500, 500))

RE_ROW = re.compile(r'<tr class="Fila(?:Impar|Par)">(.*?)</tr>', re.S | re.I)
RE_TITLE = re.compile(
    r'<a href="[^"]*idEdictoSeleccionado=(\d+)"[^>]*>([^<]+)</a>',
    re.S | re.I,
)
RE_CELLS = re.compile(r'<td class="listado_representantes">(.*?)</td>', re.S | re.I)
RE_CODIGO = re.compile(r'DescargarAnuncio(?:Retirado)?\.do\?codigo=([^"&]+)')
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR = re.compile(r"(?i)sector\s*([0-9IVXLC]+)")

RE_LICENCIA = re.compile(
    r"(?i)(licencia|llic[eè]ncia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n.*obra|informaci[oó]n p[uú]blica.*actividad|art\.?\s*55|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de )?detalle|sector|homologaci[oó]n|consulta p[uú]blica|"
    r"integraci[oó]n paisaj|iate|alumbrado|normativa urban)",
)
RE_SITAE_NON_URBAN = re.compile(
    r"(?i)(subvenci[oó]n.*agricult|mantenimiento y mejora de la actividad agr|"
    r"oposiciones|concurso|recursos humanos|nombramiento|empleo p[uú]blico)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").upper().replace("Ó", "O").replace("É", "E").replace("Í", "I"))


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for feat in features:
        g = feat.get("geometry")
        if not isinstance(g, dict):
            continue
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


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "consulta p" in n and "blica" in n:
        return "consulta pública"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "homologaci" in n:
        return "homologación planeamiento"
    if "integraci" in n and "paisaj" in n:
        return "estudio integración paisajística"
    return "urbanismo"


class AlborayaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portalesmunicipales + SITAE tablón GVA + sede-virtual + ICV WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SITAE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sitae_base = str(self.config.get("sitae_base") or SITAE_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.governalia_base = str(self.config.get("governalia_base") or GOVERNALIA_BASE).rstrip("/")
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS_BASE).rstrip("/")
        self.icv_type_name = str(geom_cfg.get("type_name") or ICV_TYPE_NAME)
        self.icv_offsets = list(geom_cfg.get("offsets") or ICV_OFFSETS)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or COD_INE_MUN)
        self._icv_zones_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alboraya/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("latin-1", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 120) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alboraya/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _parse_sitae_page(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row_html in RE_ROW.findall(html):
            title_m = RE_TITLE.search(row_html)
            if not title_m:
                continue
            cells = [_strip_html(c) for c in RE_CELLS.findall(row_html)]
            cod_m = RE_CODIGO.search(row_html)
            eid = title_m.group(1)
            titulo = _strip_html(title_m.group(2))
            tipo_edicto = cells[1] if len(cells) > 1 else ""
            departamento = cells[2] if len(cells) > 2 else ""
            fecha_pub = _parse_fecha_dmy(cells[3] if len(cells) > 3 else "")
            codigo = cod_m.group(1) if cod_m else None
            detail_url = f"{self.sitae_base}/MuestraInformacionEdictoPublicoFrontAction.do?idEdictoSeleccionado={eid}"
            pdf_url = (
                f"{self.sitae_base}/DescargarAnuncioRetirado.do?codigo={urllib.parse.quote(codigo)}"
                if codigo
                else detail_url
            )
            rows.append(
                {
                    "id_edicto": eid,
                    "titulo": titulo[:500],
                    "tipo_edicto": tipo_edicto[:80],
                    "departamento": departamento[:120],
                    "fecha": fecha_pub,
                    "codigo": codigo,
                    "url": pdf_url,
                    "detail_url": detail_url,
                    "blob": f"{titulo} {tipo_edicto} {departamento}",
                }
            )
        return rows

    def _collect_sitae(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        seeds = [
            f"{self.sitae_base}/VisualizarEdictoPublicoFrontAction.do?accion=historicoEdictos&filtrar=s",
            f"{self.sitae_base}/VisualizarEdictoPublicoFrontAction.do?accion=edictosVigor",
        ]
        for seed in seeds:
            for page in range(1, 25):
                url = seed + (f"&d-2486328-p={page}" if page > 1 and "historico" in seed else "")
                try:
                    html = self._fetch(url)
                except urllib.error.URLError:
                    break
                batch = self._parse_sitae_page(html)
                if not batch:
                    break
                for rec in batch:
                    key = rec.get("codigo") or rec["id_edicto"]
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(rec)
                if "historico" not in seed:
                    break
        return rows

    def _sitae_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        dept = (row.get("departamento") or "").lower()
        if RE_SITAE_NON_URBAN.search(blob):
            return False
        if "urban" in dept:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _collect_icv_zones(self) -> list[dict[str, Any]]:
        if self._icv_zones_cache is not None:
            return self._icv_zones_cache

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for start in self.icv_offsets:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeName": self.icv_type_name,
                    "outputFormat": "application/json; subtype=geojson",
                    "srsName": "EPSG:4326",
                    "count": "500",
                    "startIndex": str(start),
                    "CQL_FILTER": f"cod_ine_mun='{self.cod_ine_mun}'",
                }
            )
            url = f"{self.icv_wfs_url}?{params}"
            try:
                data = self._fetch_json(url, timeout=120)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            batch = data.get("features") or []
            if not batch:
                break
            for feat in batch:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                if str(props.get("cod_ine_mun") or "") != self.cod_ine_mun:
                    continue
                den = str(props.get("denominaci") or "").strip()
                exp = str(props.get("expediente") or "").strip()
                if not den or "SIN PLANEAMIENTO" in den.upper():
                    continue
                grouped.setdefault((den, exp), []).append(feat)

        zones: list[dict[str, Any]] = []
        for (den, exp), feats in grouped.items():
            merged = _merge_geometries(feats)
            zones.append(
                {
                    "denominaci": den,
                    "expediente": exp,
                    "tipo": _proyecto_tipo(den),
                    "geom_geojson": merged,
                    "geometry_source_url": (
                        f"{self.icv_wfs_url}?service=WFS&request=GetFeature&"
                        f"typeName={self.icv_type_name}&cod_ine_mun={self.cod_ine_mun}"
                    ),
                }
            )

        self._icv_zones_cache = zones
        return zones

    def _match_icv_zone(self, titulo: str) -> dict[str, Any] | None:
        norm = _normalize_title(titulo)
        sector_m = RE_SECTOR.search(titulo or "")
        sector = sector_m.group(1).upper() if sector_m else None
        best: tuple[float, dict[str, Any]] | None = None

        for zone in self._collect_icv_zones():
            den = _normalize_title(zone.get("denominaci") or "")
            score = 0.0
            if den and den in norm:
                score = 100.0
            elif sector and f"SECTOR {sector}" in den:
                score = 80.0
            else:
                tokens = [t for t in re.split(r"[^A-Z0-9]+", den) if len(t) >= 5]
                hits = sum(1 for t in tokens if t in norm)
                score = hits * 10.0
            if "PLAN GENERAL" in norm and "PLAN GENERAL" in den:
                score += 20.0
            if score > 0 and (best is None or score > best[0]):
                best = (score, zone)

        if best and best[0] >= 20:
            return best[1]
        return None

    def _zone_geometry(self, zone: dict[str, Any]) -> dict[str, Any] | None:
        geom = zone.get("geom_geojson")
        if not geom:
            return None
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": zone.get("geometry_source_url") or self.icv_wfs_url,
            "coord_source": "portal_geometry_centroid",
        }

    def _enrich_geometry(self, rec: dict[str, Any], *, licencia: bool = False) -> None:
        if record_geometry(rec):
            return
        if licencia and rec.get("origen") == "sitae":
            if not re.search(r"(?i)pol[ií]gono|parcela|sector|diseminad", rec.get("titulo") or ""):
                return
        zone = self._match_icv_zone(rec.get("titulo") or "")
        if not zone:
            return
        geom = self._zone_geometry(zone)
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.sitae_base),
                "fecha_concesion": None,
                "tipo": "tablón SITAE — licencias y actividades",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios SITAE — Gestión y control urbanístico",
                "url": f"{self.sitae_base}/VisualizarEdictoPublicoFrontAction.do?accion=historicoEdictos&filtrar=s",
                "source": "ayuntamiento",
                "nota": "Edictos de licencias, actividades e IP art. 55 en SITAE GVA",
                "origen": "sitae_info",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica — trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites licencias y urbanismo",
                "url": self.sede_base,
                "source": "ayuntamiento",
                "nota": "sede-virtual.es (CloudFront geo-block en CI); sin listado histórico público",
                "origen": "sede_tramite",
            },
        ]

    def _collect_icv_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        visor_gva = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"
        for zone in self._collect_icv_zones():
            titulo = zone["denominaci"]
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv:{zone['expediente']}:{titulo}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_expediente(zone.get("expediente", "")),
                "tipo": zone.get("tipo") or "planeamiento",
                "url": visor_gva,
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "expte": zone.get("expediente"),
            }
            geom = self._zone_geometry(zone)
            if geom:
                rec.update(geom)
                cen = geometry_centroid(geom["geom_geojson"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        visor_gva = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"
        return [
            {
                "id": _stable_id("proy", self.sitae_base),
                "municipio": MUNICIPIO,
                "titulo": "Tablón SITAE — edictos urbanísticos históricos",
                "fecha": None,
                "tipo": "tablón",
                "url": f"{self.sitae_base}/VisualizarEdictoPublicoFrontAction.do?accion=historicoEdictos&filtrar=s",
                "source": "ayuntamiento",
                "origen": "sitae_info",
            },
            {
                "id": _stable_id("proy", self.web_base),
                "municipio": MUNICIPIO,
                "titulo": "Web municipal — transparencia y urbanismo",
                "fecha": None,
                "tipo": "transparencia",
                "url": f"{self.web_base}/es/transparencia",
                "source": "ayuntamiento",
                "origen": "web_info",
                "nota": "Drupal portalesmunicipales; timeout intermitente desde CI",
            },
            {
                "id": _stable_id("proy", visor_gva),
                "municipio": MUNICIPIO,
                "titulo": "ICV — zonificación urbanística Comunitat Valenciana",
                "fecha": None,
                "tipo": "visor GIS",
                "url": visor_gva,
                "source": "ayuntamiento",
                "origen": "datos_abiertos",
            },
        ]

    def _sitae_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._sitae_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not re.search(r"(?i)actividad|licencia|art\.?\s*55", blob):
            return None
        tipo = "licencia / actividad"
        if re.search(r"(?i)art\.?\s*55", blob):
            tipo = "información pública actividad (art. 55)"
        elif re.search(r"(?i)licencia.*obra|obra", blob):
            tipo = "licencia de obra"
        key = row.get("codigo") or row["id_edicto"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sitae",
        }
        self._enrich_geometry(rec, licencia=True)
        return rec

    def _sitae_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._sitae_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob) and "urban" not in (row.get("departamento") or "").lower():
            return None
        key = row.get("codigo") or row["id_edicto"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sitae",
        }
        self._enrich_geometry(rec, licencia=False)
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
        for item in self._collect_sitae():
            rec = self._sitae_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sitae": sum(1 for r in rows if r.get("origen") == "sitae"),
            "info": sum(1 for r in rows if r.get("origen") in ("sitae_info", "sede_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_sitae():
            rec = self._sitae_to_licencia(item)
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

        for rec in self._collect_proyecto_info_pages():
            add(rec)
        for rec in self._collect_icv_proyectos():
            add(rec)
        for item in self._collect_sitae():
            add(self._sitae_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sitae": sum(1 for r in rows if r.get("origen") == "sitae"),
            "icv": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "info": sum(1 for r in rows if r.get("origen") in ("sitae_info", "web_info", "datos_abiertos")),
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
