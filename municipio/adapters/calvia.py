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

WEB_BASE = "https://www.calvia.com"
MUNICIPIO = "Calvià"
ID_PREFIX = "calvia"

URBANISMO = f"{WEB_BASE}/es/areas-municipales/urbanismo"
TRAMITES_URBANISMO = f"{URBANISMO}/urbanismo"
VISOR_PGOU_VIGENTE = f"{URBANISMO}/visores-informacion-geografica/visor-pgou-vigente"
VISOR_PGOU_TRAMIT = f"{URBANISMO}/visores-informacion-geografica/visor-pgou-en-tramitacion"
VISOR_OBRAS = f"{URBANISMO}/visor-obras-mayores"
SITMUN_VIGENTE = "https://sitmun.idelma.cat/calvia_vigent"
SITMUN_TRAMIT = "https://sitmun.idelma.cat/urb_calvia"

WFS_BASE = "https://ide.idelma.cat/geoserver/M011_Calvia/wfs"
WFS_EXP_OBRA = "M011_Calvia:M011_EXP_OBRA"
WFS_SECTORS = "M011_Calvia:M011_SECTORS_URBANISTICS"

RSS_FEEDS: tuple[tuple[str, str], ...] = (
    (f"{URBANISMO}/planeamiento-en-tramitacion/rss.xml", "planeamiento en trámite"),
    (f"{URBANISMO}/pgou-revision/rss.xml", "PGOU revisión"),
    (f"{URBANISMO}/planeamiento-vigente/rss.xml", "planeamiento vigente"),
    (f"{URBANISMO}/rss.xml", "urbanismo"),
    (
        f"{WEB_BASE}/es/ayuntamiento/normativa-y-anuncios/anuncios/informacion-publica/rss.xml",
        "información pública",
    ),
)

TRAMITE_INFO_PAGES: tuple[tuple[str, str, str], ...] = (
    (TRAMITES_URBANISMO, "licencia urbanística", "Catálogo y modelos licencia urbanística 2021+"),
    (VISOR_OBRAS, "visor obras mayores", "Visor obras mayores (Plone)"),
    (f"{WEB_BASE}/es/tramites/sede-electronica", "sede electrónica", "Acceso sede electrónica municipal"),
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"primera ocupaci[oó]n|obra[s]? (?:major|menor|mayor)|decreto|DEC\b|CPO\b)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pg-?pod|estudio de detalle|"
    r"modificaci[oó]n|informaci[oó]n p[uú]blica|expedient|unidad de actuaci|ua cb|"
    r"conveni|sector|aprobaci[oó]n|boib|front mar[ií]tim|remodelaci|participaci[oó])",
)
RE_RSS_NOISE = re.compile(
    r"(?i)^(foto|edificios)\.|\.(avif|jpg|jpeg|png)$|^_imagen proyecto\.pdf$",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_EXPE_YEAR = re.compile(r"/(\d{4})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return None


def _fecha_from_expte(expte: str) -> str | None:
    m = re.search(r"/(\d{4})\b", expte or "")
    if m:
        y = int(m.group(1))
        if 1980 <= y <= 2035:
            return f"{y}-01-01"
    return None


def _proyecto_tipo(title: str, section: str = "") -> str:
    n = f"{title} {section}".lower()
    if "estudio de detalle" in n or "ua cb" in n:
        return "estudio de detalle"
    if "pgou" in n or "pg-pod" in n or "plan general" in n:
        return "PGOU"
    if "conveni" in n:
        return "convenio urbanístico"
    if "informaci" in n and "p" in n:
        return "información pública"
    if "aprobaci" in n:
        return "aprobación planeamiento"
    if "boib" in n:
        return "publicación BOIB"
    if "participaci" in n:
        return "participación ciudadana"
    return section or "planeamiento"


def _licencia_tipo(text: str) -> str:
    n = (text or "").lower()
    if "comunicaci" in n:
        return "comunicación previa"
    if "primera ocupaci" in n:
        return "primera ocupación"
    if "decreto" in n or "dec" in n:
        return "licencia por decreto"
    return "licencia de obra"


def _norm_token(s: str) -> str:
    t = re.sub(r"[^a-z0-9]+", "", (s or "").lower())
    return t


class CalviaAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone calvia.com + IDELMA WFS (obras) + SITMUN visores."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        geom = self.config.get("geometry") or {}
        self.wfs_base = str(geom.get("wfs_url") or WFS_BASE).rstrip("/")
        self.wfs_exp_type = str(geom.get("exp_type_name") or WFS_EXP_OBRA)
        self.wfs_sector_type = str(geom.get("sector_type_name") or WFS_SECTORS)
        self.wfs_page_size = int(geom.get("page_size") or 1000)
        self.wfs_max_features = int(geom.get("max_features") or 2500)
        self._wfs_obra_cache: list[dict[str, Any]] | None = None
        self._sector_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-calvia/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 90) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-calvia/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _wfs_url(self, type_name: str, *, start: int = 0, count: int | None = None) -> str:
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": type_name,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "count": str(count or self.wfs_page_size),
            "startIndex": str(start),
        }
        return f"{self.wfs_base}?{urllib.parse.urlencode(params)}"

    def _attach_geometry(
        self,
        rec: dict[str, Any],
        geom: dict[str, Any] | None,
        *,
        source_url: str,
    ) -> None:
        if not isinstance(geom, dict) or not geom.get("type"):
            return
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_source"] = "portal_wfs_idelma"
        rec["geometry_source_url"] = source_url
        rec["coord_source"] = "portal_geometry_centroid"
        cen = geometry_centroid(geom)
        if cen:
            rec["lat"], rec["lon"] = cen

    def _collect_wfs_obra(self) -> list[dict[str, Any]]:
        if self._wfs_obra_cache is not None:
            return self._wfs_obra_cache
        rows: list[dict[str, Any]] = []
        start = 0
        query_sample = self._wfs_url(self.wfs_exp_type, start=0, count=1)
        while start < self.wfs_max_features:
            batch = min(self.wfs_page_size, self.wfs_max_features - start)
            url = self._wfs_url(self.wfs_exp_type, start=start, count=batch)
            try:
                data = self._fetch_json(url, timeout=120)
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
                break
            feats = data.get("features") if isinstance(data, dict) else []
            if not feats:
                break
            for feat in feats:
                props = feat.get("properties") or {}
                expte = str(props.get("expte") or props.get("text") or "").strip()
                ref = str(props.get("refecada") or "").strip()
                desc = str(props.get("text") or expte).strip()
                rows.append(
                    {
                        "expte": expte,
                        "descripcion": desc,
                        "refecada": ref,
                        "geometry": feat.get("geometry"),
                        "wfs_url": query_sample,
                    }
                )
            start += len(feats)
            if len(feats) < batch:
                break
        self._wfs_obra_cache = rows
        return rows

    def _collect_sectors(self) -> list[dict[str, Any]]:
        if self._sector_cache is not None:
            return self._sector_cache
        url = self._wfs_url(self.wfs_sector_type, start=0, count=200)
        try:
            data = self._fetch_json(url, timeout=90)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            self._sector_cache = []
            return self._sector_cache
        rows: list[dict[str, Any]] = []
        for feat in (data.get("features") if isinstance(data, dict) else []) or []:
            props = feat.get("properties") or {}
            name = str(props.get("urbanitz") or "").strip()
            if not name:
                continue
            rows.append(
                {
                    "urbanitz": name,
                    "norm": _norm_token(name),
                    "geometry": feat.get("geometry"),
                    "wfs_url": url,
                }
            )
        self._sector_cache = rows
        return rows

    def _match_sector_geometry(self, title: str) -> tuple[dict[str, Any] | None, str | None]:
        blob = _norm_token(title)
        if not blob:
            return None, None
        best: dict[str, Any] | None = None
        best_len = 0
        for sec in self._collect_sectors():
            norm = sec.get("norm") or ""
            if len(norm) >= 4 and norm in blob and len(norm) > best_len:
                best = sec
                best_len = len(norm)
        if best:
            return best.get("geometry"), str(best.get("wfs_url") or "")
        return None, None

    def _parse_rss(self, url: str, section: str) -> list[dict[str, Any]]:
        try:
            xml = self._fetch(url, timeout=45)
        except (urllib.error.URLError, TimeoutError):
            return []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return []
        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = _clean(item.findtext("title") or "")
            guid = _clean(item.findtext("guid") or item.findtext("link") or "")
            desc = _clean(item.findtext("description") or "")
            fecha = _parse_rss_date(item.findtext("pubDate") or "")
            if not title or not guid:
                continue
            if RE_RSS_NOISE.search(title):
                continue
            link = guid
            if not link.startswith("http"):
                link = urllib.parse.urljoin(self.web_base + "/", link)
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": link,
                    "descripcion": desc,
                    "section": section,
                    "origen": "plone_rss",
                }
            )
        return rows

    def _collect_rss_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for feed_url, section in RSS_FEEDS:
            for item in self._parse_rss(feed_url, section):
                key = item["url"]
                if key in seen:
                    continue
                seen.add(key)
                blob = f"{item['titulo']} {item.get('descripcion') or ''}"
                if not RE_PROYECTO.search(blob) and section not in (
                    "planeamiento en trámite",
                    "PGOU revisión",
                ):
                    continue
                rows.append(item)
        return rows

    def _rss_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha") or _parse_fecha_dmy(titulo),
            "tipo": _proyecto_tipo(titulo, row.get("section") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        geom, gurl = self._match_sector_geometry(titulo)
        if geom:
            self._attach_geometry(rec, geom, source_url=gurl or self._wfs_url(self.wfs_sector_type))
        return rec

    def _wfs_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        expte = row.get("expte") or ""
        desc = row.get("descripcion") or expte
        rec: dict[str, Any] = {
            "id": _stable_id("lic", f"{expte}:{row.get('refecada') or ''}"),
            "fecha_concesion": _fecha_from_expte(expte),
            "tipo": _licencia_tipo(desc),
            "distrito": row.get("refecada") or None,
            "lat": None,
            "lon": None,
            "titulo": f"Expediente obra {expte}"[:500],
            "expte": expte,
            "url": VISOR_OBRAS,
            "source": "ayuntamiento",
            "origen": "idelma_wfs_exp_obra",
        }
        self._attach_geometry(rec, row.get("geometry"), source_url=str(row.get("wfs_url") or ""))
        return rec

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, tipo, titulo in TRAMITE_INFO_PAGES:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "web_tramite",
                }
            )
        return rows

    def _collect_proyecto_visores(self) -> list[dict[str, Any]]:
        visores = (
            (VISOR_PGOU_VIGENTE, "Visor PGOU vigente (SITMUN)", SITMUN_VIGENTE),
            (VISOR_PGOU_TRAMIT, "Visor PGOU en tramitación (SITMUN)", SITMUN_TRAMIT),
            (VISOR_OBRAS, "Visor obras mayores", VISOR_OBRAS),
        )
        rows: list[dict[str, Any]] = []
        for page_url, titulo, sitmun in visores:
            rows.append(
                {
                    "id": _stable_id("proy", page_url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": None,
                    "tipo": "visor GIS",
                    "url": page_url,
                    "source": "ayuntamiento",
                    "origen": "visor",
                    "nota": f"SITMUN/IDELMA: {sitmun}",
                }
            )
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
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for wfs_row in self._collect_wfs_obra():
            rec = self._wfs_to_licencia(wfs_row)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs": sum(1 for r in rows if r.get("origen") == "idelma_wfs_exp_obra"),
            "info": sum(1 for r in rows if r.get("origen") == "web_tramite"),
            "with_geometry": with_geom,
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_proyecto_visores():
            add(rec)
        for item in self._collect_rss_proyectos():
            add(self._rss_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "rss": sum(1 for r in rows if r.get("origen") == "plone_rss"),
            "visor": sum(1 for r in rows if r.get("origen") == "visor"),
            "with_geometry": with_geom,
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
